"""Compliance engine — loads rules from compliance_rules.yaml and evaluates actions.

Replaces the naive prompt-based approach with a deterministic, auditable rules engine:
  1. Keyword matching against the action/query text
  2. Numeric field condition checks (gt/gte/lt/lte/eq) when context is provided
  3. Hard-veto list (always blocks, no exceptions)

Returns structured ComplianceResult objects with rule ID, severity, and reason.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("hr_ops.compliance")

_RULES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "compliance_rules.yaml"

# ─── Data structures ─────────────────────────────────────────────────────────


@dataclass
class ComplianceResult:
    """Result of a single rule evaluation."""

    rule_id: str
    category: str
    severity: str          # low | medium | high | critical
    action: str            # veto | flag | warn | notify
    triggered: bool
    reason: str
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    """Aggregate result of evaluating all rules against an action/context."""

    vetoed: bool
    flagged: bool
    warned: bool
    compliant: bool
    results: list[ComplianceResult] = field(default_factory=list)
    veto_reason: str = ""

    @property
    def triggered_rules(self) -> list[ComplianceResult]:
        return [r for r in self.results if r.triggered]

    @property
    def highest_severity(self) -> str:
        order = ["low", "medium", "high", "critical"]
        sev = [r.severity for r in self.triggered_rules]
        return max(sev, key=lambda s: order.index(s)) if sev else "none"


# ─── Rules loader (cached at module level) ───────────────────────────────────

_RULES: list[dict] = []
_HARD_VETO_KEYWORDS: list[str] = []
_LOADED = False


def _load_rules() -> None:
    """Load and parse compliance_rules.yaml once."""
    global _RULES, _HARD_VETO_KEYWORDS, _LOADED
    if _LOADED:
        return
    try:
        data = yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8"))
        _RULES = data.get("rules", [])
        _HARD_VETO_KEYWORDS = [k.lower() for k in data.get("hard_veto_keywords", [])]
        _LOADED = True
        logger.info("Compliance rules loaded: %d rules, %d hard-veto keywords",
                    len(_RULES), len(_HARD_VETO_KEYWORDS))
    except Exception as exc:
        logger.error("Failed to load compliance_rules.yaml: %s", exc)
        _RULES = []
        _HARD_VETO_KEYWORDS = []


# ─── Condition evaluator ─────────────────────────────────────────────────────

_OPS = {
    "gt": lambda a, b: float(a) > float(b),
    "gte": lambda a, b: float(a) >= float(b),
    "lt": lambda a, b: float(a) < float(b),
    "lte": lambda a, b: float(a) <= float(b),
    "eq": lambda a, b: str(a).lower() == str(b).lower(),
}


def _check_condition(condition: dict, context: dict) -> bool:
    """Evaluate a single condition dict against a context dict.

    Supports ``field`` + ``operator`` + ``value`` and ``reference_field`` patterns.
    Returns False (not triggered) when required field is absent from context.
    """
    field_name = condition.get("field")
    if not field_name or field_name not in context:
        return False
    operator = condition.get("operator", "gt")
    op_fn = _OPS.get(operator)
    if op_fn is None:
        return False
    field_val = context[field_name]
    if "reference_field" in condition:
        ref_val = context.get(condition["reference_field"])
        if ref_val is None:
            return False
        return op_fn(field_val, ref_val)
    if "value" in condition:
        return op_fn(field_val, condition["value"])
    return False


# ─── Core evaluation function ────────────────────────────────────────────────


def evaluate_action(action_text: str, context: dict | None = None) -> EvaluationReport:
    """Evaluate an action/query text against all compliance rules.

    Args:
        action_text : The action string or user query to check.
        context     : Optional dict with field values for numeric condition checks.
                      Keys align with rule ``conditions.field`` names
                      (e.g. ``leaves_taken``, ``salary_change_pct``).

    Returns:
        EvaluationReport with .vetoed, .flagged, .warned flags and full rule results.
    """
    _load_rules()
    ctx = context or {}
    text_lower = action_text.lower()
    report_results: list[ComplianceResult] = []

    # ── Step 1: Hard-veto keyword check ─────────────────────────────────────
    for kw in _HARD_VETO_KEYWORDS:
        if kw in text_lower:
            report_results.append(ComplianceResult(
                rule_id="HARD_VETO",
                category="security",
                severity="critical",
                action="veto",
                triggered=True,
                reason=f"Hard-veto keyword matched: '{kw}'",
                matched_keywords=[kw],
            ))
            return EvaluationReport(
                vetoed=True, flagged=False, warned=False, compliant=False,
                results=report_results,
                veto_reason=f"Hard-veto keyword '{kw}' is unconditionally blocked.",
            )

    # ── Step 2: Rule-by-rule evaluation ─────────────────────────────────────
    vetoed = False
    flagged = False
    warned = False
    veto_reason = ""

    for rule in _RULES:
        rid = rule.get("id", "UNKNOWN")
        keywords: list[str] = [k.lower() for k in rule.get("keywords", [])]
        condition: dict = rule.get("conditions", {})
        severity = rule.get("severity", "medium")
        action = rule.get("action", "warn")
        description = rule.get("description", "")

        # Keyword match
        matched_kws = [k for k in keywords if k in text_lower]
        keyword_hit = bool(matched_kws)

        # Condition match (only checked if keyword hit OR context provided)
        condition_hit = _check_condition(condition, ctx) if condition else False

        if condition:
            triggered = (keyword_hit and condition_hit) if keywords else condition_hit
        else:
            triggered = keyword_hit
        if not triggered:
            report_results.append(ComplianceResult(
                rule_id=rid, category=rule.get("category", ""),
                severity=severity, action=action, triggered=False, reason="",
            ))
            continue

        reason = f"Rule {rid}: {description}"
        if matched_kws:
            reason += f" [keyword: {', '.join(matched_kws)}]"
        if condition_hit:
            reason += f" [condition: {condition.get('field')} {condition.get('operator')} {condition.get('value', condition.get('reference_field', ''))}]"

        if action == "veto":
            vetoed = True
            veto_reason = reason
        elif action == "flag":
            flagged = True
        elif action == "warn":
            warned = True

        report_results.append(ComplianceResult(
            rule_id=rid, category=rule.get("category", ""),
            severity=severity, action=action, triggered=True, reason=reason,
            matched_keywords=matched_kws,
        ))
        logger.info("Compliance rule triggered: id=%s action=%s text=%.80s", rid, action, action_text)

    return EvaluationReport(
        vetoed=vetoed,
        flagged=flagged,
        warned=warned,
        compliant=not (vetoed or flagged),
        results=report_results,
        veto_reason=veto_reason,
    )


# ─── Legacy compatibility shim ───────────────────────────────────────────────


def check_veto(employee_id: str, action: str, context: dict | None = None) -> tuple[bool, str]:
    """Legacy shim: returns (is_allowed, reason) for backward-compatible callers."""
    report = evaluate_action(action, context)
    if report.vetoed:
        return False, report.veto_reason
    return True, ""


def validate_policy_reference(resolved: bool) -> tuple[bool, str]:
    """Ensure a policy reference was resolved; returns (is_valid, message)."""
    if not resolved:
        return False, "Policy reference is required but was not resolved"
    return True, ""
