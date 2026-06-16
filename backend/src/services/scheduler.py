import asyncio
import logging
from backend.src.services.graph_service import run_graph
from backend.src.utils.alert_store import alert_store
from backend.src.memory.episodic_memory import episodic_memory

logger = logging.getLogger("hr_ops.scheduler")

class AnomalyScheduler:
    def __init__(self, interval_seconds: int = 60 * 60): # 1 hour default
        self.interval_seconds = interval_seconds
        self._task = None

    async def _run_scheduled_anomaly_detection(self):
        while True:
            try:
                logger.info("Running scheduled anomaly detection scan")
                # Trigger anomaly detection by calling run_graph with trigger="scheduled"
                query = "Run anomaly detection across all HR datasets"
                result = await run_graph(query, trigger="scheduled")
                alert_store.add_alert(query, "scheduled", result)
                episodic_memory.store_incident("scheduled", query, result.get("final_response", ""))
            except Exception as e:
                logger.error("Failed to run scheduled anomaly detection: %s", e)
            await asyncio.sleep(self.interval_seconds)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._run_scheduled_anomaly_detection())

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None

scheduler = AnomalyScheduler()
