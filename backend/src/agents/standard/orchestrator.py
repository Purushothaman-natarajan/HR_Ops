"""Standard single-pass orchestrator for the HR agent graph.

Builds a linear LangGraph with triage, policy, and action nodes.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as script: add project root to sys.path
if __name__ == "__main__":
    _p = Path(__file__).resolve()
    for _parent in _p.parents:
        if (_parent / "backend").is_dir():
            sys.path.insert(0, str(_parent))
            break

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.config.settings import settings
from backend.src.agents.state import AgentRole, SharedState, TraceEntry, Activity
from backend.src.guardrails.registry import guardrail_registry
from backend.src.tools.api_mocks import execute_tool
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.standard_orchestrator")


async def _triage_node(state: SharedState) -> dict:
    """Classify the incoming HR query into policy, action, anomaly, or compliance."""
    start = datetime.now(timezone.utc)
    prompt = (
        f"Classify the following HR query into one of:\n"
        f"- policy (ask about HR policies, rules, benefits, etc. from documents)\n"
        f"- action (query, count, retrieve, or modify employee database records/details)\n"
        f"- anomaly (investigate data issues, discrepancies, or outliers)\n"
        f"- compliance (check policy compliance)\n\n"
        f"Query: {state.query}\n\n"
        f"Reply with exactly one word: policy/action/anomaly/compliance."
    )
    if settings.feature_flags.get("guardrails", {}).get("input_enabled", True):
        gr = guardrail_registry.check_input({"text": state.query, "messages": state.messages})
        if not gr.passed:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return {
                "final_response": f"Input guardrail blocked: {gr.message}",
                "current_agent": AgentRole.SUPERVISOR,
                "trace_log": (state.trace_log or []) + [
                    TraceEntry(
                        node="triage", agent_role=AgentRole.SUPERVISOR,
                        input_text=state.query, output_text=gr.message,
                        timestamp=start, duration_ms=elapsed,
                        guardrail_result=gr,
                    )
                ],
            }
    classification, cost = await llm_call("triage", prompt, max_tokens=20, temperature=0)
    classification = classification.strip().lower()
    if classification not in ("policy", "action", "anomaly", "compliance"):
        classification = "policy"
    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    activities = [
        Activity(
            type="llm_call",
            label="Classifying query with LLM",
            detail=f"Classified query as '{classification}'",
            status="completed",
            duration_ms=elapsed,
        )
    ]
    return {
        "rl_context": {"classification": classification, "query": state.query},
        "rl_selected_action": classification,
        "current_agent": classification,
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="triage", agent_role=AgentRole.SUPERVISOR,
                input_text=state.query, output_text=f"Classified as {classification}",
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
                activities=activities,
            )
        ],
    }


async def _policy_node(state: SharedState) -> dict:
    """Answer an HR policy question by retrieving relevant policies and generating a response."""
    start = datetime.now(timezone.utc)
    from backend.src.memory.vector_store import similarity_search

    docs = similarity_search(state.query, k=3)
    retrieval_docs = []
    for d in (docs or []):
        retrieval_docs.append({
            "source": getattr(d, "metadata", {}).get("source", "unknown"),
            "score": getattr(d, "metadata", {}).get("score", 0.0),
            "chunk": d.page_content[:200],
        })

    activities = [
        Activity(
            type="search",
            label="Searching vector DB for relevant policies",
            detail=f"Found {len(docs) if docs else 0} documents",
            status="completed",
            duration_ms=0.0,
        ),
        Activity(
            type="llm_call",
            label="Generating answer with LLM",
            detail=f"Context: {len(docs) if docs else 0} policy chunks, max_tokens=512",
            status="completed",
            duration_ms=0.0,
        )
    ]

    context = "\n\n".join(d.page_content for d in docs) if docs else "No policies found."
    prompt = (
        f"Answer the HR question based on the retrieved policies.\n\n"
        f"Policies:\n{context}\n\n"
        f"Question: {state.query}\n\n"
        f"Format your response using this structure:\n"
        f"1. Start with a brief 1-2 sentence summary answering the question directly\n"
        f"2. Use a ## heading for key points (e.g., ## Key Points or ## Policy Details)\n"
        f"3. Use bullet points (not numbered lists) for multiple items\n"
        f"4. Use **bold** for important terms or policy names\n"
        f"5. Keep paragraphs short (2-3 sentences max)\n"
        f"6. End with a clear actionable recommendation if applicable\n"
        f"7. Avoid mixing numbered lists with bullet points - use one format consistently\n"
        f"8. Do not include headers like 'Why Not More' or similar - just answer the question directly\n\n"
        f"Provide a clear, actionable answer."
    )
    answer, cost = await llm_call("rag", prompt, max_tokens=512)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    activities[1].duration_ms = elapsed

    return {
        "final_response": answer,
        "retrieved_policies": [d.page_content[:200] for d in (docs or [])],
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="policy", agent_role=AgentRole.POLICY,
                input_text=state.query, output_text=answer,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
                retrieved_docs=retrieval_docs,
                activities=activities,
            )
        ],
    }


async def _action_node(state: SharedState) -> dict:
    """Parse a tool call from the query and execute it (lookup, modify, or escalate)."""
    start = datetime.now(timezone.utc)
    from backend.src.services.db_schema_store import get_schema_understanding
    schema_understanding = await get_schema_understanding()

    prompt = (
        f"Extract the tool call from the query. Valid tools:\n"
        f"- get_database_schema()\n"
        f"- execute_db_query(sql_query, parameters)\n"
        f"- lookup_employee(employee_id: str)\n"
        f"- modify_record(employee_id: str, field: str, value: any)\n"
        f"- escalate_to_human(employee_id: str, reason: str)\n\n"
        f"Use `execute_db_query` with parameterized SQLite queries to retrieve or modify records in the active database tables. ALWAYS use `?` placeholders for user inputs to prevent SQL injection and supply the values in the `parameters` list.\n\n"
        f"Database Schema Understanding:\n{schema_understanding}\n\n"
        f"Query: {state.query}\n\n"
        f"Reply with a JSON object: {{\"name\": \"tool_name\", \"args\": {{...}}}}"
    )
    response, cost = await llm_call("action", prompt, max_tokens=256, temperature=0)
    import json
    import re

    def _parse_tool_json(s: str) -> dict | None:
        if not s or not s.strip():
            return None
        stripped = re.sub(r"```(?:json)?\s*", "", s, flags=re.IGNORECASE).strip().rstrip("`").strip()
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and "name" in obj:
                return obj
        except json.JSONDecodeError:
            pass
        match = re.search(r'\{[^{}]*"name"[^{}]*\}', stripped, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
                if isinstance(obj, dict) and "name" in obj:
                    return obj
            except json.JSONDecodeError:
                pass
        return None

    try:
        call = _parse_tool_json(response)
        if call is None:
            # Fallback: try name search
            name_m = re.search(r"named?\s+['\"]?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)['\"]?", state.query, re.IGNORECASE)
            if name_m:
                name = name_m.group(1).strip()
                call = {"name": "execute_db_query", "args": {"sql_query": "SELECT * FROM employees WHERE Employee_Name LIKE ? LIMIT 10;", "parameters": [f"%{name}%"]}}
            else:
                call = {"name": "get_database_schema", "args": {}}
            logger.warning("_action_node: LLM returned non-JSON, using fallback tool: %s", call["name"])
        tool_name = call.get("name", "unknown")
        tool_args = call.get("args", {})
        tool_result = execute_tool(tool_name, **tool_args)
        from backend.src.utils.formatter import format_tool_result_to_markdown
        result_text = format_tool_result_to_markdown(tool_result)
    except Exception as e:
        tool_name = "unknown"
        tool_args = {}
        result_text = f"Error: {e}"
    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    activities = [
        Activity(
            type="llm_call",
            label="Parsing tool call with LLM",
            detail=f"Parsed tool call: {response[:100]}",
            status="completed",
            duration_ms=elapsed,
        ),
        Activity(
            type="tool_call",
            label=f"Executing tool: {tool_name}",
            detail=f"Args: {json.dumps(tool_args)}",
            status="completed",
            duration_ms=0.0,
            metadata={"tool_name": tool_name, "args": tool_args},
        )
    ]

    return {
        "executed_actions": [result_text],
        "final_response": f"Tool result: {result_text}",
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="action", agent_role=AgentRole.ACTION,
                input_text=state.query, output_text=result_text,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
                activities=activities,
                tool_call={"tool": tool_name, "args": tool_args, "result": result_text},
            )
        ],
    }


def _route_after_triage(state: SharedState) -> str:
    """Return the agent name to route to after triage based on classification."""
    return state.current_agent or "policy"


def build_standard_graph() -> CompiledStateGraph:
    """Build and compile the standard LangGraph with triage, policy, and action nodes."""
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


if __name__ == "__main__":
    import argparse
    import asyncio
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run the standard HR orchestrator with a sample query.")
    parser.add_argument("query", nargs="?", default="What is the annual leave policy?",
                        help="HR query to process")
    parser.add_argument("--mock", action="store_true", default=None,
                        help="Use mock LLM responses (auto-detected when no API key is set)")
    args = parser.parse_args()

    async def main():
        from backend.src.tools.api_mocks import load_employees_from_csv

        load_employees_from_csv()

        query = args.query
        use_mock = args.mock if args.mock is not None else not settings.llm_is_configured

        if use_mock:
            print("Using mock LLM responses (no API keys configured)")

            # Heuristic mock: triage returns "action" if query mentions tool-like keywords
            def _mock_triage(query):
                kw = {"lookup", "update", "modify", "employee", "salary", "EMP", "escalate", "find", "search", "who is"}
                return ("action", 0.0) if kw & set(query.lower().split()) else ("policy", 0.0)

            _mock_responses = {
                "action": (
                    '{"name": "execute_db_query", "args": {"sql_query": "SELECT * FROM employees WHERE Employee_Name LIKE ? LIMIT 10;", "parameters": ["%John%"]}}', 0.0,
                ),
            }

            async def _mock_llm_call(agent_name, prompt, **kwargs):
                if agent_name == "triage":
                    resp = _mock_triage(prompt.split("Query:")[-1].strip())
                else:
                    resp = _mock_responses.get(agent_name, ("This is a mock response about HR policies.", 0.0))
                print(f"  [mock] {agent_name} <- {resp[0][:80]}...")
                return resp

            # Patch the llm_call reference used by the orchestrator module
            orchestrator_mod = sys.modules.get(__name__) or sys.modules.get("backend.src.agents.standard.orchestrator")
            if orchestrator_mod:
                orchestrator_mod.llm_call = _mock_llm_call

        print(f"\nQuery: {query}\n{'-' * 60}")
        state = SharedState(query=query)
        graph = build_standard_graph()

        try:
            result = await graph.ainvoke(state)
        except Exception as e:
            print(f"\nError running graph: {e}")
            sys.exit(1)

        print(f"\nResults:\n{'-' * 60}")
        if result.get("final_response"):
            print(f"Final response: {result['final_response']}")
        if result.get("executed_actions"):
            print(f"Executed actions: {json.dumps(result['executed_actions'], indent=2)}")
        if result.get("retrieved_policies"):
            print(f"Retrieved policies ({len(result['retrieved_policies'])}):")
            for p in result["retrieved_policies"]:
                print(f"  - {p[:100]}...")
        if result.get("trace_log"):
            print(f"Trace log ({len(result['trace_log'])} entries):")
            for t in result["trace_log"]:
                print(f"  [{t.node}] role={t.agent_role} duration={t.duration_ms:.0f}ms")

    asyncio.run(main())
