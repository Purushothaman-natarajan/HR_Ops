"""Recursive chunking that splits on descending separator priority."""

from backend.src.memory.chunking.base import Chunk, ChunkingStrategy


class RecursiveChunking(ChunkingStrategy):
    """Chunks text by recursively finding the best separator near the chunk boundary."""

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 80, separators: list[str] | None = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ".", " "]

    async def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Split text into chunks using recursive separator matching."""
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            if end < len(text):
                best_sep = -1
                for sep in self.separators:
                    pos = text.rfind(sep, start, end)
                    if pos > best_sep:
                        best_sep = pos
                if best_sep > start:
                    end = best_sep + len(self.separators[0] if self.separators else "")
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(text=chunk_text, index=idx))
                idx += 1
            start = end - self.chunk_overlap if end < len(text) else len(text)
        return chunks
