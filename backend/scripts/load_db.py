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
    
    # Try to standardize Employee_ID key if present
    eid_col = None
    for col in df.columns:
        if col.lower().replace("_", "") in ["employeeid", "empid", "id"]:
            eid_col = col
            break
            
    if eid_col:
        # Standardize ID column name to Employee_ID
        df.rename(columns={eid_col: "Employee_ID"}, inplace=True)
        # Ensure employee IDs are strings
        df["Employee_ID"] = df["Employee_ID"].astype(str)
        
    # Auto-enhance with default attributes if they are missing
    import random
    random.seed(42)
    
    if "Leaves_Accrued" not in df.columns:
        logger.info("Columns 'Leaves_Accrued' missing, generating random accruals...")
        df['Leaves_Accrued'] = [random.randint(20, 30) for _ in range(len(df))]
        
    if "Leaves_Taken" not in df.columns:
        logger.info("Columns 'Leaves_Taken' missing, generating random usages...")
        df['Leaves_Taken'] = [random.randint(0, 15) for _ in range(len(df))]
        
    if "Work_Location" not in df.columns:
        logger.info("Columns 'Work_Location' missing, generating random locations...")
        locations = ["New York", "Chicago", "San Francisco", "London", "Remote"]
        df['Work_Location'] = [random.choice(locations) for _ in range(len(df))]
        
    if "Performance_Rating" not in df.columns:
        logger.info("Columns 'Performance_Rating' missing, generating random ratings...")
        df['Performance_Rating'] = [float(random.choice([3, 4, 5])) for _ in range(len(df))]
        
    if "Manager_ID" not in df.columns:
        logger.info("Column 'Manager_ID' missing, generating manager assignments...")
        emp_ids = df["Employee_ID"].tolist() if "Employee_ID" in df.columns else [str(i) for i in range(len(df))]
        manager_pool = emp_ids[:min(5, len(emp_ids))]
        df['Manager_ID'] = [random.choice(manager_pool) if eid not in manager_pool else "CEO" for eid in emp_ids]
        
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
