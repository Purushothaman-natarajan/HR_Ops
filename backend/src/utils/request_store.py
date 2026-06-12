import logging
import uuid
from datetime import datetime
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger("hr_ops.request_store")


class RequestStore:
    def __init__(self):
        self._requests: dict[str, dict] = {}
        self._lock = Lock()

    def save(self, request_data: dict) -> str:
        req_id = str(uuid.uuid4())[:12]
        with self._lock:
            self._requests[req_id] = {
                **request_data,
                "request_id": req_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        logger.debug("Request saved: %s", req_id)
        return req_id

    def get(self, request_id: str) -> Optional[dict]:
        return self._requests.get(request_id)

    def list_recent(self, limit: int = 50) -> list[dict]:
        with self._lock:
            sorted_reqs = sorted(self._requests.values(), key=lambda r: r.get("timestamp", ""), reverse=True)
            return sorted_reqs[:limit]

    @property
    def count(self) -> int:
        return len(self._requests)


request_store = RequestStore()
