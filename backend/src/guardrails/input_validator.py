import re
from typing import Any

from backend.src.guardrails.registry import guardrail_registry

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),            # SSN
    re.compile(r"\b\d{16}\b"),                         # credit card (basic)
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),  # email
]

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above)", re.IGNORECASE),
    re.compile(r"system\s*(prompt|message|instruction)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|not)\s+", re.IGNORECASE),
]

BLOCKED_TOPICS: list[str] = []


def _load_blocked_topics() -> list[str]:
    try:
        from backend.config.settings import settings
        gc = settings.guardrails_config
        return gc.get("input", {}).get("blocked_topics", [])
    except Exception:
        return ["violence", "illegal_activity", "discrimination"]


def _check_pii(text: str) -> tuple[bool, str]:
    for pat in PII_PATTERNS:
        if pat.search(text):
            return False, "Input contains PII"
    return True, ""


def _check_injection(text: str) -> tuple[bool, str]:
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            return False, "Input appears to contain prompt injection"
    return True, ""


def _check_topic(text: str) -> tuple[bool, str]:
    global BLOCKED_TOPICS
    if not BLOCKED_TOPICS:
        BLOCKED_TOPICS.extend(_load_blocked_topics())
    text_lower = text.lower()
    for topic in BLOCKED_TOPICS:
        if topic.lower() in text_lower:
            return False, f"Input references blocked topic: {topic}"
    return True, ""


def _check_length(text: str) -> tuple[bool, str]:
    max_len = 4096
    try:
        from backend.config.settings import settings
        gc = settings.guardrails_config
        max_len = gc.get("input", {}).get("max_input_length", 4096)
    except Exception:
        pass
    if len(text) > max_len:
        return False, f"Input exceeds maximum length of {max_len} characters"
    return True, ""


def input_guardrail(context: dict) -> tuple[bool, str]:
    text = _get_text(context)
    if not text:
        return True, ""
    for check in [_check_pii, _check_injection, _check_topic, _check_length]:
        passed, msg = check(text)
        if not passed:
            return False, msg
    return True, ""


def _get_text(context: dict) -> str:
    if "text" in context:
        return str(context["text"])
    if "messages" in context:
        msgs = context["messages"]
        if isinstance(msgs, list) and msgs:
            last = msgs[-1]
            if isinstance(last, dict):
                return str(last.get("content", ""))
            return str(last)
    return ""


guardrail_registry.register_input(input_guardrail, "input_validator")
