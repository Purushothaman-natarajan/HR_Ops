#!/usr/bin/env python
"""Load sample HR policy markdown files into ChromaDB."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langchain_core.documents import Document

from backend.src.memory.vector_store import get_vector_store, index_documents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scripts.index_policies")

POLICIES_DIR = Path(__file__).parent.parent / "data" / "policies"


def main():
    store = get_vector_store("hr_policies")
    existing = store.get()
    if existing and existing.get("ids"):
        logger.info(
            "Policies already indexed (%d docs), skipping.",
            len(existing["ids"]),
        )
        return

    docs = []
    for path in sorted(POLICIES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        doc = Document(
            page_content=text,
            metadata={"source": path.name, "policy": path.stem},
        )
        docs.append(doc)
        logger.info("Loaded policy: %s (%d chars)", path.name, len(text))

    ids = index_documents(docs, "hr_policies")
    logger.info("Indexed %d policy documents: %s", len(ids), ids)


if __name__ == "__main__":
    main()
