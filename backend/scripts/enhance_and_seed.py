#!/usr/bin/env python
"""Ingest source CSV, generate additional HR attributes, and seed SQLite database."""

import logging
import random
import sys
from pathlib import Path
import pandas as pd
import sqlite3

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.src.core.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("scripts.enhance_and_seed")

DEFAULT_SOURCE_CSV = r"C:\Users\purus\Downloads\archive (1)\employee_records.csv"
DEFAULT_TARGET_DB = "./backend/data/hr_ops.db"

def enhance_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add leaves, work location, performance ratings, and manager IDs to employee records."""
    logger.info("Enhancing employee data frame with additional HR attributes...")
    random.seed(42)  # For reproducibility
    
    # 1. Employee_ID formatting: ensure consistency (e.g. EMP0001, EMP0002)
    # The source Employee_ID is integer: 1, 2, 3...
    df['Employee_ID'] = df['Employee_ID'].apply(lambda x: f"EMP{int(x):04d}")
    
    # 2. Add Leaves columns
    df['Leaves_Accrued'] = [random.randint(20, 30) for _ in range(len(df))]
    df['Leaves_Taken'] = [random.randint(0, 15) for _ in range(len(df))]
    
    # 3. Add Work_Location
    locations = ["New York", "Chicago", "San Francisco", "London", "Remote"]
    df['Work_Location'] = [random.choice(locations) for _ in range(len(df))]
    
    # 4. Add Performance_Rating
    ratings = [3.0, 3.5, 4.0, 4.5, 5.0]
    # Weight higher ratings slightly more, but add lower ones too
    df['Performance_Rating'] = [random.choices(ratings, weights=[10, 20, 40, 20, 10])[0] for _ in range(len(df))]
    
    # 5. Add Manager_ID
    # Choose from the first 5 employees to act as department managers
    manager_pool = df['Employee_ID'].head(5).tolist()
    df['Manager_ID'] = [random.choice(manager_pool) if eid not in manager_pool else "CEO" for eid in df['Employee_ID']]
    
    logger.info("Enhanced dataframe shape: %s", df.shape)
    return df

def seed_database(df: pd.DataFrame, db_path: Path):
    """Seed the enhanced dataframe into the SQLite employees table."""
    logger.info("Connecting to SQLite database at: %s", db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    try:
        # Save to database table 'employees'
        logger.info("Writing dataframe to 'employees' table...")
        df.to_sql("employees", conn, if_exists="replace", index=False)
        logger.info("Table 'employees' seeded successfully.")
        
        # Verify row count
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM employees;")
        count = cur.fetchone()[0]
        logger.info("Verified: employees table contains %d records.", count)
        
        # Log columns
        cur.execute("PRAGMA table_info(employees);")
        cols = [col[1] for col in cur.fetchall()]
        logger.info("Table schema: %s", cols)
        
    finally:
        conn.close()

def main():
    csv_path = DEFAULT_SOURCE_CSV
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        
    db_url = settings.database_url
    db_path = Path(DEFAULT_TARGET_DB)
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.replace("sqlite:///", ""))
        
    logger.info("Starting database enhancement & seeding pipeline")
    logger.info("Source CSV: %s", csv_path)
    logger.info("Target DB: %s", db_path)
    
    if not Path(csv_path).exists():
        logger.error("Source CSV file does not exist: %s", csv_path)
        sys.exit(1)
        
    try:
        df = pd.read_csv(csv_path)
        enhanced_df = enhance_dataframe(df)
        seed_database(enhanced_df, db_path)
        
        # Also save as a CSV artifact within the workspace
        artifact_csv = Path("./backend/data/enhanced_employee_records.csv")
        artifact_csv.parent.mkdir(parents=True, exist_ok=True)
        enhanced_df.to_csv(artifact_csv, index=False)
        logger.info("Enhanced CSV saved as artifact: %s", artifact_csv)
        
        logger.info("Seeding pipeline completed successfully.")
    except Exception as e:
        logger.exception("Ingestion pipeline failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
