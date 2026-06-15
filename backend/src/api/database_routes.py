"""REST endpoints for SQLite database status monitoring."""

import logging

from fastapi import APIRouter, Request

from backend.src.core.response import get_correlation_id, success_response
from backend.src.database.connection import get_db_status

logger = logging.getLogger("hr_ops.database_routes")
router = APIRouter(prefix="/database", tags=["database"])


@router.get("/status")
async def api_database_status(request: Request):
    """Return SQLite database connection status, table counts, and metadata."""
    correlation_id = get_correlation_id(request)
    status = get_db_status()
    return success_response(data=status, correlation_id=correlation_id)
