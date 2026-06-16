import { useState } from "react";
import { api } from "../api/client";
import { TraceViewer } from "../components/TraceViewer";
import type { TraceEvent } from "../types";

/** Trace query panel for looking up a single run by ID and viewing its events.
 *
 * Fetches a trace via api.trace.get(runId) and renders
 * events inside a TraceViewer component.
 *
 * @example
 * <TraceQueryPanel />
 */
export function TraceQueryPanel() {
  const [runIdInput, setRunIdInput] = useState("");
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleFetch = async () => {
    if (!runIdInput.trim()) return;
    setLoading(true);
    setError("");
      try {
        const res = await api.trace.get(runIdInput.trim());
        setEvents((res.data.trace_events || []) as TraceEvent[]);
    } catch (e) {
      setError(String(e));
      setEvents([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Trace Query</h1>
        <p className="page-desc">Fetch execution traces by run ID for analysis and debugging</p>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-body">
          <div className="query-input-row">
            <input
              type="text"
              className="input"
              value={runIdInput}
              onChange={(e) => setRunIdInput(e.target.value)}
              placeholder="Enter run ID (e.g. run_abc123)"
              disabled={loading}
            />
            <button className="btn btn-primary" onClick={handleFetch} disabled={loading || !runIdInput.trim()}>
              {loading ? "Fetching..." : "Fetch"}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <span>{error}</span>
        </div>
      )}

      <TraceViewer events={events} />
    </div>
  );
}
