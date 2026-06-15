from __future__ import annotations

"""REST endpoints for debugging – request history replay.

Enables listing recent API requests and re-playing them through the
graph to reproduce results for investigation.
"""

import logging

from fastapi import APIRouter, Request

from backend.src.agents.state import SharedState
from backend.src.api.serializers import serialize_graph_result
from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)
from backend.src.graph import build_full_graph
from backend.src.middleware.metrics_middleware import metrics_store
from backend.src.utils.alerting import check_alert_rules
from backend.src.utils.request_store import request_store

logger = logging.getLogger("hr_ops.api.debug")

router = APIRouter(prefix="/debug", tags=["debug"])

_graph = build_full_graph()


@router.get("/requests")
async def list_requests(limit: int = 50, request: Request = None):  # type: ignore[assignment]
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


@router.get("/metrics")
async def get_metrics(request: Request = None):  # type: ignore[assignment]
    """Return per-endpoint latency histograms (p50/p95/p99) and error rates.

    ---
    Request:
        GET /debug/metrics

    Response 200:
        {
          "success": true,
          "data": {
            "total_requests": 42,
            "total_errors": 1,
            "endpoints": {
              "POST /graph/run": {
                "count": 10, "errors": 0, "error_rate_pct": 0.0,
                "p50_ms": 1245.3, "p95_ms": 3200.1, "p99_ms": 4100.5,
                "min_ms": 890.2, "max_ms": 4200.0, "avg_ms": 1500.4
              }
            }
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request) if request else ""
    return success_response(
        data={
            "total_requests": metrics_store.total_requests,
            "total_errors": metrics_store.total_errors,
            "endpoints": metrics_store.snapshot(),
        },
        correlation_id=correlation_id,
    )


@router.get("/alerts")
async def get_alerts(request: Request = None):  # type: ignore[assignment]
    """Return active alerts based on p99 and error rate thresholds.

    ---
    Request:
        GET /debug/alerts

    Response 200:
        {
          "success": true,
          "data": {
            "alerts": [
              {"endpoint": "POST /graph/run", "rule": "p99_latency", "value": 12300, "threshold": 10000, "message": "..."}
            ],
            "count": 1
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request) if request else ""
    alerts = check_alert_rules(metrics_store.snapshot())
    return success_response(
        data={"alerts": alerts, "count": len(alerts)},
        correlation_id=correlation_id,
    )


@router.post("/replay/{request_id}")
async def replay_request(request_id: str, request: Request = None):  # type: ignore[assignment]
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
