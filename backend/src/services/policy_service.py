from __future__ import annotations

"""File-based policy management service with ChromaDB vector index.

Provides CRUD operations for HR policy documents stored on disk, text
extraction for .md / .pdf / .txt files, and automatic re-indexing into
the vector store whenever policies are created, updated, or deleted.
"""

import logging
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document

from backend.src.memory.vector_store import get_vector_store, index_documents

logger = logging.getLogger("hr_ops.policy_service")

POLICIES_DIR = Path(__file__).parent.parent.parent / "data" / "policies"
ALLOWED_EXTENSIONS = {".md", ".pdf", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _slugify(name: str) -> str:
    """Convert a file name into a URL-safe slug (lowercase, hyphens replaced with underscores)."""
    name = Path(name).stem
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name).lower()
    return name.strip("_") or "untitled"


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


def get_policy(policy_id: str) -> Optional[dict]:
    """Retrieve a single policy's metadata and full text content by its slug ID."""
    for path in POLICIES_DIR.iterdir():
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            if _slugify(path.name) == policy_id:
                info = _make_policy_dict(path)
                info["content"] = extract_text(path)
                return info
    return None


def get_policy_path(policy_id: str) -> Optional[Path]:
    """Resolve a policy slug ID to its filesystem Path, or None if not found."""
    for path in POLICIES_DIR.iterdir():
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            if _slugify(path.name) == policy_id:
                return path
    return None


def _reindex_all():
    """Rebuild the entire ChromaDB collection for hr_policies from scratch.

    Reads all supported files from POLICIES_DIR, creates Document objects,
    deletes the existing collection contents, and re-indexes every document.
    """
    docs = []
    for path in sorted(POLICIES_DIR.iterdir()):
        if path.suffix.lower() in ALLOWED_EXTENSIONS and path.is_file():
            text = extract_text(path)
            doc = Document(
                page_content=text,
                metadata={"source": path.name, "policy": _slugify(path)},
            )
            docs.append(doc)
    store = get_vector_store("hr_policies")
    existing = store.get()
    if existing and existing.get("ids"):
        store.delete(existing["ids"])  # clear stale vectors before re-import
    if docs:
        index_documents(docs, "hr_policies")
    logger.info("Re-indexed %d policy documents", len(docs))


def create_policy(filename: str, content: bytes, title: Optional[str] = None) -> dict:
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

    _reindex_all()
    info = _make_policy_dict(dest)
    info["content"] = extract_text(dest)
    return info


def update_policy(policy_id: str, title: Optional[str] = None) -> Optional[dict]:
    """Update a policy's title (first-line heading) and re-index the vector store."""
    path = get_policy_path(policy_id)
    if not path:
        return None
    if title:
        _set_title(path, title)
    _reindex_all()
    info = _make_policy_dict(path)
    info["content"] = extract_text(path)
    return info


def delete_policy(policy_id: str) -> bool:
    """Delete a policy file from disk and re-index the vector store."""
    path = get_policy_path(policy_id)
    if not path:
        return False
    path.unlink()  # remove file from disk
    _reindex_all()
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
