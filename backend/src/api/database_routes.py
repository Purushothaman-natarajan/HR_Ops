"""REST endpoints for SQLite database status monitoring and runtime loading."""

import logging
import shutil
from pathlib import Path
from fastapi import APIRouter, Request, UploadFile, File

from backend.src.core.response import get_correlation_id, success_response, error_response
from backend.src.database.connection import get_db_status
from backend.scripts.load_db import load_csv, load_sqlite_db
from backend.config.settings import settings

logger = logging.getLogger("hr_ops.database_routes")
router = APIRouter(prefix="/database", tags=["database"])


@router.get("/status")
async def api_database_status(request: Request):
    """Return SQLite database connection status, table counts, and metadata."""
    correlation_id = get_correlation_id(request)
    status = get_db_status()
    return success_response(data=status, correlation_id=correlation_id)


@router.post("/upload")
async def api_upload_database(request: Request, file: UploadFile = File(...)):
    """Upload a CSV or SQLite DB file to replace or enhance the active database."""
    correlation_id = get_correlation_id(request)
    filename = file.filename
    if not filename:
        return error_response(
            message="No filename provided",
            correlation_id=correlation_id,
            status_code=400,
        )

    ext = Path(filename).suffix.lower()
    if ext not in [".csv", ".db", ".sqlite", ".sqlite3"]:
        return error_response(
            message="Unsupported file format. Must be .csv or .db SQLite file.",
            correlation_id=correlation_id,
            status_code=400,
        )

    db_url = settings.database_url
    target_db_path = Path("./backend/data/hr_ops.db")
    if db_url.startswith("sqlite:///"):
        target_db_path = Path(db_url.replace("sqlite:///", ""))

    # Save to a temp location to run the ingestion helper
    temp_dir = Path("./backend/data/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = temp_dir / filename

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if ext == ".csv":
            load_csv(temp_file_path, target_db_path)
        else:
            load_sqlite_db(temp_file_path, target_db_path)

        # Force clear of semantic cache so old responses matching changed databases aren't used
        from backend.src.memory.cache import semantic_cache
        semantic_cache.clear()

        # Fetch status to return
        status = get_db_status()
        return success_response(
            data={"filename": filename, "message": "Database uploaded and loaded successfully.", "status": status},
            correlation_id=correlation_id
        )
    except Exception as e:
        logger.exception("Failed to load uploaded database: %s", filename)
        return error_response(
            message=f"Failed to ingest database file: {str(e)}",
            correlation_id=correlation_id,
            status_code=500
        )
    finally:
        if temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception:
                pass

