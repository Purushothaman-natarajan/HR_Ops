"""Full database seeder — loads employee CSV into all ORM tables.

Run:
    python -m backend.scripts.seed_full_database

Generates realistic attendance, payroll, leave, and performance records
for every employee row in the CSV. Idempotent: clears existing rows first.
"""

import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import text

# ── project root must be in sys.path ─────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.database.connection import Base, SessionLocal, engine  # noqa: E402
from backend.src.database.models import (  # noqa: E402
    Attendance,
    Employee,
    Leave,
    Payroll,
    Performance,
)

CSV_PATH = PROJECT_ROOT / "backend" / "data" / "enhanced_employee_records.csv"

LEAVE_TYPES = ["Annual", "Sick", "Casual", "Maternity", "Paternity", "Unpaid"]
ATTENDANCE_STATUSES = ["Present", "Absent", "Late", "Work from Home", "On Leave"]
DEPARTMENTS = ["HR", "Engineering", "Finance", "Marketing", "Operations", "Legal", "Sales"]

random.seed(42)


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))


def _generate_attendance(employee_id: str, joining_date: date) -> list[dict]:
    """Generate ~90 days of attendance records from a random window."""
    records = []
    start = max(joining_date, date(2024, 1, 1))
    end = date(2025, 12, 31)
    if start >= end:
        return records
    current = start
    days_generated = 0
    while current <= end and days_generated < 90:
        if current.weekday() < 5:  # Mon–Fri
            # 85 % present, 5 % absent, 5 % late, 5 % WFH
            roll = random.random()
            if roll < 0.85:
                status = "Present"
                hours = round(random.uniform(7.5, 9.5), 2)
            elif roll < 0.90:
                status = "Absent"
                hours = 0.0
            elif roll < 0.95:
                status = "Late"
                hours = round(random.uniform(4, 7), 2)
            else:
                status = "Work from Home"
                hours = round(random.uniform(7.0, 9.0), 2)
            records.append({
                "employee_id": employee_id,
                "date": current.isoformat(),
                "status": status,
                "hours_worked": hours,
            })
            days_generated += 1
        current += timedelta(days=1)
    return records


def _generate_payroll(employee_id: str, salary: float) -> list[dict]:
    """Generate 12 monthly payroll records."""
    records = []
    base_monthly = salary / 12
    for i in range(12):
        month_offset = i
        pay_date = date(2025, 1, 1) + timedelta(days=month_offset * 30)
        period_str = pay_date.strftime("%Y-%m")
        gross = round(base_monthly * random.uniform(0.97, 1.05), 2)
        deductions = round(gross * random.uniform(0.08, 0.18), 2)
        records.append({
            "employee_id": employee_id,
            "pay_period": period_str,
            "gross_pay": gross,
            "deductions": deductions,
            "net_pay": round(gross - deductions, 2),
            "payment_date": pay_date.isoformat(),
        })
    return records


def _generate_leaves(employee_id: str, leaves_taken: int) -> list[dict]:
    """Generate leave records totalling approximately leaves_taken days."""
    records = []
    remaining = max(int(leaves_taken), 0)
    attempts = 0
    while remaining > 0 and attempts < 20:
        attempts += 1
        leave_days = random.randint(1, min(remaining, 7))
        start = _random_date(date(2025, 1, 1), date(2025, 11, 30))
        end = start + timedelta(days=leave_days - 1)
        status = random.choices(["Approved", "Rejected", "Pending"], weights=[0.75, 0.10, 0.15])[0]
        records.append({
            "employee_id": employee_id,
            "leave_type": random.choice(LEAVE_TYPES),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "status": status,
            "reason": random.choice([
                "Medical appointment", "Family event", "Personal work",
                "Vacation", "Home emergency", "Religious holiday", "",
            ]),
        })
        if status == "Approved":
            remaining -= leave_days
    return records


def _generate_performance(employee_id: str, base_rating: float) -> list[dict]:
    """Generate 3 annual performance reviews with slight rating variation."""
    records = []
    for year in [2023, 2024, 2025]:
        rating = max(1.0, min(5.0, round(base_rating + random.uniform(-0.5, 0.5), 1)))
        records.append({
            "employee_id": employee_id,
            "review_date": f"{year}-12-15",
            "rating": rating,
            "comments": random.choice([
                "Meets expectations consistently.",
                "Exceeds targets, strong contributor.",
                "Needs improvement in time management.",
                "Outstanding performance this cycle.",
                "Good teamwork, average deliverables.",
                "Below expectations, improvement plan in progress.",
            ]),
            "reviewer": "System",
        })
    return records


def seed(limit: int | None = None) -> None:
    """Seed the database from CSV. Pass limit to seed only a subset."""
    # Recreate all tables (drop if exist)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    df = pd.read_csv(CSV_PATH)
    if limit:
        df = df.head(limit)

    print(f"Seeding {len(df)} employees …")

    with SessionLocal() as session:
        for _, row in df.iterrows():
            try:
                joining_date = date.fromisoformat(str(row["Joining_Date"]))
            except (ValueError, TypeError):
                joining_date = date(2020, 1, 1)

            emp = Employee(
                employee_id=str(row["Employee_ID"]),
                name=str(row["Employee_Name"]),
                age=int(row["Age"]),
                country=str(row["Country"]),
                department=str(row["Department"]),
                position=str(row["Position"]),
                salary=float(row["Salary"]),
                joining_date=str(row["Joining_Date"]),
                leaves_accrued=int(row["Leaves_Accrued"]),
                leaves_taken=int(row["Leaves_Taken"]),
                work_location=str(row["Work_Location"]),
                performance_rating=float(row["Performance_Rating"]),
                manager_id=str(row["Manager_ID"]),
            )
            session.add(emp)

            for rec in _generate_attendance(emp.employee_id, joining_date):
                session.add(Attendance(**rec))
            for rec in _generate_payroll(emp.employee_id, emp.salary):
                session.add(Payroll(**rec))
            for rec in _generate_leaves(emp.employee_id, emp.leaves_taken):
                session.add(Leave(**rec))
            for rec in _generate_performance(emp.employee_id, emp.performance_rating):
                session.add(Performance(**rec))

        session.commit()

    # Verify
    with SessionLocal() as session:
        counts = {}
        for table in ["employees", "attendance", "payroll", "leaves", "performance"]:
            r = session.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            counts[table] = r
    print("[OK] Seed complete. Row counts:")
    for t, c in counts.items():
        print(f"  {t}: {c:,}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed HR Ops database from CSV")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max employees to seed (default: all)")
    args = parser.parse_args()
    seed(limit=args.limit)
