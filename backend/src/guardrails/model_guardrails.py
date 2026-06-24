"""Guardrails for model cost and timeout thresholds."""

from backend.src.guardrails.registry import guardrail_registry


def model_cost_guardrail(context: dict) -> tuple[bool, str]:
    """Reject inference if estimated cost exceeds the configured threshold."""
    cost = context.get("estimated_cost_usd", 0)
    threshold = 0.50
    if cost > threshold:
        return False, f"Estimated cost ${cost:.3f} exceeds threshold ${threshold:.3f}"
    return True, ""


def model_timeout_guardrail(context: dict) -> tuple[bool, str]:
    """Reject inference if timeout exceeds the configured threshold."""
    from backend.src.core.settings import settings
    timeout = context.get("timeout_seconds", 0)
    threshold = settings.guardrails_config.get("model", {}).get("timeout_seconds", 30)
    if timeout > threshold:
        return False, f"Timeout {timeout}s exceeds threshold {threshold}s"
    return True, ""


guardrail_registry.register_model(model_cost_guardrail, "model_cost_guardrail")
guardrail_registry.register_model(model_timeout_guardrail, "model_timeout_guardrail")
