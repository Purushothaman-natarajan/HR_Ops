from __future__ import annotations

"""REST endpoints for vector store status monitoring."""

import logging

from fastapi import APIRouter, Request

from backend.config.settings import settings
from backend.src.core.response import get_correlation_id, success_response
from backend.src.memory.vector_store import get_vector_store

logger = logging.getLogger("hr_ops.vector_routes")
router = APIRouter(prefix="/vector-store", tags=["vector-store"])


@router.get("/status")
async def api_vector_status(request: Request):
    """Return vector store collection info, document count, and embedding model."""
    correlation_id = get_correlation_id(request)
    try:
        store = get_vector_store()
        chunk_count = store._collection.count()
        persist = getattr(store, "_persist_directory", str(store._collection._persist_directory) if hasattr(store._collection, "_persist_directory") else "")
        
        # Calculate unique source files in collection
        import os
        data = store._collection.get(include=["metadatas"])
        unique_sources = set()
        if data and data.get("metadatas"):
            for m in data["metadatas"]:
                if m and m.get("source"):
                    unique_sources.add(os.path.basename(m["source"]))
        doc_count = len(unique_sources)

        cfg = settings.embed_config.get("embedding", {})
        return success_response(
            data={
                "available": True,
                "collection": "hr_policies",
                "document_count": doc_count,
                "chunk_count": chunk_count,
                "embedding_model": cfg.get("model_name", "nvidia/nv-embed-v1"),
                "dimension": cfg.get("dimension", 4096),
                "persist_dir": persist,
            },
            correlation_id=correlation_id,
        )
    except Exception as e:
        return success_response(
            data={
                "available": False,
                "error": str(e),
                "collection": "hr_policies",
                "document_count": 0,
                "embedding_model": "unavailable",
                "dimension": 0,
                "persist_dir": "",
            },
            message=f"Vector store unavailable: {e}",
            correlation_id=correlation_id,
        )
