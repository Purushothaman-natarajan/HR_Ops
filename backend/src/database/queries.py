"""Query helpers for graph nodes — fetch employee data from SQLAlchemy ORM sessions."""

import statistics

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.src.database.connection import SessionLocal
from backend.src.database.models import (
    Attendance,
    Employee,
    Leave,
    Payroll,
    Performance,
)


def _get_session() -> Session:
    return SessionLocal()


def _row_to_dict(obj, model_cls) -> dict:
    """Convert an ORM row to a plain dict using Python attribute names."""
    mapper = sa_inspect(model_cls)
    return {attr.key: getattr(obj, attr.key) for attr in mapper.attrs}


def query_employee(employee_id: str) -> dict | None:
    """Fetch a single employee record by ID. Returns None if not found."""
    with _get_session() as session:
        emp = session.get(Employee, employee_id)
        if emp is None:
            return None
        return _row_to_dict(emp, Employee)


def query_all_employees() -> list[dict]:
    """Return all employee records (useful for anomaly detection sweeps)."""
    with _get_session() as session:
        return [_row_to_dict(e, Employee) for e in session.query(Employee).all()]


def query_employees_by_department(department: str) -> list[dict]:
    """Return all employees in a given department."""
    with _get_session() as session:
        rows = session.query(Employee).filter(Employee.department == department).all()
        return [_row_to_dict(e, Employee) for e in rows]


def query_attendance(employee_id: str, limit: int = 30) -> list[dict]:
    """Return recent attendance records for an employee."""
    with _get_session() as session:
        rows = (
            session.query(Attendance)
            .filter(Attendance.employee_id == employee_id)
            .order_by(Attendance.date.desc())
            .limit(limit)
            .all()
        )
        return [_row_to_dict(r, Attendance) for r in rows]


def query_payroll(employee_id: str, limit: int = 12) -> list[dict]:
    """Return payroll history for an employee."""
    with _get_session() as session:
        rows = (
            session.query(Payroll)
            .filter(Payroll.employee_id == employee_id)
            .order_by(Payroll.pay_period.desc())
            .limit(limit)
            .all()
        )
        return [_row_to_dict(r, Payroll) for r in rows]


def query_leaves(employee_id: str, limit: int = 10) -> list[dict]:
    """Return leave records for an employee."""
    with _get_session() as session:
        rows = (
            session.query(Leave)
            .filter(Leave.employee_id == employee_id)
            .order_by(Leave.start_date.desc())
            .limit(limit)
            .all()
        )
        return [_row_to_dict(r, Leave) for r in rows]


def query_leave_balance(employee_id: str) -> dict:
    """Return aggregated leave balance (total approved days per leave type)."""
    with _get_session() as session:
        rows = session.execute(
            text("""
                SELECT leave_type, SUM(
                    julianday(end_date) - julianday(start_date) + 1
                ) as days
                FROM leaves WHERE employee_id = :eid AND status = 'Approved'
                GROUP BY leave_type
            """),
            {"eid": employee_id},
        ).fetchall()
        return {r[0]: int(r[1]) for r in rows} if rows else {}


def query_leave_summary(employee_id: str) -> dict:
    """Return leave accrued, taken, and remaining from the Employee record directly."""
    with _get_session() as session:
        emp = session.get(Employee, employee_id)
        if emp is None:
            return {}
        accrued = emp.leaves_accrued or 0
        taken = emp.leaves_taken or 0
        return {
            "leaves_accrued": accrued,
            "leaves_taken": taken,
            "leaves_remaining": max(accrued - taken, 0),
        }


def query_performance(employee_id: str, limit: int = 5) -> list[dict]:
    """Return performance reviews for an employee."""
    with _get_session() as session:
        rows = (
            session.query(Performance)
            .filter(Performance.employee_id == employee_id)
            .order_by(Performance.review_date.desc())
            .limit(limit)
            .all()
        )
        return [_row_to_dict(r, Performance) for r in rows]


def query_employee_full(employee_id: str) -> dict | None:
    """Return a comprehensive employee profile with all related data."""
    emp = query_employee(employee_id)
    if emp is None:
        return None
    emp["attendance"] = query_attendance(employee_id)
    emp["payroll"] = query_payroll(employee_id)
    emp["leaves"] = query_leaves(employee_id)
    emp["performance"] = query_performance(employee_id)
    emp["leave_balance"] = query_leave_balance(employee_id)
    emp["leave_summary"] = query_leave_summary(employee_id)
    return emp


def query_salary_cohort_stats(department: str) -> dict:
    """Return salary mean and stdev for a department cohort (for anomaly Z-score)."""
    employees = query_employees_by_department(department)
    salaries = [e["salary"] for e in employees if e.get("salary")]
    if len(salaries) < 3:
        return {"mean": 0.0, "stdev": 1.0, "count": len(salaries)}
    return {
        "mean": statistics.mean(salaries),
        "stdev": statistics.stdev(salaries) or 1.0,
        "count": len(salaries),
    }


def query_all_payroll_current() -> list[dict]:
    """Return the most recent payroll record for every employee."""
    with _get_session() as session:
        rows = session.execute(
            text("""
                SELECT p.*
                FROM payroll p
                INNER JOIN (
                    SELECT employee_id, MAX(pay_period) as max_period
                    FROM payroll GROUP BY employee_id
                ) latest ON p.employee_id = latest.employee_id
                         AND p.pay_period  = latest.max_period
            """)
        ).fetchall()
        keys = ["id", "employee_id", "pay_period", "gross_pay", "deductions", "net_pay", "payment_date"]
        return [dict(zip(keys, r)) for r in rows]
