import sqlite3
from pathlib import Path

import pytest

from backend.src.guardrails.tool_validator import tool_guardrail
from backend.src.tools.api_mocks import execute_db_query, get_database_schema


from backend.config.settings import settings

def _get_active_db_path() -> Path:
    """Return the path to the active SQLite database."""
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        return Path(db_url.replace("sqlite:///", ""))
    return Path("./backend/data/test_hr_ops.db")


def test_database_schema_retrieval():
    """Verify that get_database_schema dynamically inspects the database tables and columns."""
    res = get_database_schema()
    assert res.get("success") is True
    schema = res.get("schema", {})
    assert "employees" in schema

    # Check that our enhanced columns are listed
    columns = [col["name"] for col in schema["employees"]]
    assert "Employee_ID" in columns
    assert "Employee_Name" in columns
    assert "Leaves_Accrued" in columns
    assert "Leaves_Taken" in columns
    assert "Work_Location" in columns
    assert "Performance_Rating" in columns
    assert "Manager_ID" in columns


def test_execute_db_query_read():
    """Verify that execute_db_query executes read operations correctly."""
    query = "SELECT Employee_ID, Employee_Name, Work_Location FROM employees LIMIT 3;"
    res = execute_db_query(query)
    assert res.get("success") is True
    assert res.get("type") == "read"
    assert res.get("row_count") == 3
    assert len(res.get("rows", [])) == 3
    assert "Employee_ID" in res.get("columns", [])


def test_execute_db_query_write():
    """Verify that execute_db_query executes write operations correctly and commits changes."""
    # Save original Work_Location first
    orig_res = execute_db_query("SELECT Work_Location FROM employees WHERE Employee_ID = 'EMP0001';")
    orig_location = orig_res.get("rows", [{}])[0].get("Work_Location", "Remote")

    # Update employee EMP0001
    query_update = "UPDATE employees SET Work_Location = 'Mars' WHERE Employee_ID = 'EMP0001';"
    res_update = execute_db_query(query_update)
    assert res_update.get("success") is True
    assert res_update.get("type") == "write"

    # Query to verify it was updated
    query_select = "SELECT Work_Location FROM employees WHERE Employee_ID = 'EMP0001';"
    res_select = execute_db_query(query_select)
    assert res_select.get("success") is True
    assert res_select.get("rows")[0]["Work_Location"] == "Mars"

    # Restore original value
    execute_db_query(f"UPDATE employees SET Work_Location = '{orig_location}' WHERE Employee_ID = 'EMP0001';")


def test_tool_guardrail_allows_database_tools():
    """Verify that the tool validator whitelist accepts our database tools."""
    # Allowed tool
    res_schema = tool_guardrail({"tool_name": "get_database_schema"})
    assert res_schema[0] is True

    res_query = tool_guardrail({"tool_name": "execute_db_query", "args": {"sql_query": "SELECT 1"}})
    assert res_query[0] is True

    # Blocked tool
    res_blocked = tool_guardrail({"tool_name": "drop_tables_xyz"})
    assert res_blocked[0] is False
    assert "not in the allowed list" in res_blocked[1]

def test_execute_db_query_with_parameters():
    """Verify that execute_db_query securely executes queries with parameters."""
    query = "SELECT Employee_ID, Employee_Name FROM employees WHERE Employee_Name LIKE ? LIMIT 3;"
    parameters = ["%Alice%"]
    res = execute_db_query(query, parameters)
    assert res.get("success") is True
    assert res.get("type") == "read"
    assert len(res.get("rows", [])) > 0
    assert "Alice" in res.get("rows", [])[0]["Employee_Name"]
