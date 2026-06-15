# Backend — Self-Healing HR Ops Platform

FastAPI + LangGraph backend with multi-agent orchestration, RL feedback, policy CRUD, multi-turn conversation, and AG-UI HITL.

## Architecture

An interactive SVG diagram of the backend agents and endpoints is available in the [interactive architecture page](file:///c:/Users/purus/learn/HR_Ops/backend/data/architecture.html).


```
FastAPI (main.py)
 ├── /graph         → graph_service.run_graph()   → LangGraph StateGraph
 ├── /conversation  → conversation_service.py      → SessionStore → graph_service
 ├── /policies      → policy_service.py            → File I/O + ChromaDB re-index
 ├── /feedback      → feedback_service.py          → FeedbackStore → rl_agent.update()
 ├── /agui          → agui_store.py                → In-memory interaction store
 ├── /trace         → trace_store.py               → In-memory run history
 └── /debug         → request_store.py             → Request replay
```

## Module Map

| Directory | Purpose |
|-----------|---------|
| `main.py` | FastAPI app factory, middleware, exception handlers, router registration |
| `config/` | Pydantic `Settings` singleton + 7 YAML config files |
| `src/agents/` | `SharedState` dataclass, standard/advanced orchestrators, 5 agent nodes |
| `src/api/` | Route handlers (graph, conversation, policies, feedback, agui, trace, debug) |
| `src/core/` | `APIResponse` envelope, exception hierarchy, `get_correlation_id` |
| `src/guardrails/` | Input/Output/Tool/Model validators + `GuardrailRegistry` |
| `src/intelligence/` | `LinUCBAgent`, DSPy signatures/optimizer, anomaly detector, compliance engine |
| `src/memory/` | ChromaDB vector store, semantic cache, 6 chunking strategies |
| `src/services/` | Business logic: graph, policy, conversation, feedback services |
| `src/repositories/` | `BaseStore` pattern for data access |
| `src/tools/` | Tool schemas (Pydantic) + mock API implementations |
| `src/utils/` | Model router (LiteLLM), Langfuse setup, AG-UI store, trace/request stores, logger |

## How to Add a New API Endpoint

1. Create a new router file in `src/api/` (e.g., `src/api/analytics_routes.py`)
2. Define your endpoints with `APIRouter(prefix="/analytics", tags=["Analytics"])`
3. Use `success_response()` / `error_response()` from `src/core/response.py`
4. Register the router in `backend/main.py`:
   ```python
   from backend.src.api.analytics_routes import router as analytics_router
   app.include_router(analytics_router)
   ```
5. Add the frontend API method in `frontend/src/api/client.ts`

## How to Add a New Agent Node

1. Create a node function in `src/agents/nodes/` following this signature:
   ```python
   def my_node(state: SharedState) -> dict:
       # ... logic ...
       return {"field_to_update": value}
   ```
2. Add the node to the graph in `src/graph.py`:
   ```python
   from backend.src.agents.nodes.my_node import my_node
   workflow.add_node("my_node", my_node)
   workflow.add_edge("previous_node", "my_node")
   ```
3. Optionally add a DSPy signature in `src/intelligence/signatures/`
4. Add model routing config in `config/model_config.yaml`

## Graph Flow

```
                      ┌─────────────────────┐
                      │     Supervisor       │
                      │  (RL or LLM triage)  │
                      └────────┬────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
    ┌──────────┐         ┌──────────┐         ┌──────────┐
    │  Policy  │         │  Action  │         │ Anomaly  │
    │  (RAG)   │         │ (tools)  │         │ (stats)  │
    └────┬─────┘         └────┬─────┘         └────┬─────┘
         │                    │                    │
         ▼                    ▼                    ▼
    ┌──────────────────────────────────────────────────┐
    │         HITL Escalation (if needed) / END        │
    └──────────────────────────────────────────────────┘
```

### Modes
- **Standard**: `StandardOrchestrator` — linear flow, no RL, no triggers
- **Advanced**: `Supervisor` with RL routing, anomaly triggers, compliance veto

## RL Feedback Layer

```
User rating (👍/👎)
       │
       ▼
FeedbackStore.record_feedback()
       │
       ▼
Record in buffer (max RL_BATCH_SIZE)
       │
       ▼
When buffer >= batch_size:
  → FeedbackStore._flush()
  → rl_agent.update(contexts, actions, rewards)
  → rl_agent.save() → data/rl_bandit.pkl
```

### Auto-rewards
- Compliance veto → `reward = -0.5`
- Action executed → `reward = +0.3`
- HITL approval → `reward = +0.5`
- HITL rejection → `reward = -0.3`

## Policy CRUD Service

- **Storage**: Files on disk under `backend/data/policies/`
- **Supported formats**: `.pdf` (via PyMuPDF), `.md`, `.txt`
- **Vector index**: ChromaDB re-indexed automatically after every create/update/delete
- **Endpoints**: `list`, `get`, `download`, `upload` (multipart), `update`, `delete`
- **Authorization**: POST/PUT/DELETE guarded against `user` role (returns 403)

## Multi-Turn Conversation

- **Store**: `SessionStore` — dictionary of session_id → `ConversationSession`
- **Session creation**: `POST /conversation/start` with `mode` (standard|advanced)
- **Turn execution**: `run_turn()` restores prior messages into `SharedState`, runs graph, appends result
- **Persistence**: In-memory; sessions survive until server restart or explicit delete

## Configuration Reference

### Settings (`config/settings.py`)
```python
environment: str = "development"       # "development" | "production"
log_level: str = "INFO"
agui_timeout_seconds: int = 300        # HITL timeout
app_role: str = "admin"                # env var APP_ROLE (overrides YAML)
langfuse_public_key: str = ""          # Langfuse API key
langfuse_secret_key: str = ""          # Langfuse secret key
langfuse_host: str = "https://cloud.langfuse.com"
openai_api_key: str = ""               # Primary LLM provider
anthropic_api_key: str = ""            # Fallback provider
groq_api_key: str = ""                 # Fallback provider
chroma_persist_dir: str = "./data/chroma_db"
rl_alpha: float = 0.1                  # LinUCB exploration
rl_gamma: float = 0.9                  # LinUCB discount
rl_batch_size: int = 10                # Feedback batch threshold
```

### YAML Config Files
| File | Purpose |
|------|---------|
| `feature_flags.yaml` | Toggle guardrails, RL, DSPy, cache, HITL, cost tracking |
| `chunking_config.yaml` | Chunking strategy selection and parameters |
| `model_config.yaml` | Per-agent model routing (primary, fallback, temperature) |
| `guardrails_config.yaml` | Guardrail thresholds and rules |
| `compliance_config.yaml` | Veto rules (COMP-001 through COMP-015) |
| `cost_config.yaml` | Budget limits and cost thresholds |
| `roles_config.yaml` | Role definitions: sections + policy_crud per role |

## Testing

```bash
# Run all tests (83 total)
pytest backend/tests/ -v --tb=short

# Test categories
pytest backend/tests/test_api_endpoints.py -v   # 20 base + policy + role guard
pytest backend/tests/test_conversation.py -v     # 13 multi-turn tests
pytest backend/tests/test_feedback.py -v         # 8 feedback + RL tests

# With coverage
pytest backend/tests/ -v --cov=backend/src --cov-report=term
```

## Key Dependencies

| Package | Use |
|---------|-----|
| `fastapi` | API framework |
| `langgraph` | State graph orchestration |
| `chromadb` | Vector store for RAG |
| `litellm` | Per-agent model routing with fallback |
| `langfuse` | Observability + cost tracking |
| `dspy` | Prompt optimization (MIPROv2) |
| `pymupdf` | PDF text extraction for policies |
| `pydantic-settings` | Config management |
| `tenacity` | Retry logic for tool calls |
| `pyyaml` | YAML config loading |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/index_policies.py` | Index policy files into ChromaDB |
| `scripts/run_rl_simulation.py` | 2-cycle RL bandit simulation |
| `scripts/run_dspy_optimization.py` | Run MIPROv2 prompt optimization |
