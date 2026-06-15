"""Validates tool calls against an allowed list and argument constraints."""

from backend.src.guardrails.registry import guardrail_registry

ALLOWED_TOOLS = {"lookup_employee", "modify_record", "escalate_to_human", "get_database_schema", "execute_db_query"}


def tool_guardrail(context: dict) -> tuple[bool, str]:
    """Verify tool_name is allowed and no argument exceeds maximum length."""
    tool_name = context.get("tool_name", "")
    if tool_name and tool_name not in ALLOWED_TOOLS:
        return False, f"Tool '{tool_name}' is not in the allowed list"
    args = context.get("args", {})
    for key, val in args.items():
        if isinstance(val, str) and len(val) > 2000:
            return False, f"Argument '{key}' exceeds maximum length"
    return True, ""


guardrail_registry.register_tool(tool_guardrail, "tool_validator")
