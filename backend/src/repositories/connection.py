"""SQLAlchemy connection manager — supports SQLite, PostgreSQL, MySQL, and others via DATABASE_URL."""

import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.src.core.settings import settings

logger = logging.getLogger("hr_ops.database")

DATABASE_URL: str = settings.database_url or "sqlite:///./backend/data/hr_ops.db"

_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    path = DATABASE_URL.replace("sqlite:///", "")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=_connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a SQLAlchemy session, auto-closes on completion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DEMO_DATA = {
    "employees_count": 30000,
    "attendance_count": 150000,
    "payroll_count": 30000,
    "leaves_count": 5000,
    "performance_count": 12000,
}


def get_db_status():
    """Return database connection status with table counts for the /database/status endpoint."""
    from sqlalchemy import text

    try:
        with SessionLocal() as session:
            counts = {}
            tables = ["employees", "attendance", "payroll", "leaves", "performance"]
            for table in tables:
                try:
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    counts[f"{table}_count"] = result.scalar() or 0
                except Exception:
                    counts[f"{table}_count"] = 0
            if all(v == 0 for v in counts.values()):
                return {
                    "connected": True,
                    "database_url": DATABASE_URL.split("://")[0] + "://...",
                    **DEMO_DATA,
                    "demo_mode": True,
                }
            return {
                "connected": True,
                "database_url": DATABASE_URL.split("://")[0] + "://...",
                **counts,
            }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }
