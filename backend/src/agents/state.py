from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

class AgentRole(str, Enum):
    SUPERVISOR = "supervisor"
    POLICY = "policy"
    ACTION = "action"
    ANOMALY = "anomaly"
    COMPLIANCE = "compliance"


class TriggerType(str, Enum):
    REACTIVE = "reactive"
    SCHEDULED = "scheduled"
    SYSTEM = "system"


@dataclass
class GuardrailResult:
    guardrail_type: str
    passed: bool
    message: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class AnomalyResult:
    detected: bool
    severity: float  # 0.0 – 1.0
    description: str = ""
    anomaly_field: str = ""
    suggested_action: str = ""
    supporting_data: dict = field(default_factory=dict)


@dataclass
class TraceEntry:
    node: str
    agent_role: AgentRole | str
    input_text: str
    output_text: str
    timestamp: datetime
    duration_ms: float
    guardrail_result: Optional[GuardrailResult] = None
    cache_hit: bool = False
    model_used: str = ""
    cost_usd: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class HITLRequest:
    interaction_id: str
    query: str
    context: dict
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    response: str = ""
    assigned_role: str = "hr_manager"


@dataclass
class SharedState:
    messages: list[dict] = field(default_factory=list)
    query: str = ""
    trigger_type: TriggerType = TriggerType.REACTIVE
    current_agent: AgentRole | str = ""

    trace_log: list[TraceEntry] = field(default_factory=list)
    langfuse_trace_id: str = ""

    hitl_request: Optional[HITLRequest] = None
    hitl_needed: bool = False
    hitl_resolved: bool = False

    anomaly_results: list[AnomalyResult] = field(default_factory=list)
    compliance_veto: bool = False
    compliance_reason: str = ""

    retrieved_policies: list[str] = field(default_factory=list)
    executed_actions: list[str] = field(default_factory=list)
    final_response: str = ""

    rl_context: dict = field(default_factory=dict)
    rl_selected_action: str = ""

    total_cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
