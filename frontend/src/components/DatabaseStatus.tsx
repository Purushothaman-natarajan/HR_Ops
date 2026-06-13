import { useState, useEffect } from "react";
import { api } from "../api/client";

interface DatabaseInfo {
  connected: boolean;
  employees_count: number;
  attendance_count?: number;
  payroll_count?: number;
  leaves_count?: number;
  performance_count?: number;
  database_path?: string;
}

export function DatabaseStatus() {
  const [info, setInfo] = useState<DatabaseInfo | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.database.status()
      .then((r) => setInfo(r.data))
      .catch(() => setError("unavailable"));
  }, []);

  const statusColor =
    error || (info && !info.connected)
      ? "var(--color-error)"
      : info && info.connected && info.employees_count > 0
        ? "var(--color-success)"
        : "#999";

  return (
    <div className="status-indicator">
      <span className="status-dot" style={{ background: statusColor }} />
      <span className="status-text">
        {error
          ? "DB: Offline"
          : info && !info.connected
            ? "DB: disconnected"
            : info
              ? `DB: ${info.employees_count} employees`
              : "DB: checking..."}
      </span>
    </div>
  );
}
