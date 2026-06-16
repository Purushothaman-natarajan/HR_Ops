"""Thread-safe in-memory store for human-in-the-loop (AG-UI) interaction requests and responses."""

import logging
from datetime import datetime, timezone
from threading import Lock

from backend.src.core.settings import settings
from backend.src.services.feedback_service import feedback_store
from backend.src.domain.agui import (
    InteractionRequest,
    InteractionResponse,
    PendingRequest,
)

logger = logging.getLogger("hr_ops.agui_store")


class AGUIStore:
    """Thread-safe in-memory store for AG-UI (human-in-the-loop) interaction requests and responses with expiry checks."""

    def __init__(self):
        self._requests: dict[str, InteractionRequest] = {}
        self._responses: dict[str, InteractionResponse] = {}
        self._lock = Lock()
        self._cache_pending = None

    def _clear_caches(self):
        self._cache_pending = None
        try:
            from backend.src.utils.alert_store import alert_store
            alert_store.clear_cache()
        except ImportError:
            pass

    def add_request(self, request: InteractionRequest) -> str:
        """Store a new pending interaction request and return its interaction_id."""
        with self._lock:
            self._requests[request.interaction_id] = request
            logger.info("AG-UI request added: %s", request.interaction_id)
            self._clear_caches()
        return request.interaction_id

    def get_pending(self) -> list[PendingRequest]:
        """Return all pending requests that have not yet exceeded the configured timeout."""
        with self._lock:
            if self._cache_pending is not None:
                return self._cache_pending
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
                                session_id=req.session_id,
                                assigned_role=req.assigned_role,
                                context=req.context,
                            )
                        )
            self._cache_pending = pending
            return pending

    def respond(self, interaction_id: str, response_text: str, metadata: dict | None = None) -> bool:
        """Record a human response to an interaction, mark the request as resolved, and optionally log a HITL reward."""
        with self._lock:
            if interaction_id not in self._requests:
                logger.warning("AG-UI respond: unknown interaction_id=%s", interaction_id)
                return False
            req = self._requests[interaction_id]
            req.status = "resolved"
            resp = InteractionResponse(
                interaction_id=interaction_id,
                response=response_text,
                metadata=metadata or {},
            )
            self._responses[interaction_id] = resp
            logger.info("AG-UI response recorded: %s", interaction_id)
            self._clear_caches()
            
            # Extract trigger sub-agent and its query context
            trigger_agent = (req.context or {}).get("current_agent", "policy")
            rl_context = (req.context or {}).get("rl_context", {})
            session_id = req.session_id

        action = (metadata or {}).get("action", "")

        # If there is a pending tool call, execute it on approval
        pending_tool_call = (req.context or {}).get("pending_tool_call")
        if pending_tool_call and action == "approve":
            try:
                from backend.src.tools.api_mocks import execute_tool
                tool_name = pending_tool_call.get("name")
                tool_args = pending_tool_call.get("args", {})
                logger.info("Executing approved pending tool call: %s(%s)", tool_name, tool_args)
                tool_result = execute_tool(tool_name, **tool_args)
                logger.info("Approved tool execution result: %s", tool_result)
                resp.response = f"Approved & Executed successfully. Details: {resp.response}"
            except Exception as e:
                logger.exception("Failed to execute approved pending tool call")
                resp.response = f"Approved but execution failed: {e}. Details: {resp.response}"

        # If it's an anomaly interaction, update the anomaly bandit
        anomalies = (req.context or {}).get("anomaly_results", [])
        if anomalies:
            anomaly = anomalies[0]
            # Form the anomaly context dictionary needed for the bandit feature vector
            anomaly_context = {
                "recommended_action": anomaly.get("recommended_action", "flag_for_review"),
                "confidence_score": anomaly.get("confidence_score", 0.7),
                "severity": anomaly.get("severity", 0.5),
                "anomaly_type": anomaly.get("anomaly_type", ""),
            }
            proposed_action = anomaly_context["recommended_action"]
            
            if action == "approve":
                feedback_store.record_anomaly_bandit_reward(anomaly_context, proposed_action, 1.0, session_id=session_id)
            elif action == "reject":
                feedback_store.record_anomaly_bandit_reward(anomaly_context, proposed_action, -1.0, session_id=session_id)
            elif action == "modify":
                modified_action = (metadata or {}).get("modified_action", "")
                if modified_action:
                    # +1.0 for modified action, -1.0 for proposed action
                    feedback_store.record_anomaly_bandit_reward(anomaly_context, modified_action, 1.0, session_id=session_id)
                    feedback_store.record_anomaly_bandit_reward(anomaly_context, proposed_action, -1.0, session_id=session_id)

        if action in ("approve", "reject"):
            feedback_store.record_hitl_reward(interaction_id, action, trigger_agent=trigger_agent, rl_context=rl_context)
        return True

    def check_and_resolve_expired_requests(self) -> list[str]:
        """Identify pending requests that have exceeded the timeout window and resolve them with 'flag-for-audit'."""
        resolved_ids = []
        with self._lock:
            now = datetime.now(timezone.utc)
            for req in list(self._requests.values()):
                if req.status == "pending":
                    delta = (now - req.created_at).total_seconds()
                    if delta > settings.agui_timeout_seconds:
                        req.status = "resolved"
                        resp = InteractionResponse(
                            interaction_id=req.interaction_id,
                            response="Auto-resolved: action timed out. Escalated to flag-for-audit.",
                            metadata={"action": "flag-for-audit", "auto_resolved": True},
                        )
                        self._responses[req.interaction_id] = resp
                        resolved_ids.append(req.interaction_id)
                        logger.info("AG-UI request auto-resolved (timeout): %s", req.interaction_id)
                        
                        # Process bandit penalty on timeout
                        anomalies = (req.context or {}).get("anomaly_results", [])
                        if anomalies:
                            anomaly = anomalies[0]
                            anomaly_context = {
                                "recommended_action": anomaly.get("recommended_action", "flag_for_review"),
                                "confidence_score": anomaly.get("confidence_score", 0.7),
                                "severity": anomaly.get("severity", 0.5),
                                "anomaly_type": anomaly.get("anomaly_type", ""),
                            }
                            proposed_action = anomaly_context["recommended_action"]
                            feedback_store.record_anomaly_bandit_reward(anomaly_context, proposed_action, -1.0, session_id=req.session_id)
            if resolved_ids:
                self._clear_caches()
        return resolved_ids

    def get_response(self, interaction_id: str) -> InteractionResponse | None:
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
