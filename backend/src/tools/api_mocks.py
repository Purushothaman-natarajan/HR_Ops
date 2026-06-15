"""Mock HRIS API tools (lookup, modify, escalate) with in-memory and SQLite-backed employee data."""

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.src.database.queries import query_employee as _db_query_employee

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

        from backend.src.database.connection import SessionLocal
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
    """Create an escalation ticket for human review and return the ticket ID and status."""
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    logger.info("escalate_to_human: ticket=%s emp=%s reason=%s", ticket_id, employee_id, reason)
    return {"ticket_id": ticket_id, "status": "escalated", "timestamp": datetime.now(timezone.utc).isoformat()}


TOOL_REGISTRY: dict[str, Any] = {  # Maps tool names to their implementation functions
    "lookup_employee": lookup_employee,
    "modify_record": modify_record,
    "escalate_to_human": escalate_to_human,
}


def execute_tool(name: str, **kwargs) -> dict:
    """Dispatch a tool call by name, passing keyword arguments, and return the result wrapped in a result envelope."""
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        raise ValueError(f"Unknown tool: {name}")
    result = fn(**kwargs)
    return {"tool": name, "result": result}
