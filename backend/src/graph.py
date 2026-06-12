import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from backend.src.agents.state import SharedState
from backend.src.agents.advanced.supervisor import supervisor_decision
from backend.src.agents.nodes.policy_node import policy_node
from backend.src.agents.nodes.action_node import action_node
from backend.src.agents.nodes.anomaly_node import anomaly_node
from backend.src.agents.nodes.compliance_node import compliance_node
from backend.src.agents.nodes.hitl_escalation_node import hitl_escalation_node

logger = logging.getLogger("hr_ops.graph")


def _should_continue(state: SharedState) -> str:
    if state.hitl_needed:
        return "hitl"
    if state.compliance_veto:
        return END
    if state.final_response:
        return END
    return END


def _route_from_supervisor(state: SharedState) -> str:
    return state.current_agent or "policy"


def build_full_graph() -> StateGraph:
    graph = StateGraph(SharedState)

    graph.add_node("supervisor", supervisor_decision)
    graph.add_node("policy", policy_node)
    graph.add_node("action", action_node)
    graph.add_node("anomaly", anomaly_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("hitl", hitl_escalation_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "policy": "policy",
            "action": "action",
            "anomaly": "anomaly",
            "compliance": "compliance",
        },
    )

    for node in ("policy", "action", "anomaly", "compliance"):
        graph.add_conditional_edges(node, _should_continue, {"hitl": "hitl", END: END})

    graph.add_edge("hitl", END)

    return graph.compile()
