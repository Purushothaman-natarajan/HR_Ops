import csv
import os
import sqlite3
import tempfile
from pathlib import Path
import pytest

# Force test database URL
os.environ["DATABASE_URL"] = "sqlite:///./backend/data/test_hr_ops.db"

from backend.config.settings import settings
from backend.scripts.load_db import load_csv


def _get_active_db_path() -> Path:
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        return Path(db_url.replace("sqlite:///", ""))
    return Path("./backend/data/test_hr_ops.db")


@pytest.fixture(scope="session", autouse=True)
def ensure_db_has_data():
    """Ensure the test database exists and has seed data before any tests run."""
    db_path = _get_active_db_path()
    needs_seed = False
    
    try:
        if not db_path.exists():
            needs_seed = True
        else:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM employees")
            count = cur.fetchone()[0]
            cur.execute("PRAGMA table_info(employees)")
            cols = [c[1] for c in cur.fetchall()]
            conn.close()
            
            expected = {"Employee_ID", "Employee_Name", "Leaves_Accrued", "Leaves_Taken",
                        "Work_Location", "Performance_Rating", "Manager_ID"}
            if count < 3 or not expected.issubset(set(cols)):
                needs_seed = True
    except Exception:
        needs_seed = True

    if needs_seed:
        # Create minimal seed data
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
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as tf:
            writer = csv.DictWriter(tf, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
            tmp_path = tf.name
        
        load_csv(Path(tmp_path), db_path)
        Path(tmp_path).unlink(missing_ok=True)
