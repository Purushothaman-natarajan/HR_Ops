# Self-Healing HR Ops Platform — Architecture Brief

## Overview
Multi-agent LangGraph system with RL feedback, AG-UI HITL, Langfuse observability, and a React/Vite frontend. Built for Darwinbox AI Engineering Assignment 2026 (Advanced Track).

## Tech Stack
- **Backend:** FastAPI + LangGraph + ChromaDB + Langfuse + DSPy
- **Frontend:** React 18 + Vite + TypeScript
- **LLM Routing:** LiteLLM (per-agent config, cost-aware fallback)
- **Guardrails:** Input (PII/injection/topic), Output (PII/tone/hallucination), Tool (args/schema), Model (cost/timeout)
- **RL:** LinUCB contextual bandit for action routing
- **Prompt Optimization:** DSPy MIPROv2 weekly optimization from HITL feedback

## Architecture
```
User → Supervisor → {Policy, Action, Anomaly, Compliance} → Output
                     ↕                              ↕
                  Semantic Cache              Hard Veto Rules
                     ↕
               ChromaDB (RAG)
```

## Key Components
| Component | Role |
|-----------|------|
| Supervisor | Triage: routes queries to correct sub-agent (RL-augmented) |
| Policy Agent | RAG over HR policy documents; semantic cache backed |
| Action Agent | Executes CRUD tools (lookup, modify, escalate) |
| Anomaly Agent | Statistical outlier detection + LLM narrative |
| Compliance Agent | Hard veto rules + LLM compliance check |
| AG-UI | Human-in-the-Loop protocol for escalation |

## Key Metrics
| Metric | Target |
|--------|--------|
| Cost reduction vs all-GPT-4o | ≥20% (achieved 61%) |
| RL accuracy after 2 cycles | 100% |
| RAG precision@3 | ≥0.85 |

## Data Flow
1. Query enters → Input guardrails check
2. Supervisor routes via RL bandit → Sub-agent
3. Sub-agent runs with retry + guardrails + caching
4. Output guardrails validate → Response returned
5. All events logged to Langfuse + in-memory trace_log

## Project Structure
```
HR_Ops/
├── backend/
│   ├── config/          # Pydantic settings + 6 YAML files
│   ├── src/
│   │   ├── agents/      # Supervisor, nodes, state
│   │   ├── api/         # AG-UI, Trace, Debug routes
│   │   ├── guardrails/  # Input/Output/Tool/Model
│   │   ├── intelligence/# RL, DSPy, Anomaly, Compliance
│   │   ├── memory/      # Chunking, VectorStore, Cache
│   │   ├── tools/       # Schemas, API mocks
│   │   └── utils/       # Model router, Langfuse, AG-UI
│   └── main.py
├── frontend/            # React + Vite + TypeScript
├── scripts/             # DSPy optimizer, RL simulation
├── tests/               # test_standard.py, test_advanced.py
└── docs/                # architecture.md, plan.md, todo.md
```
