"""Compliance node: deterministic rules-engine check (no LLM) + optional narrative.

Flow:
  1. Run evaluate_action() against all compliance_rules.yaml rules.
  2. Veto → block and return immediately.
  3. Flag → HITL escalation.
  4. Warn → pass with warning logged.
  5. Clean → proceed normally.
"""

import logging
from datetime import datetime, timezone

from backend.src.agents.state import Activity, SharedState, TraceEntry
from backend.src.intelligence.compliance import evaluate_action

logger = logging.getLogger("hr_ops.nodes.compliance")

# Action string severity mapping for audit logs
_SEVERITY_EMOJI = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW"}


async def compliance_node(state: SharedState) -> dict:
    """Evaluate the query against all compliance rules and route accordingly."""
    start = datetime.now(timezone.utc)
    activities = []

    activities.append(Activity(
        type="guardrail", label="Running compliance rules engine",
        detail=f"Evaluating {len(state.query)} chars against compliance_rules.yaml",
        status="running",
    ))

    # Pass context from rl_context if available (e.g. leaves_taken, salary_change_pct)
    ctx = dict(state.rl_context or {})
    report = evaluate_action(state.query, context=ctx)

    triggered = report.triggered_rules
    activities[-1].status = "completed"
    activities[-1].detail = (
        f"{len(triggered)} rule(s) triggered — "
        f"vetoed={report.vetoed}, flagged={report.flagged}, warned={report.warned}"
    )
    activities[-1].metadata = {
        "vetoed": report.vetoed,
        "flagged": report.flagged,
        "warned": report.warned,
        "triggered_count": len(triggered),
        "highest_severity": report.highest_severity,
        "rules_evaluated": len(report.results),
    }

    # Build audit trail for all triggered rules
    if triggered:
        rule_summary = "\n".join(
            f"  [{_SEVERITY_EMOJI.get(r.severity, r.severity)}] {r.rule_id}: {r.reason}"
            for r in triggered
        )
        activities.append(Activity(
            type="guardrail", label="Compliance rule audit trail",
            detail=rule_summary[:500],
            status="completed",
            metadata={"triggered_rules": [r.rule_id for r in triggered]},
        ))

    # Determine response text
    if report.vetoed:
        final_text = f"[COMPLIANCE VETO] Action blocked. {report.veto_reason}"
        hitl_needed = False   # veto is hard block — no HITL needed
    elif report.flagged:
        flag_rules = [r.rule_id for r in triggered if r.action == "flag"]
        final_text = f"[COMPLIANCE FLAG] Action requires human review. Rules triggered: {', '.join(flag_rules)}"
        hitl_needed = True
    elif report.warned:
        warn_rules = [r.rule_id for r in triggered if r.action == "warn"]
        final_text = f"[COMPLIANCE WARN] Proceeding with warnings. Rules: {', '.join(warn_rules)}"
        hitl_needed = False
    else:
        final_text = "Compliance check passed — no rules triggered."
        hitl_needed = False

    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    return {
        "compliance_veto": report.vetoed,
        "compliance_reason": report.veto_reason if report.vetoed else final_text,
        "hitl_needed": hitl_needed,
        "final_response": final_text,
        "rl_context": {
            **ctx,
            "compliance_triggered": len(triggered),
            "compliance_vetoed": report.vetoed,
            "compliance_flagged": report.flagged,
        },
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="compliance_node", agent_role="compliance",
                input_text=state.query, output_text=final_text,
                timestamp=start, duration_ms=elapsed,
                activities=activities,
                metadata={
                    "vetoed": report.vetoed,
                    "flagged": report.flagged,
                    "warned": report.warned,
                    "triggered_rules": [r.rule_id for r in triggered],
                },
            )
        ],
    }
