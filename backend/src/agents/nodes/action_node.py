"""Action node: parses HR tool calls from queries, executes them, then synthesises
a readable natural-language response from the raw tool result.

Flow:
  1. Pre-screen query for direct name/ID lookups — bypass LLM parsing with deterministic routing
  2. If not matched, call LLM to select + parameterise the correct tool
  3. Run guardrail check on the chosen tool call
  4. Execute the tool
  5. Synthesise a clean human-readable response from the raw result via a second LLM call
"""

import json
import logging
import re
from datetime import datetime, timezone

from backend.src.agents.state import Activity, SharedState, TraceEntry
from backend.src.guardrails.registry import guardrail_registry
from backend.src.tools.api_mocks import execute_tool
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.nodes.action")


# ─── Tool call JSON parser ────────────────────────────────────────────────────


def _parse_tool_json(response: str) -> dict | None:
    """Try to extract a valid JSON tool call from LLM response.

    Supports direct JSON, markdown-fences, and embedded JSON in conversational preambles.
    """
    if not response or not response.strip():
        return None

    # Try simple direct parse of the stripped response
    stripped = response.strip()
    # Strip markdown code fences if present
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    stripped = stripped.strip()

    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and "name" in obj:
            return obj
    except json.JSONDecodeError:
        pass

    # Find the first occurrences of '{' and scan for a valid JSON object
    start_idx = response.find("{")
    while start_idx != -1:
        # Try to find matching closing bracket by parsing substrings of increasing length
        for end_idx in range(len(response), start_idx, -1):
            try:
                candidate = response[start_idx:end_idx]
                obj = json.loads(candidate)
                if isinstance(obj, dict) and "name" in obj:
                    return obj
            except json.JSONDecodeError:
                continue
        # Find next occurrence of '{'
        start_idx = response.find("{", start_idx + 1)

    return None


# ─── Pre-screen: deterministic lookup routing ─────────────────────────────────

# All patterns that indicate "find employee by name"
_NAME_LOOKUP_PATTERNS = [
    # employee named 'John' or named John
    r"(?:employee\s+)?named\s+['\"]?([A-Za-z]+(?:\s+[A-Za-z]+)*)['\"]?",
    # find/search/look up/show/get [employee] John Doe
    r"(?:find|search|look\s*up|show|get|who\s+is)\s+(?:info(?:rmation)?\s+(?:about|for|on)\s+)?(?:employee\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)*)",
    # John Doe's profile/details/record
    r"([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(?:'s\s+)?(?:info(?:rmation)?|profile|details?|record)",
    # John Doe employee/staff
    r"([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(?:employee|staff)",
]

_FORBIDDEN_NAME_WORDS = {
    "policy", "leave", "holiday", "vacation", "rules", "guidelines", "handbook",
    "schema", "table", "database", "query", "record", "system", "hr", "ops",
    "payroll", "salary", "bonus", "attendance", "performance", "training",
    "safety", "employee", "staff", "person", "info", "information", "data", "all",
    "and", "or", "but", "show", "list", "get", "find", "search", "who", "whom", 
    "whose", "what", "where", "when", "why", "how", "their", "his", "her", "its", 
    "them", "they", "him", "she", "me", "my", "your", "our", "us", "department", 
    "dept", "office", "location", "role", "title", "position", "manager", "boss"
}

_EMP_ID_PATTERN = re.compile(r"\b(EMP\d{4,})\b", re.IGNORECASE)


def _is_valid_name(name: str) -> bool:
    name_lower = name.lower()
    if len(name_lower) < 2:
        return False
    words = name_lower.split()
    if len(words) > 3:
        return False
    if set(words) & _FORBIDDEN_NAME_WORDS:
        return False
    return True


def _prescreen_query(query: str) -> dict | None:
    """Return a direct tool call dict if the query is a clear name/ID lookup."""
    q = query.strip()

    # Employee ID lookup
    m = _EMP_ID_PATTERN.search(q)
    if m:
        eid = m.group(1).upper()
        return {"name": "lookup_employee", "args": {"employee_id": eid}}

    # Name lookup — try all patterns
    for pattern in _NAME_LOOKUP_PATTERNS:
        m = re.search(pattern, q, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if _is_valid_name(name):
                return {"name": "search_employee_by_name", "args": {"name": name}}

    return None


# ─── Fallback for when LLM returns non-JSON ──────────────────────────────────


def _build_fallback(query: str) -> dict:
    """Construct a best-effort tool call when LLM parsing fails."""
    q_lower = query.lower()

    # Name search fallback
    for pattern in _NAME_LOOKUP_PATTERNS:
        m = re.search(pattern, query, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if _is_valid_name(name):
                return {"name": "search_employee_by_name", "args": {"name": name}}

    # Count / list queries
    if any(kw in q_lower for kw in ["how many", "count", "list all", "show all", "all employees"]):
        return {"name": "execute_db_query", "args": {"sql_query": "SELECT COUNT(*) as total_employees FROM employees;"}}

    # Schema inspection as last resort
    return {"name": "get_database_schema", "args": {}}


# ─── Response synthesiser ─────────────────────────────────────────────────────


async def _synthesise_response(query: str, tool_name: str, tool_result: dict) -> str:
    """Convert a raw tool result dict into a clean, readable HR response via LLM."""
    result_json = json.dumps(tool_result, indent=2)[:2000]  # cap to avoid token overflow

    prompt = (
        "You are an HR assistant. A user asked a question and a tool was executed. "
        "Summarise the tool result in clear, friendly language — use bullet points or "
        "a structured format when returning employee details. "
        "Do NOT repeat the raw JSON.\n\n"
        f"User query: {query}\n"
        f"Tool used: {tool_name}\n"
        f"Tool result:\n{result_json}\n\n"
        "Provide a concise, well-formatted answer:"
    )
    response, _ = await llm_call("action_synthesis", prompt, max_tokens=512, temperature=0.1)
    return response.strip() or result_json


# ─── Main node ────────────────────────────────────────────────────────────────


async def action_node(state: SharedState) -> dict:
    """Parse a tool call from the query, run it through guardrails, execute it, and synthesise a response."""
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
        logger.info("action_node: pre-screened as %s(%s)", call["name"], call["args"])
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
            "  - Use ? placeholders in SQL, provide values in 'parameters' list.\n\n"
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
            logger.warning("action_node: LLM returned non-JSON, using fallback. response=%r", response[:200])
            call = _build_fallback(state.query)
            activities[-1].detail = f"Fallback: {call['name']} (LLM non-JSON)"
        else:
            activities[-1].detail = f"Parsed: {call.get('name')}({json.dumps(call.get('args', {}))})"

        # Safety override: if LLM chose get_database_schema for a name query, re-route
        if call.get("name") == "get_database_schema":
            override = _build_fallback(state.query)
            if override.get("name") != "get_database_schema":
                logger.warning("action_node: overriding LLM schema call with %s", override["name"])
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
        logger.exception("action_node tool execution failed")

    # Output guardrail (soft check)
    output_gr = guardrail_registry.check_output({"text": result_text})
    if not output_gr.passed:
        logger.warning("Output guardrail flagged: %s", output_gr.message)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
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
