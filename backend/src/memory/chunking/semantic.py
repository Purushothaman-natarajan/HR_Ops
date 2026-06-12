from backend.src.memory.chunking.base import Chunk, ChunkingStrategy
from backend.src.memory.cache import _ENCODER

import numpy as np


class SemanticChunking(ChunkingStrategy):
    def __init__(
        self,
        threshold: float = 0.75,
        min_chunk_size: int = 100,
        max_chunk_size: int = 500,
    ):
        self.threshold = threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        if _ENCODER is None:
            return self._fallback(text)
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return [Chunk(text=text.strip(), index=0)]

        embeddings = _ENCODER.encode(sentences, normalize_embeddings=True)
        chunks = []
        current = []
        current_emb = None
        idx = 0

        for i, (sent, emb) in enumerate(zip(sentences, embeddings)):
            if current_emb is not None:
                sim = float(np.dot(emb, current_emb))
            else:
                sim = 1.0

            current.append(sent)
            current_text = " ".join(current)

            if sim < self.threshold and len(current_text) >= self.min_chunk_size:
                chunks.append(Chunk(text=current_text, index=idx))
                idx += 1
                current = []
                current_emb = None
            else:
                current_emb = emb if current_emb is None else (current_emb + emb) / 2

        if current:
            chunks.append(Chunk(text=" ".join(current), index=idx))

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        import re
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]

    def _fallback(self, text: str) -> list[Chunk]:
        return RecursiveChunking().chunk(text)
