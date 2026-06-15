"""Policy node: answers HR policy questions using RAG and semantic caching."""

import logging
from datetime import datetime, timezone

from backend.config.settings import settings
from backend.src.agents.state import SharedState, TraceEntry
from backend.src.memory.cache import semantic_cache
from backend.src.memory.vector_store import similarity_search
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.nodes.policy")


async def policy_node(state: SharedState) -> dict:
    """Retrieve relevant policies and generate an answer; checks semantic cache first."""
    start = datetime.now(timezone.utc)
    cache_enabled = settings.feature_flags.get("semantic_cache", {}).get("enabled", True)
    cached = semantic_cache.get(state.query) if cache_enabled else None
    if cached:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return {
            "final_response": cached,
            "messages": state.messages + [
                {"role": "user", "content": state.query},
                {"role": "assistant", "content": cached, "node": "policy"},
            ],
            "trace_log": [
                TraceEntry(
                    node="policy_node", agent_role="policy",
                    input_text=state.query, output_text=cached,
                    timestamp=start, duration_ms=elapsed, cache_hit=True,
                )
            ],
        }
    docs = similarity_search(state.query, k=4)
    reranker_config = settings.embed_config.get("reranker", {})
    rerank_enabled = reranker_config.get("enabled", True)
    retrieval_docs = []
    if rerank_enabled:
        from backend.src.utils.reranker import rerank_documents
        docs = await rerank_documents(state.query, docs, top_k=4)
    for d in (docs or []):
        retrieval_docs.append({
            "source": getattr(d, "metadata", {}).get("source", "unknown"),
            "score": getattr(d, "metadata", {}).get("score", 0.0),
            "chunk": d.page_content[:200],
        })
    context = "\n\n".join(d.page_content for d in docs) if docs else "No policies retrieved."
    prompt = (
        f"Retrieved HR policies:\n{context}\n\n"
        f"User question: {state.query}\n\n"
        f"Provide a concise, policy-backed answer."
    )
    answer, cost = await llm_call("rag", prompt, max_tokens=512)
    if cache_enabled:
        semantic_cache.set(state.query, answer)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    return {
        "retrieved_policies": [d.page_content[:300] for d in (docs or [])],
        "final_response": answer,
        "messages": state.messages + [
            {"role": "user", "content": state.query},
            {"role": "assistant", "content": answer, "node": "policy"},
        ],
        "trace_log": [
            TraceEntry(
                node="policy_node", agent_role="policy",
                input_text=state.query, output_text=answer,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
                cache_hit=False, retrieved_docs=retrieval_docs,
            )
        ],
    }
