import { useState } from "react";
import { useAGUI } from "../hooks/useAGUI";

export function HITLPanel() {
  const { pending, loading, resolve } = useAGUI();
  const [responses, setResponses] = useState<Record<string, string>>({});

  if (pending.length === 0) {
    return <div style={{ padding: 16, color: "#666" }}>No pending HITL requests.</div>;
  }

  return (
    <div style={{ padding: 16 }}>
      <h3>Human-in-the-Loop Requests</h3>
      {pending.map((item) => (
        <div
          key={item.interaction_id}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: 12,
            marginBottom: 12,
          }}
        >
          <p><strong>ID:</strong> {item.interaction_id}</p>
          <p><strong>Query:</strong> {item.query}</p>
          <textarea
            placeholder="Your response..."
            value={responses[item.interaction_id] || ""}
            onChange={(e) =>
              setResponses((prev) => ({ ...prev, [item.interaction_id]: e.target.value }))
            }
            style={{ width: "100%", minHeight: 60, marginTop: 8, padding: 8, borderRadius: 4, border: "1px solid #ccc" }}
          />
          <button
            onClick={() => resolve(item.interaction_id, responses[item.interaction_id] || "")}
            disabled={loading}
            style={{ marginTop: 8, padding: "6px 16px", background: "#059669", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}
          >
            {loading ? "Resolving..." : "Resolve"}
          </button>
        </div>
      ))}
    </div>
  );
}
