#!/usr/bin/env python
"""Load HR policy files into ChromaDB using NVIDIA nv-embed-v1 with chunking."""

import asyncio
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langchain_core.documents import Document

from backend.config.settings import settings
from backend.src.memory.chunking.recursive import RecursiveChunking
from backend.src.memory.vector_store import get_vector_store
from backend.src.services.policy_service import extract_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("scripts.index_policies")

POLICIES_DIR = Path(__file__).parent.parent / "data" / "policies"
ALLOWED_EXTENSIONS = {".md", ".pdf", ".txt"}
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def _slugify(name: str) -> str:
    name = Path(name).stem
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name).lower()
    return name.strip("_") or "untitled"


async def _chunk_text(text: str) -> list[str]:
    """Split text into chunks using recursive chunking strategy."""
    chunker = RecursiveChunking(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = await chunker.chunk(text)
    return [c.text for c in chunks if c.text.strip()]


def main():
    logger.info("Using NVIDIA embedding: %s", settings.embed_config.get("embedding", {}).get("model_name", "nvidia/nv-embed-v1"))

    store = get_vector_store("hr_policies")

    # Clear existing data if any
    existing = store.get()
    if existing and existing.get("ids"):
        ids = existing["ids"]
        logger.info("Deleting %d existing documents before re-indexing...", len(ids))
        store.delete(ids)

    docs = []
    doc_ids = []
    for path in sorted(POLICIES_DIR.iterdir()):
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            text = extract_text(path)
            slug = _slugify(path)

            # Chunk the text for better embedding quality
            chunks = asyncio.run(_chunk_text(text))
            logger.info("Loaded policy: %s (%d chars, %d chunks)", path.name, len(text), len(chunks))

            for i, chunk_text in enumerate(chunks):
                chunk_id = f"{slug}__chunk_{i:03d}"
                doc = Document(
                    page_content=chunk_text,
                    metadata={"source": path.name, "policy": slug, "chunk_index": i},
                )
                docs.append(doc)
                doc_ids.append(chunk_id)

    if docs:
        # Index in batches to avoid API rate limits
        batch_size = 10
        for i in range(0, len(docs), batch_size):
            batch_docs = docs[i:i + batch_size]
            batch_ids = doc_ids[i:i + batch_size]
            store.add_documents(batch_docs, ids=batch_ids)
            logger.info("Indexed batch %d-%d of %d", i, min(i + batch_size, len(docs)), len(docs))

    logger.info("Indexed %d policy chunks from %d documents: %s", len(doc_ids), len(set(d.metadata["policy"] for d in docs)), list(set(d.metadata["policy"] for d in docs)))


if __name__ == "__main__":
    main()
