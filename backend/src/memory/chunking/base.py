from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Chunk:
    text: str
    index: int
    metadata: dict = field(default_factory=dict)


class ChunkingStrategy(ABC):
    @abstractmethod
    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        ...
