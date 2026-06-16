from __future__ import annotations

"""REST endpoints for human-in-the-loop (AGUI) interaction handling.

Exposes pending interactions, response submission, response retrieval,
and expiry status checks for HITL workflows.
"""

from fastapi import APIRouter, Request

from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)
from backend.src.domain.agui import InteractionResponse
from backend.src.utils.agui_store import agui_store

router = APIRouter(prefix="/agui", tags=["agui"])


@router.get("/pending")
async def get_pending(request: Request):
    """Return all pending HITL interactions awaiting human response.

    ---
    Request:
        GET /agui/pending

    Response 200:
        {
          "success": true,
          "data": {
            "pending": [
              {
                "interaction_id": "int_abc123",
                "query": "Anomaly detected: salary outlier for EMP0012",
                "created_at": "2026-06-13T00:00:00",
                "status": "pending",
                "assigned_role": "hr_manager"
              }
            ]
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request)
    return success_response(
        data={"pending": agui_store.get_pending()},
        correlation_id=correlation_id,
    )


@router.post("/respond/{interaction_id}")
async def respond(interaction_id: str, resp: InteractionResponse, request: Request):
    """Submit a human response to a specific HITL interaction.

    ---
    Request:
        POST /agui/respond/int_abc123
        {"interaction_id": "int_abc123", "response": "Approved — adjust salary to market rate", "metadata": {}}

    Response 200:
        {
          "success": true,
          "data": {"status": "resolved", "interaction_id": "int_abc123"},
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 404:
        {"success": false, "message": "Interaction not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    success = agui_store.respond(interaction_id, resp.response, resp.metadata)
    if not success:
        return error_response(
            message="Interaction not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    return success_response(
        data={"status": "resolved", "interaction_id": interaction_id},
        correlation_id=correlation_id,
    )


@router.get("/response/{interaction_id}")
async def get_response(interaction_id: str, request: Request):
    """Retrieve the human response submitted for a given interaction.

    ---
    Request:
        GET /agui/response/int_abc123

    Response 200:
        {
          "success": true,
          "data": {
            "interaction_id": "int_abc123",
            "response": "Approved — adjust salary to market rate",
            "resolved_at": "2026-06-13T00:01:00",
            "metadata": {}
          },
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 404:
        {"success": false, "message": "Response not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    resp = agui_store.get_response(interaction_id)
    if not resp:
        return error_response(
            message="Response not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    return success_response(data=resp, correlation_id=correlation_id)


@router.get("/status/{interaction_id}")
async def get_status(interaction_id: str, request: Request):
    """Check whether a HITL interaction has expired and return the pending count.

    ---
    Request:
        GET /agui/status/int_abc123

    Response 200:
        {
          "success": true,
          "data": {
            "interaction_id": "int_abc123",
            "expired": false,
            "pending_count": 2
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request)
    expired = agui_store.is_expired(interaction_id)
    return success_response(
        data={
            "interaction_id": interaction_id,
            "expired": expired,
            "pending_count": agui_store.pending_count,
        },
        correlation_id=correlation_id,
    )
