"""Top-level LangGraph assembly for the full HR agent workflow with supervisor routing."""

import logging
from typing import Literal

from langgraph.graph import StateGraph, END, CompiledStateGraph

from backend.config.settings import settings
from backend.src.agents.state import SharedState
from backend.src.agents.advanced.supervisor import supervisor_decision
from backend.src.agents.nodes.policy_node import policy_node
from backend.src.agents.nodes.action_node import action_node
from backend.src.agents.nodes.anomaly_node import anomaly_node
from backend.src.agents.nodes.compliance_node import compliance_node
from backend.src.agents.nodes.hitl_escalation_node import hitl_escalation_node

logger = logging.getLogger("hr_ops.graph")


def _should_continue(state: SharedState) -> str:
    """Return 'hitl' if HITL escalation is needed and feature is enabled, otherwise END."""
    if state.hitl_needed and settings.feature_flags.get("hitl", {}).get("enabled", True):
        return "hitl"
    return END


def _route_from_supervisor(state: SharedState) -> str:
    """Return the agent route chosen by the supervisor, respecting feature flags."""
    route = state.current_agent or "policy"
    flags = settings.feature_flags
    if route == "anomaly" and not flags.get("rl", {}).get("enabled", True):
        route = "policy"
    if route == "compliance" and not flags.get("dspy", {}).get("enabled", True):
        route = "policy"
    return route


def build_full_graph() -> CompiledStateGraph:
    """Build and compile the full LangGraph with supervisor, agent nodes, and HITL escalation."""
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
