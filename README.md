# Self-Healing HR Ops Platform

Multi-agent LangGraph system for HR operations with RL feedback, AG-UI human-in-the-loop, Langfuse observability, policy CRUD, multi-turn conversation, role-based access, and a React/Vite frontend.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                      │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ │
│  │ChatInterf.│ │PolicyMgr │ │HITLPanel │ │RLDashboard│ │More..│ │
│  └─────┬────┘ └─────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┘ │
└────────┼────────────┼────────────┼─────────────┼────────────────┘
         │            │            │             │
         ▼            ▼            ▼             ▼
┌──────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (port 8000)                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Routes: /graph, /conversation, /policies, /feedback,      │ │
│  │          /agui, /trace, /debug, /health                     │ │
│  └─────┬──────────────────────────────────────────────────────┘ │
│        │                                                        │
│        ▼                                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │               LangGraph State Graph                         │ │
│  │                                                             │ │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐              │ │
│  │  │Supervisor│───▶│  Policy  │───▶│  Action  │              │ │
│  │  │(RL-augm.)│    │ (RAG)    │    │ (tools)  │              │ │
│  │  └────┬─────┘    └──────────┘    └──────────┘              │ │
│  │       │                                                     │ │
│  │       ▼                                                     │ │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐              │ │
│  │  │ Anomaly  │    │Compliance│    │  HITL    │              │ │
│  │  │(stats+DSPy│    │ (veto)   │    │ (AG-UI)  │              │ │
│  │  └──────────┘    └──────────┘    └──────────┘              │ │
│  └──────┬─────────────────────────────────────────────────────┘ │
│         │                        │                               │
│         ▼                        ▼                               │
│  ┌──────────────┐       ┌──────────────┐                        │
│  │   ChromaDB   │       │   Langfuse   │                        │
│  │  Vector Store│       │Observability │                        │
│  └──────────────┘       └──────────────┘                        │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Query enters** via `POST /graph/run` or `POST /conversation/send`
2. **Input guardrails** check PII, injection, topic, length
3. **Supervisor agent** classifies intent using RL-augmented routing (LinUCB bandit)
4. **Sub-agent executes** — Policy RAG (ChromaDB), Action tools, Anomaly detection, Compliance check
5. **Output guardrails** validate response (PII, tone, hallucination)
6. **HITL escalation** if confidence below threshold (AG-UI protocol)
7. **Response returned** with full trace metadata and correlation ID

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, FastAPI, LangGraph, LiteLLM, ChromaDB |
| **Frontend** | React 18, TypeScript, Vite, Recharts |
| **LLM** | GPT-4o (primary), Claude-3-Haiku / GPT-4o-mini (fallback per agent) |
| **RL** | LinUCB contextual bandit (4-action, 8-dim context) |
| **Prompt Optimization** | DSPy MIPROv2 (manual / scheduled externally) |
| **HITL** | AG-UI protocol (interrupt/resume) |
| **Observability** | Langfuse-native trace capture, cost tracking, latency monitoring |
| **Vector Store** | ChromaDB with `all-MiniLM-L6-v2` embeddings (384d) |
| **Cache** | Semantic embedding cache (0.95 similarity threshold, no TTL enforcement) |
| **Guardrails** | Input, Output, Tool, Model — 4 categories, config-driven |

## Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent Orchestration** | LangGraph state graph with 6 agents: Supervisor, Policy, Action, Anomaly, Compliance, HITL |
| **RL Routing** | LinUCB contextual bandit selects sub-agent per query; batch update from feedback |
| **Policy Knowledge Base** | Full CRUD: upload/update/delete policies (PDF, MD, TXT), auto-re-index ChromaDB |
| **Multi-Turn Conversation** | Server-side sessions, conversation history restored per turn |
| **Feedback Layer** | Inline 👍/👎 ratings, auto-rewards from compliance/HITL, batch flush to RL bandit |
| **DSPy Optimization** | MIPROv2 weekly prompt optimization from HITL feedback |
| **AG-UI HITL** | Human-in-the-loop via AG-UI protocol with configurable timeout |
| **Guardrails** | PII detection, prompt injection, tone/hallucination check, tool validation, cost limits |
| **RAG** | ChromaDB with 6 pluggable chunking strategies (recursive, semantic, agentic, etc.) |
| **Semantic Cache** | Embedding-similarity cache deduplicates repeated queries |
| **Observability** | Langfuse traces per run with cost, latency, cache hit, guardrail results |
| **Role-Based Access** | Admin/User roles: User loses Observability, Insights, policy edit/delete |
| **Standard & Advanced Modes** | Basic graph (no RL) or Advanced (RL routing + triggers), per-session |

## Quick Start

```bash
# Prerequisites: Python 3.10+, Node.js 18+

# Backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # Fill in API keys
uvicorn backend.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev

# Or one-command launcher
python app.py

# Docker
docker compose -f docker-compose.dev.yml up --build
```

## Project Structure

```
backend/
├── main.py                     # FastAPI entrypoint
├── config/                     # Pydantic settings + YAML configs
│   ├── settings.py             # Centralized Settings singleton
│   ├── feature_flags.yaml      # Feature toggles
│   ├── chunking_config.yaml    # Chunking strategy config
│   ├── model_config.yaml       # Per-agent model routing
│   ├── guardrails_config.yaml  # Guardrail rules
│   ├── compliance_config.yaml  # Compliance veto rules
│   ├── cost_config.yaml        # Cost budgets & thresholds
│   └── roles_config.yaml       # Admin/User role defs
├── src/
│   ├── agents/
│   │   ├── state.py            # SharedState TypedDict, TraceEntry
│   │   ├── standard/           # Basic orchestrator (no RL)
│   │   ├── advanced/           # Supervisor agent with RL routing
│   │   └── nodes/              # policy_node, action_node, anomaly_node,
│   │                           # compliance_node, hitl_escalation_node
│   ├── api/                    # FastAPI route handlers
│   │   ├── graph_routes.py     # POST /graph/run
│   │   ├── conversation_routes.py  # Multi-turn session endpoints
│   │   ├── policy_routes.py    # Policy CRUD endpoints
│   │   ├── feedback_routes.py  # Feedback + RL endpoints
│   │   ├── agui_routes.py      # AG-UI interaction endpoints
│   │   ├── trace_routes.py     # Langfuse trace query
│   │   ├── debug_routes.py     # Request replay
│   │   └── serializers.py      # Response serializers
│   ├── core/                   # Exceptions, response envelope, DI
│   ├── guardrails/             # Input/Output/Tool/Model validators + registry
│   ├── intelligence/           # RL bandit, DSPy signatures/optimizer, anomaly, compliance
│   ├── memory/                 # Vector store, semantic cache, chunking strategies
│   ├── services/               # graph_service, policy_service, conversation_service, feedback_service
│   ├── repositories/           # BaseStore pattern
│   ├── tools/                  # Tool schemas + API mocks (mock employee DB)
│   └── utils/                  # Model router, Langfuse setup, AG-UI store, trace store, logger
├── tests/                      # Pytest suite (79 pytest tests + 8 custom-runner tests)
├── data/                       # ChromaDB persist dir, policy files, RL pickle
└── scripts/                    # Index policies, RL simulation, DSPy optimization

frontend/
├── src/
│   ├── api/client.ts           # All API methods (health, graph, conversation, policies, feedback, RL, etc.)
│   ├── components/             # ChatInterface, PolicyManager, HITLPanel, StatusIndicator,
│   │                           # RLDashboard, TraceViewer, Sidebar, Dashboard, etc.
│   ├── types/index.ts          # TypeScript interfaces (TraceEvent, ConversationSession, etc.)
│   └── App.tsx                 # Root component: sidebar routing + role gating
```

## API Reference

All responses use the standard envelope: `{success, data, message, correlation_id}`.

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Backend health + role info |

### Graph Execution
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/graph/run` | Execute LangGraph with query `{query, mode?}` |

### Conversation (Multi-Turn)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/conversation/start` | Create session `{mode: standard|advanced}` |
| POST | `/conversation/send` | Send message in session `{session_id, query}` |
| GET | `/conversation/{session_id}` | Get session history |
| DELETE | `/conversation/{session_id}` | Delete session |
| GET | `/conversations` | List all sessions |

### Policy Knowledge Base
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/policies` | List all policies |
| GET | `/policies/{id}` | Get policy by ID |
| GET | `/policies/{id}/download` | Download policy file |
| POST | `/policies/upload` | Upload new policy (Admin only) |
| PUT | `/policies/{id}` | Update policy (Admin only) |
| DELETE | `/policies/{id}` | Delete policy (Admin only) |

### Feedback & RL
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/feedback` | Submit rating `{session_id, message_idx, rating, action?}` |
| GET | `/feedback/stats` | Feedback statistics (per-arm rewards, pending buffer) |
| GET | `/feedback/rl/state` | RL bandit internal state |

### AG-UI (HITL)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agui/pending` | List pending interactions |
| POST | `/agui/respond/{id}` | Respond to interaction |
| GET | `/agui/response/{id}` | Get interaction response |
| GET | `/agui/status/{id}` | Check interaction status |

### Traces
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/trace/runs?limit=50` | List trace runs |
| GET | `/trace/runs/{id}` | Get specific trace |
| GET | `/trace/compare?run_ids=a,b` | Compare two traces |

### Debug
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/debug/requests?limit=50` | List recent requests |
| POST | `/debug/replay/{id}` | Replay a previous request |

Interactive docs: [Swagger UI](http://localhost:8000/docs) | [ReDoc](http://localhost:8000/redoc)

## Configuration

### Environment Variables
```
OPENAI_API_KEY=sk-...           # Required
ANTHROPIC_API_KEY=sk-ant-...    # Optional (fallback)
GROQ_API_KEY=gsk-...            # Optional (fallback)
LANGFUSE_PUBLIC_KEY=...         # Optional (observability)
LANGFUSE_SECRET_KEY=...         # Optional (observability)
LANGFUSE_HOST=...               # Optional (self-hosted Langfuse URL)
CHROMA_PERSIST_DIR=...          # Optional (ChromaDB directory, default: ./backend/data/chroma_db)
LOG_LEVEL=INFO                  # Logging verbosity
ENVIRONMENT=development         # development | production
AGUI_TIMEOUT_SECONDS=300        # HITL timeout
APP_ROLE=admin                  # admin | user (env overrides roles_config.yaml)
RL_ALPHA=0.1                    # Bandit exploration
RL_GAMMA=0.9                    # Bandit discount
RL_BATCH_SIZE=10                # Feedback batch before bandit update
```

### Feature Flags (`config/feature_flags.yaml`)
Toggle guardrails, RL, DSPy, semantic cache, HITL, and cost tracking on/off.

### Role-Based Access (`config/roles_config.yaml`)
Defines `sections` (visible UI sections) and `policy_crud` (can edit/delete policies) per role.

## Agent System

| Agent | File | Model | Role |
|-------|------|-------|------|
| **Supervisor** | `backend/src/agents/advanced/supervisor.py` | GPT-4o (Haiku fallback) | Triages queries, RL-augmented routing |
| **Policy** | `backend/src/agents/nodes/policy_node.py` | GPT-4o-mini | RAG over HR policy documents (ChromaDB) |
| **Action** | `backend/src/agents/nodes/action_node.py` | GPT-4o-mini | Executes CRUD tools (lookup, modify, escalate) |
| **Anomaly** | `backend/src/agents/nodes/anomaly_node.py` | GPT-4o (narrative) | Statistical outlier detection + LLM narrative |
| **Compliance** | `backend/src/agents/nodes/compliance_node.py` | GPT-4o-mini | Hard veto rules + LLM compliance check |
| **HITL Escalation** | `backend/src/agents/nodes/hitl_escalation_node.py` | — | AG-UI interrupt for human approval |

### Graph Modes
- **Standard**: Basic linear flow without RL routing or triggers
- **Advanced**: RL-augmented supervisor routing + anomaly/trigger detection

## Guardrails

| Category | Checks |
|----------|--------|
| **Input** | PII detection (SSN, credit card, email), prompt injection, blocked topics, length limits (4096 chars) |
| **Output** | PII redaction, professional tone enforcement, hallucination detection (hedging language) |
| **Tool** | Argument validation (max 2000 chars), whitelist-based allowed tools |
| **Model** | Cost threshold ($0.50/call), timeout threshold (30s) |

All configurable via `config/guardrails_config.yaml` and `config/feature_flags.yaml`.

## RL Feedback Layer

- **Algorithm**: LinUCB contextual bandit with 4-action space (policy/action/anomaly/compliance)
- **Context**: 8-dimensional vector (classification encoding + query features)
- **Feedback**: Inline 👍/👎 ratings + auto-rewards from compliance vetoes and HITL approvals
- **Batch Update**: Accumulates in buffer; calls `rl_agent.update()` after `RL_BATCH_SIZE` (default 10) ratings
- **Persistence**: Auto-loads from `data/rl_bandit.pkl` on import; saves after each batch update

## Security

| Risk | Mitigation | Priority for Production |
|------|-----------|------------------------|
| API keys in env vars | `.env` in `.gitignore` | — |
| Prompt injection | Input guardrails detect injection patterns | P1: Add LLM-as-judge |
| PII leakage | Regex PII detection in input + output guardrails | P2: Add NER-based detection |
| No authentication | Out of scope (inline) | P0: Add JWT or API key auth |
| No rate limiting | Not implemented | P1: Add rate limiting middleware |
| Dependency vulns | Manual review | P2: Regular `pip audit` + `npm audit` |

## Testing

```bash
# Backend (79 pytest tests + 8 custom-runner tests)
pytest backend/tests/ -v --tb=short

# With coverage
cd backend && python -m pytest tests/ -v --cov=src --cov-report=term

# Custom integration tests (direct graph invocation, no API)
cd backend && python tests/test_graph_run.py

# All at once (from repo root)
make test
```

## Deployment

See architecture notes for production considerations:
- Qdrant instead of ChromaDB for vector storage
- Redis-backed LangGraph persistence
- Langfuse self-hosted deployment
- Kubernetes orchestration

### Docker
```bash
# Development
docker compose -f docker-compose.dev.yml up --build

# Production
docker compose up --build
```

### Makefile
```bash
make install    # Install backend + frontend deps
make run        # Start backend
make test       # Run tests
make lint       # Lint with ruff
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Backend won't start | Ensure `.env` has `OPENAI_API_KEY`; run `pip install -r requirements.txt` |
| Frontend can't connect | Ensure backend on port 8000; check `VITE_API_URL` (default empty, proxied via Vite) |
| ChromaDB slow first query | Embeddings load lazily via sentence-transformers (~2-3s delay first call) |
| RL bandit not learning | Ensure `rl.enabled: true` and `rl.learn_mode: true` in feature_flags.yaml |
| Tests fail | Run from repo root: `python -m pytest backend/tests/` |
| Stale uvicorn on :8000 | Check for orphan processes before starting |
