import pytest
import sqlite3
from unittest.mock import patch, MagicMock

from backend.src.agents.nodes.action_node import action_node
from backend.src.agents.standard.orchestrator import build_standard_graph
from backend.src.agents.state import SharedState
from backend.src.utils.agui_models import InteractionRequest
from backend.src.utils.agui_store import agui_store
from backend.src.tools.api_mocks import execute_db_query
from backend.config.settings import settings

@pytest.fixture(autouse=True)
def clean_agui_store():
    """Clear AG-UI store before and after tests."""
    agui_store._requests.clear()
    agui_store._responses.clear()
    yield
    agui_store._requests.clear()
    agui_store._responses.clear()


@pytest.mark.asyncio
@patch("backend.src.agents.nodes.action_node.llm_call")
async def test_action_node_intercepts_write_query(mock_llm_call):
    # Mock LLM to return an INSERT tool call
    mock_llm_call.return_value = (
        '{"name": "execute_db_query", "args": {"sql_query": "INSERT INTO leaves (employee_id, leave_type, start_date, end_date) VALUES (\'EMP0001\', \'Annual\', \'2026-06-15\', \'2026-06-17\')"}}',
        0.0
    )

    state = SharedState(
        session_id="session-test-write",
        query="Apply for leave",
        messages=[],
        trace_log=[]
    )

    result = await action_node(state)

    # Action node should intercept and flag for HITL without executing
    assert result.get("hitl_needed") is True
    assert "pending_tool_call" in result.get("rl_context", {})
    assert result["rl_context"]["pending_tool_call"]["name"] == "execute_db_query"
    assert "database modification" in result.get("final_response")


@pytest.mark.asyncio
@patch("backend.src.agents.standard.orchestrator.llm_call")
async def test_standard_graph_routing_to_hitl(mock_llm_call):
    # Mock LLM to classify as action, then return INSERT tool call
    def mock_calls(agent_name, prompt, **kwargs):
        if agent_name == "triage":
            return "action", 0.0
        return (
            '{"name": "execute_db_query", "args": {"sql_query": "INSERT INTO leaves (employee_id, leave_type, start_date, end_date) VALUES (\'EMP0001\', \'Annual\', \'2026-06-15\', \'2026-06-17\')"}}',
            0.0
        )

    mock_llm_call.side_effect = mock_calls

    graph = build_standard_graph()
    state = SharedState(
        session_id="session-standard-hitl",
        query="Apply for 3 days leave starting June 15",
    )

    result = await graph.ainvoke(state)

    # Verification: Standard graph runs and ends in hitl
    assert result.get("hitl_needed") is True
    assert "pending_tool_call" in result.get("rl_context", {})
    
    # Verify a request was created in agui_store
    pending = agui_store.get_pending()
    assert len(pending) == 1
    assert pending[0].session_id == "session-standard-hitl"
    assert "pending_tool_call" in pending[0].context
    assert pending[0].context["pending_tool_call"]["name"] == "execute_db_query"


@pytest.mark.asyncio
async def test_agui_store_executes_on_approval():
    # Insert a dummy record test and see if database changes on approval
    # First get leaves count
    res_count = execute_db_query("SELECT COUNT(*) as count FROM leaves;")
    initial_count = res_count["rows"][0]["count"]

    # Add a mock pending request with an INSERT query to agui_store
    interaction_id = "HITL-TEST-WRITE"
    req = InteractionRequest(
        interaction_id=interaction_id,
        query="Test query",
        session_id="session-exec-test",
        context={
            "pending_tool_call": {
                "name": "execute_db_query",
                "args": {
                    "sql_query": "INSERT INTO leaves (employee_id, leave_type, start_date, end_date) VALUES (?, ?, ?, ?)",
                    "parameters": ["EMP0002", "Annual", "2026-06-15", "2026-06-17"]
                }
            }
        }
    )
    agui_store.add_request(req)

    # Approve the request
    success = agui_store.respond(interaction_id, "Approved by admin", {"action": "approve"})
    assert success is True

    # Verify database has the new leave record
    res_count_after = execute_db_query("SELECT COUNT(*) as count FROM leaves;")
    after_count = res_count_after["rows"][0]["count"]
    assert after_count == initial_count + 1

    # Clean up the test database insertion
    execute_db_query("DELETE FROM leaves WHERE employee_id = 'EMP0002' AND start_date = '2026-06-15';")
