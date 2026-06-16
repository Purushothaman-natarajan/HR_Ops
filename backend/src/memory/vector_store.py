"""ChromaDB vector store — embed + index + similarity search for RAG.

How embedding works in real-time with agents:

1. A user asks "What is the leave policy?"
2. The triage agent classifies the intent as "policy"
3. The policy node calls similarity_search(query) which:
   a) Embeds the query via NVIDIA nv-embed-v1 (4096-dim vector)
   b) Searches ChromaDB for the top-k nearest vectors via cosine similarity
   c) Returns the original document texts of the closest matches
4. Those policy texts are injected into the LLM prompt as context
5. The LLM generates a grounded answer — this is Retrieval-Augmented Generation

The embedding model is loaded once (lazy singleton) and shared across
all agent nodes within the process. See backend/config/nvidia_config.yaml
for tunable parameters.
"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from backend.config.settings import settings
from backend.src.utils.nvidia_embeddings import NVIDIAEmbeddings

logger = logging.getLogger("hr_ops.vector_store")

_EMBEDDING_MODEL: Embeddings | None = None


def _get_embeddings() -> Embeddings:
    """Lazy-load NVIDIA nv-embed-v1 embedding model via NVIDIA NIM API."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        cfg = settings.embed_config.get("embedding", {})
        model_name = cfg.get("model_name", "nvidia/nv-embed-v1")
        _EMBEDDING_MODEL = NVIDIAEmbeddings(
            model=model_name,
            input_type=cfg.get("input_type", "query"),
        )
        logger.info("Loaded NVIDIA embedding model: %s (dim=%d)", model_name, cfg.get("dimension", 4096))
    return _EMBEDDING_MODEL


def get_vector_store(collection_name: str | None = None) -> Chroma:
    """Create or retrieve a Chroma vector store, reading config from nvidia_config.yaml."""
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


def index_document(doc: Document, doc_id: str, collection_name: str = "hr_policies") -> str:
    """Embed and store a single document with an explicit ChromaDB ID."""
    store = get_vector_store(collection_name)
    store.add_documents([doc], ids=[doc_id])
    logger.info("Indexed document '%s' in collection '%s'", doc_id, collection_name)
    return doc_id


def delete_document(doc_id: str, collection_name: str = "hr_policies"):
    """Remove a single document from the vector store by its ID."""
    store = get_vector_store(collection_name)
    store.delete([doc_id])
    logger.info("Removed document '%s' from collection '%s'", doc_id, collection_name)


def get_document_count(collection_name: str = "hr_policies") -> int:
    """Return the number of documents currently stored in the vector collection."""
    try:
        store = get_vector_store(collection_name)
        return store._collection.count()
    except Exception:
        return 0


def similarity_search(query: str, k: int | None = None, collection_name: str = "hr_policies") -> list[Document]:
    """Embed the query and return the top-k most similar documents from the vector store.

    Args:
        query: Free-text question or search string.
        k: Number of results to return (default from nvidia_config.yaml).
        collection_name: Chroma collection to search.

    Returns:
        List of Document objects with .page_content and .metadata populated.
        Returns empty list on any failure to prevent graph crashes.
    """
    cfg = settings.embed_config.get("vector_store", {})
    try:
        store = get_vector_store(collection_name)
        results = store.similarity_search_with_score(query, k=k or cfg.get("default_k", 4))
        
        docs = []
        for doc, distance in results:
            # Convert L2 distance or cosine distance to similarity score in [0, 1] range
            # Using 1 / (1 + distance) is robust for mapping any positive distance to [0, 1]
            similarity = 1.0 / (1.0 + distance)
            doc.metadata["score"] = similarity
            docs.append(doc)
            
        logger.debug("similarity_search query=%.50s hits=%d", query, len(docs))
        return docs
    except Exception as e:
        logger.error("similarity_search failed: query=%.50s error=%s", query, e)
        return []
