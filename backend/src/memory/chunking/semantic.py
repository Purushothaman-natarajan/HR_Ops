"""Semantic chunking that groups sentences by embedding similarity.

Used during policy ingestion to split documents into coherent chunks
before embedding them into ChromaDB. Sentences whose cosine similarity
falls below the threshold trigger a new chunk boundary.

Uses NVIDIA nv-embed-v1 (via NVIDIA NIM API) for embeddings — ensuring
that chunks, cached queries, and live queries all live in the same vector space.
"""

from __future__ import annotations

import numpy as np

from backend.src.core.settings import settings
from backend.src.memory.chunking.base import Chunk, ChunkingStrategy
from backend.src.memory.chunking.recursive import RecursiveChunking
from backend.src.infrastructure.nvidia_embeddings import NVIDIAEmbeddings

_ENCODER = NVIDIAEmbeddings(input_type="passage")


class SemanticChunking(ChunkingStrategy):
    """Chunks text by grouping sentences whose embeddings are similar above a threshold.

    Threshold, min/max chunk sizes come from nvidia_config.yaml.
    """

    def __init__(
        self,
        threshold: float = 0.75,
        min_chunk_size: int = 100,
        max_chunk_size: int = 500,
    ):
        self.threshold = threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    async def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Split text into semantically coherent chunks using NVIDIA embeddings."""
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return [Chunk(text=text.strip(), index=0)]

        try:
            embeddings = _ENCODER.embed_documents(sentences)
        except Exception:
            return await self._fallback(text)

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
                current_emb = (
                    emb if current_emb is None else (current_emb + emb) / 2
                )

        if current:
            chunks.append(Chunk(text=" ".join(current), index=idx))

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences on sentence-ending punctuation."""
        import re

        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]

    async def _fallback(self, text: str) -> list[Chunk]:
        """Fallback to RecursiveChunking when embeddings are unavailable."""
        return await RecursiveChunking().chunk(text)
