interface CostData {
  total_cost_usd: number;
  per_agent: Record<string, number>;
  run_count: number;
}

interface Props {
  data?: CostData;
}

export function CostDashboard({ data }: Props) {
  if (!data) {
    return (
      <div style={{ padding: 16 }}>
        <h3>Cost Dashboard</h3>
        <p style={{ color: "#666" }}>No cost data yet — run the graph to see cost breakdown.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <h3>Cost Dashboard</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
        <div style={{ padding: 16, background: "#f0fdf4", borderRadius: 8 }}>
          <strong>Total Cost</strong>
          <p style={{ fontSize: 24, margin: 0 }}>${data.total_cost_usd.toFixed(4)}</p>
        </div>
        <div style={{ padding: 16, background: "#eff6ff", borderRadius: 8 }}>
          <strong>Run Count</strong>
          <p style={{ fontSize: 24, margin: 0 }}>{data.run_count}</p>
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <strong>Per Agent</strong>
        <ul>
          {Object.entries(data.per_agent).map(([agent, cost]) => (
            <li key={agent}>{agent}: ${cost.toFixed(5)}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
