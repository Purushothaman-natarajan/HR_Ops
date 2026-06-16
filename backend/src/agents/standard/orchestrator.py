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
from backend.src.agents.nodes.action_node import (
    _prescreen_query, _build_fallback, _parse_tool_json, _synthesise_response,
)
from backend.src.guardrails.registry import guardrail_registry
from backend.src.tools.api_mocks import execute_tool
from backend.src.utils.model_router import llm_call
from backend.src.agents.nodes.hitl_escalation_node import hitl_escalation_node

logger = logging.getLogger("hr_ops.standard_orchestrator")


async def _triage_node(state: SharedState) -> dict:
    """Classify the incoming HR query into policy, action, anomaly, or compliance."""
    start = datetime.now(timezone.utc)
    history = state.messages
    history_context = ""
    if history:
        recent = history[-4:]
        history_context = "Conversation history:\n" + "\n".join(
            f"{m['role']}: {m['content'][:200]}" for m in recent
        ) + "\n\n"

    prompt = (
        f"{history_context}"
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
    """Parse a tool call from the query, run it through guardrails, execute it, and synthesise a response."""
    import json

    start = datetime.now(timezone.utc)
    activities = []
    cost = 0.0

    # ── Step 1: Pre-screen for direct lookup ────────────────────────────────
    call = _prescreen_query(state.query)
    if call:
        activities.append(Activity(
            type="decision", label="Direct lookup routing",
            detail=f"Matched: {call['name']}({call['args']})",
            status="completed",
        ))
        logger.info("_action_node: pre-screened as %s(%s)", call["name"], call["args"])
    else:
        # ── Step 2: LLM tool parsing ─────────────────────────────────────────
        from backend.src.services.db_schema_store import get_schema_understanding
        schema_understanding = await get_schema_understanding()

        history = state.messages
        history_context = ""
        if history:
            recent = history[-4:]
            history_context = "Conversation history:\n" + "\n".join(
                f"{m['role']}: {m['content'][:200]}" for m in recent
            ) + "\n\n"

        prompt = (
            f"{history_context}"
            "Extract a tool call from the HR query. Use the conversation history to resolve pronouns (e.g. 'he', 'she', 'their') or contextual references.\n"
            "Available tools:\n"
            "  search_employee_by_name(name)           ← USE THIS for any name/person lookup\n"
            "  lookup_employee(employee_id)             ← USE THIS only when you have an EMP ID\n"
            "  execute_db_query(sql_query, parameters)  ← for complex SQL queries\n"
            "  modify_record(employee_id, field, value)\n"
            "  escalate_to_human(employee_id, reason)\n"
            "  get_database_schema()\n\n"
            "RULES:\n"
            "  - If the query mentions a person's name (like 'John', 'ALICE', 'find Bob'), "
            "use search_employee_by_name with the name.\n"
            "  - Do NOT use get_database_schema unless the user explicitly asks about schema.\n"
            "  - Use ? placeholders in SQL, provide values in 'parameters' list.\n"
            "  - If the query asks to create, record, request, or apply for something (like applying for leave), "
            "you MUST generate an INSERT statement instead of a SELECT query. For leave requests, insert into the `leaves` table "
            "(columns: employee_id, leave_type, start_date, end_date, status, reason) with status set to 'Pending'.\n"
            "  - If the query asks to modify or update data, generate an UPDATE statement.\n\n"
            f"Database Schema Understanding:\n{schema_understanding}\n\n"
            f"Query: {state.query}\n\n"
            "Reply ONLY with valid JSON:\n"
            '{"name": "tool_name", "args": {...}}'
        )

        activities.append(Activity(
            type="llm_call", label="Parsing tool call from query",
            detail=f"Query: {state.query[:80]}...",
            status="running",
        ))
        response, cost = await llm_call("action", prompt, max_tokens=256, temperature=0)
        activities[-1].status = "completed"

        call = _parse_tool_json(response)
        if call is None:
            logger.warning("_action_node: LLM returned non-JSON, using fallback. response=%r", response[:200])
            call = _build_fallback(state.query)
            activities[-1].detail = f"Fallback: {call['name']} (LLM non-JSON)"
        else:
            activities[-1].detail = f"Parsed: {call.get('name')}({json.dumps(call.get('args', {}))})"

        # Safety override: if LLM chose get_database_schema for a name query, re-route
        if call.get("name") == "get_database_schema":
            override = _build_fallback(state.query)
            if override.get("name") != "get_database_schema":
                logger.warning("_action_node: overriding LLM schema call with %s", override["name"])
                call = override
                activities.append(Activity(
                    type="decision", label="Schema-call override",
                    detail=f"Re-routed to {call['name']} — query is a lookup, not schema inspection",
                    status="completed",
                ))

    tool_call_info: dict = {"tool": call.get("name", ""), "args": call.get("args", {})}
    result_text = ""

    # ── Step 3: Guardrail check ──────────────────────────────────────────────
    try:
        activities.append(Activity(
            type="guardrail", label="Running guardrail check",
            detail=f"Tool: {call.get('name', 'unknown')}",
            status="running",
        ))
        gr = guardrail_registry.check_tool({"tool_name": call.get("name", ""), "args": call.get("args", {})})
        if not gr.passed:
            activities[-1].status = "completed"
            activities[-1].detail = f"BLOCKED: {gr.message}"
            result_text = f"Tool guardrail blocked: {gr.message}"
        else:
            activities[-1].status = "completed"
            activities[-1].detail = "Guardrail PASSED"

            # ── Step 4: Execute tool ─────────────────────────────────────────
            # Intercept database write queries and modify_record calls for HITL approval
            is_write_query = False
            if call["name"] == "execute_db_query":
                sql_query = call["args"].get("sql_query", "").strip().upper()
                is_write_query = any(sql_query.startswith(kw) for kw in ["UPDATE", "INSERT", "DELETE", "CREATE", "DROP", "ALTER", "REPLACE"])
            elif call["name"] == "modify_record":
                is_write_query = True

            if is_write_query:
                state.rl_context["pending_tool_call"] = call
                state.hitl_needed = True
                activities.append(Activity(
                    type="decision", label="Intercepted write query",
                    detail=f"Intercepted {call['name']} for approval",
                    status="completed",
                ))
                result_text = f"The requested database modification has been recorded and submitted for human approval."
                tool_call_info["result"] = {
                    "status": "pending_approval",
                    "query": call["args"].get("sql_query") if call["name"] == "execute_db_query" else f"Modify {call['args'].get('field')} for {call['args'].get('employee_id')}"
                }
            else:
                activities.append(Activity(
                    type="tool_call", label=f"Executing {call.get('name', 'tool')}",
                    detail=f"Args: {json.dumps(call.get('args', {}))}",
                    status="running",
                ))
                tool_args = dict(call["args"])
                if call["name"] == "escalate_to_human":
                    ctx = dict(tool_args.get("context") or {})
                    ctx["session_id"] = state.session_id
                    tool_args["context"] = ctx

                raw_result = execute_tool(call["name"], **tool_args)
                activities[-1].status = "completed"
                activities[-1].detail = f"Tool returned: {json.dumps(raw_result)[:120]}"
                tool_call_info["result"] = raw_result.get("result")

                # ── Step 5: Synthesise readable response ─────────────────────────
                inner = raw_result.get("result", raw_result)
                activities.append(Activity(
                    type="llm_call", label="Synthesising human-readable response",
                    detail="Converting raw tool result to natural language",
                    status="running",
                ))
                result_text = await _synthesise_response(state.query, call["name"], inner)
                activities[-1].status = "completed"
                activities[-1].detail = f"Response: {result_text[:80]}..."

    except Exception as e:
        result_text = f"Error executing tool `{call.get('name', 'unknown')}`: {e}"
        tool_call_info["error"] = str(e)
        if activities and activities[-1].status == "running":
            activities[-1].status = "failed"
            activities[-1].detail = f"Error: {e}"
        logger.exception("_action_node tool execution failed")

    # Output guardrail (soft check)
    output_gr = guardrail_registry.check_output({"text": result_text})
    if not output_gr.passed:
        logger.warning("Output guardrail flagged: %s", output_gr.message)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    return {
        "hitl_needed": state.hitl_needed,
        "rl_context": state.rl_context,
        "executed_actions": [result_text],
        "final_response": result_text,
        "messages": state.messages + [
            {"role": "user", "content": state.query},
            {"role": "assistant", "content": result_text, "node": "action"},
        ],
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="action", agent_role=AgentRole.ACTION,
                input_text=state.query, output_text=result_text,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
                tool_call=tool_call_info,
                activities=activities,
            )
        ],
    }


def _route_after_triage(state: SharedState) -> str:
    """Return the agent name to route to after triage based on classification."""
    return state.current_agent or "policy"


def _should_continue(state: SharedState) -> str:
    """Return 'hitl' if HITL escalation is needed, otherwise END."""
    if state.hitl_needed:
        return "hitl"
    return END


def build_standard_graph() -> CompiledStateGraph:
    """Build and compile the standard LangGraph with triage, policy, action, and hitl nodes."""
    graph = StateGraph(SharedState)
    graph.add_node("triage", _triage_node)
    graph.add_node("policy", _policy_node)
    graph.add_node("action", _action_node)
    graph.add_node("hitl", hitl_escalation_node)
    graph.set_entry_point("triage")
    graph.add_conditional_edges("triage", _route_after_triage, {
        "policy": "policy", "action": "action",
        "anomaly": "policy", "compliance": "policy",
    })
    graph.add_conditional_edges("action", _should_continue, {
        "hitl": "hitl",
        END: END
    })
    graph.add_edge("policy", END)
    graph.add_edge("hitl", END)
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
