# Implementation Plan — Self-Healing HR Ops Platform

**Total duration:** 17 days across 8 phases

---

## Phase 1: Foundation + Config + API Logger + Guardrails (Input) — Days 1–2

### Goal: Scaffolding, Pydantic config, input guardrails, API logger

| Day | Tasks | Deliverables |
|-----|-------|-------------|
| 1 | Create full directory tree, requirements.txt, .env.example, .gitignore | Scaffold |
| 1 | Implement `backend/config/settings.py` — Pydantic BaseSettings | Centralized config |
| 1 | Create all `config/*.yaml` files (feature_flags, chunking, model, guardrails, cost, compliance) | Config files |
| 1 | Implement `backend/src/utils/api_logger.py` — FastAPI middleware with correlation ID | API logger |
| 2 | Implement `backend/src/guardrails/input_validator.py` — PII detection, prompt injection, topic, length | Input guardrails |
| 2 | Implement `backend/src/guardrails/registry.py` — guardrail registration + execution pipeline | Guardrail registry |
| 2 | Implement `backend/src/agents/state.py` — AnomalyResult, TraceEntry, SharedState (with trace_log, guardrail fields, model_used, cache_hit) | State models |
| 2 | Initialize frontend with Vite + React + TypeScript | Frontend scaffold |

**Verification:** `python backend/config/settings.py` loads correctly. API logger adds `X-Correlation-ID` header. Input guardrail blocks PII test payload.

---

## Phase 2: Langfuse Deep + Model Router + Semantic Cache + RAG — Days 3–4

### Goal: Observability, flexible models, caching, RAG with pluggable chunking

| Day | Tasks | Deliverables |
|-----|-------|-------------|
| 3 | Set up `backend/src/utils/langfuse_setup.py` — Langfuse client + callback handler | Langfuse init |
| 3 | Wire `LangfuseCallbackHandler` into all LangChain invocations | Trace capture |
| 3 | Create Langfuse custom dashboards (cost by agent, latency, error rate, RL rewards) | Dashboards |
| 3 | Implement `backend/src/utils/model_router.py` — LiteLLM per-agent router with fallback | Model router |
| 3 | Wire model_router into all agent LLM calls + track `model_used` in state | Model tracking |
| 4 | Implement `backend/src/memory/cache.py` — semantic cache with TTL + similarity threshold | Semantic cache |
| 4 | Implement `backend/src/memory/chunking/` package (base.py, factory.py, recursive.py, fixed_size.py, semantic.py, parent_document.py, agentic.py, late_chunking.py) | Chunking framework |
| 4 | Implement `backend/src/memory/vector_store.py` — ChromaDB wrapper | Vector store |
| 4 | Embed policies with text-embedding-3-small, implement RetrievalQA | RAG agent |
| 4 | Wire semantic cache into RAG retriever + supervisor query path | Cache integration |

**Verification:** Langfuse trace visible. Model router falls back on rate-limit. Semantic cache returns cached results for repeated queries. Chunking strategy configurable via YAML.

---

## Phase 3: Standard Assignment + Guardrails (Output/Tool/Model) — Days 5–6

### Goal: Part 1 deliverables, remaining guardrails

| Day | Tasks | Deliverables |
|-----|-------|-------------|
| 5 | Implement `backend/src/agents/standard/orchestrator.py` — core agent loop | Orchestrator |
| 5 | Define tool schemas in `backend/src/tools/schemas.py` | Tool schemas |
| 5 | Implement `backend/src/tools/api_mocks.py` — mock API calls | API mocks |
| 5 | Implement retry logic + graceful fallback | Reliability |
| 5 | Implement multi-turn conversation state persistence | Conversation memory |
| 6 | Implement `backend/src/guardrails/output_validator.py` — PII redaction, hallucination check, tone | Output guardrails |
| 6 | Implement `backend/src/guardrails/tool_validator.py` — param schema + business rules + rate limiting | Tool guardrails |
| 6 | Implement `backend/src/guardrails/model_guardrails.py` — temperature, max_tokens, structured output | Model guardrails |
| 6 | Wire guardrails into agent nodes: input → supervisor, tool → before execution, output → before response | Guardrail integration |

**Verification:** Send "Apply for 3 days leave starting June 15" → orchestrator routes → tools execute with retry → output guardrail checks response. PII blocked.

---

## Phase 4: Advanced Agents + Graph + Compliance — Days 7–8

### Goal: All Part 2 agents wired into LangGraph

| Day | Tasks | Deliverables |
|-----|-------|-------------|
| 7 | Implement `backend/src/agents/advanced/supervisor.py` — triage + entity extraction | Supervisor |
| 7 | Implement `backend/src/agents/nodes/policy_node.py`, `action_node.py` | Agent nodes |
| 7 | Implement `backend/src/intelligence/compliance.py` + `backend/src/agents/nodes/compliance_node.py` | Compliance |
| 8 | Implement `backend/src/intelligence/anomaly.py` — z-score, clustering, rules | Anomaly scorer |
| 8 | Implement `backend/src/agents/nodes/anomaly_node.py` + DSPy-optimized narrative | Anomaly node |
| 8 | Build LangGraph StateGraph — wire all nodes + conditional edges | Graph topology |
| 8 | Verify Langfuse spans + guardrails active in all nodes | Verification |

**Verification:** Full end-to-end flow. Langfuse shows 5 agent spans + guardrail results. Compliance veto stops invalid actions.

---

## Phase 5: RL + DSPy + Memory + Chunking — Days 9–10

### Goal: LinUCB bandit, DSPy signatures, episodic memory, chunking config

| Day | Tasks | Deliverables |
|-----|-------|-------------|
| 9 | Implement `backend/src/intelligence/rl_layer.py` — LinUCB bandit | Bandit |
| 9 | Implement 12-dim context vector + composite reward function | RL core |
| 9 | Bandit persistence: pickle save/load | Persistence |
| 9 | Implement `backend/src/intelligence/signatures/` — triage.py, policy_qa.py, anomaly_narrative.py | DSPy signatures |
| 9 | Implement `backend/src/intelligence/metrics/` — approval_rate, cost_per_resolution, false_positive_rate | DSPy metrics |
| 10 | Implement `backend/src/intelligence/dspy_optimizer.py` — MIPROv2 optimizer | DSPy optimizer |
| 10 | Implement `backend/scripts/run_dspy_optimization.py` — reads Langfuse dataset, runs optimization | DSPy script |
| 10 | Implement episodic ChromaDB collection + k-NN retrieval | Episodic memory |
| 10 | Wire DSPy-optimized prompts into Supervisor + Policy + Anomaly agents | Prompt integration |
| 10 | Wire chunking_config.yaml into vector_store.ingest() | Chunking config |

**Verification:** `python scripts/run_rl_simulation.py --cycles 2` → action distribution shifts. DSPy optimization produces improved prompts.

---

## Phase 6: AG-UI + HITL + Cost Strategy — Days 11–12

### Goal: Human-in-the-loop, interaction store, cost budgets

| Day | Tasks | Deliverables |
|-----|-------|-------------|
| 11 | Implement `backend/src/utils/agui_models.py`, `backend/src/utils/agui_store.py` | AG-UI store |
| 11 | Implement `backend/src/api/agui_routes.py` — /ag-ui/request, pending, respond, interaction | AG-UI endpoints |
| 11 | Implement `hitl_escalation_node` using `interrupt()` + `Command(resume=...)` | AG-UI interrupt |
| 12 | Implement timeout handling: expired flag + safe fallback | Timeout logic |
| 12 | Implement `frontend/src/hooks/useAGUI.ts` — poll + resolve hook | AG-UI hook |
| 12 | Wire AG-UI wait time as Langfuse span | HITL trace |
| 12 | Configure `backend/config/cost_strategy.yaml` — budgets, alerts, attribution, FinOps export | Cost config |
| 12 | Set up Langfuse cost dashboards + alerts at 80%/100% | Cost monitoring |

**Verification:** Send query → agent hits threshold → AG-UI interaction created → frontend polls → user approves → agent resumes. Cost alert fires at 80% budget.

---

## Phase 7: Frontend + Trace API + Debug Endpoints — Days 13–14

### Goal: All UI components, trace query, debug endpoints

| Day | Tasks | Deliverables |
|-----|-------|-------------|
| 13 | Build `frontend/src/api/client.ts` — all endpoints | API client |
| 13 | Build `frontend/src/components/QueryInput.tsx` — NL query form | Query input |
| 13 | Build `frontend/src/components/HITLPanel.tsx` — AG-UI approval interface | HITL panel |
| 13 | Build `frontend/src/components/TraceViewer.tsx` — trace display | Trace viewer |
| 13 | Build `frontend/src/components/TraceQueryPanel.tsx` — search/filter/compare traces | Trace query |
| 14 | Build `frontend/src/components/RLDashboard.tsx` — RL charts using Recharts | RL dashboard |
| 14 | Build `frontend/src/components/CostDashboard.tsx` — cost breakdown using Recharts | Cost dashboard |
| 14 | Wire up `frontend/src/App.tsx` — layout, routing, state management | App shell |
| 14 | Implement `backend/src/api/trace_routes.py` — /traces, /traces/compare | Trace API |
| 14 | Implement `backend/src/api/debug_routes.py` — /debug/requests, /debug/replay | Debug API |
| 14 | Implement APScheduler + CORS | Scheduler + CORS |

**Verification:** `cd frontend && npm run dev` → all 6 components render. Trace query returns filtered results. Debug replay works.

---

## Phase 8: Testing, DSPy Pipeline, Documentation, Polish — Days 15–17

### Goal: Evaluation harness, DSPy cron, docs, Loom

| Day | Tasks | Deliverables |
|-----|-------|-------------|
| 15 | Implement `backend/tests/test_standard.py` + `backend/tests/test_advanced.py` (15 cases) | Test suite |
| 15 | Verify Langfuse traces + guardrails active during tests | Test verification |
| 15 | Run full harness: `pytest backend/tests/ -v --tb=short` | Pass/fail |
| 16 | Set up `backend/scripts/run_dspy_optimization.py` as weekly cron (triggered after 50 samples) | DSPy cron |
| 16 | Validate optimized prompts improve metrics | DSPy validation |
| 16 | Write `architecture_brief.md` — 1-page brief | Architecture brief |
| 16 | Finalize `README.md` — ASCII diagram, setup, trade-offs, cost numbers | README |
| 17 | Review git history — meaningful commits | Clean history |
| 17 | Record Loom walkthrough (≤10 min) | Loom video |
| 17 | Buffer for any cleanup or bug fixes | Buffer |

**Verification:** All 15 tests pass. Langfuse shows traces for each test. DSPy optimized prompts loaded on startup. Cost numbers documented.
