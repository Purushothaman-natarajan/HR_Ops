"""Supervisor agent that routes queries using LLM classification, semantic cache, and RL bandit feedback."""

import logging
import time
from datetime import datetime, timezone

import numpy as np

from backend.src.agents.state import AgentRole, Activity, SharedState, TraceEntry, TriggerType
from backend.src.intelligence.rl_layer import rl_agent
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.supervisor")

try:
    from backend.src.infrastructure.nvidia_embeddings import NVIDIAEmbeddings
    _SUPERVISOR_ENCODER = NVIDIAEmbeddings(input_type="query")
except ImportError:
    _SUPERVISOR_ENCODER = None


class SupervisorCache:
    """Semantic cache for supervisor classification decisions.

    Caches the LLM classification result so that semantically similar queries
    skip the LLM call entirely. Uses the same embedding model as the vector store.
    """

    def __init__(self, threshold: float = 0.95, ttl_seconds: int = 3600):
        self.threshold = threshold
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, dict] = {}

    async def _embed(self, text: str) -> list[float]:
        if _SUPERVISOR_ENCODER:
            import asyncio
            return await asyncio.to_thread(_SUPERVISOR_ENCODER.embed_query, text)
        return []

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        a_arr = np.array(a)
        b_arr = np.array(b)
        return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-10))

    async def get(self, query: str) -> str | None:
        q_emb = await self._embed(query)
        now = time.time()
        for key, entry in list(self._store.items()):
            if now - entry["ts"] > self.ttl_seconds:
                del self._store[key]
                continue
            sim = self._cosine_sim(q_emb, entry["embedding"])
            if sim >= self.threshold:
                logger.debug("Supervisor cache HIT: query=%.50s agent=%s sim=%.4f", query, entry["agent"], sim)
                return entry["agent"]
        logger.debug("Supervisor cache MISS: query=%.50s", query)
        return None

    async def set(self, query: str, agent: str):
        import hashlib
        key = hashlib.md5(query.encode()).hexdigest()
        q_emb = await self._embed(query)
        self._store[key] = {
            "agent": agent,
            "embedding": q_emb,
            "ts": time.time(),
        }

    def clear(self):
        self._store.clear()


supervisor_cache = SupervisorCache()


async def supervisor_decision(state: SharedState) -> dict:
    """Route a query to the appropriate agent using LLM classification + LinUCB bandit.

    The LLM first classifies the query based on trigger type (reactive → LLM classify,
    scheduled → anomaly, otherwise → compliance). The LinUCB agent then re-ranks the
    decision using context features (query complexity, urgency) to balance exploration
    vs. exploitation. The final agent is written to ``current_agent``."""
    start = datetime.now(timezone.utc)
    trigger = state.trigger_type
    cached_agent = None
    activities = []

    if trigger == TriggerType.REACTIVE:
        activities.append(Activity(
            type="cache_check", label="Checking supervisor cache",
            detail="Comparing query embedding against cached classifications",
            status="completed",
        ))
        cached_agent = await supervisor_cache.get(state.query)
        if cached_agent:
            llm_decision = cached_agent
            reasoning_detail = f"Cache hit: routed to {cached_agent}"
            activities[-1].detail = f"Cache HIT — reusing classification: {cached_agent}"
            logger.debug("Supervisor cache used: query=%.50s -> %s", state.query, llm_decision)
        else:
            activities[-1].detail = "Cache MISS — calling LLM classifier"
            history = state.messages
            history_context = ""
            if history:
                recent = history[-4:]
                history_context = "Conversation history:\n" + "\n".join(
                    f"{m['role']}: {m['content'][:200]}" for m in recent
                ) + "\n\n"

            prompt = (
                f"{history_context}"
                f"Given the HR query below, decide which agent should handle it.\n"
                f"Options:\n"
                f"- policy: questions about HR policies, rules, benefits, guidelines, or general documentation.\n"
                f"- action: queries seeking to retrieve, count, search, or modify employee details, databases, or records.\n"
                f"- anomaly: tasks investigating data discrepancies, outliers, errors, or anomalies. ALSO choose this option for instructions requesting to 'run anomaly detection', 'run scan', 'check for anomalies', or generate anomaly reports across datasets.\n"
                f"- compliance: tasks checking if actions or queries comply with rules/regulations.\n\n"
                f"Query: {state.query}\n"
                f"Reply with exactly one word from the options."
            )
            activities.append(Activity(
                type="llm_call", label="Classifying query with LLM",
                detail=f"Query: {state.query[:80]}...",
                status="running",
            ))
            llm_decision, _ = await llm_call("supervisor", prompt, max_tokens=20, temperature=0)
            llm_decision = llm_decision.strip().lower()
            activities[-1].status = "completed"
            activities[-1].detail = f"LLM classified as: {llm_decision}"
            await supervisor_cache.set(state.query, llm_decision)
            reasoning_detail = f"LLM classified as '{llm_decision}'"
    elif trigger == TriggerType.SCHEDULED:
        llm_decision = "anomaly"
        reasoning_detail = "Scheduled trigger: routed to anomaly"
        activities.append(Activity(
            type="decision", label="Scheduled trigger detected",
            detail="Routing to anomaly agent by default",
            status="completed",
        ))
    else:
        llm_decision = "compliance"
        reasoning_detail = "Default trigger: routed to compliance"
        activities.append(Activity(
            type="decision", label="Default trigger detected",
            detail="Routing to compliance agent by default",
            status="completed",
        ))

    valid = {"policy", "action", "anomaly", "compliance"}
    llm_decision = llm_decision if llm_decision in valid else "policy"
    if llm_decision not in valid:
        reasoning_detail += f" (invalid, defaulted to policy)"

    rl_context = {
        "classification": llm_decision,
        "query": state.query,
        "query_complexity": min(len(state.query) / 200, 1.0),
        "urgent": 1.0 if any(kw in state.query.lower() for kw in ["urgent", "asap", "immediately"]) else 0.0,
    }

    activities.append(Activity(
        type="decision", label="RL bandit re-ranking",
        detail=f"LLM suggested: {llm_decision} — selecting final agent",
        status="running",
    ))
    decision = rl_agent.select_action(rl_context)
    activities[-1].status = "completed"
    activities[-1].detail = f"RL selected: {decision} (LLM suggested: {llm_decision})"
    reasoning_detail += f" | RL bandit selected '{decision}'"

    # Override bandit if LLM detected a specialized system execution task (anomaly or compliance)
    if llm_decision in ("anomaly", "compliance") and decision != llm_decision:
        logger.info("Supervisor override: routing specialized task '%s' directly (bandit chose '%s')", llm_decision, decision)
        decision = llm_decision
        activities.append(Activity(
            type="decision", label="Specialized task override",
            detail=f"Routing directly to '{llm_decision}' instead of bandit's choice '{decision}'",
            status="completed",
        ))

    logger.info(
        "Supervisor routed: query=%s -> final=%s rl=%s llm=%s",
        state.query[:50], decision, rl_context.get("classification"), llm_decision,
    )

    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    return {
        "current_agent": decision,
        "rl_selected_action": decision,
        "rl_context": rl_context,
        "supervisor_cache_hit": cached_agent is not None if trigger == TriggerType.REACTIVE else False,
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="supervisor",
                agent_role=AgentRole.SUPERVISOR,
                input_text=state.query,
                output_text=f"LLM classification: {llm_decision}, RL decision: {decision}",
                timestamp=start,
                duration_ms=elapsed,
                cache_hit=cached_agent is not None if trigger == TriggerType.REACTIVE else False,
                reasoning=reasoning_detail,
                alternatives=[
                    {"agent": agent, "score": getattr(rl_agent, "arm_scores", {}).get(agent, 0)}
                    for agent in ["policy", "action", "anomaly", "compliance"]
                    if hasattr(rl_agent, "arm_scores")
                ],
                activities=activities,
            )
        ],
    }
