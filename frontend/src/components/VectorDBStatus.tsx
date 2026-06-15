import { useState, useEffect } from "react";
import { api } from "../api/client";

interface VectorStoreInfo {
  available: boolean;
  collection: string;
  document_count: number;
  embedding_model: string;
  dimension: number;
  persist_dir: string;
}

/** Live status card for the vector DB (embedding) store.
 *
 * Fetches /vector-store/status on mount and shows document count,
 * embedding model name, and a health indicator.
 */
export function VectorDBStatus() {
  const [info, setInfo] = useState<VectorStoreInfo | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.vectorStore.status()
      .then((r) => setInfo(r.data))
      .catch(() => setError("unavailable"));
  }, []);

  const statusColor =
    error || (info && !info.available)
      ? "var(--color-error)"
      : info && info.document_count > 0
        ? "var(--color-success)"
        : "#999";

  return (
    <div className="status-indicator">
      <span className="status-dot" style={{ background: statusColor }} />
      <span className="status-text">
        {error
          ? "Embeddings: Offline"
          : info && !info.available
            ? `Embeddings: unavailable`
            : info
              ? `Embeddings: ${info.embedding_model} (${info.document_count} docs)`
              : "Embeddings: checking..."}
      </span>
    </div>
  );
}
