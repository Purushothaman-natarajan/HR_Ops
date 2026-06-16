#!/usr/bin/env python
"""Load any CSV or SQLite database file into the HR Ops engine at runtime.

Usage:
    python backend/scripts/load_db.py <path_to_csv_or_db>
"""

import logging
import os
import shutil
import sys
from pathlib import Path
import pandas as pd
import sqlite3

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("scripts.load_db")

DEFAULT_TARGET_DB = "./backend/data/hr_ops.db"

def load_csv(csv_path: Path, db_path: Path):
    """Load a CSV file, automatically enhance it if standard columns are missing, and write it to SQLite."""
    logger.info("Reading input CSV from: %s", csv_path)
    df = pd.read_csv(csv_path)
    
    # Standardise column mappings (case-insensitive, remove underscores)
    col_map = {c.lower().replace("_", ""): c for c in df.columns}
    
    # 1. Employee_ID
    eid_col = None
    for k in ["employeeid", "empid", "id"]:
        if k in col_map:
            eid_col = col_map[k]
            break
    if eid_col:
        df.rename(columns={eid_col: "Employee_ID"}, inplace=True)
    elif "employee_id" in df.columns:
        df.rename(columns={"employee_id": "Employee_ID"}, inplace=True)
    
    if "Employee_ID" not in df.columns:
        logger.info("Column 'Employee_ID' missing, generating sequential IDs...")
        df["Employee_ID"] = [f"EMP{i+1:04d}" for i in range(len(df))]
        
    # 2. Employee_Name
    ename_col = None
    for k in ["employeename", "name"]:
        if k in col_map:
            ename_col = col_map[k]
            break
    if ename_col:
        df.rename(columns={ename_col: "Employee_Name"}, inplace=True)
        
    if "Employee_Name" not in df.columns:
        logger.info("Column 'Employee_Name' missing, generating names (with John Doe first)...")
        first_names = ["John", "Jane", "Alice", "Bob", "Charlie", "David", "Emma", "Frank", "Grace", "Henry", "Ivy", "Jack", "Kate", "Leo", "Mia", "Noah", "Olivia", "Peter", "Ryan", "Sarah"]
        last_names = ["Smith", "Doe", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson", "Martinez", "Anderson", "Taylor", "Thomas", "Hernandez", "Moore", "Martin", "Jackson", "Thompson"]
        names = []
        for i in range(len(df)):
            if i == 0:
                names.append("John Doe")
            elif i == 1:
                names.append("Alice Smith")
            elif i == 2:
                names.append("Bob Johnson")
            else:
                fn = first_names[(i * 7) % len(first_names)]
                ln = last_names[(i * 13) % len(last_names)]
                if fn == "John" and ln == "Doe":
                    ln = "Miller"
                names.append(f"{fn} {ln}")
        df["Employee_Name"] = names

    # Re-calculate col_map after modifications
    col_map = {c.lower().replace("_", ""): c for c in df.columns}

    # 3. Age
    if "age" in col_map and col_map["age"] != "Age":
        df.rename(columns={col_map["age"]: "Age"}, inplace=True)
    elif "Age" not in df.columns:
        import random
        random.seed(42)
        df["Age"] = [random.randint(22, 60) for _ in range(len(df))]

    # 4. Country
    country_col = None
    for k in ["country", "nation"]:
        if k in col_map:
            country_col = col_map[k]
            break
    if country_col:
        df.rename(columns={country_col: "Country"}, inplace=True)
    elif "Country" not in df.columns:
        df["Country"] = "USA"

    # 5. Department
    dept_col = None
    for k in ["department", "dept"]:
        if k in col_map:
            dept_col = col_map[k]
            break
    if dept_col:
        df.rename(columns={dept_col: "Department"}, inplace=True)
    elif "Department" not in df.columns:
        departments = ["Engineering", "HR", "Sales", "Marketing", "Finance"]
        df["Department"] = [departments[i % len(departments)] for i in range(len(df))]

    # 6. Position
    pos_col = None
    for k in ["position", "role", "title"]:
        if k in col_map:
            pos_col = col_map[k]
            break
    if pos_col:
        df.rename(columns={pos_col: "Position"}, inplace=True)
    elif "Position" not in df.columns:
        positions = ["Software Engineer", "HR Specialist", "Account Executive", "Marketing Manager", "Financial Analyst"]
        df["Position"] = [positions[i % len(positions)] for i in range(len(df))]

    # 7. Salary
    salary_col = None
    for k in ["salary", "pay", "compensation"]:
        if k in col_map:
            salary_col = col_map[k]
            break
    if salary_col:
        df.rename(columns={salary_col: "Salary"}, inplace=True)
    elif "Salary" not in df.columns:
        import random
        random.seed(42)
        df["Salary"] = [float(random.randint(50, 150) * 1000) for _ in range(len(df))]

    # 8. Joining_Date
    joining_col = None
    for k in ["joiningdate", "startdate", "hiredate"]:
        if k in col_map:
            joining_col = col_map[k]
            break
    if joining_col:
        df.rename(columns={joining_col: "Joining_Date"}, inplace=True)
    elif "Joining_Date" not in df.columns:
        jyear_col = None
        for k in ["joiningyear", "year"]:
            if k in col_map:
                jyear_col = col_map[k]
                break
        if jyear_col:
            df["Joining_Date"] = df[jyear_col].apply(lambda yr: f"{int(yr)}-06-15" if pd.notna(yr) else "2024-06-15")
        else:
            df["Joining_Date"] = "2024-06-15"

    # 9. Leaves_Accrued
    leaves_acc_col = None
    for k in ["leavesaccrued", "leavesaccrual"]:
        if k in col_map:
            leaves_acc_col = col_map[k]
            break
    if leaves_acc_col:
        df.rename(columns={leaves_acc_col: "Leaves_Accrued"}, inplace=True)
    elif "Leaves_Accrued" not in df.columns:
        import random
        random.seed(42)
        df["Leaves_Accrued"] = [random.randint(20, 30) for _ in range(len(df))]

    # 10. Leaves_Taken
    leaves_taken_col = None
    for k in ["leavestaken", "leavesused"]:
        if k in col_map:
            leaves_taken_col = col_map[k]
            break
    if leaves_taken_col:
        df.rename(columns={leaves_taken_col: "Leaves_Taken"}, inplace=True)
    elif "Leaves_Taken" not in df.columns:
        import random
        random.seed(42)
        df["Leaves_Taken"] = [random.randint(0, 15) for _ in range(len(df))]

    # 11. Work_Location
    loc_col = None
    for k in ["worklocation", "location", "office"]:
        if k in col_map:
            loc_col = col_map[k]
            break
    if loc_col:
        df.rename(columns={loc_col: "Work_Location"}, inplace=True)
    elif "Work_Location" not in df.columns:
        city_col = col_map.get("city")
        if city_col:
            df["Work_Location"] = df[city_col]
        else:
            locations = ["New York", "Chicago", "San Francisco", "London", "Remote"]
            import random
            random.seed(42)
            df["Work_Location"] = [random.choice(locations) for _ in range(len(df))]

    # 12. Performance_Rating
    perf_col = None
    for k in ["performancerating", "rating"]:
        if k in col_map:
            perf_col = col_map[k]
            break
    if perf_col:
        df.rename(columns={perf_col: "Performance_Rating"}, inplace=True)
    elif "Performance_Rating" not in df.columns:
        import random
        random.seed(42)
        df["Performance_Rating"] = [float(random.choice([3, 4, 5])) for _ in range(len(df))]

    # 13. Manager_ID
    mgr_col = None
    for k in ["managerid", "manager"]:
        if k in col_map:
            mgr_col = col_map[k]
            break
    if mgr_col:
        df.rename(columns={mgr_col: "Manager_ID"}, inplace=True)
    elif "Manager_ID" not in df.columns:
        emp_ids = df["Employee_ID"].tolist()
        manager_pool = emp_ids[:min(5, len(emp_ids))]
        import random
        random.seed(42)
        df["Manager_ID"] = [random.choice(manager_pool) if eid not in manager_pool else "CEO" for eid in emp_ids]
            
    # Ensure Employee_ID is string
    if "Employee_ID" in df.columns:
        df["Employee_ID"] = df["Employee_ID"].astype(str)



        
    # Seed into SQL database
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        logger.info("Writing CSV table to database...")
        df.to_sql("employees", conn, if_exists="replace", index=False)
        
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM employees;")
        count = cur.fetchone()[0]
        cur.execute("PRAGMA table_info(employees);")
        cols = [col[1] for col in cur.fetchall()]
        
        logger.info("Successfully loaded CSV schema with %d records into SQLite.", count)
        logger.info("Discovered columns: %s", cols)
    finally:
        conn.close()

def load_sqlite_db(src_db_path: Path, target_db_path: Path):
    """Copy an arbitrary SQLite database file to the configured database location."""
    logger.info("Loading SQLite database from: %s", src_db_path)
    if not os.path.exists(src_db_path):
        logger.error("Source database file does not exist: %s", src_db_path)
        sys.exit(1)
        
    target_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Verify the database can be connected to and inspect tables
    conn = sqlite3.connect(str(src_db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        logger.info("Found tables in source database: %s", tables)
    except Exception as e:
        logger.error("Failed to read tables from source SQLite database: %s", e)
        sys.exit(1)
    finally:
        conn.close()
        
    # Copy file over
    logger.info("Copying database file to %s...", target_db_path)
    shutil.copyfile(str(src_db_path), str(target_db_path))
    logger.info("Database replacement complete.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python backend/scripts/load_db.py <path_to_csv_or_db>")
        sys.exit(1)
        
    src_path = Path(sys.argv[1])
    if not src_path.exists():
        logger.error("File does not exist: %s", src_path)
        sys.exit(1)
        
    db_url = settings.database_url
    target_db_path = Path(DEFAULT_TARGET_DB)
    if db_url.startswith("sqlite:///"):
        target_db_path = Path(db_url.replace("sqlite:///", ""))
        
    suffix = src_path.suffix.lower()
    if suffix == ".csv":
        load_csv(src_path, target_db_path)
    elif suffix in [".db", ".sqlite", ".sqlite3"]:
        load_sqlite_db(src_path, target_db_path)
    else:
        logger.error("Unsupported file format '%s'. Must be .csv or .db SQLite file.", suffix)
        sys.exit(1)

if __name__ == "__main__":
    main()
