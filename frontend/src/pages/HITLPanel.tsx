import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { Icon } from "../components/Icons";
import type { PendingItem, AnomalyResult } from "../types";

/** HITL Panel — review pending agent escalations, approve/reject, and resume conversations.
 *
 * - Lists pending escalations with fully exposed context, proposed action, confidence, and reasoning
 * - Shows an interactive "Approve" and "Reject" decision portal
 * - Provides a "Continue in Chat" option to seamlessly pick up the conversation
 * - Keeps a resolved log for operator review
 */
interface HITLPanelProps {
  onContinueSession?: (sessionId: string, mode?: "standard" | "advanced") => void;
}

interface ResolvedItem {
  interaction_id: string;
  query: string;
  action: "approve" | "reject" | "modify";
  response: string;
  resolved_at: string;
  session_id?: string;
  context?: Record<string, any>;
  metadata?: Record<string, any>;
}

const AVAILABLE_ACTIONS = [
  "escalate_hr_review",
  "flag_for_review",
  "request_manager_review",
  "send_notification",
  "initiate_pip",
  "ignore"
];

export function HITLPanel({ onContinueSession }: HITLPanelProps) {
  const [items, setItems] = useState<PendingItem[]>([]);
  const [resolved, setResolved] = useState<ResolvedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"pending" | "resolved">("pending");

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.hitl.list();
      setItems(res.data.pending || []);
    } catch {
      setItems([]);
      console.warn("HITLPanel: failed to fetch pending items");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems();
    const t = setInterval(fetchItems, 15_000);
    return () => clearInterval(t);
  }, [fetchItems]);

  const handleAction = async (item: PendingItem, action: "approve" | "reject" | "modify", responseText: string, metadata?: Record<string, any>) => {
    try {
      await api.hitl.respond(item.interaction_id, action, responseText, metadata);
      setItems((prev) => prev.filter((i) => i.interaction_id !== item.interaction_id));
      setResolved((prev) => [
        {
          interaction_id: item.interaction_id,
          query: item.query,
          action,
          response: responseText || "Processed by operator.",
          resolved_at: new Date().toISOString(),
          session_id: item.session_id,
          context: item.context,
          metadata,
        },
        ...prev,
      ]);
    } catch (e) {
      console.warn("HITLPanel: respond failed", e);
    }
  };

  const tabBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: "8px 20px",
    borderRadius: 8,
    border: "none",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    background: active ? "linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%)" : "transparent",
    color: active ? "#fff" : "var(--color-text-secondary)",
    transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
    display: "flex",
    alignItems: "center",
    gap: 8,
    boxShadow: active ? "0 4px 12px rgba(99, 102, 241, 0.25)" : "none",
  });

  return (
    <div style={{ maxWidth: 840, margin: "0 auto", padding: "24px 0" }}>
      <div style={{ marginBottom: 24 }}>
        <h1 className="page-title" style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.025em" }}>
          Human-in-the-Loop Review
        </h1>
        <p className="page-desc" style={{ marginTop: 4 }}>
          Verify flagged compliance alerts, review anomaly confidence, and manage live routing escalations.
        </p>
      </div>

      {/* Tabs & Refresh Button Row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div style={{ display: "flex", gap: 6, background: "rgba(15, 23, 42, 0.04)", borderRadius: 10, padding: 4, width: "fit-content" }}>
          <button style={tabBtnStyle(activeTab === "pending")} onClick={() => setActiveTab("pending")}>
            Pending Queue
            {items.length > 0 && (
              <span style={{ marginLeft: 2, background: "var(--color-error)", color: "#fff", borderRadius: 12, padding: "2px 8px", fontSize: 11, fontWeight: 700 }}>
                {items.length}
              </span>
            )}
          </button>
          <button style={tabBtnStyle(activeTab === "resolved")} onClick={() => setActiveTab("resolved")}>
            Resolved Log
            {resolved.length > 0 && (
              <span style={{ marginLeft: 2, background: "rgba(15, 23, 42, 0.1)", color: "var(--color-text)", borderRadius: 12, padding: "2px 8px", fontSize: 11, fontWeight: 700 }}>
                {resolved.length}
              </span>
            )}
          </button>
        </div>

        <button className="btn btn-secondary" onClick={fetchItems} style={{ borderRadius: 8, height: 38, display: "flex", alignItems: "center", gap: 6 }}>
          <Icon name="refresh" size={14} />
          Refresh
        </button>
      </div>

      {loading && items.length === 0 && resolved.length === 0 ? (
        <div className="card" style={{ borderRadius: 12, border: "1px solid var(--color-border)" }}>
          <div className="card-body" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, padding: 48 }}>
            <div className="spinner" />
            <span style={{ color: "var(--color-text-secondary)", fontWeight: 500 }}>Retrieving escalations...</span>
          </div>
        </div>
      ) : activeTab === "pending" ? (
        items.length === 0 ? (
          <div className="empty-state" style={{ padding: "64px 32px", background: "var(--color-surface)", borderRadius: 16, border: "1px dashed var(--color-border)" }}>
            <div style={{ background: "rgba(16, 185, 129, 0.1)", color: "var(--color-success)", width: 56, height: 56, borderRadius: "50%", display: "flex", alignItems: "center", justifyItems: "center", margin: "0 auto 16px", justifyContent: "center" }}>
              <Icon name="check" size={28} />
            </div>
            <div className="empty-state-text" style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)", marginBottom: 4 }}>
              No Pending Actions
            </div>
            <div className="empty-state-text" style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
              All agent escalations have been processed. You're completely up to date!
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {items.map((item) => (
              <HitlItemCard
                key={item.interaction_id}
                item={item}
                onAction={handleAction}
                onContinueSession={onContinueSession}
              />
            ))}
          </div>
        )
      ) : (
        resolved.length === 0 ? (
          <div className="empty-state" style={{ padding: "64px 32px", background: "var(--color-surface)", borderRadius: 16, border: "1px dashed var(--color-border)" }}>
            <div className="empty-state-text" style={{ fontSize: 15, fontWeight: 600, color: "var(--color-text-secondary)" }}>
              No Resolved Decisions Yet
            </div>
            <div className="empty-state-text" style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 4 }}>
              Decisions processed in this session will appear here.
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {resolved.map((item) => (
              <ResolvedItemCard
                key={item.interaction_id}
                item={item}
                onContinueSession={onContinueSession}
              />
            ))}
          </div>
        )
      )}
    </div>
  );
}

function HitlAnomalyRow({ anomaly, idx }: { anomaly: AnomalyResult; idx: number }) {
  const fieldColors: Record<string, string> = {
    salary: "#8b5cf6",
    leave: "#3b82f6",
    attendance: "#f59e0b",
    performance: "#10b981",
    compliance: "#ef4444",
    payroll: "#ec4899",
  };
  const fieldColor = fieldColors[anomaly.anomaly_field?.toLowerCase()] || "var(--color-primary)";

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "20px 1fr 100px",
      gap: 10,
      alignItems: "center",
      padding: "8px 12px",
      borderBottom: "1px solid var(--color-border-light)",
      background: idx % 2 === 0 ? "transparent" : "rgba(15, 23, 42, 0.01)",
    }}>
      <div style={{
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: anomaly.detected ? "var(--color-error)" : "var(--color-success)",
        margin: "0 auto",
      }} />

      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 1 }}>
          <span style={{
            display: "inline-block",
            padding: "1px 6px",
            borderRadius: 3,
            fontSize: 9,
            fontWeight: 700,
            textTransform: "uppercase",
            background: `${fieldColor}12`,
            color: fieldColor,
          }}>
            {anomaly.anomaly_field || "unknown"}
          </span>
        </div>
        <div style={{
          fontSize: 12,
          color: "var(--color-text-secondary)",
          lineHeight: 1.3,
        }}>
          {anomaly.description || "No description available"}
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <span style={{
          fontSize: 10,
          fontWeight: 700,
          color: anomaly.severity >= 0.8 ? "var(--color-error)" : anomaly.severity >= 0.6 ? "var(--color-warning)" : "var(--color-success)",
          background: anomaly.severity >= 0.8 ? "rgba(239,68,68,0.08)" : anomaly.severity >= 0.6 ? "rgba(245,158,11,0.08)" : "rgba(16,185,129,0.08)",
          padding: "2px 6px",
          borderRadius: 4,
        }}>
          Sev: {Math.round((anomaly.severity ?? 0) * 100)}%
        </span>
      </div>
    </div>
  );
}

function HitlItemCard({
  item,
  onAction,
  onContinueSession,
}: {
  item: PendingItem;
  onAction: (item: PendingItem, action: "approve" | "reject" | "modify", response: string, metadata?: Record<string, any>) => void;
  onContinueSession?: (sessionId: string, mode?: "standard" | "advanced") => void;
}) {
  const [responseText, setResponseText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [grouping, setGrouping] = useState<"category" | "employee" | "flat">("category");

  const getEmployeeName = (desc: string) => {
    if (!desc) return "System / General";
    const cleanDesc = desc.replace(/^\[[A-Z0-9-]+\]\s+/, "");
    const withoutEmp = cleanDesc.replace(/^Employee\s+/, "");
    const words = withoutEmp.split(/\s+/);
    const nameWords = [];
    for (const w of words) {
      if (w && w[0] === w[0].toUpperCase() && /^[A-Za-z]/.test(w)) {
        nameWords.push(w);
      } else {
        break;
      }
    }
    return nameWords.length > 0 ? nameWords.join(" ") : "System / General";
  };

  const getEmployeeKey = (a: any) => {
    const eid = a.supporting_data?.employee_id || a.supporting_data?.Employee_ID || "";
    const name = getEmployeeName(a.description);
    if (eid) {
      return `${name} (${eid})`;
    }
    return name;
  };

  const groupedAnomalies = (() => {
    const results = item.context?.anomaly_results || [];
    if (grouping === "flat") return null;
    
    const groups: Record<string, typeof results> = {};
    for (const a of results) {
      let key = "General";
      if (grouping === "category") {
        key = a.anomaly_field || "general";
        key = key.replace(/\b\w/g, (c: string) => c.toUpperCase());
      } else if (grouping === "employee") {
        key = getEmployeeKey(a);
      }
      if (!groups[key]) groups[key] = [];
      groups[key].push(a);
    }
    return groups;
  })();

  const applyGroupAction = (groupName: string, actionType: "approve" | "reject" | "forward", targetAction?: string) => {
    const groupAnoms = (groupedAnomalies ? groupedAnomalies[groupName] : item.context?.anomaly_results) || [];
    const proposed = groupAnoms[0]?.recommended_action || groupAnoms[0]?.suggested_action || "escalate_hr_review";
    
    let resolvedAction = proposed;
    let desc = "";
    if (actionType === "approve") {
      resolvedAction = proposed;
      desc = `Approved proposed action (${proposed.replace(/_/g, " ")}) for ${groupName} issues.`;
    } else if (actionType === "reject") {
      resolvedAction = "ignore";
      desc = `Rejected/Ignored ${groupName} issues.`;
    } else if (actionType === "forward") {
      resolvedAction = targetAction || "escalate_hr_review";
      desc = `Forwarded ${groupName} issues to ${resolvedAction.replace(/_/g, " ")}.`;
    }

    setSelectedAction(resolvedAction);
    setResponseText((prev) => {
      const parts = prev ? prev.split("\n") : [];
      const filteredParts = parts.filter(p => !p.includes(`for ${groupName} issues`) && !p.includes(`${groupName} issues`));
      filteredParts.push(desc);
      return filteredParts.join("\n");
    });
  };

  const ageSeconds = Math.round((Date.now() - new Date(item.created_at).getTime()) / 1000);
  const ageLabel = ageSeconds < 60 ? `${ageSeconds}s ago` : `${Math.round(ageSeconds / 60)}m ago`;

  const anomaly = item.context?.anomaly_results?.[0];
  const confidence = anomaly?.severity !== undefined ? anomaly.severity : 0.85;
  const proposedAction = anomaly?.recommended_action || anomaly?.suggested_action || (item.context?.compliance_veto ? "veto-action" : "escalate-to-HR");
  const anomalyField = anomaly?.anomaly_field || (item.context?.compliance_veto ? "compliance" : "policy");

  const [selectedAction, setSelectedAction] = useState(proposedAction);

  const handle = async (action: "approve" | "reject") => {
    setSubmitting(true);
    if (action === "approve" && selectedAction !== proposedAction) {
      await onAction(item, "modify", responseText || `Action modified to ${selectedAction.replace(/_/g, " ")} by operator.`, { modified_action: selectedAction });
    } else {
      await onAction(item, action, responseText || "Processed by operator.");
    }
    setSubmitting(false);
  };

  // Color configuration depending on severity/agent
  const isHighRisk = confidence >= 0.8;
  const statusColor = isHighRisk ? "var(--color-error)" : "var(--color-warning)";
  const statusBg = isHighRisk ? "rgba(239, 68, 68, 0.08)" : "rgba(245, 158, 11, 0.08)";

  return (
    <div 
      className="hitl-card card" 
      style={{ 
        border: "1px solid var(--color-border)",
        borderLeft: `5px solid ${statusColor}`,
        borderRadius: 12,
        boxShadow: "var(--shadow-sm)",
        transition: "transform 0.2s, box-shadow 0.2s",
        background: "var(--color-surface)",
        overflow: "hidden"
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "var(--shadow-md)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = "var(--shadow-sm)";
      }}
    >
      <div className="card-body" style={{ padding: "24px" }}>
        {/* Card Top Badges */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="badge" style={{ background: "rgba(99, 102, 241, 0.12)", color: "var(--color-primary)", fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 12 }}>
              ROLE: {item.assigned_role?.toUpperCase() || "OPERATOR"}
            </span>
            <span className="badge" style={{ background: statusBg, color: statusColor, fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 12 }}>
              {anomalyField.toUpperCase()} ALERT
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 12, color: "var(--color-text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
              <Icon name="clock" size={12} /> {ageLabel}
            </span>
            {item.session_id && (
              <code style={{ fontSize: 11, background: "var(--color-bg)", padding: "2px 8px", borderRadius: 4, color: "var(--color-text-secondary)", border: "1px solid var(--color-border)" }}>
                ID: {item.session_id.slice(0, 8)}
              </code>
            )}
          </div>
        </div>

        {/* Structured Context Fields (Requirement D) */}
        <div style={{ 
          display: "grid", 
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", 
          gap: 16, 
          background: "var(--color-bg)", 
          borderRadius: 8, 
          padding: 16, 
          marginBottom: 16,
          border: "1px solid var(--color-border-light)"
        }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Anomaly Category
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)", marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor }} />
              {anomalyField.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>
              Action Remediation
            </div>
            <select
              value={selectedAction}
              onChange={(e) => setSelectedAction(e.target.value)}
              disabled={submitting}
              style={{
                width: "100%",
                background: "#fff",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                padding: "6px 10px",
                fontSize: 13,
                fontWeight: 600,
                color: "var(--color-primary)",
                fontFamily: "var(--font-mono)",
                cursor: "pointer",
                outline: "none",
                appearance: "none",
                WebkitAppearance: "none",
                backgroundImage: "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"12\" height=\"12\" fill=\"none\" stroke=\"%236366f1\" stroke-width=\"2\" viewBox=\"0 0 24 24\"><polyline points=\"6 9 12 15 18 9\"/></svg>')",
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 10px center",
                paddingRight: "28px"
              }}
            >
              {AVAILABLE_ACTIONS.map(act => (
                <option key={act} value={act}>
                  {act.replace(/_/g, " ")}
                </option>
              ))}
              {!AVAILABLE_ACTIONS.includes(proposedAction) && (
                <option value={proposedAction}>
                  {proposedAction.replace(/_/g, " ")} (Proposed)
                </option>
              )}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Confidence Score
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: statusColor, marginTop: 4 }}>
              {(confidence * 100).toFixed(0)}% Match
            </div>
          </div>
        </div>

        {/* Agent Reasoning & Anomalies Breakdown */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Agent Reasoning &amp; Anomaly Breakdown
            </div>
            {item.context?.anomaly_results && item.context.anomaly_results.length > 0 && (
              <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>Group:</span>
                {(["category", "employee", "flat"] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={(e) => {
                      e.stopPropagation();
                      setGrouping(mode);
                    }}
                    style={{
                      padding: "2px 8px",
                      borderRadius: 10,
                      fontSize: 9,
                      fontWeight: 700,
                      border: "1px solid var(--color-border)",
                      background: grouping === mode ? "var(--color-primary)" : "transparent",
                      color: grouping === mode ? "#fff" : "var(--color-text-secondary)",
                      cursor: "pointer",
                    }}
                  >
                    {mode.toUpperCase()}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div style={{
            background: "rgba(255,255,255,0.6)",
            padding: 14,
            borderRadius: 8,
            border: "1px solid var(--color-border-light)",
            display: "flex",
            flexDirection: "column",
            gap: 12
          }}>
            {/* Display simple query or first anomaly text if no results */}
            {(!item.context?.anomaly_results || item.context.anomaly_results.length === 0) ? (
              <div style={{ fontSize: 13, lineHeight: "1.5", color: "var(--color-text)" }}>
                {anomaly?.description || item.query}
              </div>
            ) : grouping === "flat" ? (
              <div style={{ display: "flex", flexDirection: "column", border: "1px solid var(--color-border-light)", borderRadius: 6, overflow: "hidden" }}>
                {item.context.anomaly_results.map((a: AnomalyResult, i: number) => (
                  <HitlAnomalyRow key={i} anomaly={a} idx={i} />
                ))}
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {Object.entries(groupedAnomalies || {}).map(([groupName, anoms]) => (
                  <div key={groupName} style={{
                    border: "1px solid var(--color-border-light)",
                    borderRadius: 6,
                    background: "rgba(255, 255, 255, 0.4)",
                    overflow: "hidden"
                  }}>
                    {/* Inline Group header with Quick Actions */}
                    <div style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "8px 12px",
                      background: "rgba(15, 23, 42, 0.03)",
                      borderBottom: "1px solid var(--color-border-light)"
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--color-primary)" }}>{groupName}</span>
                        <span style={{
                          fontSize: 9,
                          fontWeight: 700,
                          background: "rgba(15, 23, 42, 0.06)",
                          color: "var(--color-text-secondary)",
                          padding: "1px 6px",
                          borderRadius: 8
                        }}>
                          {anoms.length}
                        </span>
                      </div>
                      
                      {/* Group Quick Actions */}
                      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <button
                          onClick={(e) => { e.stopPropagation(); applyGroupAction(groupName, "approve"); }}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 2,
                            padding: "2px 6px",
                            borderRadius: 4,
                            fontSize: 10,
                            fontWeight: 700,
                            background: "rgba(16,185,129,0.06)",
                            color: "var(--color-success)",
                            border: "1px solid rgba(16,185,129,0.12)",
                            cursor: "pointer",
                          }}
                        >
                          Approve
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); applyGroupAction(groupName, "reject"); }}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 2,
                            padding: "2px 6px",
                            borderRadius: 4,
                            fontSize: 10,
                            fontWeight: 700,
                            background: "rgba(239,68,68,0.06)",
                            color: "var(--color-error)",
                            border: "1px solid rgba(239,68,68,0.12)",
                            cursor: "pointer",
                          }}
                        >
                          Reject
                        </button>
                        
                        <select
                          onChange={(e) => { applyGroupAction(groupName, "forward", e.target.value); e.target.value = ""; }}
                          defaultValue=""
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            padding: "2px 4px",
                            borderRadius: 4,
                            fontSize: 10,
                            fontWeight: 700,
                            background: "rgba(99,102,241,0.06)",
                            color: "var(--color-primary)",
                            border: "1px solid rgba(99,102,241,0.12)",
                            cursor: "pointer",
                            outline: "none",
                          }}
                        >
                          <option value="" disabled>Forward...</option>
                          {AVAILABLE_ACTIONS.map((act) => (
                            <option key={act} value={act}>
                              {act.replace(/_/g, " ")}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Group anomalies list */}
                    <div style={{ display: "flex", flexDirection: "column" }}>
                      {anoms.map((a: AnomalyResult, idx: number) => (
                        <HitlAnomalyRow key={idx} anomaly={a} idx={idx} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Decision Input */}
        <textarea
          className="input hitl-textarea"
          value={responseText}
          onChange={(e) => setResponseText(e.target.value)}
          placeholder="Enter operator resolution comments or modification notes..."
          disabled={submitting}
          rows={2}
          style={{ width: "100%", borderRadius: 8, padding: "10px 12px", border: "1px solid var(--color-border)", fontSize: 13, marginBottom: 16, background: "#fff", transition: "border 0.2s" }}
        />

        {/* Decision Actions */}
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <button 
            className="btn btn-success" 
            onClick={() => handle("approve")} 
            disabled={submitting}
            style={{ 
              height: 38, 
              padding: "0 18px", 
              borderRadius: 8, 
              fontWeight: 600, 
              background: selectedAction !== proposedAction
                ? "linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%)"
                : "linear-gradient(135deg, #10b981 0%, #059669 100%)", 
              color: "#fff",
              border: "none",
              boxShadow: selectedAction !== proposedAction
                ? "0 2px 6px rgba(99, 102, 241, 0.15)"
                : "0 2px 6px rgba(16, 185, 129, 0.15)",
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            {submitting ? (
              <div className="spinner" style={{ width: 14, height: 14, borderColor: "#fff" }} />
            ) : (
              <Icon name={selectedAction !== proposedAction ? "edit" : "check"} size={14} />
            )}
            {selectedAction !== proposedAction ? "Submit Modified Action" : "Approve Action"}
          </button>
          <button 
            className="btn btn-danger" 
            onClick={() => handle("reject")} 
            disabled={submitting}
            style={{ 
              height: 38, 
              padding: "0 18px", 
              borderRadius: 8, 
              fontWeight: 600, 
              background: "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)", 
              color: "#fff",
              border: "none",
              boxShadow: "0 2px 6px rgba(239, 68, 68, 0.15)",
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            {submitting ? <div className="spinner" style={{ width: 14, height: 14, borderColor: "#fff" }} /> : "✗"}
            Reject Action
          </button>
          
          {item.session_id && onContinueSession && (
            <button
              className="btn btn-secondary"
              style={{ marginLeft: "auto", borderRadius: 8, height: 38, fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}
              onClick={() => onContinueSession(item.session_id!, "advanced")}
            >
              <Icon name="arrow" size={12} />
              Resume Chat
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ResolvedItemCard({
  item,
  onContinueSession,
}: {
  item: ResolvedItem;
  onContinueSession?: (sessionId: string, mode?: "standard" | "advanced") => void;
}) {
  const anomaly = item.context?.anomaly_results?.[0];
  const isApproved = item.action === "approve";
  const isModified = item.action === "modify";
  
  let badgeColor = "var(--color-error)";
  let badgeBg = "rgba(239, 68, 68, 0.12)";
  let badgeText = "REJECTED";
  let badgeIcon = "close";

  if (isApproved) {
    badgeColor = "var(--color-success)";
    badgeBg = "rgba(16, 185, 129, 0.12)";
    badgeText = "APPROVED";
    badgeIcon = "check";
  } else if (isModified) {
    badgeColor = "var(--color-primary)";
    badgeBg = "rgba(99, 102, 241, 0.12)";
    badgeText = "MODIFIED";
    badgeIcon = "edit";
  }
  
  return (
    <div 
      className="hitl-card card" 
      style={{ 
        borderLeft: `5px solid ${isApproved ? "var(--color-success)" : isModified ? "var(--color-primary)" : "var(--color-error)"}`,
        borderRadius: 12,
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        boxShadow: "var(--shadow-sm)"
      }}
    >
      <div className="card-body" style={{ padding: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="badge" style={{ 
              background: badgeBg, 
              color: badgeColor,
              fontWeight: 700,
              fontSize: 11,
              padding: "3px 10px",
              borderRadius: 12,
              display: "flex",
              alignItems: "center",
              gap: 4
            }}>
              {badgeIcon === "check" || badgeIcon === "edit" ? <Icon name={badgeIcon} size={12} /> : "✗"}
              {badgeText}
            </span>
            {isModified && item.metadata?.modified_action && (
              <span style={{ fontSize: 12, color: "var(--color-text-secondary)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}>
                changed to <code style={{ fontSize: 11, background: "var(--color-bg)", padding: "2px 6px", borderRadius: 4, color: "var(--color-primary)", border: "1px solid var(--color-border)" }}>{item.metadata.modified_action.replace(/_/g, " ")}</code>
              </span>
            )}
            <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
              {new Date(item.resolved_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          {item.session_id && onContinueSession && (
            <button
              className="btn btn-secondary"
              style={{ fontSize: 11, padding: "4px 10px", height: "auto", display: "inline-flex", alignItems: "center", gap: 4, borderRadius: 6 }}
              onClick={() => onContinueSession(item.session_id!, "advanced")}
            >
              <Icon name="arrow" size={10} />
              Resume Context
            </button>
          )}
        </div>
        
        <div style={{ fontSize: 13, color: "var(--color-text-secondary)", fontWeight: 500, marginBottom: 8 }}>
          {anomaly?.description || item.query}
        </div>
        
        {item.response && (
          <div style={{ 
            fontSize: 12, 
            color: "var(--color-text-secondary)", 
            background: "var(--color-bg)", 
            padding: "8px 12px", 
            borderRadius: 6, 
            fontStyle: "italic",
            border: "1px solid var(--color-border-light)"
          }}>
            Operator Notes: "{item.response}"
          </div>
        )}
      </div>
    </div>
  );
}
