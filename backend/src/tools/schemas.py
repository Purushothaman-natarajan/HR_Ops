"""Pydantic schemas for tool-call payloads, tool results, and mock-HRIS input/output models."""

from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a parsed tool invocation with a name and keyword arguments."""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Standardised result envelope returned by every tool execution."""

    success: bool
    data: Any = None
    error: str = ""


# ---- Mock tool schemas ----
class LookupEmployeeInput(BaseModel):
    """Input schema for the lookup_employee mock tool."""

    employee_id: str


class LookupEmployeeOutput(BaseModel):
    """Output schema for the lookup_employee mock tool."""

    employee_id: str
    name: str
    department: str
    salary: float
    leave_balance: int
    compliance_status: str


class ModifyRecordInput(BaseModel):
    """Input schema for the modify_record mock tool."""

    employee_id: str
    field: str
    value: Any


class ModifyRecordOutput(BaseModel):
    """Output schema for the modify_record mock tool."""

    success: bool
    message: str


class EscalateToHumanInput(BaseModel):
    """Input schema for the escalate_to_human mock tool."""

    employee_id: str
    reason: str
    context: dict = Field(default_factory=dict)


class EscalateToHumanOutput(BaseModel):
    """Output schema for the escalate_to_human mock tool."""

    ticket_id: str
    status: str
