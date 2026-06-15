"""One-time CLI script to seed the SQLite database from a CSV file.

Usage:
    python backend/scripts/seed_db.py "data/employee_records.csv"
"""

import logging
import sys

sys.path.insert(0, ".")

from backend.src.database.seed import load_csv_to_sqlite

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_db")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend/scripts/seed_db.py <path_to_csv>")
        sys.exit(1)
    csv_path = sys.argv[1]
    logger.info("Loading employees from: %s", csv_path)
    count = load_csv_to_sqlite(csv_path)
    logger.info("Done. Loaded %d employees.", count)
