"""Fixed-size chunking with configurable overlap between chunks."""

from backend.src.memory.chunking.base import Chunk, ChunkingStrategy


class FixedSizeChunking(ChunkingStrategy):
    """Splits text into fixed-size chunks with optional overlap."""

    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Split text into fixed-length chunks with configurable overlap."""
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(text=chunk_text, index=idx))
                idx += 1
            start += self.chunk_size - self.chunk_overlap
        return chunks
