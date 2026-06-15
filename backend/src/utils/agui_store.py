"""Thread-safe in-memory store for human-in-the-loop (AG-UI) interaction requests and responses."""

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from backend.src.utils.agui_models import InteractionRequest, InteractionResponse, PendingRequest
from backend.config.settings import settings
from backend.src.services.feedback_service import feedback_store

logger = logging.getLogger("hr_ops.agui_store")


class AGUIStore:
    """Thread-safe in-memory store for AG-UI (human-in-the-loop) interaction requests and responses with expiry checks."""

    def __init__(self):
        self._requests: dict[str, InteractionRequest] = {}
        self._responses: dict[str, InteractionResponse] = {}
        self._lock = Lock()

    def add_request(self, request: InteractionRequest) -> str:
        """Store a new pending interaction request and return its interaction_id."""
        with self._lock:
            self._requests[request.interaction_id] = request
            logger.info("AG-UI request added: %s", request.interaction_id)
        return request.interaction_id

    def get_pending(self) -> list[PendingRequest]:
        """Return all pending requests that have not yet exceeded the configured timeout."""
        with self._lock:
            now = datetime.now(timezone.utc)
            pending = []
            for req in self._requests.values():
                if req.status == "pending":
                    delta = (now - req.created_at).total_seconds()
                    if delta <= settings.agui_timeout_seconds:
                        pending.append(
                            PendingRequest(
                                interaction_id=req.interaction_id,
                                query=req.query,
                                created_at=req.created_at,
                                status=req.status,
                            )
                        )
            return pending

    def respond(self, interaction_id: str, response_text: str, metadata: dict | None = None) -> bool:
        """Record a human response to an interaction, mark the request as resolved, and optionally log a HITL reward."""
        with self._lock:
            if interaction_id not in self._requests:
                logger.warning("AG-UI respond: unknown interaction_id=%s", interaction_id)
                return False
            self._requests[interaction_id].status = "resolved"
            resp = InteractionResponse(
                interaction_id=interaction_id,
                response=response_text,
                metadata=metadata or {},
            )
            self._responses[interaction_id] = resp
            logger.info("AG-UI response recorded: %s", interaction_id)
        action = (metadata or {}).get("action", "")
        if action in ("approve", "reject"):
            feedback_store.record_hitl_reward(interaction_id, action)
        return True

    def get_response(self, interaction_id: str) -> Optional[InteractionResponse]:
        """Retrieve the stored response for a given interaction, or None if not yet resolved."""
        return self._responses.get(interaction_id)

    def is_expired(self, interaction_id: str) -> bool:
        """Return True if the interaction request does not exist or has exceeded the timeout window."""
        req = self._requests.get(interaction_id)
        if not req:
            return True
        delta = (datetime.now(timezone.utc) - req.created_at).total_seconds()
        return delta > settings.agui_timeout_seconds

    @property
    def pending_count(self) -> int:
        """Number of non-expired pending interaction requests currently in the store."""
        return len(self.get_pending())


agui_store = AGUIStore()
