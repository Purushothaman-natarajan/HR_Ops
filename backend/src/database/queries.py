"""Query helpers for graph nodes — fetch employee data from SQLAlchemy ORM sessions."""


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


def query_employee(employee_id: str) -> dict | None:
    """Fetch a single employee record by ID. Returns None if not found."""
    with _get_session() as session:
        emp = session.get(Employee, employee_id)
        if emp is None:
            return None
        return {c.name: getattr(emp, c.name) for c in Employee.__table__.columns}


def query_all_employees() -> list[dict]:
    """Return all employee records (useful for anomaly detection sweeps)."""
    with _get_session() as session:
        return [{c.name: getattr(e, c.name) for c in Employee.__table__.columns}
                for e in session.query(Employee).all()]


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
        return [{c.name: getattr(r, c.name) for c in Attendance.__table__.columns} for r in rows]


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
        return [{c.name: getattr(r, c.name) for c in Payroll.__table__.columns} for r in rows]


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
        return [{c.name: getattr(r, c.name) for c in Leave.__table__.columns} for r in rows]


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
        return [{c.name: getattr(r, c.name) for c in Performance.__table__.columns} for r in rows]


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
    return emp
