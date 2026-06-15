import { useState, useEffect } from "react";
import { api } from "../api/client";

/** Compact top-right status indicator showing API health and graph run count.
 *
 * Calls api.health() and api.trace.runs() on mount.
 * Renders a colored dot (green/red/gray) + status text + run count.
 *
 * @example
 * <StatusIndicator />
 */
export function StatusIndicator() {
  const [health, setHealth] = useState<string>("checking...");
  const [runCount, setRunCount] = useState<number>(0);

  useEffect(() => {
    api.health()
      .then((r) => {
        const s =
          typeof r.data === "object" && r.data !== null
            ? (r.data as Record<string, unknown>).status
            : undefined;
        setHealth(typeof s === "string" ? s : "unknown");
      })
      .catch(() => setHealth("offline"));
    api.trace.runs().then((r) => setRunCount(r.data.runs.length)).catch(() => {});
  }, []);

  const dotColor =
    health === "ok" ? "var(--color-success)" : health === "offline" ? "var(--color-error)" : "#999";

  return (
    <div className="status-indicator">
      <span className="status-dot" style={{ background: dotColor }} />
      <span className="status-text">{health === "ok" ? "Online" : health}</span>
      <span className="status-sep">|</span>
      <span className="status-text">{runCount} run{runCount !== 1 ? "s" : ""}</span>
    </div>
  );
}
