import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter

from backend.src.agents.state import SharedState, TriggerType
from backend.src.graph import build_full_graph
from backend.src.utils.trace_store import trace_store
from backend.src.utils.request_store import request_store
from backend.src.utils.langfuse_setup import create_trace, get_langfuse_client

logger = logging.getLogger("hr_ops.api.graph")

router = APIRouter(prefix="/graph", tags=["graph"])

_graph = build_full_graph()


@router.post("/run")
def run_graph(payload: dict):
    query = (payload.get("query") or "").strip()
    if not query:
        return {"error": "query is required"}

    run_id = str(uuid.uuid4())[:12]
    langfuse_trace_id = create_trace(f"graph_run_{run_id}", {"query": query[:100]})

    state = SharedState(
        query=query,
        trigger_type=TriggerType.REACTIVE,
        langfuse_trace_id=langfuse_trace_id,
    )

    request_store.save({"query": query, "run_id": run_id})

    try:
        result = _graph.invoke(state)
    except Exception as e:
        logger.exception("Graph execution failed: run_id=%s", run_id)
        _log_langfuse_error(langfuse_trace_id, str(e))
        return {"error": str(e), "run_id": run_id}

    serialized = _serialize(result, run_id, langfuse_trace_id)
    trace_store.save_run(serialized)

    _log_langfuse_traces(langfuse_trace_id, serialized)

    return serialized


def _serialize(result: dict, run_id: str, langfuse_trace_id: str) -> dict:
    from backend.src.agents.state import TraceEntry, AnomalyResult

    trace_log = result.get("trace_log", [])
    anomalies = result.get("anomaly_results", [])

    return {
        "run_id": run_id,
        "langfuse_trace_id": langfuse_trace_id,
        "query": result.get("query", ""),
        "final_response": result.get("final_response", ""),
        "compliance_veto": result.get("compliance_veto", False),
        "compliance_reason": result.get("compliance_reason", ""),
        "retrieved_policies": result.get("retrieved_policies", [])[:3],
        "executed_actions": result.get("executed_actions", [])[:3],
        "total_cost_usd": result.get("total_cost_usd", 0.0),
        "trace_events": [
            {
                "node": t.node,
                "agent_role": str(t.agent_role),
                "input_text": t.input_text[:300],
                "output_text": t.output_text[:300],
                "timestamp": str(t.timestamp) if hasattr(t, "timestamp") else "",
                "duration_ms": t.duration_ms,
                "cost_usd": t.cost_usd,
                "cache_hit": t.cache_hit,
                "model_used": t.model_used,
            }
            for t in (trace_log if isinstance(trace_log, list) else [])
            if isinstance(t, TraceEntry)
        ],
        "anomaly_results": [
            {
                "detected": a.detected,
                "severity": a.severity,
                "description": a.description,
                "anomaly_field": a.anomaly_field,
                "suggested_action": a.suggested_action,
            }
            for a in (anomalies if isinstance(anomalies, list) else [])
            if isinstance(a, AnomalyResult)
        ],
    }


def _log_langfuse_traces(trace_id: str, data: dict):
    try:
        client = get_langfuse_client()
        for evt in data.get("trace_events", []):
            client.score(
                trace_id=trace_id,
                name=evt["node"],
                value=1.0,
                comment=f"{evt['agent_role']}: {evt['output_text'][:100]}",
            )
    except Exception:
        logger.debug("Langfuse scoring skipped (not configured)")


def _log_langfuse_error(trace_id: str, error: str):
    try:
        client = get_langfuse_client()
        client.score(trace_id=trace_id, name="error", value=0.0, comment=error)
    except Exception:
        pass
