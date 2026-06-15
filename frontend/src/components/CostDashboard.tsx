import { useState, useEffect } from "react";
import { api } from "../api/client";
import { Icon } from "./Icons";

interface CostEntry {
  agent: string;
  cost: number;
  calls: number;
}

/** Cost-tracking dashboard that aggregates LLM usage from trace runs.
 *
 * Fetches all trace runs via api.trace.runs() and computes
 * per-agent cost totals and call counts.
 *
 * @example
 * <CostDashboard />
 */
export function CostDashboard() {
  const [data, setData] = useState<CostEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");

  useEffect(() => {
    api.trace.runs().then((r) => {
      const runs = r.data.runs || [];
      const agg: Record<string, { cost: number; calls: number }> = {};
      for (const run of runs) {
        const events = run.trace_events || [];
        for (const evt of events) {
          const agent = evt.agent_role || "unknown";
          if (!agg[agent]) agg[agent] = { cost: 0, calls: 0 };
          agg[agent].cost += evt.cost_usd ?? 0;
          agg[agent].calls += 1;
        }
      }
      setData(
        Object.entries(agg).map(([agent, info]) => ({ agent, cost: info.cost, calls: info.calls }))
      );
    }).catch((e) => {
      console.warn("CostDashboard: failed to fetch trace runs", e);
      setFetchError("Could not load cost data. Backend may be unavailable.");
    }).finally(() => setLoading(false));
  }, []);

  const totalCost = data.reduce((s, e) => s + e.cost, 0);
  const totalCalls = data.reduce((s, e) => s + e.calls, 0);

  if (loading) {
    return (
      <div className="card">
        <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="spinner" />
          <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>Loading cost data...</span>
        </div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="card" style={{ borderLeft: "4px solid var(--color-error)" }}>
        <div className="card-body" style={{ padding: "12px 16px", display: "flex", alignItems: "flex-start", gap: 12 }}>
          <Icon name="warning" size={16} />
          <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5 }}>{fetchError}</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Cost Monitor</h1>
        <p className="page-desc">LLM usage cost breakdown by agent across all graph runs</p>
      </div>

      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Total Cost</div>
          <div className="stat-value" style={{ color: "var(--color-primary)" }}>
            ${totalCost.toFixed(5)}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total LLM Calls</div>
          <div className="stat-value">{totalCalls}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg Cost/Call</div>
          <div className="stat-value">
            ${totalCalls > 0 ? (totalCost / totalCalls).toFixed(6) : "0.000000"}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Cost Breakdown by Agent</span>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {data.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-text">No cost data available yet. Submit some queries first.</div>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Calls</th>
                  <th>Total Cost</th>
                  <th>Avg Cost</th>
                  <th>% of Total</th>
                </tr>
              </thead>
              <tbody>
                {data
                  .sort((a, b) => b.cost - a.cost)
                  .map((entry) => (
                    <tr key={entry.agent}>
                      <td><span className="badge badge-info">{entry.agent}</span></td>
                      <td>{entry.calls}</td>
                      <td>${entry.cost.toFixed(5)}</td>
                      <td>${(entry.calls > 0 ? entry.cost / entry.calls : 0).toFixed(6)}</td>
                      <td>{totalCost > 0 ? ((entry.cost / totalCost) * 100).toFixed(1) : "0.0"}%</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
