import sqlite3
from pathlib import Path

import pytest

from backend.src.guardrails.tool_validator import tool_guardrail
from backend.src.tools.api_mocks import execute_db_query, get_database_schema


def _get_active_db_path() -> Path:
    """Return the path to the active SQLite database."""
    return Path("./backend/data/hr_ops.db")


@pytest.fixture(autouse=True)
def ensure_db_has_data():
    """Ensure the database has at least 3 rows with the expected schema before each test."""
    db_path = _get_active_db_path()
    # Check if existing DB is sufficient
    needs_seed = False
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM employees")
        count = cur.fetchone()[0]
        cur.execute("PRAGMA table_info(employees)")
        cols = [c[1] for c in cur.fetchall()]
        conn.close()
        # We need at least 3 rows and all expected columns
        expected = {"Employee_ID", "Employee_Name", "Leaves_Accrued", "Leaves_Taken",
                    "Work_Location", "Performance_Rating", "Manager_ID"}
        if count < 3 or not expected.issubset(set(cols)):
            needs_seed = True
    except Exception:
        needs_seed = True

    if needs_seed:
        # Create minimal seed data using load_csv
        import csv
        import tempfile

        from backend.scripts.load_db import load_csv
        rows = [
            {"Employee_ID": "EMP0001", "Employee_Name": "Alice Chen", "Age": 30, "Country": "USA",
             "Department": "Engineering", "Position": "Engineer", "Salary": 80000, "Joining_Date": "2020-01-01"},
            {"Employee_ID": "EMP0002", "Employee_Name": "Bob Smith", "Age": 35, "Country": "UK",
             "Department": "HR", "Position": "Manager", "Salary": 90000, "Joining_Date": "2019-06-01"},
            {"Employee_ID": "EMP0003", "Employee_Name": "Carol Davis", "Age": 28, "Country": "USA",
             "Department": "Finance", "Position": "Analyst", "Salary": 70000, "Joining_Date": "2021-03-15"},
            {"Employee_ID": "EMP0004", "Employee_Name": "Dave Wilson", "Age": 42, "Country": "India",
             "Department": "Operations", "Position": "Director", "Salary": 110000, "Joining_Date": "2017-01-10"},
            {"Employee_ID": "EMP0005", "Employee_Name": "Eve Martinez", "Age": 31, "Country": "Spain",
             "Department": "Marketing", "Position": "Specialist", "Salary": 65000, "Joining_Date": "2022-07-20"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as tf:
            writer = csv.DictWriter(tf, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
            tmp_path = tf.name
        load_csv(Path(tmp_path), db_path)
        Path(tmp_path).unlink(missing_ok=True)
    yield


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
