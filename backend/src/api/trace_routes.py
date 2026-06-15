from __future__ import annotations

"""REST endpoints for browsing and comparing graph execution traces.

Provides listing of recent runs, single-run detail, and multi-run
comparison for debugging and observability.
"""

from fastapi import APIRouter, Request

from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)
from backend.src.utils.trace_store import trace_store

router = APIRouter(prefix="/trace", tags=["trace"])


@router.get("/runs")
async def list_runs(limit: int = 50, request: Request = None):  # type: ignore[assignment]
    """List recent graph execution runs with summary metadata.

    ---
    Request:
        GET /trace/runs?limit=10

    Response 200:
        {
          "success": true,
          "data": {
            "runs": [
              {"run_id": "run_abc123", "query": "What is the leave policy?", "timestamp": "2026-06-13T00:00:00", "duration_ms": 850, "cost_usd": 0.0023}
            ],
            "count": 1
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request) if request else ""
    runs = trace_store.list_runs(limit)
    return success_response(
        data={"runs": runs, "count": len(runs)},
        correlation_id=correlation_id,
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request = None):  # type: ignore[assignment]
    """Get full detail for a single graph execution run by ID.

    ---
    Request:
        GET /trace/runs/run_abc123

    Response 200:
        {
          "success": true,
          "data": {
            "run_id": "run_abc123",
            "query": "What is the leave policy?",
            "final_response": "The leave policy allows 15 days...",
            "total_cost_usd": 0.0023,
            "trace_events": [
              {"node": "supervisor", "agent_role": "supervisor", "duration_ms": 420, "cost_usd": 0.0015}
            ],
            "anomaly_results": []
          },
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 404:
        {"success": false, "message": "Run not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request) if request else ""
    run = trace_store.get_run(run_id)
    if not run:
        return error_response(
            message="Run not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    return success_response(data=run, correlation_id=correlation_id)


@router.get("/compare")
async def compare_runs(run_ids: str, request: Request = None):  # type: ignore[assignment]
    """Compare two or more runs side-by-side. Provide run_ids as comma-separated query param.

    ---
    Request:
        GET /trace/compare?run_ids=run_abc123,run_def456

    Response 200:
        {
          "success": true,
          "data": {
            "run_ids": ["run_abc123", "run_def456"],
            "runs": [
              {"run_id": "run_abc123", "query": "What is the leave policy?"},
              {"run_id": "run_def456", "query": "Update salary for EMP0001"}
            ],
            "compared": 2
          },
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 400:
        {"success": false, "message": "Provide at least 2 run_ids", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request) if request else ""
    ids = [rid.strip() for rid in run_ids.split(",") if rid.strip()]
    if len(ids) < 2:
        return error_response(
            message="Provide at least 2 run_ids",
            correlation_id=correlation_id,
            status_code=400,
        )
    runs = trace_store.compare(ids)
    return success_response(
        data={"run_ids": ids, "runs": runs, "compared": len(runs)},
        correlation_id=correlation_id,
    )
