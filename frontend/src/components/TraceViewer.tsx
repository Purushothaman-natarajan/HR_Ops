import { useState } from "react";
import type { TraceEvent } from "../types";

interface Props {
  events?: TraceEvent[];
}

const agentColors: Record<string, string> = {
  supervisor: "#6366f1",
  policy: "#10b981",
  action: "#3b82f6",
  anomaly: "#f59e0b",
  compliance: "#ef4444",
  anomaly_detection: "#f59e0b",
  compliance_veto: "#ef4444",
};

const agentIcons: Record<string, string> = {
  supervisor: "\u2605",
  policy: "\u2696",
  action: "\u2692",
  anomaly: "\u26A0",
  compliance: "\u2714",
  anomaly_detection: "\u26A0",
  compliance_veto: "\u2718",
};

/** Passive trace-event display with expandable rows.
 *
 * Renders a table of TraceEvent items with expandable detail for
 * input/output text. No API calls — events are passed as props.
 *
 * @example
 * <TraceViewer events={traceEvents} />
 */
export function TraceViewer({ events }: Props) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  if (!events || events.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">\u2601</div>
        <div className="empty-state-text">No trace events yet. Submit a query to see execution traces.</div>
      </div>
    );
  }

  const toggle = (i: number) => setExpanded((prev) => ({ ...prev, [i]: !prev[i] }));

  return (
    <div className="trace-list">
      {events.map((evt, i) => {
        const color = agentColors[evt.agent_role] || "#64748b";
        const icon = agentIcons[evt.agent_role] || "\u25CF";
        const isExpanded = expanded[i];

        return (
          <div key={i} className="trace-item">
            <div
              className={`trace-item-header${isExpanded ? " expanded" : ""}`}
              onClick={() => toggle(i)}
            >
              <div className="trace-node-icon" style={{ background: `${color}15`, color }}>
                {icon}
              </div>
              <div className="trace-node-name">
                {evt.node}
                <span style={{ fontWeight: 400, color: "var(--color-text-secondary)", marginLeft: 6 }}>
                  {evt.agent_role}
                </span>
              </div>
              <div className="trace-meta">
                {evt.cache_hit && <span className="badge badge-success">CACHED</span>}
                <span>{evt.duration_ms.toFixed(1)}ms</span>
                {evt.cost_usd !== undefined && evt.cost_usd > 0 && (
                  <span>${evt.cost_usd.toFixed(5)}</span>
                )}
                <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
                  {isExpanded ? "\u25B2" : "\u25BC"}
                </span>
              </div>
            </div>
            {isExpanded && (
              <div className="trace-item-body">
                <div className="trace-label">Input</div>
                <div className="trace-text">{evt.input_text}</div>
                <div className="trace-label">Output</div>
                <div className="trace-text">{evt.output_text}</div>
                {evt.model_used && (
                  <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>
                    Model: {evt.model_used}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
