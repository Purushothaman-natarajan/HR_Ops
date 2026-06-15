from __future__ import annotations

"""In-memory multi-turn conversation service with session management.

Maintains a thread-safe SessionStore backed by a dict, dispatches each
turn to the appropriate LangGraph (standard or advanced), and records
trace events and auto-rewards per turn.
"""

import logging
import uuid
from datetime import datetime, timezone
from threading import Lock

from backend.src.agents.standard.orchestrator import build_standard_graph
from backend.src.agents.state import SharedState, TriggerType
from backend.src.api.serializers import serialize_trace_events
from backend.src.core.exceptions import GraphExecutionError, ModelNotAvailableError
from backend.src.graph import build_full_graph
from backend.src.services.feedback_service import feedback_store
from backend.src.utils.langfuse_setup import create_trace
from backend.src.utils.trace_store import trace_store

logger = logging.getLogger("hr_ops.conversation_service")

_graph_advanced = None
_graph_standard = None


def _get_graph(mode: str):
    """Return the cached LangGraph instance for the given mode ('standard' or 'advanced')."""
    global _graph_advanced, _graph_standard
    if mode == "advanced":
        if _graph_advanced is None:
            _graph_advanced = build_full_graph()
        return _graph_advanced
    if _graph_standard is None:
        _graph_standard = build_standard_graph()
    return _graph_standard


class SessionStore:
    """Thread-safe in-memory store for multi-turn conversation sessions."""
    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._lock = Lock()

    def create_session(self, query: str, mode: str = "standard") -> dict:
        """Create a new conversation session and store it in memory.

        Args:
            query: Initial user query.
            mode: Graph mode — 'standard' or 'advanced'.

        Returns:
            Session metadata dict with session_id, mode, timestamps.
        """
        session_id = str(uuid.uuid4())[:12]
        session = {
            "session_id": session_id,
            "messages": [],
            "mode": mode,
            "turn_number": 0,
            "total_cost": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._sessions[session_id] = session
        logger.info("Session created: %s mode=%s", session_id, mode)
        return session

    def get_session(self, session_id: str) -> dict | None:
        """Return the session dict, or None if not found."""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Remove a session from the store. Returns True if deleted."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
        return False

    def run_turn(self, session_id: str, query: str) -> dict:
        """Execute a single conversational turn within an existing session.

        Increments the turn counter, invokes the appropriate graph (standard
        or advanced), appends user/assistant messages, and records auto-rewards.

        Args:
            session_id: Target session identifier.
            query: User message for this turn.

        Returns:
            Dict with session_id, turn_number, response, trace_events, cost.

        Raises:
            GraphExecutionError: If query is empty or session does not exist.
        """
        if not query or not query.strip():
            raise GraphExecutionError("Query is required")

        session = self.get_session(session_id)
        if not session:
            raise GraphExecutionError(f"Session not found: {session_id}")

        query = query.strip()
        session["turn_number"] += 1
        turn = session["turn_number"]

        langfuse_trace_id = create_trace(
            f"conversation_{session_id}_turn_{turn}", {"query": query[:100], "session_id": session_id}
        )

        state = SharedState(
            messages=list(session["messages"]),
            query=query,
            session_id=session_id,
            turn_number=turn,
            trigger_type=TriggerType.REACTIVE,
            langfuse_trace_id=langfuse_trace_id,
        )

        try:
            graph = _get_graph(session["mode"])
            result = graph.invoke(state)
        except ModelNotAvailableError:
            raise
        except Exception as e:
            logger.exception("Conversation turn failed: session=%s turn=%d", session_id, turn)
            raise GraphExecutionError(str(e)) from e

        return self._process_result(session, result, query, turn, session_id)

    async def run_turn_async(self, session_id: str, query: str) -> dict:
        """Async variant of run_turn that uses graph.ainvoke() to avoid blocking the event loop."""
        if not query or not query.strip():
            raise GraphExecutionError("Query is required")

        session = self.get_session(session_id)
        if not session:
            raise GraphExecutionError(f"Session not found: {session_id}")

        query = query.strip()
        session["turn_number"] += 1
        turn = session["turn_number"]

        langfuse_trace_id = create_trace(
            f"conversation_{session_id}_turn_{turn}", {"query": query[:100], "session_id": session_id}
        )

        state = SharedState(
            messages=list(session["messages"]),
            query=query,
            session_id=session_id,
            turn_number=turn,
            trigger_type=TriggerType.REACTIVE,
            langfuse_trace_id=langfuse_trace_id,
        )

        try:
            graph = _get_graph(session["mode"])
            result = await graph.ainvoke(state)
        except ModelNotAvailableError:
            raise
        except Exception as e:
            logger.exception("Conversation turn failed: session=%s turn=%d", session_id, turn)
            raise GraphExecutionError(str(e)) from e

        return self._process_result(session, result, query, turn, session_id)

    async def stream_turn_async(self, session_id: str, query: str):
        """Async generator that yields SSE events for each graph node as it completes.

        Yields dicts with keys:
          - node / agent_role / duration_ms / output_text / input_text / cost_usd
          (each representing one completed node)
        Finally yields a dict with event="complete" and the full response data.
        """
        if not query or not query.strip():
            raise GraphExecutionError("Query is required")

        session = self.get_session(session_id)
        if not session:
            raise GraphExecutionError(f"Session not found: {session_id}")

        query = query.strip()
        session["turn_number"] += 1
        turn = session["turn_number"]

        langfuse_trace_id = create_trace(
            f"conversation_{session_id}_turn_{turn}", {"query": query[:100], "session_id": session_id}
        )

        state = SharedState(
            messages=list(session["messages"]),
            query=query,
            session_id=session_id,
            turn_number=turn,
            trigger_type=TriggerType.REACTIVE,
            langfuse_trace_id=langfuse_trace_id,
        )

        try:
            graph = _get_graph(session["mode"])
            prev_trace_len = 0
            final_result = {}
            async for step in graph.astream(state):
                for node_name, node_state in step.items():
                    final_result.update(node_state)
                    trace_log = node_state.get("trace_log", [])
                    for t in trace_log[prev_trace_len:]:
                        activities_data = []
                        for a in getattr(t, "activities", []):
                            activities_data.append({
                                "type": getattr(a, "type", ""),
                                "label": getattr(a, "label", ""),
                                "detail": getattr(a, "detail", ""),
                                "status": getattr(a, "status", "completed"),
                                "duration_ms": getattr(a, "duration_ms", 0),
                                "metadata": getattr(a, "metadata", {}),
                            })
                        yield {
                            "event": "node_complete",
                            "node": getattr(t, "node", node_name),
                            "agent_role": str(getattr(t, "agent_role", "")),
                            "input_text": getattr(t, "input_text", "")[:300],
                            "output_text": getattr(t, "output_text", "")[:300],
                            "duration_ms": getattr(t, "duration_ms", 0),
                            "cost_usd": getattr(t, "cost_usd", 0),
                            "cache_hit": getattr(t, "cache_hit", False),
                            "model_used": getattr(t, "model_used", ""),
                            "activities": activities_data,
                            "reasoning": getattr(t, "reasoning", ""),
                            "retrieved_docs": getattr(t, "retrieved_docs", []),
                            "tool_call": getattr(t, "tool_call", {}),
                        }
                    prev_trace_len = len(trace_log)
                    # Track final_response from any node that sets it
                    # (parallel_check_node doesn't return final_response, so we must preserve it)
                    if node_state.get("final_response"):
                        final_result["final_response"] = node_state["final_response"]
        except ModelNotAvailableError:
            raise
        except Exception as e:
            logger.exception("Conversation stream failed: session=%s turn=%d", session_id, turn)
            raise GraphExecutionError(str(e)) from e

        processed = self._process_result(session, final_result, query, turn, session_id)
        yield {"event": "complete", **processed}

    def _process_result(self, session: dict, result: dict, query: str, turn: int, session_id: str) -> dict:
        """Shared post-processing for sync and async turn execution."""
        final_response = result.get("final_response", "")
        trace_log = result.get("trace_log", [])

        feedback_store.record_auto_rewards(result, session_id=session_id)

        trace_events = serialize_trace_events(trace_log)
        total_cost = result.get("total_cost_usd", 0.0)

        user_msg = {"role": "user", "content": query}
        assistant_msg = {
            "role": "assistant",
            "content": final_response,
            "node": result.get("current_agent", ""),
            "cost": total_cost,
            "liveEvents": trace_events
        }

        with self._lock:
            s = self._sessions.get(session_id)
            if s:
                s["messages"].append(user_msg)
                s["messages"].append(assistant_msg)
                s["total_cost"] += total_cost
                s["updated_at"] = datetime.now(timezone.utc).isoformat()

        trace_store.save_run({
            "run_id": f"conv_{session_id}_turn_{turn}",
            "session_id": session_id,
            "turn_number": turn,
            "query": query,
            "final_response": final_response,
            "trace_events": trace_events,
            "total_cost_usd": total_cost,
            "cost_usd": total_cost,
            "duration_ms": sum(t.get("duration_ms", 0) for t in trace_events),
        })

        return {
            "session_id": session_id,
            "turn_number": turn,
            "response": final_response,
            "trace_events": trace_events,
            "total_cost_usd": total_cost,
        }

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """Return the most recent sessions, sorted by updated_at descending."""
        with self._lock:
            sorted_sessions = sorted(
                self._sessions.values(),
                key=lambda s: s.get("updated_at", ""),
                reverse=True,
            )
            return [
                {
                    "session_id": s["session_id"],
                    "mode": s["mode"],
                    "turn_number": s["turn_number"],
                    "message_count": len(s["messages"]),
                    "total_cost": round(s["total_cost"], 5),
                    "updated_at": s["updated_at"],
                    "created_at": s["created_at"],
                }
                for s in sorted_sessions[:limit]
            ]


session_store = SessionStore()
