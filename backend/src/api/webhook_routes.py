import logging
from fastapi import APIRouter, Request, BackgroundTasks
from backend.src.core.response import get_correlation_id, success_response, error_response
from backend.src.services.graph_service import run_graph
from backend.src.utils.alert_store import alert_store
from backend.src.memory.episodic_memory import episodic_memory

logger = logging.getLogger("hr_ops.api.webhook")
router = APIRouter(prefix="/webhook", tags=["webhook"])

@router.post("/alert")
async def system_alert(payload: dict, request: Request, background_tasks: BackgroundTasks):
    correlation_id = get_correlation_id(request)
    query = payload.get("query", "")

    if not query:
        return error_response("query is required", correlation_id=correlation_id, status_code=400)

    logger.info("Received system alert: %s", query)

    async def process_alert():
        try:
            result = await run_graph(query, trigger="system")
            alert_store.add_alert(query, "system", result)
            episodic_memory.store_incident("system", query, result.get("final_response", ""))
        except Exception as e:
            logger.error("Failed to process system alert: %s", e)

    background_tasks.add_task(process_alert)

    return success_response({"status": "processing"}, "Alert received and processing started", correlation_id=correlation_id)
