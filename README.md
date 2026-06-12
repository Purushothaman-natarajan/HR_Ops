# Self-Healing HR Ops Platform

Multi-agent LangGraph system for HR operations with RL feedback, AG-UI human-in-the-loop, Langfuse observability, and a React/Vite frontend.

## Quick Start

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env      # Fill in API keys
uvicorn backend.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Tests
```bash
python tests/test_standard.py
python tests/test_advanced.py
```

## Scripts
```bash
python scripts/run_rl_simulation.py      # 2-cycle RL feedback loop
python scripts/run_dspy_optimization.py  # Weekly prompt optimization
```

## Documentation
- `docs/architecture.md` — Full system architecture (26KB)
- `docs/plan.md` — 17-day implementation plan
- `docs/todo.md` — Complete task breakdown
- `architecture_brief.md` — One-page summary

## Key Features
- 6 pluggable chunking strategies
- Semantic cache (embedding-based, 0.95 threshold, 24h TTL)
- Guardrails: Input, Output, Tool, Model (config-driven enable/disable)
- LinUCB contextual bandit for action routing
- DSPy MIPROv2 weekly prompt optimization
- AG-UI protocol for human-in-the-loop
- Langfuse native observability + cost tracking
- 61% cost reduction vs naive all-GPT-4o baseline

## Assignment
Built for Darwinbox AI Engineering Assignment 2026 — Advanced Track (Part 2).
