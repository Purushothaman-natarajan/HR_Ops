from __future__ import annotations

"""Service layer for LangGraph execution, serialization, and Langfuse error logging.

Houses the singleton graph instance, the main run_graph entry point,
result serialisation helpers, and a Langfuse error-scoring utility.
"""

import logging
import uuid
from datetime import datetime, timezone

from backend.src.agents.state import SharedState, TriggerType
from backend.src.api.serializers import serialize_graph_result
from backend.src.core.exceptions import GraphExecutionError, ModelNotAvailableError
from backend.src.graph import build_full_graph
from backend.src.services.feedback_service import feedback_store
from backend.src.utils.langfuse_setup import create_trace, get_langfuse_client
from backend.src.utils.pii_redaction import redact_run_data
from backend.src.utils.trace_sampling import should_sample
from backend.src.utils.trace_store import trace_store

logger = logging.getLogger("hr_ops.services.graph")

_graph_instance = None


def _get_graph():
    """Return the cached singleton LangGraph instance, building it if necessary."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_full_graph()
    return _graph_instance


async def run_graph(query: str, trigger: str = "reactive", existing_state: SharedState | None = None) -> dict:
    """Execute the full LangGraph pipeline for a given query.

    Creates or reuses a SharedState, invokes the graph, records auto-rewards,
    and returns a serialised result dict.

    Args:
        query: User input string.
        trigger: Execution mode — 'reactive' or 'scheduled'.
        existing_state: Optional pre-existing state for continuation.

    Returns:
        Serialised result containing final response, trace events, anomalies, etc.

    Raises:
        ModelNotAvailableError: If the LLM backend is unavailable.
        GraphExecutionError: If the graph invocation or validation fails.
    """
    if not query or not query.strip():
        raise GraphExecutionError("Query is required")

    query = query.strip()
    run_id = str(uuid.uuid4())[:12]
    langfuse_trace_id = create_trace(
        f"graph_run_{run_id}", {"query": query[:100]}
    )

    if existing_state:
        state = existing_state
        state.query = query
        state.langfuse_trace_id = langfuse_trace_id
    else:
        trigger_type = (
            TriggerType.SCHEDULED if trigger == "scheduled" else TriggerType.REACTIVE
        )
        state = SharedState(
            query=query,
            trigger_type=trigger_type,
            langfuse_trace_id=langfuse_trace_id,
        )

    try:
        graph = _get_graph()
        result = await graph.ainvoke(state)
    except ModelNotAvailableError:
        raise
    except Exception as e:
        logger.exception("Graph execution failed: run_id=%s", run_id)
        _log_langfuse_error(langfuse_trace_id, str(e))
        raise GraphExecutionError(str(e)) from e

    feedback_store.record_auto_rewards(result)

    serialized = serialize_graph_result(result, run_id, langfuse_trace_id)

    redact_run_data(serialized)

    if should_sample(serialized):
        trace_store.save_run(serialized)
    else:
        logger.debug("Trace sampling skipped: run_id=%s", run_id)

    return serialized


def _log_langfuse_error(trace_id: str, error: str):
    """Score a failed trace in Langfuse with value 0.0 and the error comment.

    Args:
        trace_id: Langfuse trace identifier.
        error: Error message string to attach as a comment.
    """
    try:
        client = get_langfuse_client()
        if client is None:
            return
        from langfuse.api.ingestion.types.ingestion_event import (
            IngestionEvent_ScoreCreate,
        )
        from langfuse.api.ingestion.types.score_body import ScoreBody
        event = IngestionEvent_ScoreCreate(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            body=ScoreBody(
                id=str(uuid.uuid4()),
                name="error",
                value=0.0,
                comment=error,
                trace_id=trace_id,
            ),
        )
        client.api.ingestion.batch(batch=[event])
    except Exception:
        pass
