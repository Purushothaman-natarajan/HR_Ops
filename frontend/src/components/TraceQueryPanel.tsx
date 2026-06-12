import { useState } from "react";
import { api } from "../api/client";

export function TraceQueryPanel() {
  const [traceIds, setTraceIds] = useState("");
  const [result, setResult] = useState<unknown>(null);

  const handleCompare = async () => {
    const ids = traceIds.split(",").map((s) => s.trim()).filter(Boolean);
    if (ids.length < 2) return;
    const data = await api.trace.compare(ids);
    setResult(data);
  };

  return (
    <div style={{ padding: 16 }}>
      <h3>Trace Query & Comparison</h3>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          value={traceIds}
          onChange={(e) => setTraceIds(e.target.value)}
          placeholder="trace_id_1,trace_id_2"
          style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid #ccc" }}
        />
        <button
          onClick={handleCompare}
          style={{ padding: "8px 20px", background: "#6366f1", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}
        >
          Compare
        </button>
      </div>
      {result && (
        <pre style={{ background: "#f9fafb", padding: 12, borderRadius: 6, fontSize: 12, overflow: "auto" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}
