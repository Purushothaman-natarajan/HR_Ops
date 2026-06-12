import hashlib
import json
import time
from typing import Any, Optional

import numpy as np

try:
    from sentence_transformers import SentenceTransformer

    _ENCODER = SentenceTransformer("all-MiniLM-L6-v2")
except ImportError:
    _ENCODER = None


class SemanticCache:
    def __init__(self, threshold: float = 0.95, ttl_seconds: int = 86400):
        self.threshold = threshold
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, dict] = {}

    def _embed(self, text: str) -> list[float]:
        if _ENCODER:
            emb = _ENCODER.encode(text, normalize_embeddings=True)
            return emb.tolist()
        return []

    def _key(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        a = np.array(a)
        b = np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

    def get(self, query: str) -> Optional[str]:
        q_emb = self._embed(query)
        for key, entry in self._store.items():
            if time.time() - entry["ts"] > self.ttl_seconds:
                continue
            sim = self._cosine_sim(q_emb, entry["embedding"])
            if sim >= self.threshold:
                return entry["response"]
        return None

    def set(self, query: str, response: str):
        self._store[self._key(query)] = {
            "response": response,
            "embedding": self._embed(query),
            "ts": time.time(),
        }

    def invalidate(self, query: str):
        self._store.pop(self._key(query), None)

    def clear(self):
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


semantic_cache = SemanticCache()
