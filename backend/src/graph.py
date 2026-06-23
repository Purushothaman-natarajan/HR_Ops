"""Top-level LangGraph assembly for the full HR agent workflow with supervisor routing and parallel background checks."""

import logging

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.src.core.settings import settings
from backend.src.agents.advanced.supervisor import supervisor_decision
from backend.src.agents.nodes.action_node import action_node
from backend.src.agents.nodes.anomaly_node import anomaly_node
from backend.src.agents.nodes.compliance_node import compliance_node
from backend.src.agents.nodes.hitl_escalation_node import hitl_escalation_node
from backend.src.agents.nodes.parallel_check_node import parallel_check_node
from backend.src.agents.nodes.policy_node import policy_node
from backend.src.agents.state import SharedState

logger = logging.getLogger("hr_ops.graph")


def _should_continue(state: SharedState) -> str:
    """Return 'hitl' if HITL escalation is needed and feature is enabled, otherwise END."""
    if state.hitl_needed and settings.feature_flags.get("hitl", {}).get("enabled", True):
        return "hitl"
    return END


def _route_after_action(state: SharedState) -> str:
    """Route from action node. Hybrid queries proceed to policy; standard queries go to parallel check."""
    if state.current_agent == "hybrid":
        return "policy"
    return "parallel_check"


def _route_from_supervisor(state: SharedState) -> str:
    """Return the agent route chosen by the supervisor, respecting feature flags."""
    route = state.current_agent or "policy"
    flags = settings.feature_flags
    if route == "anomaly" and not flags.get("rl", {}).get("enabled", True):
        route = "policy"
    if route == "compliance" and not flags.get("dspy", {}).get("enabled", True):
        route = "policy"
    return route


def _wrap_with_cooperative_yield(node_fn):
    """Wrap a node function to check for active user queries and dynamically yield/pause if it is a background scan."""
    async def wrapped(state: SharedState, *args, **kwargs):
        from backend.src.services.graph_service import cooperative_yield
        await cooperative_yield(state)
        return await node_fn(state, *args, **kwargs)
    return wrapped


def build_full_graph() -> CompiledStateGraph:
    """Build and compile the full LangGraph with supervisor, agent nodes, parallel checks, and HITL escalation.

    Flow:
      supervisor → policy/action → parallel_check (anomaly + compliance concurrently) → HITL/END
      supervisor → anomaly → HITL/END  (standalone)
      supervisor → compliance → HITL/END  (standalone)
    """
    graph = StateGraph(SharedState)

    graph.add_node("supervisor", _wrap_with_cooperative_yield(supervisor_decision))
    graph.add_node("policy", _wrap_with_cooperative_yield(policy_node))
    graph.add_node("action", _wrap_with_cooperative_yield(action_node))
    graph.add_node("anomaly", _wrap_with_cooperative_yield(anomaly_node))
    graph.add_node("compliance", _wrap_with_cooperative_yield(compliance_node))
    graph.add_node("parallel_check", _wrap_with_cooperative_yield(parallel_check_node))
    graph.add_node("hitl", _wrap_with_cooperative_yield(hitl_escalation_node))

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "policy": "policy",
            "action": "action",
            "hybrid": "action",
            "anomaly": "anomaly",
            "compliance": "compliance",
        },
    )

    # Policy fans out to parallel background checks
    graph.add_edge("policy", "parallel_check")

    # Action branches: hybrid goes to policy, otherwise to parallel background checks
    graph.add_conditional_edges(
        "action", 
        _route_after_action, 
        {
            "policy": "policy", 
            "parallel_check": "parallel_check"
        }
    )

    # Standalone anomaly/compliance (when routed directly from supervisor) go straight to HITL check
    for node in ("anomaly", "compliance"):
        graph.add_conditional_edges(node, _should_continue, {"hitl": "hitl", END: END})

    # Parallel check completes with HITL decision
    graph.add_conditional_edges("parallel_check", _should_continue, {"hitl": "hitl", END: END})

    graph.add_edge("hitl", END)

    return graph.compile()
