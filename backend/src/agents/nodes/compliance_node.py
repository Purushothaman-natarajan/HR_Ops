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

    # Determine response text and set escalation flag
    if report.vetoed:
        hitl_needed = False
    elif report.flagged:
        hitl_needed = True
    else:
        hitl_needed = False

    # Generate a friendly natural-language explanation using the LLM
    from backend.src.utils.model_router import llm_call
    
    activities.append(Activity(
        type="llm_call", label="Synthesising compliance explanation",
        detail="Converting rules engine evaluation to user-friendly response",
        status="running",
    ))
    
    triggered_details = ""
    if triggered:
        triggered_details = "Triggered compliance rules:\n" + "\n".join(
            f"- [{r.rule_id}] (Severity: {r.severity}, Action: {r.action}) {r.reason}"
            for r in triggered
        )
    else:
        triggered_details = "No compliance rules were triggered."

    prompt = (
        "You are an HR compliance AI officer. The user asked a compliance-related question or requested an action:\n"
        f"Query: {state.query}\n\n"
        "Compliance Engine Evaluation:\n"
        f"Vetoed: {report.vetoed}\n"
        f"Flagged: {report.flagged}\n"
        f"Warned: {report.warned}\n"
        f"Details: {triggered_details}\n\n"
        "Provide a professional, clear, friendly, and comprehensive response. "
        "First, state the outcome clearly: whether it is APPROVED/COMPLIANT, BLOCKED/VETOED, or REQUIRES HUMAN REVIEW/FLAGGED. "
        "Explain the compliance rationale directly and advise them on guidelines or next steps (such as DPO authorization or Data Processing Agreements where appropriate). "
        "Do not output raw system status unless context demands it; make it a natural conversational reply addressing their query."
    )
    
    try:
        final_text, _ = await llm_call("compliance_synthesis", prompt, max_tokens=512, temperature=0.1)
        final_text = final_text.strip()
        activities[-1].status = "completed"
        activities[-1].detail = "Compliance response synthesised successfully"
    except Exception as exc:
        logger.warning("Compliance response synthesis failed, falling back: %s", exc)
        activities[-1].status = "failed"
        activities[-1].detail = str(exc)
        if report.vetoed:
            final_text = f"[COMPLIANCE VETO] Action blocked. {report.veto_reason}"
        elif report.flagged:
            flag_rules = [r.rule_id for r in triggered if r.action == "flag"]
            final_text = f"[COMPLIANCE FLAG] Action requires human review. Rules triggered: {', '.join(flag_rules)}"
        elif report.warned:
            warn_rules = [r.rule_id for r in triggered if r.action == "warn"]
            final_text = f"[COMPLIANCE WARN] Proceeding with warnings. Rules: {', '.join(warn_rules)}"
        else:
            final_text = "Compliance check passed — no rules triggered."

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
