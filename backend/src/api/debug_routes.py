from __future__ import annotations

"""REST endpoints for debugging – request history replay.

Enables listing recent API requests and re-playing them through the
graph to reproduce results for investigation.
"""

import logging

from fastapi import APIRouter, Request

from backend.src.api.serializers import serialize_graph_result
from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)
from backend.src.agents.state import SharedState
from backend.src.graph import build_full_graph
from backend.src.utils.request_store import request_store

logger = logging.getLogger("hr_ops.api.debug")

router = APIRouter(prefix="/debug", tags=["debug"])

_graph = build_full_graph()


@router.get("/requests")
async def list_requests(limit: int = 50, request: Request | None = None):
    """List recent API request entries stored for debugging.

    ---
    Request:
        GET /debug/requests?limit=10

    Response 200:
        {
          "success": true,
          "data": {
            "requests": [
              {"id": "req_abc123", "query": "What is the leave policy?", "run_id": "run_abc123", "timestamp": "2026-06-13T00:00:00"}
            ],
            "count": 1
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request) if request else ""
    reqs = request_store.list_recent(limit)
    return success_response(
        data={"requests": reqs, "count": len(reqs)},
        correlation_id=correlation_id,
    )


@router.post("/replay/{request_id}")
async def replay_request(request_id: str, request: Request | None = None):
    """Re-run a previous request through the graph for debugging purposes.

    ---
    Request:
        POST /debug/replay/req_abc123

    Response 200:
        {
          "success": true,
          "data": {
            "request_id": "req_abc123",
            "query": "What is the leave policy?",
            "replayed": true,
            "result": {
              "final_response": "The leave policy allows 15 days...",
              "trace_count": 2,
              "anomaly_count": 0
            }
          },
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 404:
        {"success": false, "message": "Request not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request) if request else ""
    original = request_store.get(request_id)
    if not original:
        return error_response(
            message="Request not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    query = original.get("query", "")
    if not query:
        return error_response(
            message="Original request has no query",
            correlation_id=correlation_id,
            status_code=400,
        )
    state = SharedState(query=query)
    result = _graph.invoke(state)
    result_dict = {k: getattr(result, k) for k in dir(result) if not k.startswith("_") and not callable(getattr(result, k))}
    return success_response(
        data={
            "request_id": request_id,
            "query": query,
            "replayed": True,
            "result": serialize_graph_result(result_dict),
        },
        correlation_id=correlation_id,
    )
