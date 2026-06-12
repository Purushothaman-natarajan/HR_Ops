from langfuse import Langfuse
from backend.config.settings import settings

_langfuse_client: Langfuse | None = None


def get_langfuse_client() -> Langfuse:
    global _langfuse_client
    if _langfuse_client is None:
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        else:
            from unittest.mock import MagicMock
            _langfuse_client = MagicMock()
    return _langfuse_client


def create_trace(trace_name: str, metadata: dict | None = None) -> str:
    client = get_langfuse_client()
    trace = client.trace(name=trace_name, metadata=metadata or {})
    return trace.id
