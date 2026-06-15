import { useState, useMemo } from "react";
import type { TraceEvent } from "../types";
import { Icon } from "./Icons";
import type { IconName } from "./Icons";

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

const agentIcons: Record<string, IconName> = {
  supervisor: "supervisor",
  policy: "policy",
  action: "action",
  anomaly: "anomaly",
  compliance: "compliance",
  anomaly_detection: "anomaly",
  compliance_veto: "compliance-veto",
};

type SortKey = "order" | "duration" | "cost";
type FilterKey = "all" | "supervisor" | "policy" | "action" | "anomaly" | "compliance";

export function TraceViewer({ events }: Props) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [search, setSearch] = useState("");
  const [filterRole, setFilterRole] = useState<FilterKey>("all");
  const [sortKey, setSortKey] = useState<SortKey>("order");
  const [showRaw, setShowRaw] = useState(false);

  const filtered = useMemo(() => {
    if (!events) return [];
    let list = [...events];
    if (filterRole !== "all") {
      list = list.filter((e) => e.agent_role === filterRole);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (e) =>
          e.node.toLowerCase().includes(q) ||
          e.agent_role.toLowerCase().includes(q) ||
          e.input_text.toLowerCase().includes(q) ||
          e.output_text.toLowerCase().includes(q)
      );
    }
    if (sortKey === "duration") {
      list.sort((a, b) => b.duration_ms - a.duration_ms);
    } else if (sortKey === "cost") {
      list.sort((a, b) => (b.cost_usd ?? 0) - (a.cost_usd ?? 0));
    }
    return list;
  }, [events, filterRole, search, sortKey]);

  if (!events || events.length === 0) {
    return (
      <div className="empty-state">
        <Icon name="cloud" size={48} className="empty-state-icon" />
        <div className="empty-state-text">No trace events yet. Submit a query to see execution traces.</div>
      </div>
    );
  }

  const toggle = (i: number) => setExpanded((prev) => ({ ...prev, [i]: !prev[i] }));

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(events, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `trace_events_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
        <input
          className="input"
          style={{ flex: 1, minWidth: 140, fontSize: 12, padding: "4px 8px" }}
          placeholder="Search events..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="input"
          style={{ width: "auto", fontSize: 12, padding: "4px 8px" }}
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value as FilterKey)}
        >
          <option value="all">All Roles</option>
          <option value="supervisor">Supervisor</option>
          <option value="policy">Policy</option>
          <option value="action">Action</option>
          <option value="anomaly">Anomaly</option>
          <option value="compliance">Compliance</option>
        </select>
        <select
          className="input"
          style={{ width: "auto", fontSize: 12, padding: "4px 8px" }}
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
        >
          <option value="order">Order</option>
          <option value="duration">Duration</option>
          <option value="cost">Cost</option>
        </select>
        <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={showRaw} onChange={(e) => setShowRaw(e.target.checked)} />
          Raw JSON
        </label>
        <button className="btn btn-sm btn-secondary" onClick={exportJson} style={{ fontSize: 12 }}>
          Export JSON
        </button>
      </div>

      <div className="trace-list">
        {filtered.length === 0 && (
          <div className="empty-state" style={{ padding: 16 }}>
            <div className="empty-state-text">No events match the current filter.</div>
          </div>
        )}
        {filtered.map((evt, i) => {
          const color = agentColors[evt.agent_role] || "#64748b";
          const icon = agentIcons[evt.agent_role] || "cloud";
          const isExpanded = expanded[i];
          const originalIndex = events.indexOf(evt);

          return (
            <div key={originalIndex} className="trace-item">
              <div
                className={`trace-item-header${isExpanded ? " expanded" : ""}`}
                onClick={() => toggle(originalIndex)}
              >
                <div className="trace-node-icon" style={{ background: `${color}15`, color }}>
                  <Icon name={icon} size={14} />
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
                    <Icon name={isExpanded ? "chevron-up" : "chevron-down"} size={10} />
                  </span>
                </div>
              </div>
              {isExpanded && (
                <div className="trace-item-body">
                  {showRaw ? (
                    <pre style={{ fontSize: 11, overflow: "auto", maxHeight: 300 }}>
                      {JSON.stringify(evt, null, 2)}
                    </pre>
                  ) : (
                    <>
                      <div className="trace-label">Input</div>
                      <div className="trace-text">{evt.input_text}</div>
                      <div className="trace-label">Output</div>
                      <div className="trace-text">{evt.output_text}</div>

                      {evt.reasoning && (
                        <>
                          <div className="trace-label">Reasoning</div>
                          <div className="trace-text" style={{ color: "var(--color-primary)", fontStyle: "italic" }}>
                            {evt.reasoning}
                          </div>
                        </>
                      )}

                      {evt.alternatives && evt.alternatives.length > 0 && (
                        <>
                          <div className="trace-label">Alternatives Considered</div>
                          <div style={{ fontSize: 12, display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
                            {evt.alternatives.map((alt, j) => (
                              <span key={j} className="badge badge-info">
                                {alt.agent}: {alt.score?.toFixed(3) ?? "N/A"}
                              </span>
                            ))}
                          </div>
                        </>
                      )}

                      {evt.retrieved_docs && evt.retrieved_docs.length > 0 && (
                        <>
                          <div className="trace-label">Retrieved Documents</div>
                          <div style={{ fontSize: 12, marginTop: 4 }}>
                            {evt.retrieved_docs.map((doc, j) => (
                              <div key={j} style={{ padding: "4px 8px", marginBottom: 4, background: "var(--color-bg)", borderRadius: 4 }}>
                                <div style={{ fontWeight: 600 }}>{doc.source}</div>
                                <div style={{ color: "var(--color-text-secondary)" }}>Score: {doc.score?.toFixed(3) ?? "N/A"}</div>
                                <div style={{ color: "var(--color-text-muted)", fontSize: 11, maxHeight: 60, overflow: "hidden" }}>
                                  {doc.chunk}
                                </div>
                              </div>
                            ))}
                          </div>
                        </>
                      )}

                      {evt.tool_call && Object.keys(evt.tool_call).length > 0 && (
                        <>
                          <div className="trace-label">Tool Call</div>
                          <pre style={{ fontSize: 11, background: "var(--color-bg)", padding: 8, borderRadius: 4, overflow: "auto", maxHeight: 150 }}>
                            {JSON.stringify(evt.tool_call, null, 2)}
                          </pre>
                        </>
                      )}

                      {evt.model_used && (
                        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>
                          Model: {evt.model_used}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
