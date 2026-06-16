"""Shared state definitions and data types for the HR agent workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class AgentRole(str, Enum):
    """Roles an agent node can assume within the HR pipeline."""
    SUPERVISOR = "supervisor"
    POLICY = "policy"
    ACTION = "action"
    ANOMALY = "anomaly"
    COMPLIANCE = "compliance"


class TriggerType(str, Enum):
    """Types of triggers that initiate an agent workflow."""
    REACTIVE = "reactive"
    SCHEDULED = "scheduled"
    SYSTEM = "system"


@dataclass
class GuardrailResult:
    """Result of a guardrail check, capturing whether it passed or failed."""

    guardrail_type: str
    passed: bool
    message: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class AnomalyResult:
    """Result of an anomaly detection check on HR data."""

    detected: bool
    severity: float
    confidence_score: float = 0.75
    description: str = ""
    anomaly_field: str = ""
    anomaly_type: str = ""
    suggested_action: str = ""          # kept for backward compat
    recommended_action: str = "flag_for_review"
    supporting_data: dict = field(default_factory=dict)


@dataclass
class Activity:
    """A sub-activity within a node execution (e.g., DB search, tool call, LLM call)."""

    type: str  # "search", "tool_call", "llm_call", "decision", "cache_check", "rerank", "guardrail"
    label: str  # Human-readable label: "Searching vector DB"
    detail: str = ""  # Additional info: "Found 4 documents"
    status: str = "completed"  # "running", "completed", "failed"
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)  # Extra data: doc count, tool args, etc.


@dataclass
class TraceEntry:
    """A single trace log entry recording a node execution in the agent graph."""

    node: str
    agent_role: AgentRole | str
    input_text: str
    output_text: str
    timestamp: datetime
    duration_ms: float
    guardrail_result: GuardrailResult | None = None
    cache_hit: bool = False
    model_used: str = ""
    cost_usd: float = 0.0
    metadata: dict = field(default_factory=dict)
    reasoning: str = ""
    alternatives: list[dict] = field(default_factory=list)
    retrieved_docs: list[dict] = field(default_factory=list)
    tool_call: dict = field(default_factory=dict)
    activities: list[Activity] = field(default_factory=list)


@dataclass
class HITLRequest:
    """A human-in-the-loop escalation request awaiting manual review."""

    interaction_id: str
    query: str
    context: dict
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    response: str = ""
    assigned_role: str = "hr_manager"


@dataclass
class SharedState:
    """Shared state propagated through the LangGraph agent workflow."""

    messages: list[dict] = field(default_factory=list)
    query: str = ""
    session_id: str = ""
    turn_number: int = 0
    trigger_type: TriggerType = TriggerType.REACTIVE
    current_agent: AgentRole | str = ""
    trace_log: list[TraceEntry] = field(default_factory=list)
    langfuse_trace_id: str = ""
    hitl_request: HITLRequest | None = None
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
