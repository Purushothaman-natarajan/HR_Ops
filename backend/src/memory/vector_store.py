"""ChromaDB vector store — embed + index + similarity search for RAG.

How embedding works in real-time with agents:

1. A user asks "What is the leave policy?"
2. The triage agent classifies the intent as "policy"
3. The policy node calls similarity_search(query) which:
   a) Embeds the query using SentenceTransformer (all-MiniLM-L6-v2 → 384-dim vector)
   b) Searches ChromaDB for the top-k nearest vectors via cosine similarity
   c) Returns the original document texts of the closest matches
4. Those policy texts are injected into the LLM prompt as context
5. The LLM generates a grounded answer — this is Retrieval-Augmented Generation

The embedding model is loaded once (lazy singleton) and shared across
all agent nodes within the process. See backend/config/embed_config.yaml
for tunable parameters.
"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from backend.config.settings import settings

logger = logging.getLogger("hr_ops.vector_store")

_EMBEDDING_MODEL: Embeddings | None = None


def _get_embeddings() -> Embeddings:
    """Lazy-load the embedding model from embed_config.yaml; falls back to FakeEmbeddings."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        cfg = settings.embed_config.get("embedding", {})
        model_name = cfg.get("model_name", "all-MiniLM-L6-v2")
        device = cfg.get("device", "cpu")
        normalize = cfg.get("normalize_embeddings", True)
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings

            _EMBEDDING_MODEL = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"device": device},
                encode_kwargs={"normalize_embeddings": normalize},
            )
            logger.info("Loaded embedding model: %s (device=%s)", model_name, device)
        except Exception:
            from langchain_core.embeddings import FakeEmbeddings

            dim = cfg.get("dimension", 384)
            _EMBEDDING_MODEL = FakeEmbeddings(size=dim)
            logger.warning("Embedding model load failed, using FakeEmbeddings(size=%d)", dim)
    return _EMBEDDING_MODEL


def get_vector_store(collection_name: str | None = None) -> Chroma:
    """Create or retrieve a Chroma vector store, reading config from embed_config.yaml."""
    cfg = settings.embed_config.get("vector_store", {})
    collection = collection_name or cfg.get("collection_name", "hr_policies")
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("Opening vector store: collection=%s persist=%s", collection, persist_dir)
    return Chroma(
        collection_name=collection,
        embedding_function=_get_embeddings(),
        persist_directory=str(persist_dir),
    )


def index_documents(docs: list[Document], collection_name: str = "hr_policies"):
    """Embed and store documents into Chroma; returns the generated IDs."""
    store = get_vector_store(collection_name)
    ids = store.add_documents(docs)
    logger.info("Indexed %d documents in collection '%s'", len(docs), collection_name)
    return ids


def similarity_search(query: str, k: int | None = None, collection_name: str = "hr_policies") -> list[Document]:
    """Embed the query and return the top-k most similar documents from the vector store.

    Args:
        query: Free-text question or search string.
        k: Number of results to return (default from embed_config.yaml).
        collection_name: Chroma collection to search.

    Returns:
        List of Document objects with .page_content and .metadata populated.

    Real-time flow:
        Called by the policy agent node during graph execution. The query is
        embedded immediately via SentenceTransformer, then cosine-compared
        against all stored document vectors in ChromaDB. The top-k matches
        are returned as context for the LLM prompt.
    """
    cfg = settings.embed_config.get("vector_store", {})
    store = get_vector_store(collection_name)
    result = store.similarity_search(query, k=k or cfg.get("default_k", 4))
    logger.debug("similarity_search query=%.50s hits=%d", query, len(result))
    return result
