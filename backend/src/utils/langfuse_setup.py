"""Langfuse client initialisation with lazy singleton pattern and graceful fallback when credentials are absent."""

import logging
import uuid
from datetime import datetime, timezone

from langfuse import Langfuse
from langfuse.api.ingestion.types.ingestion_event import IngestionEvent_TraceCreate
from langfuse.api.ingestion.types.trace_body import TraceBody

from backend.config.settings import settings

logger = logging.getLogger("hr_ops.langfuse")

_langfuse_client: Langfuse | None = None


def get_langfuse_client() -> Langfuse | None:
    """Return the singleton Langfuse client, initialising it on first call, or None if not configured."""
    global _langfuse_client
    if _langfuse_client is None:
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        else:
            _langfuse_client = None
    return _langfuse_client


def create_trace(trace_name: str, metadata: dict | None = None) -> str:
    """Create a new Langfuse trace with the given name and optional metadata, returning the trace ID.
    Returns an empty string when Langfuse is not configured."""
    client = get_langfuse_client()
    if client is None:
        logger.debug("Langfuse not configured — skipping trace creation for %s", trace_name)
        return ""
    trace_id = str(uuid.uuid4())
    event = IngestionEvent_TraceCreate(
        id=trace_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        body=TraceBody(
            id=trace_id,
            name=trace_name,
            metadata=metadata or {},
        ),
    )
    client.api.ingestion.batch(batch=[event])
    return trace_id
