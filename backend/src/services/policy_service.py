from __future__ import annotations

"""File-based policy management service with ChromaDB vector index.

Provides CRUD operations for HR policy documents stored on disk, text
extraction for .md / .pdf / .txt files, and automatic re-indexing into
the vector store whenever policies are created, updated, or deleted.
"""

import hashlib
import json
import logging
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.documents import Document

from backend.src.memory.cache import semantic_cache
from backend.src.memory.vector_store import (
    delete_document,
    get_vector_store,
    index_document,
    index_documents,
)

logger = logging.getLogger("hr_ops.policy_service")

POLICIES_DIR = Path(__file__).parent.parent.parent / "data" / "policies"
POLICY_METADATA_FILE = Path(__file__).parent.parent.parent / "data" / ".policy_metadata.json"
ALLOWED_EXTENSIONS = {".md", ".pdf", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _slugify(name: str) -> str:
    """Convert a file name into a URL-safe slug (lowercase, hyphens replaced with underscores)."""
    name = Path(name).stem
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name).lower()
    return name.strip("_") or "untitled"


def _compute_file_hash(path: Path, algorithm: str = "sha256") -> str:
    """Compute a hash digest of file contents (used to detect if file has changed).
    
    Args:
        path: Path to the file.
        algorithm: Hash algorithm to use (default: sha256).
    
    Returns:
        Hex digest of the file's hash.
    """
    hasher = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def _get_file_metadata(path: Path) -> dict:
    """Extract metadata about a policy file: size, mtime, and content hash.
    
    Returns a dict with keys: mtime, size, hash
    """
    stat = path.stat()
    return {
        "mtime": stat.st_mtime,
        "size": stat.st_size,
        "hash": _compute_file_hash(path),
    }


def _load_policy_metadata() -> dict:
    """Load the stored metadata about which policy files have been indexed.
    
    Returns a dict mapping relative file paths to metadata dicts (mtime, size, hash).
    Empty dict if the metadata file doesn't exist.
    """
    if not POLICY_METADATA_FILE.exists():
        return {}
    try:
        with open(POLICY_METADATA_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load policy metadata: %s", e)
        return {}


def _save_policy_metadata(metadata: dict):
    """Save the metadata about which policy files have been indexed.
    
    Args:
        metadata: Dict mapping relative file paths to metadata dicts.
    """
    try:
        POLICY_METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(POLICY_METADATA_FILE, "w") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        logger.warning("Failed to save policy metadata: %s", e)


def _content_type(ext: str) -> str:
    """Return the MIME content type string for a given file extension."""
    return mimetypes.types_map.get(ext, "application/octet-stream")


def _read_md(path: Path) -> str:
    """Read and return the full text content of a Markdown file."""
    return path.read_text(encoding="utf-8")


def _read_txt(path: Path) -> str:
    """Read and return the full text content of a plain-text file."""
    return path.read_text(encoding="utf-8")


def _read_pdf(path: Path) -> str:
    """Extract and return plain text from a PDF file using PyMuPDF (fitz)."""
    try:
        import fitz
    except ImportError:
        raise RuntimeError("PyMuPDF (fitz) is required to parse PDF files")
    doc = fitz.open(path)
    text = "\n\n".join(page.get_text() for page in doc)
    doc.close()
    return text.strip()


def extract_text(path: Path) -> str:
    """Read and extract plain text from a policy file (.md, .pdf, .txt).

    Args:
        path: Path to the policy file on disk.

    Returns:
        Extracted plain-text content.

    Raises:
        ValueError: If the file extension is not supported.
        RuntimeError: If PyMuPDF is not installed for PDF parsing.
    """
    ext = path.suffix.lower()
    if ext == ".md":
        return _read_md(path)
    elif ext == ".pdf":
        return _read_pdf(path)
    elif ext == ".txt":
        return _read_txt(path)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


def _make_policy_dict(path: Path) -> dict:
    stat = path.stat()
    ext = path.suffix.lower()
    return {
        "id": _slugify(path.name),
        "filename": path.name,
        "title": path.stem.replace("_", " ").title(),
        "content_type": _content_type(ext),
        "file_size": stat.st_size,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def list_policies() -> list[dict]:
    """Return metadata for all policy files in the policies directory."""
    policies = []
    for path in sorted(POLICIES_DIR.iterdir()):
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            policies.append(_make_policy_dict(path))
    return policies


def get_policy(policy_id: str) -> dict | None:
    """Retrieve a single policy's metadata and full text content by its slug ID."""
    for path in POLICIES_DIR.iterdir():
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            if _slugify(path.name) == policy_id:
                info = _make_policy_dict(path)
                info["content"] = extract_text(path)
                return info
    return None


def get_policy_path(policy_id: str) -> Path | None:
    """Resolve a policy slug ID to its filesystem Path, or None if not found."""
    for path in POLICIES_DIR.iterdir():
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            if _slugify(path.name) == policy_id:
                return path
    return None


_MIGRATED = False


async def _migrate_if_needed():
    """One-time startup check: ensure ChromaDB is in sync with on-disk policies.

    Runs only once per process lifetime. Triggers a full reindex if:
      1. Legacy UUID-based or non-chunk IDs are found (pre-slug migration), OR
      2. Document count in ChromaDB is 0 while there are files on disk.
    """
    global _MIGRATED
    if _MIGRATED:
        return
    needs_reindex = False
    try:
        import asyncio
        store = get_vector_store("hr_policies")
        existing = await asyncio.to_thread(store.get)
        db_count = len(existing.get("ids", [])) if existing else 0
        on_disk = sum(
            1 for p in POLICIES_DIR.iterdir()
            if p.suffix.lower() in ALLOWED_EXTENSIONS and p.is_file()
        )
        if db_count == 0 and on_disk > 0:
            logger.info("Database is empty, triggering startup re-indexing")
            needs_reindex = True
        elif existing and existing.get("ids"):
            legacy = [i for i in existing["ids"] if not re.match(r"^[a-z0-9_]+__chunk_\d+$", i)]
            if legacy:
                logger.info("Migrating %d legacy UUID-based or non-chunk vectors to slug-based IDs", len(legacy))
                needs_reindex = True
    except Exception:
        logger.debug("Migration check skipped (collection may not exist yet)")
        needs_reindex = True
    if needs_reindex:
        await _reindex_all()
    _MIGRATED = True


async def _reindex_all():
    """Rebuild the ChromaDB collection for hr_policies incrementally.

    Reads all supported files from POLICIES_DIR, tracks file metadata (mtime, size, hash),
    and only re-chunks/re-indexes files that are new or have changed since the last run.
    Deletes vectors for files that have been removed from disk.
    Also scans and deletes duplicates or invalid chunk IDs.
    """
    from backend.src.memory.chunking.recursive import RecursiveChunking
    import hashlib

    chunker = RecursiveChunking(chunk_size=800, chunk_overlap=150)
    store = get_vector_store("hr_policies")

    import asyncio

    # 1. Retrieve all existing chunks from the database to check for duplicates & hashes
    existing = await asyncio.to_thread(store.get)
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
                # Invalid metadata or legacy structure - clean it up
                duplicates_to_delete.append(doc_id)
                
        if duplicates_to_delete:
            logger.info("Deleting %d duplicate or invalid chunk records from database...", len(duplicates_to_delete))
            try:
                await asyncio.to_thread(store.delete, duplicates_to_delete)
            except Exception:
                logger.exception("Failed to delete duplicate/invalid chunks")

    # 2. Iterate through files on disk, compute their hashes, and detect changes
    indexed_files = set()
    total_indexed_chunks = 0
    new_metadata = {}
    changed_files = []

    for path in sorted(POLICIES_DIR.iterdir()):
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            filename = path.name
            slug = _slugify(filename)
            indexed_files.add(filename)

            # Read file content and calculate hash
            text = extract_text(path)
            current_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

            # Track file metadata (mtime, size, hash)
            stat = path.stat()
            new_metadata[filename] = {
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "hash": current_hash,
            }

            # Check if policy is unchanged in the DB
            is_unchanged = False
            if filename in existing_files:
                hashes = existing_files[filename]["hashes"]
                if len(hashes) == 1 and current_hash in hashes:
                    is_unchanged = True

            if is_unchanged:
                logger.info("Policy is unchanged (skipping index): %s (hash: %s)", filename, current_hash)
                total_indexed_chunks += len(existing_files[filename]["ids"])
                continue

            # If policy changed or is new, delete old chunks first to prevent duplicates
            if filename in existing_files:
                old_ids = existing_files[filename]["ids"]
                logger.info("Policy %s changed/mismatched — deleting %d old chunks...", filename, len(old_ids))
                try:
                    await asyncio.to_thread(store.delete, old_ids)
                except Exception:
                    logger.exception("Failed to delete old chunks for changed policy %s", filename)

            # Chunk and index new content
            changed_files.append(filename)
            chunks = await chunker.chunk(text)
            logger.info("Indexing modified/new policy: %s (%d chunks, hash: %s)", filename, len(chunks), current_hash)

            batch_docs = []
            batch_ids = []
            for chunk in chunks:
                if chunk.text.strip():
                    chunk_id = f"{slug}__chunk_{chunk.index:03d}"
                    doc = Document(
                        page_content=chunk.text,
                        metadata={
                            "source": filename,
                            "policy": slug,
                            "chunk_index": chunk.index,
                            "file_hash": current_hash,
                        },
                    )
                    batch_docs.append(doc)
                    batch_ids.append(chunk_id)

            if batch_docs:
                batch_size = 10
                for idx in range(0, len(batch_docs), batch_size):
                    await asyncio.to_thread(store.add_documents, batch_docs[idx:idx + batch_size], ids=batch_ids[idx:idx + batch_size])
                logger.info("Indexed %d chunks for %s", len(batch_docs), filename)
                total_indexed_chunks += len(batch_docs)

    # 3. Clean up files deleted from disk
    for existing_file, info in existing_files.items():
        if existing_file not in indexed_files:
            logger.info("Policy file %s was deleted from disk — removing %d chunks from vector database...", existing_file, len(info["ids"]))
            try:
                await asyncio.to_thread(store.delete, info["ids"])
            except Exception:
                logger.exception("Failed to delete chunks for removed file %s", existing_file)

    logger.info("Database synchronization complete. Total policy chunks now in database: %d", total_indexed_chunks)

    # Save updated metadata for next run
    _save_policy_metadata(new_metadata)


# NOTE: Migration should not run at import time because it may perform
# asynchronous work (embedding/chunking) which can conflict with the
# ASGI server's event loop during startup. The migration is intentionally
# deferred and scheduled by the application lifespan handler in
# backend.main so it runs in a background thread after the app starts.


async def create_policy(filename: str, content: bytes, title: str | None = None) -> dict:
    """Write a new policy file to disk and re-index the vector store.

    Args:
        filename: Original filename used to determine extension and slug.
        content: Raw file bytes to write.
        title: Optional override title written as first-line heading.

    Returns:
        Dict with policy metadata and extracted text content.

    Raises:
        ValueError: If the file extension is unsupported or size exceeds limit.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)} MB")

    slug = _slugify(filename)
    dest = POLICIES_DIR / f"{slug}{ext}"
    dest.write_bytes(content)  # persist raw file bytes to disk

    if title:
        _set_title(dest, title)

    # Incrementally reindex all policies (will pick up the new file and chunk it properly)
    await _reindex_all()
    
    semantic_cache.clear()  # Invalidate stale cached responses
    info = _make_policy_dict(dest)
    info["content"] = extract_text(dest)
    return info


async def update_policy(policy_id: str, title: str | None = None) -> dict | None:
    """Update a policy's title (first-line heading) and re-index the vector store."""
    path = get_policy_path(policy_id)
    if not path:
        return None
    if title:
        _set_title(path, title)
    
    # Incrementally reindex all policies (will pick up changes in the file and chunk it properly)
    await _reindex_all()
    
    semantic_cache.clear()  # Invalidate stale cached responses
    info = _make_policy_dict(path)
    info["content"] = extract_text(path)
    return info


async def delete_policy(policy_id: str) -> bool:
    """Delete a policy file from disk and re-index the vector store."""
    path = get_policy_path(policy_id)
    if not path:
        return False
    path.unlink()  # remove file from disk
    
    # Incrementally reindex all policies (will detect that the file was deleted and remove its chunks)
    await _reindex_all()
    
    semantic_cache.clear()  # Invalidate stale cached responses
    return True


def _set_title(path: Path, title: str):
    """Write a title line into the file so the stem-based title can be overridden.
    Uses a simple convention: first line `# Title` for markdown, or a header comment for others.
    """
    ext = path.suffix.lower()
    if ext == ".md":
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        if lines and lines[0].startswith("# "):
            lines[0] = f"# {title}"
        else:
            lines.insert(0, f"# {title}")
        path.write_text("\n".join(lines), encoding="utf-8")
