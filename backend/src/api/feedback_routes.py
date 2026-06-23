from __future__ import annotations

"""REST endpoints for explicit feedback submission and RL agent introspection.

Supports posting ratings, listing feedback history, viewing per-arm
stats, and inspecting the internal bandit state.
"""

import logging

from fastapi import APIRouter, Request

from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)
from backend.src.intelligence.rl_layer import rl_agent, anomaly_bandit
from backend.src.services.feedback_service import feedback_store

logger = logging.getLogger("hr_ops.feedback_routes")
router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
async def api_submit_feedback(body: dict, request: Request):
    """Submit explicit user feedback with a rating of 1 or -1.

    ---
    Request:
        POST /feedback
        {"session_id": "sess_a1b2c3", "action": "policy", "rating": 1, "context": {}}

    Response 200:
        {
          "success": true,
          "data": {
            "recorded": "fb_abc123",
            "buffer_size": 3,
            "rl_batch_size": 10
          },
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 400:
        {"success": false, "message": "action (str) and rating (1 or -1) are required", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    session_id = body.get("session_id", "")
    action = body.get("action", "")
    rating = body.get("rating")

    try:
        rating_val = float(rating) if rating is not None else None
    except (ValueError, TypeError):
        return error_response(
            message="rating must be a numeric value",
            correlation_id=correlation_id,
            status_code=400,
        )

    if not action or rating_val is None or not (-1.0 <= rating_val <= 1.0):
        return error_response(
            message="action (str) and rating (numeric between -1 and 1) are required",
            correlation_id=correlation_id,
            status_code=400,
        )

    context = body.get("context", {})
    entry = feedback_store.record_feedback(session_id, action, rating_val, context)
    return success_response(
        data={
            "recorded": entry["id"],
            "buffer_size": feedback_store.buffer_size,
            "rl_batch_size": feedback_store.get_stats()["rl_batch_size"],
        },
        correlation_id=correlation_id,
    )


@router.get("")
async def api_list_feedback(request: Request, limit: int = 50):
    """List recent feedback entries (history + current buffer), newest first.

    ---
    Request:
        GET /feedback?limit=10

    Response 200:
        {
          "success": true,
          "data": {
            "feedback": [
              {"id": "fb_abc123", "session_id": "sess_a1b2c3", "action": "policy", "reward": 1.0, "source": "explicit", "timestamp": "2026-06-13T00:00:00"}
            ]
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request)
    entries = feedback_store.list_feedback(limit=limit)
    return success_response(data={"feedback": entries}, correlation_id=correlation_id)


@router.get("/stats")
async def api_feedback_stats(request: Request):
    """Return per-arm reward statistics and RL configuration values.

    ---
    Request:
        GET /feedback/stats

    Response 200:
        {
          "success": true,
          "data": {
            "per_arm": [
              {"arm": "policy", "total_reward": 5.0, "count": 3, "avg_reward": 1.67, "source": "explicit"},
              {"arm": "action", "total_reward": -0.5, "count": 1, "avg_reward": -0.5, "source": "compliance"}
            ],
            "buffer_size": 3,
            "total_feedbacks": 10,
            "rl_batch_size": 10
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request)
    stats = feedback_store.get_stats()
    return success_response(data=stats, correlation_id=correlation_id)


@router.get("/rl/state")
async def api_rl_state(request: Request, type: str = "standard"):
    """Inspect the internal bandit agent state and pending feedback count.

    ---
    Request:
        GET /feedback/rl/state?type=standard (or advanced)

    Response 200:
        {
          "success": true,
          "data": {
            "arms": {
              "policy": {"theta": [0.5, 0.3, -0.1, 0.0, 0.0, 0.0, 0.0, 0.0], "pulls": 5, "reward": 3.0},
              "action": {"theta": [0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "pulls": 3, "reward": 1.5},
              "anomaly": {"theta": [0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "pulls": 1, "reward": 0.5},
              "compliance": {"theta": [0.3, -0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "pulls": 2, "reward": -0.5}
            },
            "config": {"batch_size": 10, "alpha": 0.1, "gamma": 0.9},
            "pending_feedbacks": 3
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request)
    if type == "advanced":
        state = anomaly_bandit.get_state()
    else:
        state = rl_agent.get_state()
    state["pending_feedbacks"] = feedback_store.buffer_size
    return success_response(data=state, correlation_id=correlation_id)
