import logging
from datetime import datetime

from langgraph.graph import StateGraph, END
from backend.src.agents.state import SharedState, AgentRole, TraceEntry
from backend.src.utils.model_router import llm_call
from backend.src.guardrails.registry import guardrail_registry
from backend.src.tools.api_mocks import execute_tool

logger = logging.getLogger("hr_ops.standard_orchestrator")


def _triage_node(state: SharedState) -> dict:
    start = datetime.utcnow()
    prompt = (
        f"Classify the following HR query into one of:\n"
        f"- policy (ask about HR policies)\n"
        f"- action (modify a record)\n"
        f"- anomaly (investigate data issue)\n"
        f"- compliance (check policy compliance)\n\n"
        f"Query: {state.query}\n\n"
        f"Reply with exactly one word: policy/action/anomaly/compliance."
    )
    gr = guardrail_registry.check_input({"text": state.query, "messages": state.messages})
    if not gr.passed:
        elapsed = (datetime.utcnow() - start).total_seconds() * 1000
        return {
            "final_response": f"Input guardrail blocked: {gr.message}",
            "current_agent": AgentRole.SUPERVISOR,
            "trace_log": [
                TraceEntry(
                    node="triage", agent_role=AgentRole.SUPERVISOR,
                    input_text=state.query, output_text=gr.message,
                    timestamp=start, duration_ms=elapsed,
                    guardrail_result={"guardrail_type": "input", "passed": False, "message": gr.message},
                )
            ],
        }
    classification, cost = llm_call("triage", prompt, max_tokens=20, temperature=0)
    classification = classification.strip().lower()
    if classification not in ("policy", "action", "anomaly", "compliance"):
        classification = "policy"
    elapsed = (datetime.utcnow() - start).total_seconds() * 1000
    return {
        "rl_context": {"classification": classification, "query": state.query},
        "rl_selected_action": classification,
        "current_agent": classification,
        "trace_log": [
            TraceEntry(
                node="triage", agent_role=AgentRole.SUPERVISOR,
                input_text=state.query, output_text=f"Classified as {classification}",
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
            )
        ],
    }


def _policy_node(state: SharedState) -> dict:
    start = datetime.utcnow()
    from backend.src.memory.vector_store import similarity_search

    docs = similarity_search(state.query, k=3)
    context = "\n\n".join(d.page_content for d in docs) if docs else "No policies found."
    prompt = (
        f"Answer the HR question based on the retrieved policies.\n\n"
        f"Policies:\n{context}\n\n"
        f"Question: {state.query}\n\n"
        f"Provide a clear, actionable answer."
    )
    answer, cost = llm_call("rag", prompt, max_tokens=512)
    elapsed = (datetime.utcnow() - start).total_seconds() * 1000
    return {
        "final_response": answer,
        "retrieved_policies": [d.page_content[:200] for d in (docs or [])],
        "trace_log": [
            TraceEntry(
                node="policy", agent_role=AgentRole.POLICY,
                input_text=state.query, output_text=answer,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
            )
        ],
    }


def _action_node(state: SharedState) -> dict:
    start = datetime.utcnow()
    prompt = (
        f"Extract the tool call from the query. Valid tools:\n"
        f"- lookup_employee(employee_id: str)\n"
        f"- modify_record(employee_id: str, field: str, value: any)\n"
        f"- escalate_to_human(employee_id: str, reason: str)\n\n"
        f"Query: {state.query}\n\n"
        f"Reply with a JSON object: {{\"name\": \"tool_name\", \"args\": {{...}}}}"
    )
    response, cost = llm_call("action", prompt, max_tokens=256, temperature=0)
    import json

    try:
        call = json.loads(response)
        tool_result = execute_tool(call["name"], **call["args"])
        result_text = json.dumps(tool_result, indent=2)
    except Exception as e:
        result_text = f"Error: {e}"
    elapsed = (datetime.utcnow() - start).total_seconds() * 1000
    return {
        "executed_actions": [result_text],
        "final_response": f"Tool result: {result_text}",
        "trace_log": [
            TraceEntry(
                node="action", agent_role=AgentRole.ACTION,
                input_text=state.query, output_text=result_text,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
            )
        ],
    }


def _route_after_triage(state: SharedState) -> str:
    return state.current_agent or "policy"


def build_standard_graph() -> StateGraph:
    graph = StateGraph(SharedState)
    graph.add_node("triage", _triage_node)
    graph.add_node("policy", _policy_node)
    graph.add_node("action", _action_node)
    graph.set_entry_point("triage")
    graph.add_conditional_edges("triage", _route_after_triage, {
        "policy": "policy", "action": "action",
        "anomaly": "policy", "compliance": "policy",
    })
    graph.add_edge("policy", END)
    graph.add_edge("action", END)
    return graph.compile()
