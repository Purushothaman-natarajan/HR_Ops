"""NVIDIA nv-embed-v1 embeddings via NVIDIA NIM API.

Provides both sync and async embedding with a shared async client
for connection pooling (avoids creating a new client per call).
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.embeddings import Embeddings
from openai import OpenAI

from backend.src.core.settings import settings

logger = logging.getLogger("hr_ops.embeddings")

import httpx

# Shared async client singleton for connection pooling
_async_client = None
_async_http_client: httpx.AsyncClient | None = None
_async_client_api_key: str | None = None
_async_client_base_url: str | None = None


def _get_async_client(api_key: str, base_url: str):
    """Return a shared AsyncOpenAI client, creating one only if needed."""
    global _async_client, _async_client_api_key, _async_client_base_url, _async_http_client
    if _async_client is None or _async_client_api_key != api_key or _async_client_base_url != base_url:
        from openai import AsyncOpenAI
        
        timeout = httpx.Timeout(
            connect=10.0,
            read=30.0,
            write=10.0,
            pool=5.0,
        )
        limits = httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=30.0,
        )
        _async_http_client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=True,
        )
        
        _async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=_async_http_client,
        )
        _async_client_api_key = api_key
        _async_client_base_url = base_url
        logger.info("Created shared AsyncOpenAI embedding client (HTTP/2 pooling enabled)")
    return _async_client


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
        self._api_key = api_key or settings.nvidia_api_key
        self._base_url = base_url
        self.client = OpenAI(
            api_key=self._api_key,
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
        """Async embed a list of documents using shared connection-pooled client."""
        if not texts:
            return []
        async_client = _get_async_client(self._api_key, self._base_url)
        response = await async_client.embeddings.create(
            input=texts,
            model=self.model,
            encoding_format=self.encoding_format,
            extra_body={"input_type": "passage", "truncate": self.truncate},
        )
        return [d.embedding for d in response.data]

    async def aembed_query(self, text: str) -> list[float]:
        """Async embed a single query using shared connection-pooled client."""
        async_client = _get_async_client(self._api_key, self._base_url)
        response = await async_client.embeddings.create(
            input=[text],
            model=self.model,
            encoding_format=self.encoding_format,
            extra_body={"input_type": self.input_type, "truncate": self.truncate},
        )
        return response.data[0].embedding
