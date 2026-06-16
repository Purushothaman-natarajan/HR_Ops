"""PII redaction utility for trace events. Redacts emails, SSNs, and numeric IDs before storage."""

import logging
import re

from backend.src.core.settings import settings

logger = logging.getLogger("hr_ops.pii_redaction")

_REDACT_LABEL = "[REDACTED]"

_compiled_patterns: list[re.Pattern] | None = None


def _get_patterns() -> list[re.Pattern]:
    global _compiled_patterns
    if _compiled_patterns is None:
        cfg = settings.embed_config.get("pii_redaction", {})
        raw_patterns = cfg.get("patterns", [])
        _compiled_patterns = [re.compile(p) for p in raw_patterns]
    return _compiled_patterns


def redact_text(text: str) -> str:
    """Replace PII patterns in text with [REDACTED]."""
    if not text:
        return text
    cfg = settings.embed_config.get("pii_redaction", {})
    if not cfg.get("enabled", True):
        return text
    for pattern in _get_patterns():
        text = pattern.sub(_REDACT_LABEL, text)
    return text


def redact_run_data(run_data: dict) -> dict:
    """Deep-redact trace data in-place."""
    cfg = settings.embed_config.get("pii_redaction", {})
    if not cfg.get("enabled", True):
        return run_data

    for event in run_data.get("trace_events", []):
        if isinstance(event, dict):
            for field in ("input_text", "output_text"):
                if field in event and isinstance(event[field], str):
                    event[field] = redact_text(event[field])
        elif hasattr(event, "input_text"):
            event.input_text = redact_text(event.input_text)
            event.output_text = redact_text(event.output_text)

    for key in ("query", "final_response"):
        if key in run_data and isinstance(run_data[key], str):
            run_data[key] = redact_text(run_data[key])

    return run_data
