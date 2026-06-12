from fastapi import APIRouter, HTTPException

from backend.src.agents.state import SharedState
from backend.src.graph import build_full_graph
from backend.src.utils.request_store import request_store

router = APIRouter(prefix="/debug", tags=["debug"])

_graph = build_full_graph()


@router.get("/requests")
def list_requests(limit: int = 50):
    reqs = request_store.list_recent(limit)
    return {"requests": reqs, "count": len(reqs)}


@router.post("/replay/{request_id}")
def replay_request(request_id: str):
    original = request_store.get(request_id)
    if not original:
        raise HTTPException(status_code=404, detail="Request not found")
    query = original.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="Original request has no query")
    state = SharedState(query=query)
    result = _graph.invoke(state)
    return {
        "request_id": request_id,
        "query": query,
        "replayed": True,
        "result": _serialize_result(result),
    }


def _serialize_result(result: dict) -> dict:
    from backend.src.agents.state import TraceEntry, AnomalyResult
    trace_log = result.get("trace_log", [])
    anomalies = result.get("anomaly_results", [])
    return {
        "final_response": result.get("final_response", ""),
        "compliance_veto": result.get("compliance_veto", False),
        "compliance_reason": result.get("compliance_reason", ""),
        "retrieved_policies": result.get("retrieved_policies", [])[:3],
        "executed_actions": result.get("executed_actions", [])[:3],
        "total_cost_usd": result.get("total_cost_usd", 0.0),
        "trace_count": len(trace_log),
        "anomaly_count": len(anomalies),
        "trace_events": [
            {
                "node": t.node,
                "agent_role": str(t.agent_role),
                "input_text": t.input_text[:200],
                "output_text": t.output_text[:200],
                "duration_ms": t.duration_ms,
                "cost_usd": t.cost_usd,
                "cache_hit": t.cache_hit,
            }
            for t in (trace_log if isinstance(trace_log, list) else [])
        ],
    }
