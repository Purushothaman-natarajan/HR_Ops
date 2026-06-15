"""LLM-driven chunking that asks a model to split text into logical chunks."""

import logging

from backend.src.memory.chunking.base import Chunk, ChunkingStrategy

logger = logging.getLogger("hr_ops.chunking.agentic")


class AgenticChunking(ChunkingStrategy):
    """Uses an LLM to intelligently split text into logical self-contained chunks."""

    def __init__(self, llm_model: str = "gpt-4o-mini", max_iterations: int = 3):
        self.llm_model = llm_model
        self.max_iterations = max_iterations

    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Split text via LLM call, falling back to RecursiveChunking on failure."""
        if len(text) < 200:
            return [Chunk(text=text.strip(), index=0)]
        try:
            from backend.src.utils.model_router import llm_call

            prompt = (
                "Split the following text into logical, self-contained chunks. "
                "Return each chunk separated by '---CHUNK---' on its own line. "
                "Do not add any commentary.\n\n"
                f"{text}"
            )
            response, _ = llm_call(
                agent_name="rag",
                prompt=prompt,
                system_prompt="You are a text chunking assistant.",
                max_tokens=2048,
            )
            parts = [p.strip() for p in response.split("---CHUNK---") if p.strip()]
            if len(parts) <= 1:
                return [Chunk(text=text.strip(), index=0)]
            return [Chunk(text=p, index=i) for i, p in enumerate(parts)]
        except Exception as e:
            logger.warning("AgenticChunking failed, falling back: %s", e)
            from backend.src.memory.chunking.recursive import RecursiveChunking

            return RecursiveChunking().chunk(text)
