import { useState, useEffect } from "react";
import { getApiMetrics } from "../api/client";

const BASE_URL = import.meta.env.VITE_API_URL || "";

interface EndpointMetric {
  count: number;
  errors: number;
  error_rate_pct: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  min_ms: number;
  max_ms: number;
  avg_ms: number;
}

export function PerformanceDashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [serverMetrics, setServerMetrics] = useState<Record<string, EndpointMetric>>({});
  const [totalRequests, setTotalRequests] = useState(0);
  const [totalErrors, setTotalErrors] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError("");
    fetch(`${BASE_URL}/debug/metrics`)
      .then((res) => res.json())
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .then((r: any) => {
        const data = r?.data || r || {};
        setServerMetrics(data.endpoints || {});
        setTotalRequests(data.total_requests || 0);
        setTotalErrors(data.total_errors || 0);
      })
      .catch((e: Error) => {
        console.warn("PerformanceDashboard: failed to fetch metrics", e);
        setError("Could not load server metrics.");
      })
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const clientMetrics = getApiMetrics();
  const avgClientLatency =
    clientMetrics.length > 0
      ? clientMetrics.reduce((s, m) => s + m.duration_ms, 0) / clientMetrics.length
      : 0;

  const endpoints = Object.entries(serverMetrics).sort(([, a], [, b]) => b.count - a.count);

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="page-title">Performance Dashboard</h1>
            <p className="page-desc">Server-side p50/p95/p99 latencies and client-side API timing</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => setRefreshKey((k) => k + 1)}>
            Refresh
          </button>
        </div>
      </div>

      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Total Requests</div>
          <div className="stat-value">{totalRequests}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Errors</div>
          <div className="stat-value" style={{ color: totalErrors > 0 ? "var(--color-error)" : undefined }}>
            {totalErrors}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Client Avg Latency</div>
          <div className="stat-value" style={{ color: "var(--color-primary)" }}>
            {avgClientLatency.toFixed(1)}ms
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Client Calls (Session)</div>
          <div className="stat-value">{clientMetrics.length}</div>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="card">
          <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div className="spinner" />
            <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>Loading metrics...</span>
          </div>
        </div>
      )}

      {!loading && endpoints.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Endpoint Latency (ms)</span>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Endpoint</th>
                  <th>Count</th>
                  <th>Errors</th>
                  <th>Error%</th>
                  <th>p50</th>
                  <th>p95</th>
                  <th>p99</th>
                  <th>Avg</th>
                  <th>Max</th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map(([key, m]) => (
                  <tr key={key}>
                    <td><span className="badge badge-info">{key}</span></td>
                    <td>{m.count}</td>
                    <td>{m.errors}</td>
                    <td>{m.error_rate_pct}%</td>
                    <td>{m.p50_ms}ms</td>
                    <td><strong>{m.p95_ms}ms</strong></td>
                    <td>{m.p99_ms}ms</td>
                    <td>{m.avg_ms}ms</td>
                    <td>{m.max_ms}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && endpoints.length === 0 && !error && (
        <div className="empty-state">
          <div className="empty-state-text">No server metrics yet. Submit API requests first.</div>
        </div>
      )}
    </div>
  );
}
