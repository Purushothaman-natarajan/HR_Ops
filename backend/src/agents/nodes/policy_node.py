"""Policy node: answers HR policy questions using RAG and semantic caching."""

import logging
from datetime import datetime, timezone

from backend.src.core.settings import settings
from backend.src.agents.state import Activity, SharedState, TraceEntry
from backend.src.guardrails.registry import guardrail_registry
from backend.src.memory.cache import semantic_cache
from backend.src.memory.vector_store import similarity_search
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.nodes.policy")


def _check_cache(query: str, cache_enabled: bool, activities: list) -> tuple[str | None, list[float]]:
    """Check semantic cache and return (cached_response, query_embedding).

    Embeds the query once and returns the embedding for reuse in ChromaDB search,
    avoiding a second embedding API call on cache miss.
    """
    activities.append(Activity(
        type="cache_check", label="Checking semantic cache",
        detail="Comparing query against cached policy answers",
        status="completed",
    ))
    if not cache_enabled:
        return None, []
    cached, q_emb = semantic_cache.get_with_embedding(query)
    if cached:
        activities[-1].detail = "Cache HIT — returning cached answer"
    else:
        activities[-1].detail = "Cache MISS — proceeding with RAG retrieval"
    return cached, q_emb


async def _retrieve_and_rerank(query: str, activities: list, query_embedding: list[float] | None = None) -> tuple[list, list]:
    """Retrieve and rerank relevant policies. Uses pre-computed embedding if available."""
    activities.append(Activity(
        type="search", label="Searching vector DB for relevant policies",
        detail=f"Query: {query[:80]}...",
        status="running",
    ))
    docs = similarity_search(query, k=4, query_embedding=query_embedding if query_embedding else None)
    doc_count = len(docs) if docs else 0
    activities[-1].status = "completed"
    activities[-1].detail = f"Found {doc_count} matching documents"
    activities[-1].metadata = {
        "doc_count": doc_count,
        "sources": [getattr(d, "metadata", {}).get("source", "unknown") for d in (docs or [])],
    }

    reranker_config = settings.embed_config.get("reranker", {})
    rerank_enabled = reranker_config.get("enabled", True)
    if rerank_enabled and docs:
        activities.append(Activity(
            type="rerank", label="Reranking retrieved documents",
            detail=f"Reranking {doc_count} documents by relevance",
            status="running",
        ))
        from backend.src.utils.reranker import rerank_documents
        docs = await rerank_documents(query, docs, top_k=4)
        activities[-1].status = "completed"
        activities[-1].detail = f"Reranked to top {len(docs)} documents"

    retrieval_docs = []
    for d in (docs or []):
        retrieval_docs.append({
            "source": getattr(d, "metadata", {}).get("source", "unknown"),
            "score": getattr(d, "metadata", {}).get("score", 0.0),
            "chunk": d.page_content[:200],
        })
    return docs, retrieval_docs


async def _generate_answer(query: str, docs: list, activities: list, history: list) -> tuple[str, float]:
    """Generate answer using LLM."""
    context = "\n\n".join(d.page_content for d in docs) if docs else "No policies retrieved."
    history_context = ""
    if history:
        recent = history[-4:]
        history_context = "Conversation history & Tool execution context:\n" + "\n".join(
            f"{m.get('role', 'unknown')}: {str(m.get('content', ''))[:500]}" for m in recent
        ) + "\n\n"

    prompt = (
        f"{history_context}"
        f"Retrieved HR policies:\n{context}\n\n"
        f"User question: {query}\n\n"
        f"Provide a concise, policy-backed answer using any provided context."
    )
    doc_count = len(docs) if docs else 0
    activities.append(Activity(
        type="llm_call", label="Generating answer with LLM",
        detail=f"Context: {doc_count} policy chunks, max_tokens=512",
        status="running",
    ))
    answer, cost = await llm_call("rag", prompt, max_tokens=512)
    activities[-1].status = "completed"
    activities[-1].detail = f"Generated {len(answer)}-char response"

    # Run output guardrails (soft check — log warnings but don't block)
    output_gr = guardrail_registry.check_output({"text": answer})
    if not output_gr.passed:
        logger.warning("Output guardrail flagged in policy_node: %s", output_gr.message)

    return answer, cost


async def policy_node(state: SharedState) -> dict:
    """Retrieve relevant policies and generate an answer; checks semantic cache first."""
    start = datetime.now(timezone.utc)
    activities = []
    cache_enabled = settings.feature_flags.get("semantic_cache", {}).get("enabled", True)

    cached, q_emb = _check_cache(state.query, cache_enabled, activities)
    if cached:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return {
            "final_response": cached,
            "messages": state.messages + [
                {"role": "user", "content": state.query},
                {"role": "assistant", "content": cached, "node": "policy"},
            ],
            "trace_log": (state.trace_log or []) + [
                TraceEntry(
                    node="policy_node", agent_role="policy",
                    input_text=state.query, output_text=cached,
                    timestamp=start, duration_ms=elapsed, cache_hit=True,
                    activities=activities,
                )
            ],
        }

    docs, retrieval_docs = await _retrieve_and_rerank(state.query, activities, query_embedding=q_emb or None)
    answer, cost = await _generate_answer(state.query, docs, activities, state.messages)

    if cache_enabled:
        semantic_cache.set_with_embedding(state.query, answer, q_emb)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    return {
        "retrieved_policies": [d.page_content[:300] for d in (docs or [])],
        "final_response": answer,
        "messages": state.messages + [
            {"role": "user", "content": state.query},
            {"role": "assistant", "content": answer, "node": "policy"},
        ],
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="policy_node", agent_role="policy",
                input_text=state.query, output_text=answer,
                timestamp=start, duration_ms=elapsed, cost_usd=cost, model_used="model_router",
                cache_hit=False, retrieved_docs=retrieval_docs,
                activities=activities,
            )
        ],
    }
