import logging
from datetime import datetime

from backend.src.agents.state import SharedState, TraceEntry
from backend.src.utils.model_router import llm_call
from backend.src.memory.cache import semantic_cache
from backend.src.memory.vector_store import similarity_search

logger = logging.getLogger("hr_ops.nodes.policy")


def policy_node(state: SharedState) -> dict:
    start = datetime.utcnow()
    cached = semantic_cache.get(state.query)
    if cached:
        elapsed = (datetime.utcnow() - start).total_seconds() * 1000
        return {
            "final_response": cached,
            "trace_log": [
                TraceEntry(
                    node="policy_node", agent_role="policy",
                    input_text=state.query, output_text=cached,
                    timestamp=start, duration_ms=elapsed, cache_hit=True,
                )
            ],
        }
    docs = similarity_search(state.query, k=4)
    context = "\n\n".join(d.page_content for d in docs) if docs else "No policies retrieved."
    prompt = (
        f"Retrieved HR policies:\n{context}\n\n"
        f"User question: {state.query}\n\n"
        f"Provide a concise, policy-backed answer."
    )
    answer, cost = llm_call("rag", prompt, max_tokens=512)
    semantic_cache.set(state.query, answer)
    elapsed = (datetime.utcnow() - start).total_seconds() * 1000
    return {
        "retrieved_policies": [d.page_content[:300] for d in (docs or [])],
        "final_response": answer,
        "trace_log": [
            TraceEntry(
                node="policy_node", agent_role="policy",
                input_text=state.query, output_text=answer,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
                cache_hit=False,
            )
        ],
    }
