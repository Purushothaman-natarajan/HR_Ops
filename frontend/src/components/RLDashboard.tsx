import { useState, useEffect } from "react";
import { api } from "../api/client";

interface RLInfo {
  status: string;
  actions_selected?: Record<string, number>;
}

export function RLDashboard() {
  const [info] = useState<RLInfo>({ status: "active" });
  const [accuracy, setAccuracy] = useState<number | null>(null);

  useEffect(() => {
    api.health().then(() => {
      /* RL info would come from a dedicated endpoint */
    });
  }, []);

  return (
    <div style={{ padding: 16 }}>
      <h3>RL (LinUCB) Dashboard</h3>
      <p>Status: {info.status}</p>
      {accuracy !== null && <p>Accuracy: {(accuracy * 100).toFixed(1)}%</p>}
      <div style={{ marginTop: 12, padding: 12, background: "#f0fdf4", borderRadius: 8 }}>
        <p><strong>Actions Selected:</strong></p>
        {info.actions_selected ? (
          <ul>
            {Object.entries(info.actions_selected).map(([action, count]) => (
              <li key={action}>{action}: {count}</li>
            ))}
          </ul>
        ) : (
          <p>No data yet — run the graph to see action distribution.</p>
        )}
      </div>
    </div>
  );
}
