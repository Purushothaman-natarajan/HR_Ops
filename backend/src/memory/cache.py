"""Semantic cache for LLM responses that skips the LLM call when a similar query was answered recently.

How it works in real-time:

1. Before calling the LLM, the policy node calls ``semantic_cache.get(query)``
2. The query is embedded using the same SentenceTransformer model
3. Every cached entry is compared via cosine similarity against the query vector
4. If any entry exceeds ``similarity_threshold`` (default 0.95), its cached
   response is returned instantly -- O(n) scan but avoids the LLM call entirely
5. On cache miss, the LLM is called and ``semantic_cache.set(query, response)``
   stores the result for future queries

This is independent of the Chroma vector store -- it is a fast in-memory cache
that saves LLM costs on repeated or near-identical questions.
"""

from __future__ import annotations

import hashlib
import logging
import time

import numpy as np

from backend.config.settings import settings

try:
    from sentence_transformers import SentenceTransformer

    _model_cfg = settings.embed_config.get("embedding", {})
    _ENCODER = SentenceTransformer(_model_cfg.get("model_name", "all-MiniLM-L6-v2"))
except ImportError:
    _ENCODER = None


class SemanticCache:
    """Cache that returns cached responses when semantic similarity exceeds a threshold."""

    def __init__(self):
        cfg = settings.embed_config.get("semantic_cache", {})
        self.threshold = cfg.get("similarity_threshold", 0.95)
        self.ttl_seconds = cfg.get("ttl_seconds", 86400)
        self._store: dict[str, dict] = {}

    def _embed(self, text: str) -> list[float]:
        """Encode text into a normalized embedding vector (384-dim for all-MiniLM-L6-v2)."""
        if _ENCODER:
            emb = _ENCODER.encode(text, normalize_embeddings=True)
            return emb.tolist()
        return []

    def _key(self, query: str) -> str:
        """Deterministic cache key from the raw query string (for dedup, not lookup)."""
        return hashlib.md5(query.encode()).hexdigest()

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        """Cosine similarity between two embedding vectors (1.0 = identical direction)."""
        if not a or not b:
            return 0.0
        a_arr = np.array(a)
        b_arr = np.array(b)
        return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-10))

    def get(self, query: str) -> str | None:
        """Find a cached response whose embedding is above the similarity threshold.

        Returns None on cache miss (caller proceeds to LLM).
        Returns the cached response string on hit (LLM call skipped entirely).
        """
        q_emb = self._embed(query)
        for key, entry in self._store.items():
            if time.time() - entry["ts"] > self.ttl_seconds:
                continue
            sim = self._cosine_sim(q_emb, entry["embedding"])
            if sim >= self.threshold:
                logger.debug("Semantic cache HIT: query=%.50s sim=%.4f", query, sim)
                return entry["response"]
        logger.debug("Semantic cache MISS: query=%.50s", query)
        return None

    def set(self, query: str, response: str):
        """Store a query-response pair for future semantic lookups."""
        self._store[self._key(query)] = {
            "response": response,
            "embedding": self._embed(query),
            "ts": time.time(),
        }

    def invalidate(self, query: str):
        """Remove the cached entry for the given query string."""
        self._store.pop(self._key(query), None)

    def clear(self):
        """Remove all cached entries (used in test teardown)."""
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


logger = logging.getLogger("hr_ops.cache")
semantic_cache = SemanticCache()
