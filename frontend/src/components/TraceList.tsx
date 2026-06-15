import { useState, useEffect } from "react";
import { api } from "../api/client";
import { TraceViewer } from "./TraceViewer";
import type { TraceEvent } from "../types";

interface TraceRun {
  run_id: string;
  query: string;
  timestamp: string;
  duration_ms: number;
  cost_usd: number;
  trace_events?: TraceEvent[];
  final_response?: string;
  session_id?: string;
  turn_number?: number;
}

export function TraceList() {
  const [runs, setRuns] = useState<TraceRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<TraceRun | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    setLoading(true);
    setError("");
      try {
        const res = await api.trace.runs();
        setRuns((res.data.runs || []) as TraceRun[]);
    } catch (e) {
      setError(String(e));
      setRuns([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectRun = (run: TraceRun) => {
    if (selectedRun?.run_id === run.run_id) {
      setSelectedRun(null);
    } else {
      setSelectedRun(run);
    }
  };

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="spinner" />
          <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>Loading trace runs...</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="page-title">Trace Events</h1>
            <p className="page-desc">View execution traces from graph runs and conversations</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={fetchRuns}>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <span>Failed to load traces: {error}</span>
        </div>
      )}

      {runs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">&#9741;</div>
          <div className="empty-state-text">No trace runs found. Execute a query to generate traces.</div>
        </div>
      ) : (
        <div className="trace-list-container">
          <div className="trace-runs-panel">
            <div className="trace-runs-header">
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
                Recent Runs ({runs.length})
              </h3>
            </div>
            <div className="trace-runs-list">
              {runs.map((run) => (
                <div
                  key={run.run_id}
                  className={`trace-run-item${selectedRun?.run_id === run.run_id ? " selected" : ""}`}
                  onClick={() => handleSelectRun(run)}
                >
                  <div className="trace-run-main">
                    <div className="trace-run-id">{run.run_id}</div>
                    <div className="trace-run-query" title={run.query}>
                      {run.query.length > 80 ? run.query.substring(0, 80) + "..." : run.query}
                    </div>
                  </div>
                  <div className="trace-run-meta">
                    <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                      {new Date(run.timestamp).toLocaleString()}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--color-text-muted)", marginLeft: 8 }}>
                      {run.duration_ms.toFixed(0)}ms
                    </span>
                    <span style={{ fontSize: 11, color: "var(--color-primary)", marginLeft: 8 }}>
                      ${run.cost_usd.toFixed(5)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {selectedRun && (
            <div className="trace-detail-panel">
              <div className="trace-detail-header">
                <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
                  {selectedRun.query}
                </h3>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: 8 }}>
                  Run ID: {selectedRun.run_id} | {new Date(selectedRun.timestamp).toLocaleString()} | {selectedRun.duration_ms.toFixed(0)}ms | ${selectedRun.cost_usd.toFixed(5)}
                </div>
                <button className="btn btn-sm btn-secondary" onClick={() => setSelectedRun(null)}>
                  Close
                </button>
              </div>
              <div className="trace-detail-body">
                {selectedRun.final_response && (
                  <div style={{ marginBottom: 16, padding: 12, background: "var(--color-bg)", borderRadius: 6, fontSize: 13, maxHeight: 200, overflow: "auto" }}>
                    <strong>Response:</strong>
                    <div style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>{selectedRun.final_response}</div>
                  </div>
                )}
                <TraceViewer events={selectedRun.trace_events || []} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}