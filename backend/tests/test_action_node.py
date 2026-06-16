import pytest
from unittest.mock import patch, MagicMock

from backend.src.agents.nodes.action_node import (
    _parse_tool_json,
    _build_fallback,
    action_node,
)
from backend.src.agents.state import SharedState


def test_parse_tool_json():
    # Valid JSON
    assert _parse_tool_json('{"name": "test_tool", "args": {"foo": "bar"}}') == {"name": "test_tool", "args": {"foo": "bar"}}

    # Markdown-fenced JSON
    assert _parse_tool_json('```json\n{"name": "test_tool"}\n```') == {"name": "test_tool"}
    assert _parse_tool_json('```\n{"name": "test_tool"}\n```') == {"name": "test_tool"}

    # JSON embedded in text
    assert _parse_tool_json('Here is the tool: {"name": "test_tool"}') == {"name": "test_tool"}

    # Empty/whitespace
    assert _parse_tool_json('') is None
    assert _parse_tool_json('   \n') is None

    # Invalid JSON syntax
    assert _parse_tool_json('{"name": "test_tool", "args": {') is None

    # Missing "name" field
    assert _parse_tool_json('{"args": {}}') is None


def test_build_fallback():
    # Name search
    res = _build_fallback("find John Doe")
    assert res["name"] == "search_employee_by_name"
    assert res["args"]["name"] == "John Doe"

    res = _build_fallback("employee named 'Jane Smith'")
    assert res["name"] == "search_employee_by_name"
    assert res["args"]["name"] == "Jane Smith"

    # Generic count/select
    res = _build_fallback("count all staff")
    assert res["name"] == "execute_db_query"
    assert "COUNT(*)" in res["args"]["sql_query"]

    # Generic fallback
    res = _build_fallback("what is the database structure?")
    assert res["name"] == "get_database_schema"


@pytest.mark.asyncio
@patch("backend.src.agents.nodes.action_node.llm_call")
@patch("backend.src.agents.nodes.action_node.execute_tool")
@patch("backend.src.agents.nodes.action_node.guardrail_registry")
async def test_action_node_malformed_llm_response(mock_guardrail_registry, mock_execute_tool, mock_llm_call):
    # Mock LLM to return invalid JSON
    mock_llm_call.return_value = ("I cannot do that.", 0.0)

    mock_gr = MagicMock()
    mock_gr.passed = True
    mock_guardrail_registry.check_tool.return_value = mock_gr
    mock_guardrail_registry.check_output.return_value = mock_gr

    mock_execute_tool.return_value = {"result": "success"}

    state = SharedState(
        session_id="123",
        query="find employee John Doe",
        messages=[],
        trace_log=[]
    )

    result = await action_node(state)

    # Should use fallback tool
    assert mock_execute_tool.call_count == 1
    args, kwargs = mock_execute_tool.call_args
    assert args[0] == "search_employee_by_name"
    assert kwargs["name"] == "John Doe"

    # Verify trace log contains the fallback information
    trace = result["trace_log"][-1]
    assert trace.tool_call["tool"] == "search_employee_by_name"


@pytest.mark.asyncio
@patch("backend.src.agents.nodes.action_node.llm_call")
@patch("backend.src.agents.nodes.action_node.execute_tool")
@patch("backend.src.agents.nodes.action_node.guardrail_registry")
async def test_action_node_tool_execution_error(mock_guardrail_registry, mock_execute_tool, mock_llm_call):
    # Mock LLM to return valid JSON
    mock_llm_call.return_value = ('{"name": "test_tool", "args": {}}', 0.0)

    mock_gr = MagicMock()
    mock_gr.passed = True
    mock_guardrail_registry.check_tool.return_value = mock_gr
    mock_guardrail_registry.check_output.return_value = mock_gr

    # Mock tool execution to raise an error
    mock_execute_tool.side_effect = Exception("Tool failed")

    state = SharedState(
        session_id="123",
        query="do something",
        messages=[],
        trace_log=[]
    )

    result = await action_node(state)

    # Check that error is handled gracefully and final response reflects it
    assert "Error executing tool `test_tool`: Tool failed" in result["final_response"]

    # Verify trace log contains the error information
    trace = result["trace_log"][-1]
    assert trace.tool_call["error"] == "Tool failed"
