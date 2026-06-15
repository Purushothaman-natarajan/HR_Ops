"""Abstract base class and data model for all chunking strategies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A single text chunk with its index and optional metadata."""

    text: str
    index: int
    metadata: dict = field(default_factory=dict)


class ChunkingStrategy(ABC):
    """Abstract base class for text chunking strategies."""

    def __init__(self, **kwargs) -> None:
        """Base initializer accepting arbitrary config kwargs."""
        pass

    @abstractmethod
    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Split text into a list of Chunks. Subclasses must implement this."""
        ...
