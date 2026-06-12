import json
import logging
from datetime import datetime

from backend.src.agents.state import SharedState, TraceEntry
from backend.src.utils.model_router import llm_call
from backend.src.tools.api_mocks import execute_tool
from backend.src.guardrails.registry import guardrail_registry

logger = logging.getLogger("hr_ops.nodes.action")


def action_node(state: SharedState) -> dict:
    start = datetime.utcnow()
    prompt = (
        f"Extract a tool call from the HR query.\n"
        f"Available tools:\n"
        f"  lookup_employee(employee_id)\n"
        f"  modify_record(employee_id, field, value)\n"
        f"  escalate_to_human(employee_id, reason)\n\n"
        f"Query: {state.query}\n\n"
        f"Reply with JSON: {{\"name\": \"tool_name\", \"args\": {{...}}}}"
    )
    response, cost = llm_call("action", prompt, max_tokens=256, temperature=0)
    try:
        call = json.loads(response)
        gr = guardrail_registry.check_tool({"tool_name": call.get("name", ""), "args": call.get("args", {})})
        if not gr.passed:
            result_text = f"Tool guardrail blocked: {gr.message}"
        else:
            result = execute_tool(call["name"], **call["args"])
            result_text = json.dumps(result, indent=2)
    except Exception as e:
        result_text = f"Error: {e}"
    elapsed = (datetime.utcnow() - start).total_seconds() * 1000
    return {
        "executed_actions": [result_text],
        "final_response": result_text,
        "trace_log": [
            TraceEntry(
                node="action_node", agent_role="action",
                input_text=state.query, output_text=result_text,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
            )
        ],
    }
