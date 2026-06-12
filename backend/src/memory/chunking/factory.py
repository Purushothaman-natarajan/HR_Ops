from backend.src.memory.chunking.base import ChunkingStrategy
from backend.src.memory.chunking.recursive import RecursiveChunking
from backend.src.memory.chunking.fixed_size import FixedSizeChunking
from backend.src.memory.chunking.semantic import SemanticChunking
from backend.src.memory.chunking.parent_document import ParentDocumentChunking
from backend.src.memory.chunking.agentic import AgenticChunking
from backend.src.memory.chunking.late_chunking import LateChunking
from backend.config.settings import settings


_strategies: dict[str, type[ChunkingStrategy]] = {
    "recursive": RecursiveChunking,
    "fixed_size": FixedSizeChunking,
    "semantic": SemanticChunking,
    "parent_document": ParentDocumentChunking,
    "agentic": AgenticChunking,
    "late_chunking": LateChunking,
}


def get_strategy(name: str | None = None) -> ChunkingStrategy:
    cfg = settings.chunking_config
    default_name = cfg.get("default_strategy", "recursive")
    strategy_name = name or default_name
    strategy_cfg = cfg.get("strategies", {}).get(strategy_name, {})

    cls = _strategies.get(strategy_name)
    if cls is None:
        cls = RecursiveChunking

    try:
        if strategy_name == "recursive":
            return cls(
                chunk_size=strategy_cfg.get("chunk_size", 400),
                chunk_overlap=strategy_cfg.get("chunk_overlap", 80),
                separators=strategy_cfg.get("separators"),
            )
        elif strategy_name == "fixed_size":
            return cls(
                chunk_size=strategy_cfg.get("chunk_size", 300),
                chunk_overlap=strategy_cfg.get("chunk_overlap", 50),
            )
        elif strategy_name == "semantic":
            return cls(
                threshold=strategy_cfg.get("threshold", 0.75),
                min_chunk_size=strategy_cfg.get("min_chunk_size", 100),
                max_chunk_size=strategy_cfg.get("max_chunk_size", 500),
            )
        elif strategy_name == "parent_document":
            return cls(
                parent_chunk_size=strategy_cfg.get("parent_chunk_size", 1000),
                child_chunk_size=strategy_cfg.get("child_chunk_size", 200),
                child_overlap=strategy_cfg.get("child_overlap", 40),
            )
        elif strategy_name == "agentic":
            return cls(
                llm_model=strategy_cfg.get("llm_model", "gpt-4o-mini"),
                max_iterations=strategy_cfg.get("max_iterations", 3),
            )
        elif strategy_name == "late_chunking":
            return cls(
                base_chunk_size=strategy_cfg.get("base_chunk_size", 400),
                overlap=strategy_cfg.get("overlap", 80),
            )
    except Exception:
        pass

    return RecursiveChunking()
