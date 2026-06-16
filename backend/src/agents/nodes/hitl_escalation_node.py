"""HITL escalation node: creates a human-in-the-loop request and stores it for review."""

import logging
from datetime import datetime, timezone

from backend.src.agents.state import AgentRole, SharedState, TraceEntry
from backend.src.domain.agui import InteractionRequest

logger = logging.getLogger("hr_ops.nodes.hitl")


def hitl_escalation_node(state: SharedState) -> dict:
    """Create a HITL request and store it in the AGUI store if escalation is needed."""
    if not state.hitl_needed:
        return {}
    
    pending_tool_call = state.rl_context.get("pending_tool_call")
    
    request = InteractionRequest(
        interaction_id=f"HITL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        query=state.query,
        session_id=state.session_id,
        context={
            "current_agent": state.current_agent,
            "anomaly_results": [a.__dict__ for a in state.anomaly_results] if state.anomaly_results else [],
            "compliance_veto": state.compliance_veto,
            "rl_context": state.rl_context,
            "pending_tool_call": pending_tool_call,
        },
    )
    from backend.src.utils.agui_store import agui_store
    agui_store.add_request(request)

    response_text = f"Escalated to human. Interaction ID: {request.interaction_id}"
    if pending_tool_call:
        response_text = f"The requested database modification has been recorded and submitted for human approval. Interaction ID: {request.interaction_id}"

    return {
        "hitl_request": request,
        "final_response": response_text,
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="hitl_escalation", agent_role=AgentRole.SUPERVISOR,
                input_text=state.query,
                output_text=f"Escalated: {request.interaction_id}",
                timestamp=datetime.now(timezone.utc), duration_ms=0,
            )
        ],
    }
