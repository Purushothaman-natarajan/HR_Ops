# To-Do List — Self-Healing HR Ops Platform

## 1. Project Scaffold
- [ ] Create full directory structure:
  - `backend/data/raw/`, `backend/data/mock_db/`
  - `backend/src/agents/standard/`, `backend/src/agents/advanced/`, `backend/src/agents/nodes/`
  - `backend/src/tools/`, `backend/src/memory/chunking/`
  - `backend/src/intelligence/signatures/`, `backend/src/intelligence/metrics/`
  - `backend/src/guardrails/`, `backend/src/utils/`, `backend/src/api/`
  - `backend/config/`, `backend/tests/`, `backend/scripts/`
  - `frontend/src/components/`, `frontend/src/api/`, `frontend/src/hooks/`
  - `docs/`
- [ ] Write `backend/requirements.txt` (langchain, langgraph, chromadb, fastapi, pandas, numpy, scipy, faker, openai, langfuse, litellm, dspy, pydantic-settings, tenacity, tiktoken, structlog, python-dotenv, pyyaml, plotly)
- [ ] Create `backend/.env.example`: `OPENAI_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`, `AGUI_TIMEOUT_SECONDS`, `CHROMA_PERSIST_DIR`, `ENV`
- [ ] Create `.gitignore` (venv, `__pycache__`, chroma_store, .env, *.pkl, node_modules, dist, dspy_optimized)
- [ ] Create `README.md`

## 2. Frontend Scaffold (React + Vite + TypeScript)
- [ ] Initialize `frontend/` with Vite: `npm create vite@latest frontend -- --template react-ts`
- [ ] Configure `frontend/vite.config.ts` with proxy for backend API
- [ ] Install dependencies: axios, recharts, react-router-dom
- [ ] Set up `frontend/tsconfig.json` with strict mode

## 3. Config Management
- [ ] Implement `backend/config/settings.py` — Pydantic BaseSettings
- [ ] Create `backend/config/feature_flags.yaml`
- [ ] Create `backend/config/chunking_config.yaml`
- [ ] Create `backend/config/model_config.yaml`
- [ ] Create `backend/config/guardrails_config.yaml`
- [ ] Create `backend/config/cost_strategy.yaml`
- [ ] Create `backend/config/compliance_rules.yaml` (15 rules, COMP-001 to COMP-015)
- [ ] Wire config into all modules: `from backend.config.settings import settings`

## 4. Data Layer
- [ ] Implement `backend/scripts/generate_mock_data.py` — Faker-based 750 employee records
- [ ] Generate CSVs: employees.csv, attendance.csv, payroll.csv, leave_records.csv
- [ ] Create 3–5 page HR policy documents under `backend/data/raw/`
- [ ] Inject ~5% anomalies: payroll outliers (12), leave abuse (8), compliance violations (15)

## 5. Core State & AG-UI Models
- [ ] Implement `backend/src/agents/state.py` — AnomalyResult, TraceEntry, SharedState TypedDict
- [ ] Implement `backend/src/utils/agui_models.py` — InteractionRequest, InteractionResponse
- [ ] Implement `backend/src/utils/agui_store.py` — in-memory interaction store with TTL cleanup
- [ ] Implement LangGraph StateGraph skeleton with all nodes stubbed
- [ ] Implement conditional edge logic (intent → agent, confidence → auto/HITL)

## 6. Part 1 — Standard Assignment
- [ ] Implement `backend/src/agents/standard/orchestrator.py` — core agent loop receiving NL HR requests
- [ ] Route to at least 2 specialized sub-agents (policy lookup via RAG + action execution via mock API)
- [ ] Implement multi-turn conversation state persistence
- [ ] Implement basic trace via Langfuse callback showing: agent name, tool called, inputs, outputs, latency

## 7. Part 1 — RAG Component
- [ ] Implement `backend/src/memory/chunking/` package (7 strategies + factory):
  - `base.py`, `factory.py`, `fixed_size.py`, `recursive.py`, `semantic.py`, `parent_document.py`, `agentic.py`, `late_chunking.py`
- [ ] Implement `backend/src/memory/vector_store.py` — ChromaDB wrapper
- [ ] Embed policy documents using `text-embedding-3-small`
- [ ] Implement confidence scoring on retrieval results

## 8. Part 1 — Tool Use
- [ ] Define OpenAI-style tool schemas in `backend/src/tools/schemas.py`
- [ ] Implement `backend/src/tools/api_mocks.py` — mock API calls with structured JSON I/O
- [ ] Implement retry logic (tenacity, exponential backoff, max 3 attempts)
- [ ] Graceful fallback on persistent failure with escalation flag

## 9. Part 2 — Supervisor Agent
- [ ] Implement triage prompt (DSPy signature) + GPT-4o invocation
- [ ] Build RL context vector from current state
- [ ] Integrate episodic memory retrieval (top-k similar incidents)
- [ ] Create Langfuse trace, emit spans per transition

## 10. Part 2 — Anomaly Detection
- [ ] Implement `backend/src/intelligence/anomaly.py`: payroll outlier (z-score), leave abuse (clustering), compliance violation (rules)
- [ ] Confidence scoring per anomaly (≥0.75 auto, 0.5–0.74 HITL, <0.5 digest)
- [ ] DSPy-optimized narrative generation per anomaly

## 11. Part 2 — Compliance Rules Engine
- [ ] Write `backend/config/compliance_rules.yaml` with 15 rules
- [ ] Implement `backend/src/intelligence/compliance.py` — deterministic rule evaluator
- [ ] Hard veto logic: override Supervisor + RL recommendation on violation
- [ ] RL penalty (-0.5) on veto trigger

## 12. Part 2 — Reinforcement Learning Layer
- [ ] Implement `backend/src/intelligence/rl_layer.py`: LinUCB bandit (select_action, update, save, load)
- [ ] Implement 12-dim context vector builder + composite reward function
- [ ] Bandit persistence: pickle save/load to disk
- [ ] Implement `backend/scripts/run_rl_simulation.py` — 2-cycle feedback loop
- [ ] Generate RL diagnostics: cumulative reward curve + action distribution shift

## 13. Part 2 — DSPy Hybrid Optimization
- [ ] Implement DSPy signatures in `backend/src/intelligence/signatures/`: triage.py, policy_qa.py, anomaly_narrative.py
- [ ] Implement DSPy metrics in `backend/src/intelligence/metrics/`: approval_rate.py, cost_per_resolution.py, false_positive_rate.py
- [ ] Implement `backend/src/intelligence/dspy_optimizer.py` — MIPROv2 optimizer
- [ ] Implement `backend/scripts/run_dspy_optimization.py` — reads Langfuse dataset, runs optimization
- [ ] Integrate DSPy-optimized prompts into Supervisor + Policy + Anomaly agents

## 14. Part 2 — Episodic Memory
- [ ] Implement episodic ChromaDB collection (separate from policy RAG)
- [ ] Store incident context + action + outcome + reward per cycle
- [ ] Implement k-NN retrieval (k=3) for warm-starting
- [ ] Demonstrate faster resolution on second occurrence of same anomaly type

## 15. Guardrails Framework
- [ ] Implement `backend/src/guardrails/registry.py` — guardrail registration + execution
- [ ] Implement `backend/src/guardrails/input_validator.py` — PII detection, prompt injection, topic filtering, length limits
- [ ] Implement `backend/src/guardrails/output_validator.py` — PII redaction, hallucination check, tone check
- [ ] Implement `backend/src/guardrails/tool_validator.py` — param schema validation, business rules, rate limiting
- [ ] Implement `backend/src/guardrails/model_guardrails.py` — temperature, max_tokens, structured output enforcement
- [ ] Integrate guardrails into agent nodes (input → supervisor, output → after action, tool → before execution)
- [ ] Wire guardrail results into SharedState (input_guardrail_passed, input_guardrail_errors)

## 16. Flexible Model Routing
- [ ] Implement `backend/src/utils/model_router.py` — LiteLLM per-agent router with fallback
- [ ] Configure `backend/config/model_config.yaml` with primary/fallback/temperature per agent
- [ ] Implement cost-aware routing strategy (cheap queries → cheaper model)
- [ ] Wire model_router into all agent LLM calls
- [ ] Track `model_used` in SharedState + Langfuse trace metadata

## 17. Semantic Caching
- [ ] Implement `backend/src/memory/cache.py` — embedding similarity cache with TTL
- [ ] Integrate into RAG retriever (check cache before ChromaDB query)
- [ ] Integrate into Supervisor query path (dedup repeated queries)
- [ ] Track `cache_hit` in SharedState + Langfuse trace metadata
- [ ] Configure via `feature_flags.yaml` + `cost_strategy.yaml`

## 18. AG-UI Protocol Implementation
- [ ] Implement AG-UI interaction store (`backend/src/utils/agui_store.py`)
- [ ] Implement AG-UI API endpoints in `backend/src/api/agui_routes.py`:
  - `POST /ag-ui/request`, `GET /ag-ui/pending`, `POST /ag-ui/respond/{id}`, `GET /ag-ui/interaction/{id}`
- [ ] Implement `hitl_escalation_node` using `interrupt()` with AG-UI InteractionRequest
- [ ] Implement resume via `Command(resume=InteractionResponse)`
- [ ] Implement timeout handling: expired flag + safe fallback "flag-for-audit"
- [ ] Implement `frontend/src/hooks/useAGUI.ts` — poll + resolve hook
- [ ] Wire AG-UI wait time as a Langfuse span

## 19. Langfuse Observability Setup
- [ ] Create `backend/src/utils/langfuse_setup.py` — Langfuse client + callback handler
- [ ] Configure `LangfuseCallbackHandler` with `trace_name="hr-ops-agent"`
- [ ] Wire callback into all LangChain/LangGraph invocations
- [ ] Define trace metadata: run_id, trigger_type, cycle_id, model_used, cache_hit, environment
- [ ] Validate cost tracking per model via Langfuse dashboards
- [ ] Create custom Langfuse dashboards: cost by agent/trigger, latency p50/p95/p99, error rate, RL reward trends

## 20. Enhanced Tracing & Debug API
- [ ] Implement `backend/src/api/trace_routes.py`:
  - `GET /traces` — queryable (agent, cost_gt, max_latency_ms, date range, rl_action)
  - `GET /traces/{trace_id}/compare/{other_trace_id}` — side-by-side diff
- [ ] Implement `backend/src/api/debug_routes.py`:
  - `GET /debug/requests` — query request logs by correlation_id, path, status, date
  - `POST /debug/replay` — replay a previous request by correlation_id
- [ ] Implement `backend/src/utils/api_logger.py` — FastAPI middleware with correlation ID

## 21. Frontend — UI Components
- [ ] Build `frontend/src/api/client.ts` — API client (all endpoints)
- [ ] Build `frontend/src/components/QueryInput.tsx` — NL query form
- [ ] Build `frontend/src/components/HITLPanel.tsx` — AG-UI compliant approval interface
- [ ] Build `frontend/src/components/TraceViewer.tsx` — agent trace display
- [ ] Build `frontend/src/components/TraceQueryPanel.tsx` — search/filter/compare traces
- [ ] Build `frontend/src/components/RLDashboard.tsx` — RL diagnostics (Recharts)
- [ ] Build `frontend/src/components/CostDashboard.tsx` — cost breakdown (Recharts + Langfuse API)
- [ ] Wire up `frontend/src/App.tsx` — layout, routing, state management

## 22. Backend API Layer
- [ ] Implement `POST /api/query` (reactive NL requests)
- [ ] Implement `POST /internal/scheduled-scan` (cron trigger)
- [ ] Implement `POST /api/webhook` (system-generated alerts)
- [ ] Implement AG-UI endpoints (see §18)
- [ ] Implement trace + debug endpoints (see §20)
- [ ] Implement APScheduler cron setup
- [ ] Add CORS middleware

## 23. Testing — Evaluation Harness
- [ ] Implement `backend/tests/test_standard.py` — Part 1 test cases
- [ ] Implement `backend/tests/test_advanced.py` — 15 test cases:
  - 1–4: Happy path (reactive leave, payslip, clean scan, webhook)
  - 5–7: Edge cases (missing employee, bad date, zero anomalies)
  - 8–10: Adversarial (prompt injection, malformed payload, compliance veto)
  - 11–12: RAG-specific (hallucination guard, out-of-scope query)
  - 13–15: RL-specific (bandit convergence, DSPy prompt opt, episodic warm-start)
- [ ] Verify Langfuse traces + guardrails active in tests
- [ ] Run full harness: `pytest backend/tests/ -v --tb=short`

## 24. Documentation
- [x] `docs/architecture.md`
- [x] `docs/todo.md`
- [x] `docs/plan.md`
- [ ] `architecture_brief.md` — 1-page brief at repo root
- [ ] `README.md` — setup, architecture diagram, design decisions, cost numbers

## 25. DSPy Optimization Pipeline
- [ ] Run `scripts/run_dspy_optimization.py` weekly cron (triggered after 50 feedback samples)
- [ ] Validate optimized prompts improve approval_rate + reduce cost_per_resolution
- [ ] Save compiled programs to `dspy_optimized/` (gitignored)
- [ ] Wire optimized prompts into agent nodes at startup

## 26. Cost Verification & FinOps
- [ ] Validate monthly cost projections via Langfuse cost dashboards
- [ ] Verify ≥20% reduction (target 61%) against all-GPT-4o baseline
- [ ] Configure Langfuse alerts at 80%/100% budget thresholds
- [ ] Document cost numbers in README

## 27. Submission
- [ ] Clean git history (meaningful commit messages)
- [ ] Loom walkthrough recording (≤10 min): live demo + hardest trade-off + production scale discussion
- [ ] RL before/after comparison (LinUCB action distribution + DSPy prompt quality)
- [ ] Cost optimisation numbers verified via Langfuse dashboards
