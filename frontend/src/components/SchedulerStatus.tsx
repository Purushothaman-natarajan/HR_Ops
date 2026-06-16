import { useState, useEffect } from "react";
import { api } from "../api/client";

/** Live status indicator for the Scheduled Anomaly Scan.
 *
 * Fetches /alerts/scheduler on mount and polls it.
 * Renders a colored dot (green for active, red/gray for inactive) + status text.
 */
export function SchedulerStatus() {
  const [running, setRunning] = useState<boolean | null>(null);
  const [error, setError] = useState(false);

  const fetchStatus = () => {
    api.alerts.getScheduler()
      .then((r) => {
        setRunning(r.data.running);
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

  const statusColor = error
    ? "var(--color-error)"
    : running === true
    ? "var(--color-success)"
    : "var(--color-error)";

  const statusText = error
    ? "Scan: Error"
    : running === true
    ? "Scan: Active"
    : "Scan: Inactive";

  return (
    <div className="status-indicator" title="Scheduled Anomaly Scan Status">
      <span className="status-dot" style={{ background: statusColor }} />
      <span className="status-text">{statusText}</span>
    </div>
  );
}
