from __future__ import annotations

"""Custom exception hierarchy for the HR Ops platform.

Defines typed errors for configuration, graph execution, guardrails,
tool calls, not-found, and validation failures, all rooted in HROpsBaseError.
"""

class HROpsBaseError(Exception):
    """Base exception for all HR Ops platform errors."""

    status_code = 500

    def __init__(self, message: str = "", detail: dict | None = None):
        self.message = message
        self.detail = detail or {}
        super().__init__(self.message)


class ConfigurationError(HROpsBaseError):
    """Raised when configuration is invalid or missing."""


class GraphExecutionError(HROpsBaseError):
    """Raised when LangGraph execution fails."""

    status_code = 500


class GuardrailViolationError(HROpsBaseError):
    """Raised when a guardrail check fails."""

    status_code = 400


class ToolExecutionError(HROpsBaseError):
    """Raised when a tool call fails."""

    status_code = 400


class NotFoundError(HROpsBaseError):
    """Raised when a requested resource is not found."""

    status_code = 404


class ModelNotAvailableError(HROpsBaseError):
    """Raised when the LLM model backend is unavailable (no litellm, missing API key, auth failure).

    This is distinct from generic errors so routes can return a user-friendly
    "contact your administrator" message instead of a raw traceback.
    """

    status_code = 503


class ValidationError(HROpsBaseError):
    """Raised when input validation fails."""

    status_code = 422
