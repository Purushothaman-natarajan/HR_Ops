"""Supervisor agent that routes queries using LLM classification, semantic cache, and RL bandit feedback."""

import logging
import time
from datetime import datetime, timezone

import numpy as np

from backend.src.agents.state import AgentRole, SharedState, TraceEntry, TriggerType
from backend.src.intelligence.rl_layer import rl_agent
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.supervisor")

try:
    from sentence_transformers import SentenceTransformer
    _model_cfg = __import__("backend.config.settings", fromlist=["settings"]).settings.embed_config.get("embedding", {})
    _SUPERVISOR_ENCODER = SentenceTransformer(_model_cfg.get("model_name", "all-MiniLM-L6-v2"))
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

    def _embed(self, text: str) -> list[float]:
        if _SUPERVISOR_ENCODER:
            emb = _SUPERVISOR_ENCODER.encode(text, normalize_embeddings=True)
            return emb.tolist()
        return []

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        a_arr = np.array(a)
        b_arr = np.array(b)
        return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-10))

    def get(self, query: str) -> str | None:
        q_emb = self._embed(query)
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

    def set(self, query: str, agent: str):
        import hashlib
        key = hashlib.md5(query.encode()).hexdigest()
        self._store[key] = {
            "agent": agent,
            "embedding": self._embed(query),
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

    if trigger == TriggerType.REACTIVE:
        cached_agent = supervisor_cache.get(state.query)
        if cached_agent:
            llm_decision = cached_agent
            reasoning_detail = f"Cache hit: routed to {cached_agent}"
            logger.debug("Supervisor cache used: query=%.50s -> %s", state.query, llm_decision)
        else:
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
                f"Options: policy, action, anomaly, compliance.\n\n"
                f"Query: {state.query}\n"
                f"Reply with one word."
            )
            llm_decision, _ = await llm_call("supervisor", prompt, max_tokens=20, temperature=0)
            llm_decision = llm_decision.strip().lower()
            supervisor_cache.set(state.query, llm_decision)
            reasoning_detail = f"LLM classified as '{llm_decision}'"
    elif trigger == TriggerType.SCHEDULED:
        llm_decision = "anomaly"
        reasoning_detail = "Scheduled trigger: routed to anomaly"
    else:
        llm_decision = "compliance"
        reasoning_detail = "Default trigger: routed to compliance"

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

    decision = rl_agent.select_action(rl_context)
    reasoning_detail += f" | RL bandit selected '{decision}'"

    logger.info(
        "Supervisor routed: query=%s -> rl=%s llm=%s",
        state.query[:50], decision, llm_decision,
    )

    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    return {
        "current_agent": decision,
        "rl_selected_action": decision,
        "rl_context": rl_context,
        "supervisor_cache_hit": cached_agent is not None if trigger == TriggerType.REACTIVE else False,
        "trace_log": [
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
            )
        ],
    }
