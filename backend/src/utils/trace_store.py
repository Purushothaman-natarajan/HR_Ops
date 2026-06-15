"""Thread-safe in-memory store for LLM trace runs with comparison and listing support."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger("hr_ops.trace_store")


class TraceStore:
    """Thread-safe in-memory store for LLM trace run data with ordering, listing, and comparison utilities."""

    def __init__(self):
        """Create an empty trace store with a thread-safe lock."""
        self._runs: dict[str, dict] = {}
        self._lock = Lock()

    def save_run(self, run_data: dict) -> str:
        """Persist a trace run, generating a run_id if one is not provided, and return the run_id."""
        run_id = run_data.get("run_id") or str(uuid.uuid4())[:12]
        with self._lock:
            self._runs[run_id] = {
                **run_data,
                "run_id": run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        logger.info("Trace saved: run_id=%s", run_id)
        return run_id

    def get_run(self, run_id: str) -> Optional[dict]:
        """Retrieve a trace run by its run_id, or None if not found."""
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 50) -> list[dict]:
        """Return the most recent trace runs, sorted by timestamp descending, up to `limit` entries."""
        with self._lock:
            sorted_runs = sorted(
                self._runs.values(),
                key=lambda r: r.get("timestamp", ""),
                reverse=True,
            )
            return sorted_runs[:limit]

    def compare(self, run_ids: list[str]) -> list[Optional[dict]]:
        """Return the trace runs for the given list of run_ids in the same order (None for missing IDs)."""
        return [self._runs.get(rid) for rid in run_ids]

    @property
    def count(self) -> int:
        """Total number of trace runs currently stored."""
        return len(self._runs)


trace_store = TraceStore()
