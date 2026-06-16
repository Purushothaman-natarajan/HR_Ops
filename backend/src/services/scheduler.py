import asyncio
import logging
from datetime import datetime, timezone

from backend.src.services.graph_service import run_graph
from backend.src.utils.alert_store import alert_store
from backend.src.memory.episodic_memory import episodic_memory

logger = logging.getLogger("hr_ops.scheduler")


class AnomalyScheduler:
    """Background scheduler that periodically triggers the anomaly detection pipeline.

    Tracks run count, last run time, and last error for observability.
    The scheduler task is created inside the FastAPI lifespan so it always
    has a running event loop.
    Also handles checking and resolving expired HITL requests in a recurring background task.
    """

    def __init__(self, interval_seconds: int = 60 * 60):  # 1 hour default
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._hitl_task: asyncio.Task | None = None
        self.run_count: int = 0
        self.last_run_at: str | None = None
        self.last_error: str | None = None

    async def _run_scheduled_anomaly_detection(self):
        while True:
            try:
                logger.info("Running scheduled anomaly detection scan (run #%d)", self.run_count + 1)
                query = "Run anomaly detection across all HR datasets"
                result = await run_graph(query, trigger="scheduled")
                self.run_count += 1
                self.last_run_at = datetime.now(timezone.utc).isoformat()
                self.last_error = None
                alert_store.add_alert(query, "scheduled", result)
                episodic_memory.store_incident(
                    "scheduled", query, result.get("final_response", "")
                )
                logger.info(
                    "Scheduled scan complete (run #%d)", self.run_count
                )
            except Exception as e:
                self.last_error = str(e)
                logger.error("Scheduled anomaly scan failed: %s", e)
            await asyncio.sleep(self.interval_seconds)

    async def _run_hitl_expiry_check(self):
        """Recurring task that resolves expired HITL requests every 10 seconds."""
        from backend.src.utils.agui_store import agui_store
        while True:
            try:
                expired = agui_store.check_and_resolve_expired_requests()
                if expired:
                    logger.info("Auto-resolved %d expired HITL requests", len(expired))
            except Exception as e:
                logger.error("Error in HITL expiry check background task: %s", e)
            await asyncio.sleep(10)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._run_scheduled_anomaly_detection())
            logger.info("AnomalyScheduler started (interval=%ds)", self.interval_seconds)
        if self._hitl_task is None:
            self._hitl_task = asyncio.create_task(self._run_hitl_expiry_check())
            logger.info("HITL expiry checker started (interval=10s)")

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None
            logger.info("AnomalyScheduler stopped")
        if self._hitl_task is not None:
            self._hitl_task.cancel()
            self._hitl_task = None
            logger.info("HITL expiry checker stopped")

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def get_status(self) -> dict:
        """Return a status dict suitable for the /alerts/scheduler API response."""
        return {
            "running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "run_count": self.run_count,
            "last_run_at": self.last_run_at,
            "last_error": self.last_error,
        }


scheduler = AnomalyScheduler()
