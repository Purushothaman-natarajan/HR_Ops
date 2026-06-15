"""Action node: parses HR tool calls from queries and executes them with guardrail checks."""

import json
import logging
from datetime import datetime, timezone

from backend.src.agents.state import Activity, SharedState, TraceEntry
from backend.src.guardrails.registry import guardrail_registry
from backend.src.tools.api_mocks import execute_tool
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.nodes.action")


async def action_node(state: SharedState) -> dict:
    """Parse a tool call from the query, run it through guardrails, and execute it."""
    start = datetime.now(timezone.utc)
    activities = []
    # Fetch active database schema dynamically to inject into prompt
    from backend.src.tools.api_mocks import get_database_schema
    schema_res = get_database_schema()
    schema_str = ""
    if schema_res.get("success"):
        schema_str = "\nActive Database Schema:\n"
        for table, cols in schema_res.get("schema", {}).items():
            schema_str += f"- Table: {table}\n"
            for col in cols:
                schema_str += f"  - {col['name']} ({col['type']}){ ' [PK]' if col['pk'] else '' }\n"

    prompt = (
        f"Extract a tool call from the HR query.\n"
        f"Available tools:\n"
        f"  get_database_schema()\n"
        f"  execute_db_query(sql_query)\n"
        f"  lookup_employee(employee_id)\n"
        f"  modify_record(employee_id, field, value)\n"
        f"  escalate_to_human(employee_id, reason)\n\n"
        f"Use `execute_db_query` with standard SQLite queries to retrieve or modify records in the active database tables.\n"
        f"{schema_str}\n"
        f"Query: {state.query}\n\n"
        f"Reply with JSON: {{\"name\": \"tool_name\", \"args\": {{...}}}}"
    )
    activities.append(Activity(
        type="llm_call", label="Parsing tool call from query",
        detail=f"Query: {state.query[:80]}...",
        status="running",
    ))
    response, cost = await llm_call("action", prompt, max_tokens=256, temperature=0)
    activities[-1].status = "completed"
    tool_call_info = {}
    try:
        call = json.loads(response)
        tool_call_info = {"tool": call.get("name", ""), "args": call.get("args", {})}
        activities[-1].detail = f"Parsed tool: {call.get('name', 'unknown')}({json.dumps(call.get('args', {}))})"

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

            activities.append(Activity(
                type="tool_call", label=f"Executing {call.get('name', 'tool')}",
                detail=f"Args: {json.dumps(call.get('args', {}))}",
                status="running",
            ))
            result = execute_tool(call["name"], **call["args"])
            activities[-1].status = "completed"
            activities[-1].detail = f"Tool returned: {json.dumps(result)[:120]}"
            result_text = json.dumps(result, indent=2)
            tool_call_info["result"] = result
    except Exception as e:
        result_text = f"Error: {e}"
        tool_call_info["error"] = str(e)
        if activities and activities[-1].status == "running":
            activities[-1].status = "failed"
            activities[-1].detail = f"Error: {e}"
    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    # Run output guardrails (soft check — log warnings but don't block)
    output_gr = guardrail_registry.check_output({"text": result_text})
    if not output_gr.passed:
        logger.warning("Output guardrail flagged in action_node: %s", output_gr.message)
    return {
        "executed_actions": [result_text],
        "final_response": result_text,
        "messages": state.messages + [
            {"role": "user", "content": state.query},
            {"role": "assistant", "content": result_text, "node": "action"},
        ],
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="action_node", agent_role="action",
                input_text=state.query, output_text=result_text,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
                tool_call=tool_call_info,
                activities=activities,
            )
        ],
    }
