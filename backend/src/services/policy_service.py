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


def _migrate_if_needed():
    """One-time startup check: ensure ChromaDB is in sync with on-disk policies.

    Runs only once per process lifetime. Triggers a full reindex if:
      1. Legacy UUID-based IDs are found (pre-slug migration), OR
      2. Document count in ChromaDB doesn't match the number of files on disk.
    """
    global _MIGRATED
    if _MIGRATED:
        return
    needs_reindex = False
    try:
        store = get_vector_store("hr_policies")
        existing = store.get()
        db_count = len(existing.get("ids", [])) if existing else 0
        on_disk = sum(
            1 for p in POLICIES_DIR.iterdir()
            if p.suffix.lower() in ALLOWED_EXTENSIONS and p.is_file()
        )
        if db_count != on_disk:
            logger.info("Document count mismatch (%d in DB vs %d on disk), re-indexing", db_count, on_disk)
            needs_reindex = True
        elif existing and existing.get("ids"):
            legacy = [i for i in existing["ids"] if not re.match(r"^[a-z0-9_]+$", i)]
            if legacy:
                logger.info("Migrating %d legacy UUID-based vectors to slug-based IDs", len(legacy))
                needs_reindex = True
    except Exception:
        logger.debug("Migration check skipped (collection may not exist yet)")
        needs_reindex = True
    if needs_reindex:
        _reindex_all()
    _MIGRATED = True


def _reindex_all():
    """Rebuild the ChromaDB collection for hr_policies incrementally.

    Reads all supported files from POLICIES_DIR, tracks file metadata (mtime, size, hash),
    and only re-chunks/re-indexes files that are new or have changed since the last run.
    Deletes vectors for files that have been removed from disk.
    """
    from backend.src.memory.chunking.recursive import RecursiveChunking

    chunker = RecursiveChunking(chunk_size=800, chunk_overlap=150)

    # Load previously stored file metadata
    stored_metadata = _load_policy_metadata()
    new_metadata = {}

    # Build the full list of current on-disk chunk ids and corresponding docs
    docs_by_id: dict[str, Document] = {}
    changed_files = []  # Track which files were changed/new for logging

    for path in sorted(POLICIES_DIR.iterdir()):
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            rel_path = path.relative_to(POLICIES_DIR).as_posix()
            current_meta = _get_file_metadata(path)
            new_metadata[rel_path] = current_meta

            # Check if file is new or has changed
            stored_meta = stored_metadata.get(rel_path)
            is_new_or_changed = (
                stored_meta is None
                or stored_meta.get("mtime") != current_meta["mtime"]
                or stored_meta.get("size") != current_meta["size"]
                or stored_meta.get("hash") != current_meta["hash"]
            )

            if is_new_or_changed:
                changed_files.append(rel_path)
                text = extract_text(path)
                slug = _slugify(path)
                import asyncio
                chunks = asyncio.run(chunker.chunk(text))
                for chunk in chunks:
                    if chunk.text.strip():
                        doc_id = f"{slug}__chunk_{chunk.index:03d}"
                        docs_by_id[doc_id] = Document(
                            page_content=chunk.text,
                            metadata={"source": path.name, "policy": slug, "chunk_index": chunk.index},
                        )

    store = get_vector_store("hr_policies")
    existing = store.get()
    existing_ids = set(existing.get("ids", [])) if existing else set()

    current_ids = set(docs_by_id.keys())

    # Delete stale vectors that correspond to files removed from disk
    stale_ids = list(existing_ids - current_ids)
    if stale_ids:
        try:
            store.delete(stale_ids)
            logger.info("Deleted %d stale vectors (from removed files)", len(stale_ids))
        except Exception:
            logger.exception("Failed to delete stale vectors")

    # Index only the missing/new documents (avoid re-indexing unchanged chunks)
    missing_ids = list(current_ids - existing_ids)
    if missing_ids:
        # Prepare documents in the same order as missing_ids
        missing_docs = [docs_by_id[i] for i in missing_ids]
        batch_size = 8
        for i in range(0, len(missing_docs), batch_size):
            batch_docs = missing_docs[i : i + batch_size]
            batch_ids = missing_ids[i : i + batch_size]
            store.add_documents(batch_docs, ids=batch_ids)
        logger.info(
            "Indexed %d new policy chunks from %d files (%d changed, %d unchanged)",
            len(missing_ids),
            len(set(d.metadata["policy"] for d in missing_docs)),
            len(changed_files),
            len(new_metadata) - len(changed_files),
        )
    else:
        if changed_files:
            logger.info("No new chunks to index (detected %d file changes but all chunks already indexed)", len(changed_files))
        else:
            logger.info("No new policy chunks to index (all files unchanged)")

    # Save updated metadata for next run
    _save_policy_metadata(new_metadata)


# NOTE: Migration should not run at import time because it may perform
# asynchronous work (embedding/chunking) which can conflict with the
# ASGI server's event loop during startup. The migration is intentionally
# deferred and scheduled by the application lifespan handler in
# backend.main so it runs in a background thread after the app starts.


def create_policy(filename: str, content: bytes, title: str | None = None) -> dict:
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

    text = extract_text(dest)
    doc = Document(page_content=text, metadata={"source": dest.name, "policy": slug})
    index_document(doc, slug, "hr_policies")
    semantic_cache.clear()  # Invalidate stale cached responses
    info = _make_policy_dict(dest)
    info["content"] = text
    return info


def update_policy(policy_id: str, title: str | None = None) -> dict | None:
    """Update a policy's title (first-line heading) and re-index the vector store."""
    path = get_policy_path(policy_id)
    if not path:
        return None
    if title:
        _set_title(path, title)
    text = extract_text(path)
    doc = Document(page_content=text, metadata={"source": path.name, "policy": policy_id})
    delete_document(policy_id, "hr_policies")
    index_document(doc, policy_id, "hr_policies")
    semantic_cache.clear()  # Invalidate stale cached responses
    info = _make_policy_dict(path)
    info["content"] = text
    return info


def delete_policy(policy_id: str) -> bool:
    """Delete a policy file from disk and re-index the vector store."""
    path = get_policy_path(policy_id)
    if not path:
        return False
    path.unlink()  # remove file from disk
    delete_document(policy_id, "hr_policies")
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
