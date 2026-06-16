from fastapi import APIRouter, Request
from backend.src.core.response import get_correlation_id, success_response, error_response
from backend.src.utils.alert_store import alert_store

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("/")
async def list_alerts(request: Request):
    correlation_id = get_correlation_id(request)
    alerts = alert_store.get_alerts()
    return success_response(data={"alerts": alerts}, correlation_id=correlation_id)

@router.post("/{alert_id}/read")
async def mark_alert_read(alert_id: str, request: Request):
    correlation_id = get_correlation_id(request)
    success = alert_store.mark_read(alert_id)
    if not success:
        return error_response(message="Alert not found", correlation_id=correlation_id, status_code=404)
    return success_response(data={"id": alert_id, "status": "read"}, correlation_id=correlation_id)
