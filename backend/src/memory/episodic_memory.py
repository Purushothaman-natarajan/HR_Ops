import logging
from uuid import uuid4
from langchain_core.documents import Document
from backend.src.memory.vector_store import get_vector_store, similarity_search, index_document, index_documents

logger = logging.getLogger("hr_ops.episodic_memory")

EPISODIC_COLLECTION = "episodic_memory"

class EpisodicMemory:
    """Stores past anomalies and incidents to provide context for future decisions."""

    def __init__(self):
        self._store = get_vector_store(EPISODIC_COLLECTION)

    def store_incident(self, trigger_type: str, query: str, result_summary: str, severity: float = 0.0):
        """Index a resolved incident/anomaly into the episodic memory."""
        doc_id = str(uuid4())
        content = f"Trigger: {trigger_type}\nQuery/Event: {query}\nResult/Resolution: {result_summary}"
        doc = Document(
            page_content=content,
            metadata={
                "trigger_type": trigger_type,
                "severity": severity,
                "type": "incident"
            }
        )
        try:
            index_document(doc, doc_id, collection_name=EPISODIC_COLLECTION)
            logger.info("Stored incident in episodic memory: %s", doc_id)
        except Exception as e:
            logger.error("Failed to store incident in episodic memory: %s", e)

    def store_incidents_batch(self, incidents: list[dict]) -> int:
        """Batch-index multiple incidents with a single embedding call.

        Each incident dict should have: trigger_type, query, result_summary, severity.
        Returns the number of successfully stored incidents.
        """
        if not incidents:
            return 0
        docs = []
        ids = []
        for inc in incidents:
            doc_id = str(uuid4())
            content = (
                f"Trigger: {inc.get('trigger_type', 'anomaly')}\n"
                f"Query/Event: {inc.get('query', '')}\n"
                f"Result/Resolution: {inc.get('result_summary', '')}"
            )
            docs.append(Document(
                page_content=content,
                metadata={
                    "trigger_type": inc.get("trigger_type", "anomaly"),
                    "severity": inc.get("severity", 0.0),
                    "type": "incident",
                },
            ))
            ids.append(doc_id)
        try:
            index_documents(docs, collection_name=EPISODIC_COLLECTION)
            logger.info("Batch-stored %d incidents in episodic memory", len(docs))
            return len(docs)
        except Exception as e:
            logger.error("Failed to batch-store incidents: %s", e)
            return 0

    def recall_similar_incidents(self, query: str, k: int = 3) -> list[dict]:
        """Find past similar incidents based on the current query."""
        docs = similarity_search(query, k=k, collection_name=EPISODIC_COLLECTION)
        incidents = []
        for d in docs:
            incidents.append({
                "content": d.page_content,
                "metadata": d.metadata
            })
        return incidents

episodic_memory = EpisodicMemory()
