"""Cross-encoder re-ranker using NVIDIA's rerank-qa-mistral-4b model.

Re-sorts documents retrieved via cosine similarity using a more accurate
cross-encoder model. Supports configurable timeout and async execution.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.documents import Document

from backend.config.settings import settings

logger = logging.getLogger("hr_ops.reranker")

_RERANK_URL = "https://integrate.api.nvidia.com/v1/ranking"
_DEFAULT_MODEL = "nvidia/rerank-qa-mistral-4b"


def _build_payload(
    query: str,
    documents: list[Document],
    model: str,
) -> dict[str, Any]:
    return {
        "model": model,
        "query": {"text": query},
        "passages": [{"text": d.page_content} for d in documents],
    }


def _parse_rankings(data: dict[str, Any]) -> list[int]:
    """Extract document indices sorted by relevance score descending."""
    rankings = data.get("rankings") or data.get("results") or []
    scored = []
    for r in rankings:
        idx = r.get("index")
        score = r.get("logit") if "logit" in r else r.get("relevance_score", 0)
        if idx is not None:
            scored.append((idx, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [idx for idx, _ in scored]


async def rerank_documents(
    query: str,
    documents: list[Document],
    top_k: int | None = None,
    model: str = _DEFAULT_MODEL,
    timeout: float | None = None,
) -> list[Document]:
    """Re-rank documents using NVIDIA's cross-encoder reranking model with configurable timeout.

    Args:
        query: The original user query.
        documents: Documents retrieved via initial similarity search.
        top_k: Max documents to return (defaults to len(documents)).
        model: NVIDIA model name (e.g. nvidia/rerank-qa-mistral-4b).
        timeout: Max seconds to wait for re-ranking (None = no timeout).
                 Falls back to original order on timeout.

    Returns:
        Re-ranked documents (sorted by relevance score, highest first).
        Falls back to original order on any error or timeout.
    """
    if not documents:
        return documents

    reranker_config = settings.embed_config.get("reranker", {})
    if not reranker_config.get("enabled", True):
        logger.debug("Re-ranking disabled by config — using original order")
        return documents

    api_key = settings.nvidia_api_key
    if not api_key:
        logger.warning("nvidia_api_key not set — skipping re-ranking")
        return documents

    top_k = top_k or len(documents)
    effective_timeout = timeout if timeout is not None else reranker_config.get("timeout_seconds", 2.0)

    import httpx

    payload = _build_payload(query, documents, model)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async def _do_rerank() -> list[Document]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(effective_timeout)) as client:
            resp = await client.post(_RERANK_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        indices = _parse_rankings(data)
        if not indices:
            logger.warning("No rankings returned — using original order")
            return documents

        ranked = [documents[i] for i in indices if i < len(documents)]
        logger.debug(
            "Re-ranked %d docs from %d candidates (model=%s, timeout=%.1fs)",
            len(ranked), len(documents), model, effective_timeout,
        )
        return ranked[:top_k]

    try:
        if effective_timeout > 0:
            return await asyncio.wait_for(_do_rerank(), timeout=effective_timeout)
        return await _do_rerank()
    except asyncio.TimeoutError:
        logger.warning(
            "Re-ranking timed out after %.1fs (model=%s) — using original order",
            effective_timeout, model,
        )
        return documents
    except Exception as exc:
        logger.warning(
            "Re-ranking failed (%s: %s) — using original order",
            type(exc).__name__, exc,
        )
        return documents
