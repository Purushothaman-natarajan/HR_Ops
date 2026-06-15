"""NVIDIA nv-embed-v1 embeddings via NVIDIA NIM API."""

from __future__ import annotations

from typing import Any

from langchain_core.embeddings import Embeddings
from openai import OpenAI

from backend.config.settings import settings


class NVIDIAEmbeddings(Embeddings):
    """NVIDIA nv-embed-v1 embeddings using NVIDIA NIM API."""

    def __init__(
        self,
        model: str = "nvidia/nv-embed-v1",
        api_key: str | None = None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        input_type: str = "query",
        truncate: str = "END",
        encoding_format: str = "float",
    ):
        self.model = model
        self.input_type = input_type
        self.truncate = truncate
        self.encoding_format = encoding_format
        self.client = OpenAI(
            api_key=api_key or settings.nvidia_api_key,
            base_url=base_url,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents (passages)."""
        if not texts:
            return []
        response = self.client.embeddings.create(
            input=texts,
            model=self.model,
            encoding_format=self.encoding_format,
            extra_body={"input_type": "passage", "truncate": self.truncate},
        )
        return [d.embedding for d in response.data]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        response = self.client.embeddings.create(
            input=[text],
            model=self.model,
            encoding_format=self.encoding_format,
            extra_body={"input_type": self.input_type, "truncate": self.truncate},
        )
        return response.data[0].embedding

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Async embed a list of documents."""
        if not texts:
            return []
        from openai import AsyncOpenAI
        async_client = AsyncOpenAI(
            api_key=self.client.api_key,
            base_url=self.client.base_url,
        )
        response = await async_client.embeddings.create(
            input=texts,
            model=self.model,
            encoding_format=self.encoding_format,
            extra_body={"input_type": "passage", "truncate": self.truncate},
        )
        return [d.embedding for d in response.data]

    async def aembed_query(self, text: str) -> list[float]:
        """Async embed a single query."""
        from openai import AsyncOpenAI
        async_client = AsyncOpenAI(
            api_key=self.client.api_key,
            base_url=self.client.base_url,
        )
        response = await async_client.embeddings.create(
            input=[text],
            model=self.model,
            encoding_format=self.encoding_format,
            extra_body={"input_type": self.input_type, "truncate": self.truncate},
        )
        return response.data[0].embedding