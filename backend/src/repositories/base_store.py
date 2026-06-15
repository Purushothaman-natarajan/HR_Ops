"""Thread-safe generic in-memory key-value store with UUID generation and timestamp tracking."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from threading import Lock

logger = logging.getLogger("hr_ops.store")


class BaseStore:
    """Thread-safe in-memory store with UUID key generation and timestamp tracking."""

    def __init__(self, name: str = "base"):
        """Initialize a named store with an empty items dict and thread-safe lock."""
        self._name = name
        self._items: dict[str, dict] = {}
        self._lock = Lock()

    def save(self, item_data: dict, item_id: str | None = None) -> str:
        """Persist an item, optionally with a custom ID; auto-generates a UUID-based ID and a UTC timestamp."""
        obj_id = item_id or str(uuid.uuid4())[:12]
        with self._lock:
            self._items[obj_id] = {
                **item_data,
                f"{self._name}_id": obj_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        logger.debug("%s saved: %s", self._name, obj_id)
        return obj_id

    def get(self, item_id: str) -> dict | None:
        """Retrieve an item by ID, or None if not found."""
        return self._items.get(item_id)

    def list_recent(self, limit: int = 50) -> list[dict]:
        """Return the most recently saved items, sorted by timestamp descending, up to `limit` entries."""
        with self._lock:
            sorted_items = sorted(
                self._items.values(),
                key=lambda r: r.get("timestamp", ""),
                reverse=True,
            )
            return sorted_items[:limit]

    @property
    def count(self) -> int:
        """Total number of items currently stored."""
        return len(self._items)
