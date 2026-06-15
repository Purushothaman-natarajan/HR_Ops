from __future__ import annotations

"""REST endpoints for one-shot LangGraph execution.

POST /graph/run  – accept a query, execute the graph, return serialised
result with trace events and anomaly data.
"""

import logging

from fastapi import APIRouter, Request

from backend.src.core.exceptions import GraphExecutionError, ModelNotAvailableError
from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)
from backend.src.services.graph_service import run_graph
from backend.src.utils.request_store import request_store

logger = logging.getLogger("hr_ops.api.graph")

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/run")
async def run_graph_endpoint(payload: dict, request: Request):
    """Accept a query and execute the full LangGraph pipeline.

    Returns serialised result with trace events and anomaly data.

    ---
    Request:
        POST /graph/run
        {"query": "What is the leave policy?"}

    Response 200:
        {
          "success": true,
          "data": {
            "run_id": "a1b2c3d4e5f6",
            "final_response": "The leave policy allows 15 days per year...",
            "compliance_veto": false,
            "total_cost_usd": 0.0023,
            "trace_events": [
              {"node": "supervisor", "agent_role": "supervisor", "duration_ms": 420, "cost_usd": 0.0015}
            ],
            "anomaly_results": []
          },
          "message": "Graph execution completed",
          "correlation_id": "abc123"
        }

    Response 400:
        {"success": false, "message": "query is required", "correlation_id": "abc123"}

    Response 500:
        {"success": false, "message": "Graph execution failed: ...", "correlation_id": "abc123"}
    """
    query = (payload.get("query") or "").strip()
    correlation_id = get_correlation_id(request)

    if not query:
        return error_response(
            message="query is required",
            correlation_id=correlation_id,
            status_code=400,
        )

    try:
        result = await run_graph(query)
    except ModelNotAvailableError as e:
        return error_response(message=e.message, correlation_id=correlation_id, status_code=503)
    except GraphExecutionError as e:
        logger.exception("Graph execution failed: query=%s", query[:100])
        return error_response(
            message=str(e),
            correlation_id=correlation_id,
            status_code=500,
        )

    request_store.save({"query": query, "run_id": result.get("run_id", "")})
    return success_response(
        data=result,
        message="Graph execution completed",
        correlation_id=correlation_id,
    )
