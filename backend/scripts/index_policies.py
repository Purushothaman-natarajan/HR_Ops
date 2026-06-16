#!/usr/bin/env python
"""Load HR policy files into ChromaDB using NVIDIA nv-embed-v1 with chunking."""

import asyncio
import hashlib
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langchain_core.documents import Document

from backend.src.core.settings import settings
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

    # Retrieve all existing chunks in the vector store
    existing = store.get()
    existing_files: dict[str, dict] = {}
    
    if existing and existing.get("ids"):
        logger.info("Retrieved %d total chunks from database. Checking for duplicates & cleaning up...", len(existing["ids"]))
        
        seen_chunks = {}
        duplicates_to_delete = []
        
        for doc_id, metadata in zip(existing["ids"], existing["metadatas"]):
            source = metadata.get("source") if metadata else None
            chunk_index = metadata.get("chunk_index") if metadata else None
            if source is not None and chunk_index is not None:
                key = (source, chunk_index)
                if key in seen_chunks:
                    duplicates_to_delete.append(doc_id)
                else:
                    seen_chunks[key] = doc_id
                    if source not in existing_files:
                        existing_files[source] = {"ids": [], "hashes": set()}
                    existing_files[source]["ids"].append(doc_id)
                    file_hash = metadata.get("file_hash")
                    if file_hash:
                        existing_files[source]["hashes"].add(file_hash)
            else:
                # Invalid metadata - clean it up
                duplicates_to_delete.append(doc_id)
                
        if duplicates_to_delete:
            logger.info("Deleting %d duplicate or invalid chunk records from database...", len(duplicates_to_delete))
            store.delete(duplicates_to_delete)

    indexed_files = set()
    total_indexed_chunks = 0
    
    for path in sorted(POLICIES_DIR.iterdir()):
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            filename = path.name
            slug = _slugify(path)
            indexed_files.add(filename)
            
            # Read file content and calculate hash
            text = extract_text(path)
            current_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
            
            # Check if policy is unchanged
            is_unchanged = False
            if filename in existing_files:
                hashes = existing_files[filename]["hashes"]
                if len(hashes) == 1 and current_hash in hashes:
                    is_unchanged = True
            
            if is_unchanged:
                logger.info("Policy is unchanged (skipping index): %s (hash: %s)", filename, current_hash)
                total_indexed_chunks += len(existing_files[filename]["ids"])
                continue
                
            # If policy changed, delete old chunks first to prevent duplicates
            if filename in existing_files:
                old_ids = existing_files[filename]["ids"]
                logger.info("Policy %s changed/mismatched — deleting %d old chunks...", filename, len(old_ids))
                store.delete(old_ids)
                
            # Chunk and index new content
            chunks = asyncio.run(_chunk_text(text))
            logger.info("Indexing modified/new policy: %s (%d chunks, hash: %s)", filename, len(chunks), current_hash)
            
            batch_docs = []
            batch_ids = []
            for i, chunk_text in enumerate(chunks):
                chunk_id = f"{slug}__chunk_{i:03d}"
                doc = Document(
                    page_content=chunk_text,
                    metadata={"source": filename, "policy": slug, "chunk_index": i, "file_hash": current_hash},
                )
                batch_docs.append(doc)
                batch_ids.append(chunk_id)
                
            if batch_docs:
                batch_size = 10
                for idx in range(0, len(batch_docs), batch_size):
                    store.add_documents(batch_docs[idx:idx + batch_size], ids=batch_ids[idx:idx + batch_size])
                logger.info("Indexed %d chunks for %s", len(batch_docs), filename)
                total_indexed_chunks += len(batch_docs)
                
    # Clean up files deleted from disk
    for existing_file, info in existing_files.items():
        if existing_file not in indexed_files:
            logger.info("Policy file %s was deleted from disk — removing %d chunks from vector database...", existing_file, len(info["ids"]))
            store.delete(info["ids"])

    logger.info("Database synchronization complete. Total policy chunks now in database: %d", total_indexed_chunks)


if __name__ == "__main__":
    main()
