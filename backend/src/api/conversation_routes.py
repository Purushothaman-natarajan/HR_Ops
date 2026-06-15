from __future__ import annotations

"""REST endpoints for multi-turn conversational sessions.

Supports starting a session (standard or advanced mode), sending messages,
retrieving / deleting sessions, and listing all recent sessions.
"""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.src.core.exceptions import ModelNotAvailableError
from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)
from backend.src.services.conversation_service import session_store

logger = logging.getLogger("hr_ops.conversation_routes")
router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post("/start")
async def api_start_conversation(body: dict, request: Request):
    """Create a new session and immediately run the first turn.

    ---
    Request:
        POST /conversation/start
        {"query": "What is the leave policy?", "mode": "advanced"}

    Response 200:
        {
          "success": true,
          "data": {
            "session_id": "sess_a1b2c3",
            "turn_number": 1,
            "response": "The leave policy allows 15 days per year...",
            "trace_events": [...],
            "total_cost_usd": 0.0023,
            "mode": "advanced"
          },
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 400:
        {"success": false, "message": "query is required", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    query = (body.get("query") or "").strip()
    mode = body.get("mode", "standard")

    if not query:
        return error_response(
            message="query is required",
            correlation_id=correlation_id,
            status_code=400,
        )
    if mode not in ("standard", "advanced"):
        return error_response(
            message="mode must be 'standard' or 'advanced'",
            correlation_id=correlation_id,
            status_code=400,
        )

    session = session_store.create_session(query, mode=mode)
    try:
        result = await session_store.run_turn_async(session["session_id"], query)
    except ModelNotAvailableError as e:
        session_store.delete_session(session["session_id"])
        return error_response(message=e.message, correlation_id=correlation_id, status_code=503)
    except Exception as e:
        session_store.delete_session(session["session_id"])
        return error_response(message=str(e), correlation_id=correlation_id, status_code=500)

    return success_response(
        data={**result, "mode": mode},
        correlation_id=correlation_id,
    )


async def _stream_events(session_id: str, query: str):
    """Async generator that yields SSE-formatted events from the graph execution."""
    try:
        async for event in session_store.stream_turn_async(session_id, query):
            if event.get("event") == "complete":
                yield f"event: complete\ndata: {json.dumps(event)}\n\n"
            else:
                yield f"event: node_complete\ndata: {json.dumps(event)}\n\n"
    except ModelNotAvailableError as e:
        yield f"event: error_event\ndata: {json.dumps({'message': e.message})}\n\n"
    except Exception as e:
        yield f"event: error_event\ndata: {json.dumps({'message': str(e)})}\n\n"


@router.get("/stream/start")
async def api_stream_start(query: str, request: Request, mode: str = "standard"):
    """Create a new session and stream each graph node event via SSE.

    ---
    Request:
        GET /conversation/stream/start?query=What+is+leave+policy%3F&mode=advanced

    Response 200 (SSE stream):
        event: node_complete
        data: {"node":"triage","agent_role":"supervisor","duration_ms":420,"output_text":"Classified as policy"}

        event: node_complete
        data: {"node":"policy","agent_role":"policy","duration_ms":1500,"output_text":"The leave policy allows..."}

        event: complete
        data: {"event":"complete","session_id":"sess_abc","turn_number":1,"response":"...","trace_events":[...],"total_cost_usd":0.003}
    """
    correlation_id = get_correlation_id(request)

    if not query or not query.strip():
        return error_response(
            message="query is required",
            correlation_id=correlation_id,
            status_code=400,
        )
    if mode not in ("standard", "advanced"):
        return error_response(
            message="mode must be 'standard' or 'advanced'",
            correlation_id=correlation_id,
            status_code=400,
        )

    session = session_store.create_session(query, mode=mode)
    session_id = session["session_id"]

    return StreamingResponse(
        _stream_events(session_id, query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Correlation-ID": correlation_id,
            "X-Session-ID": session_id,
        },
    )


@router.post("/{session_id}/send")
async def api_send_message(session_id: str, body: dict, request: Request):
    """Send a user message within an existing session.

    ---
    Request:
        POST /conversation/sess_a1b2c3/send
        {"query": "What about sick leave?"}

    Response 200:
        {
          "success": true,
          "data": {
            "session_id": "sess_a1b2c3",
            "turn_number": 2,
            "response": "Sick leave is 10 days per year with medical certificate...",
            "trace_events": [...],
            "total_cost_usd": 0.0018,
            "mode": "advanced"
          },
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 404:
        {"success": false, "message": "Session not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    query = (body.get("query") or "").strip()

    if not query:
        return error_response(
            message="query is required",
            correlation_id=correlation_id,
            status_code=400,
        )

    session = session_store.get_session(session_id)
    if not session:
        return error_response(
            message="Session not found",
            correlation_id=correlation_id,
            status_code=404,
        )

    try:
        result = await session_store.run_turn_async(session_id, query)
    except ModelNotAvailableError as e:
        return error_response(message=e.message, correlation_id=correlation_id, status_code=503)
    except Exception as e:
        return error_response(message=str(e), correlation_id=correlation_id, status_code=500)

    return success_response(
        data={**result, "mode": session["mode"]},
        correlation_id=correlation_id,
    )


@router.get("/{session_id}/stream/send")
async def api_stream_send(session_id: str, query: str, request: Request):
    """Stream each graph node event via SSE for a follow-up message in an existing session.

    ---
    Request:
        GET /conversation/sess_abc/stream/send?query=What+about+sick+leave%3F

    Response 200 (SSE stream):
        event: node_complete
        data: {"node":"triage",...}

        event: node_complete
        data: {"node":"policy",...}

        event: complete
        data: {"event":"complete","session_id":"sess_abc","turn_number":2,...}
    """
    correlation_id = get_correlation_id(request)

    if not query or not query.strip():
        return error_response(
            message="query is required",
            correlation_id=correlation_id,
            status_code=400,
        )

    session = session_store.get_session(session_id)
    if not session:
        return error_response(
            message="Session not found",
            correlation_id=correlation_id,
            status_code=404,
        )

    return StreamingResponse(
        _stream_events(session_id, query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Correlation-ID": correlation_id,
        },
    )


@router.get("/{session_id}")
async def api_get_session(session_id: str, request: Request):
    """Retrieve a session's full message history and metadata.

    ---
    Request:
        GET /conversation/sess_a1b2c3

    Response 200:
        {
          "success": true,
          "data": {
            "session_id": "sess_a1b2c3",
            "messages": [
              {"role": "user", "content": "What is the leave policy?"},
              {"role": "assistant", "content": "The leave policy allows 15 days...", "node": "policy"}
            ],
            "mode": "advanced",
            "turn_number": 1,
            "total_cost": 0.0023,
            "created_at": "2026-06-13T00:00:00",
            "updated_at": "2026-06-13T00:00:05"
          },
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 404:
        {"success": false, "message": "Session not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    session = session_store.get_session(session_id)
    if not session:
        return error_response(
            message="Session not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    return success_response(
        data={
            "session_id": session["session_id"],
            "messages": session["messages"],
            "mode": session["mode"],
            "turn_number": session["turn_number"],
            "total_cost": round(session["total_cost"], 5),
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
        },
        correlation_id=correlation_id,
    )


@router.delete("/{session_id}")
async def api_delete_session(session_id: str, request: Request):
    """Delete a session and its entire message history.

    ---
    Request:
        DELETE /conversation/sess_a1b2c3

    Response 200:
        {
          "success": true,
          "data": {"id": "sess_a1b2c3"},
          "message": "OK",
          "correlation_id": "abc123"
        }

    Response 404:
        {"success": false, "message": "Session not found", "correlation_id": "abc123"}
    """
    correlation_id = get_correlation_id(request)
    deleted = session_store.delete_session(session_id)
    if not deleted:
        return error_response(
            message="Session not found",
            correlation_id=correlation_id,
            status_code=404,
        )
    return success_response(data={"id": session_id}, correlation_id=correlation_id)


@router.get("")
async def api_list_sessions(request: Request):
    """List recent sessions with summary metadata (no full messages).

    ---
    Request:
        GET /conversation

    Response 200:
        {
          "success": true,
          "data": {
            "sessions": [
              {
                "session_id": "sess_a1b2c3",
                "mode": "advanced",
                "turn_number": 3,
                "message_count": 6,
                "total_cost": 0.0062,
                "updated_at": "2026-06-13T00:05:00",
                "created_at": "2026-06-13T00:00:00"
              }
            ]
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    correlation_id = get_correlation_id(request)
    sessions = session_store.list_sessions()
    return success_response(data={"sessions": sessions}, correlation_id=correlation_id)
