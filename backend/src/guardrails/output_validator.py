import re
from typing import Any

from backend.src.guardrails.registry import guardrail_registry

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
]

ALLOWED_TONES = ["professional", "empathetic", "informative"]


def _check_output_pii(text: str) -> tuple[bool, str]:
    for pat in PII_PATTERNS:
        if pat.search(text):
            return False, "Output contains PII"
    return True, ""


def _check_tone(text: str) -> tuple[bool, str]:
    """Basic tone check — rejects adversarial or overly casual language."""
    bad_patterns = [r"\byou['\"]?re (an idiot|stupid)\b", r"\b(damn|shit)\b"]
    for pat in bad_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return False, "Output tone is inappropriate"
    return True, ""


def _check_hallucination(text: str) -> tuple[bool, str]:
    """Simple hallucination indicator check."""
    hedge_words = ["i think", "maybe", "perhaps", "could be", "i believe"]
    for hw in hedge_words:
        if text.lower().startswith(hw) or text.lower().strip().endswith(hw):
            return False, f"Output contains hedging ('{hw}') indicating potential hallucination"
    return True, ""


def output_guardrail(context: dict) -> tuple[bool, str]:
    text = str(context.get("text", context.get("output", "")))
    if not text:
        return True, ""
    for check in [_check_output_pii, _check_tone, _check_hallucination]:
        passed, msg = check(text)
        if not passed:
            return False, msg
    return True, ""


guardrail_registry.register_output(output_guardrail, "output_validator")
