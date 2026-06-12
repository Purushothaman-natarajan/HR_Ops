from backend.src.memory.chunking.base import Chunk, ChunkingStrategy
from backend.src.memory.chunking.recursive import RecursiveChunking


class LateChunking(ChunkingStrategy):
    def __init__(self, base_chunk_size: int = 400, overlap: int = 80):
        self.base_chunk_size = base_chunk_size
        self.overlap = overlap
        self._base = RecursiveChunking(
            chunk_size=base_chunk_size, chunk_overlap=overlap
        )

    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        base = self._base.chunk(text)
        merged = []
        i = 0
        while i < len(base):
            current = base[i]
            context_before = base[i - 1].text if i > 0 else ""
            context_after = base[i + 1].text if i + 1 < len(base) else ""
            enriched = current.text
            if context_before:
                enriched = context_before[-100:] + " " + enriched
            if context_after:
                enriched = enriched + " " + context_after[:100]
            merged.append(Chunk(text=enriched.strip(), index=current.index))
            i += 1
        return merged
