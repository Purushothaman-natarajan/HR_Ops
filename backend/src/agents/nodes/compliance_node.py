"""Compliance node: checks HR queries against policy rules and hard veto conditions."""

import json
import logging
from datetime import datetime, timezone

from backend.src.agents.state import Activity, SharedState, TraceEntry
from backend.src.intelligence.compliance import check_veto
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.nodes.compliance")


async def compliance_node(state: SharedState) -> dict:
    """Evaluate the query for compliance via LLM and check hard veto rules."""
    start = datetime.now(timezone.utc)
    activities = []

    activities.append(Activity(
        type="llm_call", label="Running LLM compliance check",
        detail=f"Query: {state.query[:80]}...",
        status="running",
    ))
    prompt = (
        f"Check if the following HR query complies with company policies.\n"
        f"Query: {state.query}\n\n"
        f"Reply with JSON: {{\"compliant\": true/false, \"reason\": \"...\"}}"
    )
    response, cost = await llm_call("compliance", prompt, max_tokens=256, temperature=0)
    activities[-1].status = "completed"

    try:
        result = json.loads(response)
        activities[-1].detail = f"LLM result: {'COMPLIANT' if result.get('compliant') else 'NON-COMPLIANT'} — {result.get('reason', '')[:80]}"
    except Exception as e:
        result = {"compliant": False, "reason": str(e)}
        activities[-1].detail = f"LLM parse error: {e}"

    activities.append(Activity(
        type="guardrail", label="Checking hard veto rules",
        detail="Evaluating against compliance veto conditions",
        status="running",
    ))
    veto = check_veto("", state.query)
    if not veto[0]:
        result = {"compliant": False, "reason": veto[1]}
        activities[-1].detail = f"VETO triggered: {veto[1]}"
    else:
        activities[-1].detail = "No veto triggered"

    activities[-1].status = "completed"
    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    compliance_veto = not result.get("compliant", True)
    return {
        "compliance_veto": compliance_veto,
        "compliance_reason": result.get("reason", ""),
        "hitl_needed": compliance_veto,
        "final_response": "Compliance check passed." if result.get("compliant") else f"Compliance veto: {result.get('reason')}",
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="compliance_node", agent_role="compliance",
                input_text=state.query, output_text=json.dumps(result),
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
                activities=activities,
            )
        ],
    }
