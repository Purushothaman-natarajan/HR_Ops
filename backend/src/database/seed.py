"""CSV loader — one-time offline seed script for the SQLite database via SQLAlchemy."""

import csv
import logging

from backend.src.database.connection import Base, SessionLocal, engine
from backend.src.database.models import ALL_MODELS

logger = logging.getLogger("hr_ops.database.seed")


def load_csv_to_sqlite(csv_path: str) -> int:
    """Load employee records from CSV into the employees table. Returns count of loaded rows."""
    from backend.src.database.models import Employee

    Base.metadata.create_all(bind=engine)
    count = 0
    with SessionLocal() as session:
        batch = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = row.get("Employee_ID", "").strip()
                if not eid:
                    continue
                existing = session.get(Employee, eid)
                if existing:
                    continue
                batch.append(
                    Employee(
                        employee_id=eid,
                        name=row.get("Employee_Name", "Unknown").strip(),
                        age=int(row.get("Age", 0) or 0),
                        country=row.get("Country", "").strip(),
                        department=row.get("Department", "General").strip(),
                        position=row.get("Position", "Staff").strip(),
                        salary=float(row.get("Salary", 0) or 0),
                        joining_date=row.get("Joining_Date", "").strip(),
                    )
                )
                count += 1
                if count % 5000 == 0:
                    session.add_all(batch)
                    session.commit()
                    batch = []
                    logger.info("Loaded %d employees...", count)
        if batch:
            session.add_all(batch)
            session.commit()
    logger.info("Loaded %d employee records from CSV", count)
    return count
