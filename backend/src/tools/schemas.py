from pydantic import BaseModel, Field
from typing import Any


class ToolCall(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str = ""


# ---- Mock tool schemas ----
class LookupEmployeeInput(BaseModel):
    employee_id: str


class LookupEmployeeOutput(BaseModel):
    employee_id: str
    name: str
    department: str
    salary: float
    leave_balance: int
    compliance_status: str


class ModifyRecordInput(BaseModel):
    employee_id: str
    field: str
    value: Any


class ModifyRecordOutput(BaseModel):
    success: bool
    message: str


class EscalateToHumanInput(BaseModel):
    employee_id: str
    reason: str
    context: dict = Field(default_factory=dict)


class EscalateToHumanOutput(BaseModel):
    ticket_id: str
    status: str
