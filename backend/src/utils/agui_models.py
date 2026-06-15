"""Pydantic models for AG-UI (human-in-the-loop) interaction request/response payloads."""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class InteractionRequest(BaseModel):
    """A human-in-the-loop interaction request submitted by an agent, awaiting human decision."""

    interaction_id: str
    query: str
    context: dict = Field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_role: str = "hr_manager"


class InteractionResponse(BaseModel):
    """The human's response payload for a given interaction, attached after the request is resolved."""

    interaction_id: str
    response: str
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)


class PendingRequest(BaseModel):
    """Lightweight projection of a pending interaction used for polling APIs."""

    interaction_id: str
    query: str
    created_at: datetime
    status: str = "pending"
