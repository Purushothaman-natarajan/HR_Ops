from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class InteractionRequest(BaseModel):
    interaction_id: str
    query: str
    context: dict = Field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_role: str = "hr_manager"


class InteractionResponse(BaseModel):
    interaction_id: str
    response: str
    resolved_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class PendingRequest(BaseModel):
    interaction_id: str
    query: str
    created_at: datetime
    status: str = "pending"
