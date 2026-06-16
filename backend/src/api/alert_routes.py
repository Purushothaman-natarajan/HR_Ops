from fastapi import APIRouter, Request
from pydantic import BaseModel
from backend.src.core.response import get_correlation_id, success_response, error_response
from backend.src.utils.alert_store import alert_store
from backend.src.services.scheduler import scheduler
from backend.src.services.graph_service import run_graph

router = APIRouter(prefix="/alerts", tags=["alerts"])

class SchedulerConfig(BaseModel):
    interval_seconds: int
    running: bool | None = None

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

@router.get("/scheduler")
async def get_scheduler_status(request: Request):
    correlation_id = get_correlation_id(request)
    return success_response(
        data=scheduler.get_status(),
        correlation_id=correlation_id,
    )

@router.post("/scheduler")
async def update_scheduler_config(config: SchedulerConfig, request: Request):
    correlation_id = get_correlation_id(request)
    if config.interval_seconds < 5:
        return error_response(
            message="Interval must be at least 5 seconds",
            correlation_id=correlation_id,
            status_code=400,
        )

    was_running = scheduler.is_running
    target_running = config.running if config.running is not None else was_running

    scheduler.stop()
    scheduler.interval_seconds = config.interval_seconds
    if target_running:
        scheduler.start()

    return success_response(
        data=scheduler.get_status(),
        correlation_id=correlation_id,
    )

@router.post("/scheduler/scan")
async def trigger_manual_scan(request: Request):
    """Trigger an immediate anomaly detection scan outside the scheduled cycle."""
    correlation_id = get_correlation_id(request)
    try:
        result = await run_graph("Run anomaly detection across all HR datasets", trigger="manual")
        summary = result.get("final_response", "")[:200] if result else "Scan completed."
        return success_response(
            data={"triggered": True, "result_summary": summary},
            correlation_id=correlation_id,
        )
    except Exception as e:
        return error_response(
            message=f"Scan failed: {e}",
            correlation_id=correlation_id,
            status_code=500,
        )
