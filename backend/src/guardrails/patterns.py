"""Pre-compiled regex patterns for PII detection and prompt injection detection."""

from __future__ import annotations

import re

PII_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{16}\b"),  # credit card (basic)
    re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    ),  # email
]

INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|above)", re.IGNORECASE),
    re.compile(r"system\s*(prompt|message|instruction)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|not)\s+", re.IGNORECASE),
]
