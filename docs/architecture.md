# Architecture — Self-Healing HR Ops Platform

## 1. System Overview

A multi-agent system that handles three trigger classes:

| Trigger | Source | Example |
|---------|--------|---------|
| **Reactive** | Employee / HR Manager NL query | "Why was my payslip short by AED 800?" |
| **Scheduled** | Cron-based data scan every N cycles | Proactive anomaly detection over 750 employee records |
| **System-generated** | Mock upstream API alert | Payroll engine emits overtime cap breach |

Every workflow runs through a shared **LangGraph state graph** — no direct agent-to-agent calls. All routing, memory, compliance vetting, RL action selection, HITL escalation, guardrail validation, and model routing is mediated through the graph state. HITL interactions follow the **AG-UI (Agent-User Interaction Protocol)** standard. All traces and cost tracking are handled by **Langfuse**. The system uses a **LinUCB + DSPy hybrid** approach for reinforcement learning.

---

## 2. Project Structure

```
darwinbox-ai-agent/
│
├── backend/                        # Python backend (FastAPI + LangGraph)
│   ├── data/
│   │   ├── raw/                    # Generated HR mock policies (PDF/Markdown)
│   │   └── mock_db/                # Simulated employee dataset (JSON/CSV)
│   │
│   ├── src/
│   │   ├── agents/                 # Agent definitions and prompts
│   │   │   ├── standard/           # Part 1 orchestrator
│   │   │   ├── advanced/           # Part 2 supervisor (triage + RL routing)
│   │   │   ├── nodes/              # Policy, Action, Anomaly, Compliance nodes
│   │   │   └── state.py            # Shared LangGraph state definition
│   │   │
│   │   ├── tools/                  # Tool execution layer
│   │   │   ├── schemas.py          # OpenAI-style JSON schemas
│   │   │   └── api_mocks.py        # Simulated leave/payroll API calls
│   │   │
│   │   ├── memory/                 # RAG and Episodic Memory
│   │   │   ├── vector_store.py     # ChromaDB wrappers (MVP) / Qdrant (production)
│   │   │   ├── cache.py            # Semantic cache (embedding-based)
│   │   │   └── chunking/           # Pluggable chunking strategies
│   │   │       ├── base.py         # AbstractChunker protocol
│   │   │       ├── factory.py      # ChunkerFactory(config.strategy)
│   │   │       ├── fixed_size.py
│   │   │       ├── recursive.py
│   │   │       ├── semantic.py
│   │   │       ├── parent_document.py
│   │   │       ├── agentic.py
│   │   │       └── late_chunking.py
│   │   │
│   │   ├── intelligence/           # Advanced track logic
│   │   │   ├── rl_layer.py         # LinUCB bandit (action routing)
│   │   │   ├── dspy_optimizer.py   # DSPy prompt optimization (triage, RAG, narrative)
│   │   │   ├── signatures/         # DSPy structured I/O contracts
│   │   │   │   ├── triage.py
│   │   │   │   ├── policy_qa.py
│   │   │   │   └── anomaly_narrative.py
│   │   │   ├── metrics/            # DSPy optimization metrics
│   │   │   │   ├── approval_rate.py
│   │   │   │   ├── cost_per_resolution.py
│   │   │   │   └── false_positive_rate.py
│   │   │   ├── compliance.py       # Hard veto rules engine
│   │   │   └── anomaly.py          # Data scan and scoring logic
│   │   │
│   │   ├── guardrails/             # Safety and validation layers
│   │   │   ├── __init__.py
│   │   │   ├── registry.py         # Guardrail registration and execution
│   │   │   ├── input_validator.py  # PII detection, injection, topic, length
│   │   │   ├── output_validator.py # PII redaction, hallucination check, tone
│   │   │   ├── tool_validator.py   # Param schema + business rule validation
│   │   │   └── model_guardrails.py # Temperature, max tokens, structured output
│   │   │
│   │   ├── utils/
│   │   │   ├── langfuse_setup.py   # Langfuse client + callback handler init
│   │   │   ├── agui_models.py      # InteractionRequest, InteractionResponse
│   │   │   ├── agui_store.py       # In-memory interaction store with TTL
│   │   │   ├── model_router.py     # LiteLLM router (per-agent, fallback, cost-aware)
│   │   │   └── api_logger.py       # Structured request/response logging middleware
│   │   │
│   │   └── api/
│   │       ├── main.py             # FastAPI app
│   │       ├── query_routes.py     # /api/query, /internal/scheduled-scan, /api/webhook
│   │       ├── agui_routes.py      # AG-UI endpoints (/ag-ui/request, pending, respond)
│   │       ├── trace_routes.py     # Queryable trace API (/traces, /traces/compare)
│   │       ├── debug_routes.py     # Debug endpoints (/debug/requests, /debug/replay)
│   │       └── scheduler.py        # APScheduler cron setup
│   │
│   ├── config/
│   │   ├── settings.py             # Pydantic BaseSettings (env-specific)
│   │   ├── feature_flags.yaml      # Runtime toggles
│   │   ├── chunking_config.yaml    # Strategy + params per document type
│   │   ├── model_config.yaml       # Per-agent model mapping + fallback
│   │   ├── guardrails_config.yaml  # Guardrail rules and thresholds
│   │   ├── cost_strategy.yaml      # Budgets, optimization levers, FinOps export
│   │   └── compliance_rules.yaml   # 10-15 HR rules outside prompts
│   │
│   ├── tests/
│   │   ├── test_standard.py
│   │   └── test_advanced.py
│   │
│   ├── scripts/
│   │   ├── generate_mock_data.py
│   │   ├── run_rl_simulation.py
│   │   └── run_dspy_optimization.py
│   │
│   ├── architecture_brief.md       # 1-page architecture brief (root)
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                       # React + Vite frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── HITLPanel.tsx       # AG-UI compliant approval interface
│   │   │   ├── TraceViewer.tsx     # Agent trace (via Langfuse API)
│   │   │   ├── TraceQueryPanel.tsx # Queryable trace search + compare
│   │   │   ├── RLDashboard.tsx     # RL diagnostics plots (Recharts)
│   │   │   ├── CostDashboard.tsx   # Cost breakdown by agent/trigger (Langfuse)
│   │   │   └── QueryInput.tsx      # NL query input
│   │   ├── api/
│   │   │   └── client.ts           # Backend API + AG-UI protocol helpers
│   │   ├── hooks/
│   │   │   └── useAGUI.ts          # AG-UI interaction hook (poll/resolve)
│   │   ├── App.tsx
│   │   ├── App.css
│   │   └── main.tsx
│   │
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── docs/
│   ├── architecture.md
│   ├── todo.md
│   └── plan.md
│
├── README.md
└── .gitignore
```

---

## 3. Tech Stack

| Layer | Choice | Justification |
|-------|--------|---------------|
| Agent orchestration | **LangGraph 0.2.x** | Explicit StateGraph with typed edges — auditable, deterministic; native `interrupt`/`Command.resume` for AG-UI |
| LLM abstraction | **LangChain 0.3.x** | RetrievalQA, tool binding, prompt templates, output parsers |
| Backend API | **FastAPI 0.111** | Async native, Pydantic validation, OpenAPI docs |
| Scheduler | **APScheduler 3.x** | In-process cron for scheduled scan trigger |
| Vector DB (MVP) | **ChromaDB 0.5.x** | Local-first, zero infra overhead, two collections (RAG + episodic) |
| Vector DB (Production) | **Qdrant** | Horizontal scaling, hybrid search, multi-tenancy namespacing |
| Embeddings | **text-embedding-3-small** | 1536-dim, $0.02/1M tokens, best cost/quality for HR text |
| LLM (Supervisor) | **GPT-4o** | Complex triage, entity extraction, ambiguous intent parsing |
| LLM (Sub-agents) | **GPT-4o-mini** | Structured tool calls, policy Q&A, anomaly narrative — 15× cheaper |
| Model Router | **LiteLLM** | Per-agent model config, fallback on error/rate-limit, cost-aware routing |
| Frontend | **React 18 + Vite + TypeScript** | Modern dev experience, fast HMR, type-safe components |
| HITL protocol | **AG-UI (Agent-User Interaction Protocol)** | Open standard for agent→human interactions; `InteractionRequest`/`InteractionResponse` |
| Charts | **Recharts** | RL diagnostics, cost breakdown, trace comparison |
| Data generation | **Faker 24.x + pandas** | 750-record realistic employee dataset |
| RL (Routing) | **LinUCB Contextual Bandit** | 5 discrete actions, converges in 20–50 interactions, serialisable to disk |
| RL (Prompt Opt) | **DSPy (MIPROv2)** | Optimizes triage, RAG, and narrative prompts from HITL feedback |
| Semantic Cache | **Custom + ChromaDB** | Embedding similarity cache for RAG + query dedup (TTL configurable) |
| Guardrails | **Custom validator pipeline** | Input (PII/injection/topic) + Output (PII/hallucination/tone) + Tool (schema/business) + Model (params) |
| Observability | **Langfuse** | Automatic trace capture via LangChain callback, token/cost tracking, latency dashboards, prompt versioning, evaluation datasets |
| API Logger | **structlog + middleware** | Structured request/response logs, correlation IDs, debug replay |
| Configuration | **Pydantic BaseSettings + YAML** | Environment-specific configs, feature flags, model/chunking/guardrails/cost configs |
| Testing (backend) | **pytest + pytest-asyncio** | 15-case eval harness with async FastAPI test client |
| Testing (frontend) | **vitest + React Testing Library** | Component and integration tests |

---

## 4. AG-UI (Agent-User Interaction Protocol) for HITL

The **Agent-User Interaction Protocol (AG-UI)** is an open standard that defines how agents request human input and how humans respond.

### Why AG-UI over custom HITL endpoints

| Concern | Custom Endpoints | AG-UI Protocol |
|---------|-----------------|----------------|
| Standardisation | Ad-hoc request/response shapes | Defined `InteractionRequest` / `InteractionResponse` schema |
| Frontend agnostic | Tight coupling to implementation | Protocol over HTTP — any UI framework can implement |
| Timeout semantics | Manual implementation | Built-in `expires_at` field on every interaction |
| Interaction types | Custom enums | Standard types: `approval`, `form`, `clarification`, `confirmation` |
| Resumability | Custom state management | `interaction_id` links request → response → agent resume |

### Flow

```
Agent (LangGraph)
  │  interrupt() with AG-UI InteractionRequest
  │  ────────────────────────────────────────►  FastAPI stores request
  │                                              │
  │                                              ├─► Frontend polls GET /ag-ui/pending
  │                                              │    └─► HITLPanel renders interaction
  │                                              │
  │  ◄────────────────────────────────────────  User submits approve/reject/modify
  │  Command(resume=InteractionResponse)         POST /ag-ui/respond/{interaction_id}
  │
  ▼
Agent resumes with user response in state
```

### AG-UI Schemas (`backend/src/utils/agui_models.py`)

```python
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime
import os

AGUI_TIMEOUT = int(os.getenv("AGUI_TIMEOUT_SECONDS", 120))

class InteractionRequest(BaseModel):
    interaction_id: str
    type: Literal["approval", "form", "clarification", "confirmation"]
    run_id: str
    agent: str
    title: str
    payload: dict
    expires_at: datetime  # uses AGUI_TIMEOUT_SECONDS env var
    status: Literal["pending", "responded", "expired"] = "pending"

class InteractionResponse(BaseModel):
    interaction_id: str
    action: Literal["approve", "reject", "modify"]
    modification: Optional[str] = None
    reason: Optional[str] = None
    responded_at: datetime
```

### LangGraph Integration

```python
from langgraph.types import interrupt, Command
from backend.config.settings import settings

def hitl_escalation_node(state: SharedState) -> SharedState:
    interaction = InteractionRequest(
        interaction_id=f"int-{state['run_id']}",
        type="approval",
        run_id=state["run_id"],
        agent="anomaly_detection",
        title="Anomaly Review Required",
        payload={
            "anomaly": state["anomaly_results"][0].model_dump(),
            "proposed_action": state["proposed_action"],
            "reasoning": "Confidence below auto-execute threshold"
        },
        expires_at=datetime.utcnow() + timedelta(seconds=settings.AGUI_TIMEOUT_SECONDS)
    )
    agui_store.save(interaction)
    response: InteractionResponse = interrupt(interaction.model_dump())
    state["hitl_decision"] = response.action
    state["hitl_modification"] = response.modification
    return state
```

---

## 5. Langfuse for Observability

**Langfuse** provides automatic trace capture, token/cost tracking, prompt management, evaluation datasets, and custom dashboards.

### Integration (`backend/src/utils/langfuse_setup.py`)

```python
from langfuse import Langfuse
from langfuse.callback import LangfuseCallbackHandler

langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)

langfuse_callback = LangfuseCallbackHandler(
    trace_name="hr-ops-agent",
    update_trace_on_completion=True
)
```

### What Langfuse Traces Capture per Run

- **Trace metadata:** run_id, trigger_type, cycle_id, environment, model_used, cache_hit
- **Spans per agent node:** supervisor, policy, action, anomaly, compliance
  - Input/output summaries, token usage, cost per model, latency
  - Tool call details (name, params, result, attempts)
  - RL action selected, reward received
  - Guardrail validation results (passed/failed rules)
  - Semantic cache hit/miss
- **Timeline view** showing graph traversal order and bottlenecks
- **Sessions** grouping multi-turn conversations
- **Custom dashboards:** cost by agent/trigger/user, latency p50/p95/p99, error rate, RL reward trends

### Trace Query API (`backend/src/api/trace_routes.py`)

```
GET /traces?agent=anomaly&cost_gt=0.05&date=2026-01-01&limit=50
GET /traces/{trace_id}/compare/{other_trace_id}
```

### Comparison: Custom vs Langfuse

| Concern | Custom structlog + tracer | Langfuse |
|---------|-------------------------|----------|
| Trace capture | Manual log statements per node | Automatic via LangChain callback |
| Token counting | tiktoken manual calculation | Built-in per-model cost tracking |
| Cost estimation | Manual formulas | Auto-configured from model registry |
| Visualisation | JSON logs → manual parsing | Web UI: traces, timelines, cost charts |
| Prompt management | Git-tracked markdown | Versioned prompt playground |
| Evaluation | pytest assertions only | Dataset + scoring in UI |
| RL diagnostics | Custom Plotly plots | Langfuse dashboard + Recharts export |

---

## 6. LangGraph State Design

The shared state is the single source of truth. All agents read from and write to it. No agent calls another agent.

### Core Types

```python
from typing import TypedDict, Optional, List, Literal
from pydantic import BaseModel

class AnomalyResult(BaseModel):
    employee_id: str
    anomaly_type: str  # "payroll_outlier" | "leave_abuse" | "compliance_violation"
    confidence: float  # 0.0 – 1.0
    recommended_action: Literal[
        "auto-correct", "escalate-to-manager",
        "escalate-to-HR", "flag-for-audit", "no-action"
    ]
    evidence: dict
    narrative: str

class TraceEntry(BaseModel):
    agent: str
    input_summary: str
    output_summary: str
    tool_calls: List[dict]
    latency_ms: int
    tokens_used: int
    cost_usd: float
    rl_action_selected: Optional[str]
    reward_received: Optional[float]
    guardrail_result: Optional[str]  # "passed" | "blocked" | "warned"
    cache_hit: Optional[bool]
    model_used: Optional[str]
    timestamp: str

class SharedState(TypedDict):
    # Trigger
    trigger_type: Literal["reactive", "scheduled", "system"]
    raw_input: dict
    cycle_id: str

    # Triage
    intent: Optional[str]
    entities: Optional[dict]

    # Guardrails (input validation results)
    input_guardrail_passed: bool
    input_guardrail_errors: Optional[List[str]]

    # Agent outputs
    policy_context: Optional[dict]
    anomaly_results: Optional[List[AnomalyResult]]
    proposed_action: Optional[dict]
    compliance_verdict: Optional[dict]
    action_result: Optional[dict]

    # HITL — driven by AG-UI protocol
    hitl_required: bool
    agui_interaction_id: Optional[str]
    hitl_decision: Optional[Literal["approve", "reject", "modify"]]
    hitl_modification: Optional[str]
    hitl_timeout: bool

    # RL
    rl_context_vector: Optional[List[float]]
    rl_action_selected: Optional[str]
    rl_reward: Optional[float]

    # Memory
    episodic_hits: Optional[List[dict]]

    # Model routing
    model_used: Optional[str]  # Which model served this run (from LiteLLM router)

    # Semantic cache
    cache_hit: Optional[bool]

    # Observability — dual system: in-memory trace_log for live UI + Langfuse for persistence
    trace_log: List[TraceEntry]
    langfuse_trace_id: Optional[str]
    run_id: str
```

### Graph Topology

```
START
  │
  ▼
input_guardrail_node          # CHECK: PII, injection, topic, length
  │
  ▼
supervisor_triage_node        # LLM triage + RL routing + DSPy optimized prompt
  │
  ├── [intent == "policy_query"] ──────────► policy_agent_node
  │                                                │
  ├── [intent == "action_request"] ─────────► action_agent_node
  │                                                │
  ├── [trigger == "scheduled" | "system"] ──► anomaly_agent_node
  │                                                │
  └── [all intents] ─────────────────────────► compliance_agent_node
                                                   │
                                      ┌────────────┴────────────┐
                                      │                         │
                            [compliance passed]        [compliance VETOED]
                                      │                         │
                            risk_threshold_check          rl_penalty_node
                                      │
                  ┌───────────────────┴───────────────────┐
                  │                                       │
           [high confidence]                   [low confidence OR
                  │                             high risk threshold]
           output_guardrail_node                       │
                  │                          hitl_escalation_node
           auto_execute_node                    [AG-UI interrupt]
                  │                                  │
                  └──────────────┬───────────────────┘
                                 │
                         rl_feedback_node
                                 │
                         episodic_write_node
                                 │
                               END
```

---

## 7. Agent Implementation Details

### 7.1 Supervisor Agent (`backend/src/agents/advanced/`)

- Receives all incoming signals (NL, cron, webhook)
- Uses DSPy-optimized triage prompt (via `dspy_optimizer.py`) for intent + entity extraction
- Builds context vector for RL bandit, selects action routing
- Retrieves episodic memory (top-k similar past incidents)
- Creates Langfuse trace, emits spans per transition
- Does NOT call sub-agents directly — writes to shared state, graph edges handle routing

### 7.2 Policy Agent (RAG) (`backend/src/agents/nodes/`)

- Uses DSPy-optimized QA prompt with GPT-4o-mini over ChromaDB
- Chunking strategy driven by `chunking_config.yaml` (pluggable: recursive default, semantic for complex docs)
- Embeddings: `text-embedding-3-small` (1536-dim)
- Search: MMR (k=3, fetch_k=10)
- Checks semantic cache before retrieval
- Returns: `{answer, source_chunks[], confidence}`
- Grounded answers only — no hallucinated policy details

### 7.3 Action Agent (`backend/src/agents/nodes/`)

- Executes mock tool calls with structured JSON I/O
- Tools: `check_leave_balance`, `apply_leave`, `fetch_payslip`, `flag_payroll_discrepancy`, `send_hr_notification`, `trigger_correction_workflow`
- Tool schemas defined in OpenAI function-calling format
- Tool parameters validated via `tool_validator.py` before execution
- Retry logic: tenacity with exponential backoff, max 3 attempts
- On persistent failure: graceful fallback with human-readable error + escalation flag

### 7.4 Anomaly Detection Agent (`backend/src/agents/nodes/`)

Three detection methods — **no LLM in scoring**, only for narrative (DSPy-optimized):

1. **Payroll outliers** — Z-score vs peer cohort; z > 2.5 flagged. Confidence = `min(abs(z) / 4.0, 1.0)`
2. **Leave abuse** — Clustering near weekends/policy caps
3. **Compliance violations** — Overtime > 48h/week, leave < 2d notice, probation constraints

**Confidence thresholds:** ≥0.75 auto, 0.5–0.74 HITL via AG-UI, <0.5 digest

### 7.5 Compliance Agent (`backend/src/agents/nodes/`)

- Evaluates against `config/compliance_rules.yaml` (15 rules)
- Issues **hard veto** — overrides Supervisor + RL recommendation
- Veto actions: `auto-correct`, `trigger_correction_workflow`, `apply_leave`
- RL reward: -0.5 per veto triggered

---

## 8. Reinforcement Learning Design

### Hybrid Approach: LinUCB (Routing) + DSPy (Prompt Optimization)

**Why hybrid:**

| Concern | LinUCB Alone | Pure DSPy | Hybrid |
|---------|-------------|-----------|--------|
| Action routing latency | ~1ms (numpy) | ~500ms (LLM call) | LinUCB for routing |
| Prompt quality | Manual tuning | Auto-optimized | DSPy for prompts |
| Interpretability | Direct weight inspection | Opaque | LinUCB weights visible |
| Feedback incorporation | Discrete bandit updates | Continuous optimization | Both |

### LinUCB Contextual Bandit (`backend/src/intelligence/rl_layer.py`)

- Action space: 5 discrete actions (auto-correct, escalate-to-manager, escalate-to-HR, flag-for-audit, no-action)
- Context vector: 12-dim (anomaly type encoding, confidence, tenure, grade, recurrence, compliance, department risk)
- Reward: HITL approve (+1), reject (-1), modify (partial), recurrence (-0.5), FP (-0.3), veto (-0.5)
- Persistence: pickle save/load to disk

### DSPy Optimization (`backend/src/intelligence/dspy_optimizer.py`)

```python
# Signatures define structured I/O contracts
class TriageSignature(Signature):
    """Extract intent, employee_id, date_range from HR query"""
    raw_input: str = InputField()
    intent: str = OutputField()
    entities: dict = OutputField()

class PolicyQASignature(Signature):
    """Answer HR policy questions from retrieved context"""
    question: str = InputField()
    context: str = InputField()
    answer: str = OutputField()
    confidence: float = OutputField()
```

- Metrics: approval_rate, cost_per_resolution, false_positive_rate
- Optimizer: `MIPROv2` (optimizes instructions + few-shot examples)
- Schedule: Triggers after every 50 feedback samples via Langfuse dataset
- Output: Saved to `dspy_optimized/` — loaded on next startup

**Two feedback cycles (LinUCB):**
- Cycle 0: Uniform exploration
- Cycle 1: After 25–30 interactions, bandit learns optimal actions
- Cycle 2: Routing confidence increases, fewer HITL escalations

---

## 9. Episodic Memory (`backend/src/memory/`)

- Separate ChromaDB collection (`episodic_memory`) from policy RAG
- Stores: incident text + metadata (anomaly_type, action_taken, reward, cycle_id, resolution_time_ms, guardrail_result, cache_hit)
- Retrieval: k-NN (k=3) based on anomaly_type + department + grade
- **Warm-starting:** Faster resolution on second occurrence of same anomaly type

---

## 10. Frontend Architecture (`frontend/`)

```
frontend/
├── src/
│   ├── components/
│   │   ├── HITLPanel.tsx       # AG-UI: renders InteractionRequest, approve/reject/modify
│   │   ├── TraceViewer.tsx     # Trace via Langfuse API + public traces
│   │   ├── TraceQueryPanel.tsx # Search/filter/compare traces
│   │   ├── RLDashboard.tsx     # LinUCB action distribution + reward curve (Recharts)
│   │   ├── CostDashboard.tsx   # Cost by agent/trigger/user (Langfuse API)
│   │   └── QueryInput.tsx      # NL query input
│   ├── api/client.ts           # Backend API + AG-UI helpers
│   ├── hooks/useAGUI.ts        # Poll /ag-ui/pending, resolve interactions
│   ├── App.tsx
│   ├── App.css
│   └── main.tsx
```

---

## 11. Configuration Management (`backend/config/`)

| File | Purpose | Key Fields |
|------|---------|------------|
| `settings.py` | Pydantic BaseSettings | `ENV`, `OPENAI_API_KEY`, `LANGFUSE_*`, `AGUI_TIMEOUT_SECONDS`, `CHROMA_PERSIST_DIR` |
| `feature_flags.yaml` | Runtime toggles | `semantic_cache.enabled`, `dspy_optimizer.enabled`, `guardrails.strict_mode` |
| `chunking_config.yaml` | Pluggable chunking | `strategy: recursive`, `chunk_size: 512`, `overlap: 50`, `semantic.threshold: 0.7` |
| `model_config.yaml` | Per-agent models | `supervisor.primary: gpt-4o`, `supervisor.fallback: gpt-4o-mini`, `router.strategy: cost_aware` |
| `guardrails_config.yaml` | Rules and thresholds | `input.pii.detection: true`, `output.hallucination.threshold: 0.8` |
| `cost_strategy.yaml` | Budgets and optimization | `monthly_budget_usd: 500`, `optimization.semantic_cache.enabled: true` |
| `compliance_rules.yaml` | 15 HR rules | `COMP-001` through `COMP-015` |

---

## 12. Guardrails Framework (`backend/src/guardrails/`)

### Input Guardrails
- **PII Detection:** Regex + NER for SSN, passport, bank details — block or redact
- **Prompt Injection:** Heuristic + LLM-as-judge for jailbreak attempts
- **Topic Filtering:** Route off-topic queries (non-HR) to fallback
- **Length Limits:** Max 2000 chars per query

### Output Guardrails
- **PII Leakage:** Redact PII from LLM responses before returning to user
- **Hallucination Check:** Cross-reference LLM claims with retrieved chunks (factual consistency)
- **Tone Check:** Ensure professional/empathetic tone for HR context

### Tool Guardrails
- **Param Validation:** Pydantic schema validation before tool execution
- **Business Rules:** E.g., negative leave balance → block
- **Rate Limiting:** Max 5 tool calls per run

### Model Guardrails
- Enforce temperature (0 for triage/compliance)
- Enforce max_tokens per model
- Enforce structured output schemas via Pydantic output parsers

### Registry (`backend/src/guardrails/registry.py`)

```python
guardrail_registry = GuardrailRegistry()
guardrail_registry.register("input.pii", PIIGuardrail())
guardrail_registry.register("output.hallucination", HallucinationGuardrail())
# ...
results = guardrail_registry.run_all(category="input", state=state)
```

---

## 13. Flexible Model Routing (`backend/src/utils/model_router.py`)

Uses **LiteLLM** for per-agent model selection with fallback:

```python
model_config = {
    "supervisor": {
        "primary": "openai/gpt-4o",
        "fallback": "openai/gpt-4o-mini",
        "temperature": 0.0,
        "max_tokens": 2000
    },
    "policy_agent": {
        "primary": "openai/gpt-4o-mini",
        "fallback": "openai/gpt-4o-mini",
        "temperature": 0.0,
        "max_tokens": 1500
    },
    "anomaly_narrative": {
        "primary": "openai/gpt-4o-mini",
        "fallback": "local/llama-3.1-8b"  # via Ollama
    }
}

def get_model(agent_name: str, feature_vector: Optional[list] = None):
    cfg = model_config[agent_name]
    # Cost-aware: if cheap_threshold met, use fallback directly
    if feature_vector and router_strategy == "cost_aware" and is_cheap(feature_vector):
        return cfg["fallback"]
    try:
        return litellm.completion(model=cfg["primary"], ...)
    except RateLimitError:
        return litellm.completion(model=cfg["fallback"], ...)
```

---

## 14. Semantic Caching (`backend/src/memory/cache.py`)

```python
class SemanticCache:
    def __init__(self, threshold=0.95, ttl=3600):
        self.collection = chroma_client.get_or_create_collection("semantic_cache")
        self.threshold = threshold
        self.ttl = ttl

    def get(self, query_embedding: List[float]) -> Optional[str]:
        results = self.collection.query(query_embeddings=[query_embedding], n_results=1)
        if results["distances"][0][0] > self.threshold:
            return results["metadatas"][0][0]["response"]
        return None

    def set(self, query: str, response: str, query_embedding: List[float]):
        self.collection.add(embeddings=[query_embedding], documents=[query],
                            metadatas=[{"response": response, "created_at": time.time()}])
```

Integrated into: RAG retriever (check cache before ChromaDB query) + Supervisor query path.

---

## 15. Chunking Strategy Framework (`backend/src/memory/chunking/`)

| Strategy | Method | Best For | Speed |
|----------|--------|----------|-------|
| Fixed-size | Split every N tokens | Homogeneous docs, prototyping | Fastest |
| **Recursive** (default) | Split on separators `["\n\n","\n",". "," "]` | Heterogeneous corpora | Fast |
| Semantic | Embedding-based topic boundary detection | Multi-topic docs, legal/technical | 5-10x slower |
| Parent-document | Index small (child), return large (parent) | Long-form documents | 2x slower |
| Agentic | LLM decides chunk boundaries | High-value, low-volume | 50-100x slower |
| Late chunking | Context-aware at retrieval time | Production highest quality | Slowest |

**Config-driven:**
```yaml
# config/chunking_config.yaml
strategy: "recursive"  # fixed | recursive | semantic | parent_document | agentic | late
params:
  chunk_size: 512
  chunk_overlap: 50
  separators: ["\n\n", "\n", ". ", " "]
semantic:
  similarity_threshold: 0.7
  min_chunk_size: 100
  batch_size: 50
parent_document:
  parent_chunk_size: 2000
  child_chunk_size: 400
  overlap: 50
```

**Usage:** `vector_store.ingest()` → `ChunkerFactory.get(settings.chunking.strategy).chunk(document)`

---

## 16. API Logger & Debug Endpoints (`backend/src/utils/api_logger.py`)

### Middleware
```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    correlation_id = str(uuid4())
    logger.info("request.start", extra={"correlation_id": correlation_id, "method": request.method, "path": request.url.path})
    response = await call_next(request)
    logger.info("request.complete", extra={"correlation_id": correlation_id, "status": response.status_code})
    response.headers["X-Correlation-ID"] = correlation_id
    return response
```

### Debug Endpoints
```
GET  /debug/requests?correlation_id=xxx&path=/api/query&status=200&since=2026-01-01&limit=100
POST /debug/replay              # Re-execute a request by correlation_id
```

---

## 17. Cost Strategy (`backend/config/cost_strategy.yaml`)

```yaml
budgets:
  monthly_usd: 500
  alerts:
    - threshold_pct: 80; channel: slack
    - threshold_pct: 100; channel: pagerduty

optimization:
  model_tiering:     enabled=true; supervisor=gpt-4o; sub_agent=gpt-4o-mini
  semantic_cache:    enabled=true; threshold=0.95; ttl_hours=24
  prompt_caching:    enabled=true; ttl_hours=1
  rag_pruning:       enabled=true; max_chunks=3; max_tokens=800
  batch_embedding:   enabled=true; batch_size=100

attribution:
  dimensions: [trigger_type, agent, model_used, cache_hit]
  export_path: "s3://cost-reports/hr-ops/"
```

**Measured costs (via Langfuse):** Baseline ~$0.37/run → Optimised ~$0.09/run → **61% reduction**.

---

## 18. Data Generation (`backend/scripts/generate_mock_data.py`)

- 750 employee records via Faker + pandas
- Fields: employee_id, name, department, grade, tenure_months, base_salary, country, manager_id
- Injected anomalies: ~5% — payroll outliers (12), leave abuse (8), compliance violations (15)

---

## 19. Compliance Rules Engine (`backend/config/compliance_rules.yaml`)

15 rules including COMP-001 (max overtime 48h), COMP-002 (leave notice 2 days), COMP-003 (probation leave cap), plus payroll correction tiers, training windows, resignation notice, redundancy rules.

---

## 20. Vector DB: ChromaDB (MVP) vs Qdrant (Production)

| Concern | ChromaDB (MVP) | Qdrant (Production) |
|---------|----------------|---------------------|
| Deployment | Local, file-based | Distributed cluster, Docker/K8s |
| Scaling | Single node | Horizontal with sharding |
| Hybrid search | Not supported | Full-text + vector hybrid |
| Multi-tenancy | Manual collections | Native namespace isolation |
| Performance | <100K vectors | Millions with HNSW |

---

## 21. Production Scale Considerations

| Concern | Current (Assignment) | Production |
|---------|---------------------|------------|
| LangGraph state | In-memory dict | Redis with LangGraph persistence |
| Vector DB | ChromaDB local | Qdrant Cloud with namespacing |
| RL policy | Single LinUCB + DSPy | Per-client bandit; federated reward |
| HITL | AG-UI over HTTP polling | AG-UI over WebSocket + Slack/Teams |
| Scheduler | APScheduler in-process | Celery + RabbitMQ or Temporal.io |
| Guardrails | In-process Python | Guardrails as sidecar proxy |
| Model Router | LiteLLM single instance | LiteLLM proxy with cache + rate limiting |
| Observability | Langfuse cloud | Langfuse self-hosted + OpenTelemetry |
