"""Validates LLM output for PII leakage, inappropriate tone, and hedging."""

from __future__ import annotations

import re
from typing import Any

from backend.src.guardrails.patterns import PII_PATTERNS
from backend.src.guardrails.registry import guardrail_registry


def _check_output_pii(text: str) -> tuple[bool, str]:
    """Check if output contains PII that should not be exposed."""
    for pat in PII_PATTERNS:
        if pat.search(text):
            return False, "Output contains PII"
    return True, ""


def _check_tone(text: str) -> tuple[bool, str]:
    """Check if output contains inappropriate or offensive language."""
    bad_patterns = [
        r"\byou['\"]?re (an idiot|stupid)\b",
        r"\b(damn|shit)\b",
    ]
    for pat in bad_patterns:
        if re.search(pat, text, re.IGNORECASE):
            return False, "Output tone is inappropriate"
    return True, ""


def _check_hallucination(text: str) -> tuple[bool, str]:
    """Flag output that uses hedging language suggestive of hallucination."""
    hedge_words = ["i think", "maybe", "perhaps", "could be", "i believe", "not sure", "possibly"]
    text_lower = text.lower().strip()
    for hw in hedge_words:
        if hw in text_lower:
            return (
                False,
                f"Output contains hedging ('{hw}') indicating potential hallucination",
            )
    return True, ""


def output_guardrail(context: dict) -> tuple[bool, str]:
    """Entry-point guardrail: runs PII, tone, and hallucination checks on output."""
    text = str(context.get("text", context.get("output", "")))
    if not text:
        return True, ""
    for check in [_check_output_pii, _check_tone, _check_hallucination]:
        passed, msg = check(text)
        if not passed:
            return False, msg
    return True, ""


guardrail_registry.register_output(output_guardrail, "output_validator")
