interface TraceEvent {
  node: string;
  agent_role: string;
  input_text: string;
  output_text: string;
  duration_ms: number;
  cost_usd?: number;
  cache_hit?: boolean;
}

interface Props {
  events?: TraceEvent[];
}

export function TraceViewer({ events }: Props) {
  if (!events || events.length === 0) {
    return <div style={{ padding: 16, color: "#666" }}>No trace events.</div>;
  }

  return (
    <div style={{ padding: 16 }}>
      <h3>Trace Events</h3>
      {events.map((evt, i) => (
        <div
          key={i}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: 12,
            marginBottom: 8,
            fontFamily: "monospace",
            fontSize: 13,
          }}
        >
          <div>
            <strong>{evt.node}</strong> ({evt.agent_role})
            {evt.cache_hit && <span style={{ marginLeft: 8, color: "#059669" }}>CACHED</span>}
          </div>
          <div style={{ color: "#666", marginTop: 4 }}>
            {evt.duration_ms.toFixed(1)}ms
            {evt.cost_usd !== undefined && ` · $${evt.cost_usd.toFixed(5)}`}
          </div>
          <details style={{ marginTop: 4 }}>
            <summary>Details</summary>
            <p><strong>Input:</strong> {evt.input_text}</p>
            <p><strong>Output:</strong> {evt.output_text}</p>
          </details>
        </div>
      ))}
    </div>
  );
}
