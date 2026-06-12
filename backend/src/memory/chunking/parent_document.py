from backend.src.memory.chunking.base import Chunk, ChunkingStrategy
from backend.src.memory.chunking.recursive import RecursiveChunking


class ParentDocumentChunking(ChunkingStrategy):
    def __init__(
        self,
        parent_chunk_size: int = 1000,
        child_chunk_size: int = 200,
        child_overlap: int = 40,
    ):
        self.parent_chunk_size = parent_chunk_size
        self.child_chunk_size = child_chunk_size
        self.child_overlap = child_overlap
        self._parent_strategy = RecursiveChunking(
            chunk_size=parent_chunk_size, chunk_overlap=0
        )
        self._child_strategy = RecursiveChunking(
            chunk_size=child_chunk_size, chunk_overlap=child_overlap
        )

    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        parents = self._parent_strategy.chunk(text)
        all_chunks = []
        child_idx = 0
        for parent in parents:
            children = self._child_strategy.chunk(parent.text)
            for child in children:
                child.metadata["parent_index"] = parent.index
                child.metadata["parent_text"] = parent.text[:200]
                child.index = child_idx
                all_chunks.append(child)
                child_idx += 1
        return all_chunks
