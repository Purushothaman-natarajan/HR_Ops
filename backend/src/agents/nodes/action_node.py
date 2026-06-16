"""Action node: parses HR tool calls from queries and executes them with guardrail checks."""

import json
import logging
import re
from datetime import datetime, timezone

from backend.src.agents.state import Activity, SharedState, TraceEntry
from backend.src.guardrails.registry import guardrail_registry
from backend.src.tools.api_mocks import execute_tool
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.nodes.action")


def _parse_tool_json(response: str) -> dict | None:
    """Try to extract a valid JSON tool call from LLM response.
    
    Handles:
    - Clean JSON: {"name": "...", "args": {...}}
    - Markdown-fenced JSON: ```json {...} ```
    - JSON embedded in text
    """
    if not response or not response.strip():
        return None

    # Strip markdown code fences
    stripped = re.sub(r"```(?:json)?\s*", "", response, flags=re.IGNORECASE).strip()
    stripped = stripped.rstrip("`").strip()

    # Try to parse directly
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and "name" in obj:
            return obj
    except json.JSONDecodeError:
        pass

    # Find first JSON object in the text
    match = re.search(r'\{[^{}]*"name"[^{}]*\}', stripped, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group())
            if isinstance(obj, dict) and "name" in obj:
                return obj
        except json.JSONDecodeError:
            pass

    return None


def _build_name_search_fallback(query: str, schema_tables: list[str]) -> dict:
    """Build a fallback execute_db_query tool call when JSON parsing fails.
    
    Attempts to detect employee name searches and construct appropriate SQL.
    """
    # Check for common employee name lookup patterns
    name_patterns = [
        r"(?:find|search|look\s*up|who\s*is|employee\s+named?)\s+(?:data\s+about\s+)?(?:employee\s+)?([a-zA-Z]+(?:\s+[a-zA-Z]+)*)",
        r"named?\s+['\"]?([a-zA-Z]+(?:\s+[a-zA-Z]+)*)['\"]?",
        r"([a-zA-Z]+(?:\s+[a-zA-Z]+)*)\s+(?:employee|record|profile)",
    ]

    emp_table = next((t for t in schema_tables if "employee" in t.lower()), "employees")
    
    for pattern in name_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Use LIKE for partial match
            sql = f"SELECT * FROM {emp_table} WHERE Employee_Name LIKE ? LIMIT 10;"
            return {"name": "execute_db_query", "args": {"sql_query": sql, "parameters": [f"%{name}%"]}}

    # Generic: try a broad search if keywords suggest a lookup
    kw_select = any(kw in query.lower() for kw in ["how many", "count", "list all", "show all", "all employees"])
    if kw_select:
        sql = f"SELECT COUNT(*) as total_employees FROM {emp_table};"
        return {"name": "execute_db_query", "args": {"sql_query": sql}}

    # Last resort: schema inspection
    return {"name": "get_database_schema", "args": {}}


async def action_node(state: SharedState) -> dict:
    """Parse a tool call from the query, run it through guardrails, and execute it."""
    start = datetime.now(timezone.utc)
    activities = []
    # Fetch active database schema dynamically to inject into prompt
    from backend.src.tools.api_mocks import get_database_schema
    schema_res = get_database_schema()
    schema_str = ""
    schema_tables = []
    if schema_res.get("success"):
        schema_str = "\nActive Database Schema:\n"
        for table, cols in schema_res.get("schema", {}).items():
            schema_tables.append(table)
            schema_str += f"- Table: {table}\n"
            for col in cols:
                schema_str += f"  - {col['name']} ({col['type']}){ ' [PK]' if col['pk'] else '' }\n"

    prompt = (
        f"Extract a tool call from the HR query.\n"
        f"Available tools:\n"
        f"  get_database_schema()\n"
        f"  execute_db_query(sql_query, parameters)\n"
        f"  lookup_employee(employee_id)\n"
        f"  modify_record(employee_id, field, value)\n"
        f"  escalate_to_human(employee_id, reason)\n\n"
        f"Use `execute_db_query` with parameterized SQLite queries to retrieve or modify records. MUST always use `?` placeholders for user input to prevent SQL injection.\n"
        f"Provide the values in the `parameters` list.\n"
        f"Example: {{\"name\": \"execute_db_query\", \"args\": {{\"sql_query\": \"SELECT * FROM employees WHERE Employee_Name LIKE ? LIMIT 10;\", \"parameters\": [\"%name%\"]}}}}\n"
        f"{schema_str}\n"
        f"Query: {state.query}\n\n"
        f"IMPORTANT: Reply ONLY with valid JSON, no markdown, no explanation:\n"
        f'{{\"name\": \"tool_name\", \"args\": {{...}}}}'
    )
    activities.append(Activity(
        type="llm_call", label="Parsing tool call from query",
        detail=f"Query: {state.query[:80]}...",
        status="running",
    ))
    response, cost = await llm_call("action", prompt, max_tokens=256, temperature=0)
    activities[-1].status = "completed"

    tool_call_info = {}
    call = _parse_tool_json(response)

    if call is None:
        # LLM didn't return valid JSON — use intelligent fallback
        logger.warning("action_node: LLM returned non-JSON response, using fallback. Response: %r", response[:200])
        call = _build_name_search_fallback(state.query, schema_tables)
        activities[-1].detail = f"Fallback tool: {call['name']} (LLM returned non-JSON)"
        activities.append(Activity(
            type="decision", label="Fallback tool selection",
            detail=f"LLM response was not valid JSON. Auto-selected: {call['name']}",
            status="completed",
        ))
    else:
        activities[-1].detail = f"Parsed tool: {call.get('name', 'unknown')}({json.dumps(call.get('args', {}))})"

    tool_call_info = {"tool": call.get("name", ""), "args": call.get("args", {})}

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

            activities.append(Activity(
                type="tool_call", label=f"Executing {call.get('name', 'tool')}",
                detail=f"Args: {json.dumps(call.get('args', {}))}",
                status="running",
            ))
            # Inject session_id into context for tools like escalate_to_human
            tool_args_with_ctx = dict(call["args"])
            if call["name"] == "escalate_to_human":
                ctx = dict(tool_args_with_ctx.get("context") or {})
                ctx["session_id"] = state.session_id
                tool_args_with_ctx["context"] = ctx
            result = execute_tool(call["name"], **tool_args_with_ctx)
            activities[-1].status = "completed"
            activities[-1].detail = f"Tool returned: {json.dumps(result)[:120]}"
            from backend.src.utils.formatter import format_tool_result_to_markdown
            result_text = format_tool_result_to_markdown(result)
            tool_call_info["result"] = result.get("result")
    except Exception as e:
        result_text = f"Error executing tool `{call.get('name', 'unknown')}`: {e}"
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
