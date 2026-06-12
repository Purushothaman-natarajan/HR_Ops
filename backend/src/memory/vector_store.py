import logging
from pathlib import Path
from typing import Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from backend.config.settings import settings

logger = logging.getLogger("hr_ops.vector_store")

_EMBEDDING_MODEL: Optional[Embeddings] = None


def _get_embeddings() -> Embeddings:
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings

            _EMBEDDING_MODEL = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        except ImportError:
            from langchain_core.embeddings import FakeEmbeddings

            _EMBEDDING_MODEL = FakeEmbeddings(size=384)
    return _EMBEDDING_MODEL


def get_vector_store(collection_name: str = "hr_policies") -> Chroma:
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        embedding_function=_get_embeddings(),
        persist_directory=str(persist_dir),
    )


def index_documents(docs: list[Document], collection_name: str = "hr_policies"):
    store = get_vector_store(collection_name)
    ids = store.add_documents(docs)
    logger.info("Indexed %d documents in collection '%s'", len(docs), collection_name)
    return ids


def similarity_search(query: str, k: int = 4, collection_name: str = "hr_policies") -> list[Document]:
    store = get_vector_store(collection_name)
    return store.similarity_search(query, k=k)
