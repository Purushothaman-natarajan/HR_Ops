import logging
from datetime import datetime
from threading import Lock
from typing import Optional

from backend.src.utils.agui_models import InteractionRequest, InteractionResponse, PendingRequest
from backend.config.settings import settings

logger = logging.getLogger("hr_ops.agui_store")


class AGUIStore:
    def __init__(self):
        self._requests: dict[str, InteractionRequest] = {}
        self._responses: dict[str, InteractionResponse] = {}
        self._lock = Lock()

    def add_request(self, request: InteractionRequest) -> str:
        with self._lock:
            self._requests[request.interaction_id] = request
            logger.info("AG-UI request added: %s", request.interaction_id)
        return request.interaction_id

    def get_pending(self) -> list[PendingRequest]:
        with self._lock:
            now = datetime.utcnow()
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
        return True

    def get_response(self, interaction_id: str) -> Optional[InteractionResponse]:
        return self._responses.get(interaction_id)

    def is_expired(self, interaction_id: str) -> bool:
        req = self._requests.get(interaction_id)
        if not req:
            return True
        delta = (datetime.utcnow() - req.created_at).total_seconds()
        return delta > settings.agui_timeout_seconds

    @property
    def pending_count(self) -> int:
        return len(self.get_pending())


agui_store = AGUIStore()
