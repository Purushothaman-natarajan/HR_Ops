import logging
from typing import Any

from backend.config.settings import settings

logger = logging.getLogger("hr_ops.compliance")

HARD_VETO_RULES: list[str] = []


def _load_veto_rules() -> list[str]:
    try:
        cc = settings.compliance_config
        return cc.get("hard_veto_rules", [])
    except Exception:
        return []


def check_veto(employee_id: str, action: str, context: dict | None = None) -> tuple[bool, str]:
    global HARD_VETO_RULES
    if not HARD_VETO_RULES:
        HARD_VETO_RULES.extend(_load_veto_rules())

    action_lower = action.lower()
    for rule in HARD_VETO_RULES:
        rule_key = rule.replace("cannot_", "").replace("_", " ")
        if rule_key in action_lower:
            logger.info("Veto triggered: rule=%s action=%s emp=%s", rule, action, employee_id)
            return False, f"Hard veto: {rule}"

    return True, ""


def validate_policy_reference(resolved: bool) -> tuple[bool, str]:
    if not resolved:
        return False, "Policy reference is required but was not resolved"
    return True, ""
