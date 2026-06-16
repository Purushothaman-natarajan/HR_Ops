"""Mock HRIS API tools (lookup, modify, escalate) with in-memory and SQLite-backed employee data."""

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.src.repositories.queries import (
    query_employee as _db_query_employee,
    query_employee_full as _db_query_employee_full,
)

logger = logging.getLogger("hr_ops.tools")

_EMPLOYEES: dict[str, dict] = {}
_DB_LOADED: bool = False


def _db_has_data() -> bool:
    """Check if the SQLite employees table has records."""
    global _DB_LOADED
    if _DB_LOADED:
        return True
    try:
        from sqlalchemy import text

        from backend.src.repositories.connection import SessionLocal
        with SessionLocal() as session:
            result = session.execute(text("SELECT COUNT(*) FROM employees"))
            count = result.scalar()
            return (count or 0) > 0
    except Exception:
        return False


def _try_db_lookup(employee_id: str) -> dict | None:
    """Attempt to load an employee from SQLite. Returns None if unavailable or not found."""
    try:
        emp = _db_query_employee(employee_id)
        if emp is not None:
            emp["compliance_status"] = "compliant"
            return emp
    except Exception:
        pass
    return None


def load_employees_from_csv(path: str | None = None):
    """Load employee records from a CSV file, or fall back to generated sample data if no path is given."""
    global _EMPLOYEES
    if path:
        import csv

        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = row.get("employee_id", str(uuid.uuid4())[:8])
                _EMPLOYEES[eid] = {
                    "employee_id": eid,
                    "name": row.get("name", "Unknown"),
                    "department": row.get("department", "General"),
                    "salary": float(row.get("salary", 0) or 0),
                    "leave_balance": int(row.get("leave_balance", 0) or 0),
                    "compliance_status": row.get("compliance_status", "compliant"),
                }
    else:
        _EMPLOYEES = _generate_sample_employees()


def _generate_sample_employees() -> dict[str, dict]:
    """Generate 20 randomised employee records for development / testing use."""
    sample = {}
    names = ["Alice Chen", "Bob Smith", "Carol Davis", "Dave Wilson", "Eve Martinez"]
    depts = ["Engineering", "HR", "Finance", "Marketing", "Operations"]
    for i in range(20):
        eid = f"EMP{i+1:04d}"
        sample[eid] = {
            "employee_id": eid,
            "name": random.choice(names),
            "department": random.choice(depts),
            "salary": round(random.uniform(40000, 150000), 2),
            "leave_balance": random.randint(0, 30),
            "compliance_status": random.choice(["compliant", "compliant", "compliant", "flagged"]),
        }
    return sample


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def lookup_employee(employee_id: str) -> dict:
    """Look up an employee record by ID. Tries SQLite first (advanced mode), falls back to in-memory store."""
    if _db_has_data():
        result = _try_db_lookup(employee_id)
        if result is not None:
            logger.info("lookup_employee (db): found %s", employee_id)
            return result
    if employee_id in _EMPLOYEES:
        logger.info("lookup_employee (memory): found %s", employee_id)
        return _EMPLOYEES[employee_id]
    raise ValueError(f"Employee {employee_id} not found")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def modify_record(employee_id: str, field: str, value: Any) -> dict:
    """Update a single field on an employee record in the in-memory store. Raises ValueError if employee or field is unknown."""
    if employee_id not in _EMPLOYEES:
        raise ValueError(f"Employee {employee_id} not found")
    if field not in _EMPLOYEES[employee_id]:
        raise ValueError(f"Field '{field}' not recognized")
    _EMPLOYEES[employee_id][field] = value
    logger.info("modify_record: %s.%s = %s", employee_id, field, value)
    return {"success": True, "message": f"Updated {field} for {employee_id}"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def escalate_to_human(employee_id: str, reason: str, context: dict | None = None) -> dict:
    """Create an escalation ticket for human review, register in AGUI store, and return the ticket ID and status."""
    from backend.src.domain.agui import InteractionRequest
    from backend.src.utils.agui_store import agui_store

    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    session_id = (context or {}).get("session_id", "")
    logger.info("escalate_to_human: ticket=%s emp=%s reason=%s session=%s", ticket_id, employee_id, reason, session_id)

    req = InteractionRequest(
        interaction_id=ticket_id,
        query=f"[Employee: {employee_id}] {reason}",
        context=context or {},
        assigned_role="hr_manager",
        session_id=session_id,
    )
    agui_store.add_request(req)

    return {"ticket_id": ticket_id, "status": "escalated", "timestamp": datetime.now(timezone.utc).isoformat()}


def get_database_schema(db_name: str = "hr_ops") -> dict:
    """Dynamically query the active SQLite database schema to inspect tables and columns.
    
    Allows the agent to understand the database structure dynamically without hardcoded schemas.
    """
    import sqlite3
    from backend.src.core.settings import settings
    
    # Resolve DB file path from settings
    db_url = settings.database_url
    db_path = "./backend/data/hr_ops.db"
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Get list of all tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cur.fetchall()]
        
        schema = {}
        for table in tables:
            # Query column details
            cur.execute(f"PRAGMA table_info({table});")
            cols = cur.fetchall()
            schema[table] = [
                {
                    "cid": col[0],
                    "name": col[1],
                    "type": col[2],
                    "notnull": bool(col[3]),
                    "dflt_value": col[4],
                    "pk": bool(col[5])
                }
                for col in cols
            ]
        conn.close()
        return {"success": True, "schema": schema}
    except Exception as e:
        logger.exception("Failed to fetch database schema")
        return {"success": False, "error": str(e)}


def search_employee_by_name(name: str, limit: int = 10) -> dict:
    """Search employees by partial name match (case-insensitive LIKE).

    Returns a list of matching employee profiles with their leave summary
    and most recent performance rating.
    """
    import sqlite3
    from backend.src.core.settings import settings

    db_url = settings.database_url
    db_path = "./backend/data/hr_ops.db"
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM employees WHERE Employee_Name LIKE ? LIMIT ?",
            (f"%{name}%", limit),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()

        if not rows:
            return {"success": True, "found": False, "message": f"No employees found matching '{name}'."}

        # Enrich with leave balance and latest performance rating
        enriched = []
        for row in rows:
            eid = row.get("Employee_ID")
            profile = dict(row)
            try:
                full = _db_query_employee_full(eid)
                if full:
                    ls = full.get("leave_summary", {})
                    profile["leaves_remaining"] = ls.get("leaves_remaining", "N/A")
                    perf = full.get("performance", [])
                    if perf:
                        profile["latest_performance_rating"] = perf[0].get("rating", "N/A")
                        profile["performance_review_date"] = perf[0].get("review_date", "N/A")
            except Exception:
                pass
            enriched.append(profile)

        return {
            "success": True,
            "found": True,
            "count": len(enriched),
            "employees": enriched,
        }
    except Exception as e:
        logger.exception("search_employee_by_name failed: %s", e)
        return {"success": False, "error": str(e)}


def execute_db_query(sql_query: str, parameters: list | dict | None = None, db_name: str = "hr_ops") -> dict:
    """Execute an arbitrary raw SQL query against the active database.
    
    Supports both read (SELECT) and write (UPDATE, INSERT, DELETE) statements.
    For write operations, performs connection commits.
    """
    import sqlite3
    from backend.src.core.settings import settings
    
    db_url = settings.database_url
    db_path = "./backend/data/hr_ops.db"
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Determine if statement is write or read
        query_strip = sql_query.strip().upper()
        is_write = any(query_strip.startswith(kw) for kw in ["UPDATE", "INSERT", "DELETE", "CREATE", "DROP", "ALTER", "REPLACE"])
        
        if parameters:
            cur.execute(sql_query, parameters)
        else:
            cur.execute(sql_query)
        
        if is_write:
            conn.commit()
            rows_affected = cur.rowcount
            conn.close()
            return {
                "success": True,
                "type": "write",
                "rows_affected": rows_affected,
                "message": f"Successfully executed write query. Rows affected: {rows_affected}."
            }
        else:
            # SELECT or read query
            cols = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
            results = [dict(zip(cols, row)) for row in rows]
            conn.close()
            # Limit results size for model prompt
            return {
                "success": True,
                "type": "read",
                "rows": results[:100],  # Return up to 100 rows
                "columns": cols,
                "row_count": len(results)
            }
    except Exception as e:
        logger.exception("Failed to execute database query: %s", sql_query)
        return {"success": False, "error": str(e)}


TOOL_REGISTRY: dict[str, Any] = {  # Maps tool names to their implementation functions
    "lookup_employee": lookup_employee,
    "search_employee_by_name": search_employee_by_name,
    "modify_record": modify_record,
    "escalate_to_human": escalate_to_human,
    "get_database_schema": get_database_schema,
    "execute_db_query": execute_db_query,
}


def execute_tool(tool_name: str, **kwargs) -> dict:
    """Dispatch a tool call by name, passing keyword arguments, and return the result wrapped in a result envelope."""
    fn = TOOL_REGISTRY.get(tool_name)
    if not fn:
        raise ValueError(f"Unknown tool: {tool_name}")
    result = fn(**kwargs)
    return {"tool": tool_name, "result": result}
