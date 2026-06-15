"""Standardized API response envelope (success_response, error_response) and correlation ID helpers.

All API endpoints return responses through these helpers to ensure a consistent
{success, data, message, correlation_id} format across the entire platform.
"""

from __future__ import annotations

import uuid
from typing import Any, TypeVar

from fastapi import Request
from fastapi.responses import JSONResponse

T = TypeVar("T")


class APIResponse:
    """Standardized API response envelope.

    All API responses should use this format:
    {
        "success": true,
        "data": {},
        "message": "",
        "correlation_id": ""
    }
    """

    def __init__(
        self,
        success: bool,
        data: Any = None,
        message: str = "",
        correlation_id: str = "",
    ):
        self.success = success
        self.data = data
        self.message = message
        self.correlation_id = correlation_id

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "correlation_id": self.correlation_id,
        }


def success_response(
    data: Any = None,
    message: str = "OK",
    correlation_id: str = "",
) -> dict:
    """Returns a standardized success envelope dictionary.

    Args:
        data: Payload to include in the response.
        message: Human-readable status message.
        correlation_id: Request correlation ID for tracing.

    Returns:
        dict: Standard {success, data, message, correlation_id} envelope.
    """
    return APIResponse(
        success=True, data=data, message=message, correlation_id=correlation_id
    ).to_dict()


def error_response(
    message: str = "An error occurred",
    correlation_id: str = "",
    status_code: int = 500,
    data: Any = None,
) -> JSONResponse:
    """Returns a standardized error JSON response.

    Args:
        message: Human-readable error description.
        correlation_id: Request correlation ID for tracing.
        status_code: HTTP status code (default 500).
        data: Optional error payload.

    Returns:
        JSONResponse: FastAPI JSON response with the error envelope.
    """
    content = APIResponse(
        success=False, data=data, message=message, correlation_id=correlation_id
    ).to_dict()
    return JSONResponse(status_code=status_code, content=content)


def get_correlation_id(request: Request | None) -> str:
    """Extracts the correlation ID from the request header or generates a new one.

    Args:
        request: The incoming FastAPI request, or None if unavailable.

    Returns:
        str: Correlation ID from X-Correlation-ID header or a new UUID fragment.
    """
    if request is None:
        return str(uuid.uuid4())[:12]
    return request.headers.get("X-Correlation-ID", str(uuid.uuid4())[:12])
