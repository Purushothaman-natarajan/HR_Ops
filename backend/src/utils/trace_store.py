import logging
import uuid
from datetime import datetime
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger("hr_ops.trace_store")


class TraceStore:
    def __init__(self):
        self._runs: dict[str, dict] = {}
        self._lock = Lock()

    def save_run(self, run_data: dict) -> str:
        run_id = run_data.get("run_id") or str(uuid.uuid4())[:12]
        with self._lock:
            self._runs[run_id] = {**run_data, "run_id": run_id, "timestamp": datetime.utcnow().isoformat()}
        logger.info("Trace saved: run_id=%s", run_id)
        return run_id

    def get_run(self, run_id: str) -> Optional[dict]:
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 50) -> list[dict]:
        with self._lock:
            sorted_runs = sorted(self._runs.values(), key=lambda r: r.get("timestamp", ""), reverse=True)
            return sorted_runs[:limit]

    def compare(self, run_ids: list[str]) -> list[Optional[dict]]:
        return [self._runs.get(rid) for rid in run_ids]

    @property
    def count(self) -> int:
        return len(self._runs)


trace_store = TraceStore()
