import { useState, useEffect } from "react";
import { api } from "../api/client";

/** Live status indicator for the Scheduled Anomaly Scan.
 *
 * Fetches /alerts/scheduler on mount and polls every 5s.
 *
 * Color semantics:
 *   green  → scheduler task is running (Active)
 *   amber  → scheduler task is stopped but server is reachable (Inactive)
 *   red    → cannot reach /alerts/scheduler at all (Error)
 */

interface SchedulerData {
  running: boolean;
  interval_seconds: number;
  run_count?: number;
  last_run_at?: string | null;
  last_error?: string | null;
}

export function SchedulerStatus() {
  const [data, setData] = useState<SchedulerData | null>(null);
  const [error, setError] = useState(false);

  const fetchStatus = () => {
    api.alerts.getScheduler()
      .then((r) => {
        setData(r.data as SchedulerData);
        setError(false);
      })
      .catch(() => {
        setError(true);
      });
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const running = data?.running ?? false;
  const runCount = data?.run_count ?? 0;

  // red = comms error, amber = intentionally stopped, green = running
  const statusColor = error
    ? "var(--color-error)"
    : running
    ? "var(--color-success)"
    : "var(--color-warning)";

  const statusText = error
    ? "Scan: Error"
    : running
    ? "Scan: Active"
    : "Scan: Inactive";

  const title = error
    ? "Cannot reach scheduler endpoint"
    : `Scheduled Anomaly Scan | ${runCount} run${runCount !== 1 ? "s" : ""} | interval: ${data?.interval_seconds ?? "—"}s${data?.last_error ? ` | Last error: ${data.last_error}` : ""}`;

  return (
    <div className="status-indicator" title={title}>
      <span className="status-dot" style={{ background: statusColor }} />
      <span className="status-text">
        {statusText}
        {!error && (
          <span style={{ opacity: 0.65, fontSize: "0.85em", marginLeft: 4 }}>
            | {runCount} run{runCount !== 1 ? "s" : ""}
          </span>
        )}
      </span>
    </div>
  );
}
