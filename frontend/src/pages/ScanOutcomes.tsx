import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { Icon } from "../components/Icons";
import type { ScanOutcome, SchedulerStatus, AnomalyResult } from "../types";

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function relativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  } catch {
    return "";
  }
}

function formatInterval(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

const AVAILABLE_ACTIONS = [
  "escalate_hr_review",
  "flag_for_review",
  "request_manager_review",
  "send_notification",
  "initiate_pip",
  "ignore"
];

// ── Severity Bar ─────────────────────────────────────────────────────────────

function SeverityBar({ severity }: { severity: number }) {
  const pct = Math.round(severity * 100);
  const color =
    pct >= 80 ? "var(--color-error)" :
    pct >= 60 ? "var(--color-warning)" :
    "var(--color-success)";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 120 }}>
      <div style={{
        flex: 1,
        height: 6,
        background: "var(--color-border)",
        borderRadius: 3,
        overflow: "hidden",
      }}>
        <div style={{
          width: `${pct}%`,
          height: "100%",
          background: color,
          borderRadius: 3,
          transition: "width 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
        }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, minWidth: 32 }}>{pct}%</span>
    </div>
  );
}

// ── Single Anomaly Row ────────────────────────────────────────────────────────

function AnomalyRow({ anomaly, idx }: { anomaly: AnomalyResult; idx: number }) {
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
      gridTemplateColumns: "32px 1fr 160px 180px",
      gap: 12,
      alignItems: "center",
      padding: "10px 16px",
      borderBottom: "1px solid var(--color-border-light)",
      background: idx % 2 === 0 ? "transparent" : "rgba(15, 23, 42, 0.015)",
    }}>
      {/* Status dot */}
      <div style={{
        width: 10,
        height: 10,
        borderRadius: "50%",
        background: anomaly.detected ? "var(--color-error)" : "var(--color-success)",
        boxShadow: anomaly.detected ? "0 0 0 3px rgba(239,68,68,0.15)" : "0 0 0 3px rgba(16,185,129,0.15)",
        margin: "0 auto",
      }} />

      {/* Field + description */}
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{
            display: "inline-block",
            padding: "1px 8px",
            borderRadius: 4,
            fontSize: 10,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            background: `${fieldColor}18`,
            color: fieldColor,
          }}>
            {anomaly.anomaly_field || "unknown"}
          </span>
          {!anomaly.detected && (
            <span style={{ fontSize: 10, color: "var(--color-text-muted)", fontStyle: "italic" }}>No anomaly</span>
          )}
        </div>
        <div style={{
          fontSize: 12,
          color: "var(--color-text-secondary)",
          lineHeight: 1.4,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}>
          {anomaly.description || "No description available"}
        </div>
      </div>

      {/* Severity */}
      <SeverityBar severity={anomaly.severity ?? 0} />

      {/* Suggested action */}
      <div style={{
        fontSize: 11,
        color: "var(--color-text-muted)",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }} title={anomaly.suggested_action}>
        {anomaly.suggested_action || "—"}
      </div>
    </div>
  );
}

// ── Scan Card ─────────────────────────────────────────────────────────────────

function ScanCard({ outcome, onMarkRead, onRefresh }: {
  outcome: ScanOutcome;
  onMarkRead: (id: string) => void;
  onRefresh: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [selectedAction, setSelectedAction] = useState("");
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
    const results = outcome.anomaly_results;
    if (grouping === "flat") return null;
    
    const groups: Record<string, typeof results> = {};
    for (const a of results) {
      let key = "General";
      if (grouping === "category") {
        key = a.anomaly_field || "general";
        key = key.replace(/\b\w/g, (c) => c.toUpperCase());
      } else if (grouping === "employee") {
        key = getEmployeeKey(a);
      }
      if (!groups[key]) groups[key] = [];
      groups[key].push(a);
    }
    return groups;
  })();

  const applyGroupAction = (groupName: string, actionType: "approve" | "reject" | "forward", targetAction?: string) => {
    const groupAnoms = (groupedAnomalies ? groupedAnomalies[groupName] : outcome.anomaly_results) || [];
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

  const hitlReq = outcome.hitl_request;
  const anomaly = hitlReq?.context?.anomaly_results?.[0];
  const confidence = anomaly?.severity !== undefined ? anomaly.severity : 0.85;
  const proposedAction = anomaly?.recommended_action || anomaly?.suggested_action || (hitlReq?.context?.compliance_veto ? "veto-action" : "escalate-to-HR");

  useEffect(() => {
    if (hitlReq) {
      const anomaly = hitlReq.context?.anomaly_results?.[0];
      const proposed = anomaly?.recommended_action || anomaly?.suggested_action || (hitlReq.context?.compliance_veto ? "veto-action" : "escalate-to-HR");
      setSelectedAction(proposed);
    }
  }, [hitlReq]);

  const handleAction = async (action: "approve" | "reject") => {
    if (!hitlReq) return;
    setSubmitting(true);
    try {
      if (action === "approve" && selectedAction !== proposedAction) {
        await api.hitl.respond(hitlReq.interaction_id, "modify", responseText || `Action modified to ${selectedAction.replace(/_/g, " ")} by operator.`, { modified_action: selectedAction });
      } else {
        await api.hitl.respond(hitlReq.interaction_id, action, responseText || "Processed by operator.");
      }
      onRefresh();
    } catch (e) {
      console.warn("Scan outcomes hitl respond failed", e);
    } finally {
      setSubmitting(false);
    }
  };

  const isNew = outcome.alert_status === "new";
  const hasAnomalies = outcome.total_anomalies > 0;
  const hasError = outcome.status === "error";

  const borderColor =
    hasError ? "var(--color-error)" :
    outcome.compliance_veto ? "var(--color-error)" :
    hasAnomalies ? "var(--color-warning)" :
    "var(--color-success)";

  const headerBg =
    hasError ? "rgba(239,68,68,0.04)" :
    outcome.compliance_veto ? "rgba(239,68,68,0.04)" :
    hasAnomalies ? "rgba(245,158,11,0.04)" :
    "rgba(16,185,129,0.04)";

  return (
    <div className="scan-card" style={{
      borderLeft: `4px solid ${borderColor}`,
      opacity: isNew ? 1 : 0.85,
    }}>
      {/* Card header — always visible */}
      <div
        className="scan-card-header"
        style={{ background: headerBg }}
        onClick={() => {
          setExpanded(!expanded);
          if (isNew) onMarkRead(outcome.id);
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
          {/* Trigger badge */}
          <span className={`scan-trigger-badge scan-trigger-${outcome.trigger_type}`}>
            <Icon
              name={outcome.trigger_type === "scheduled" ? "clock" : "scan"}
              size={10}
            />
            {outcome.trigger_type === "scheduled" ? "Scheduled" : "Manual"}
          </span>

          {/* Compliance veto */}
          {outcome.compliance_veto && (
            <span className="scan-veto-badge">
              <Icon name="shield" size={10} /> VETOED
            </span>
          )}

          {/* Status */}
          <span className={`scan-status-badge scan-status-${outcome.status}`}>
            {outcome.status === "error" ? "Error" : "Completed"}
          </span>

          {/* Anomaly count */}
          {hasAnomalies ? (
            <span className="scan-anomaly-count scan-anomaly-count-warn">
              <Icon name="anomaly" size={11} />
              {outcome.total_anomalies} anomal{outcome.total_anomalies !== 1 ? "ies" : "y"}
            </span>
          ) : !hasError ? (
            <span className="scan-anomaly-count scan-anomaly-count-ok">
              <Icon name="check" size={11} /> Clean
            </span>
          ) : null}

          {isNew && <span className="scan-new-dot" />}
        </div>

        {/* Time + expand */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, color: "var(--color-text-secondary)", fontWeight: 500 }}>
              {relativeTime(outcome.created_at)}
            </div>
            <div style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
              {formatTime(outcome.created_at)}
            </div>
          </div>
          {outcome.total_cost_usd > 0 && (
            <span className="scan-cost-chip">
              ${outcome.total_cost_usd.toFixed(5)}
            </span>
          )}
          <Icon
            name={expanded ? "chevron-up" : "chevron-down"}
            size={14}
            style={{ color: "var(--color-text-muted)", flexShrink: 0 }}
          />
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="scan-card-body">
          {/* Agent summary */}
          {outcome.final_response && (
            <div style={{ marginBottom: 20 }}>
              <div className="scan-section-label">Agent Summary</div>
              <div className="scan-summary-text">{outcome.final_response}</div>
            </div>
          )}

          {/* Anomaly breakdown table */}
          {outcome.anomaly_results.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div className="scan-section-label" style={{ marginBottom: 0 }}>
                  Anomaly Breakdown
                  <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 400, color: "var(--color-text-muted)" }}>
                    ({outcome.total_anomalies} of {outcome.anomaly_results.length} detected)
                  </span>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <span style={{ fontSize: 11, color: "var(--color-text-muted)", fontWeight: 500 }}>Group by:</span>
                  {(["category", "employee", "flat"] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={(e) => {
                        e.stopPropagation();
                        setGrouping(mode);
                      }}
                      style={{
                        padding: "3px 10px",
                        borderRadius: 12,
                        fontSize: 10,
                        fontWeight: 700,
                        border: "1px solid var(--color-border)",
                        background: grouping === mode ? "var(--color-primary)" : "transparent",
                        color: grouping === mode ? "#fff" : "var(--color-text-secondary)",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      {mode.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {grouping === "flat" ? (
                <div className="scan-anomaly-table">
                  {/* Table header */}
                  <div style={{
                    display: "grid",
                    gridTemplateColumns: "32px 1fr 160px 180px",
                    gap: 12,
                    padding: "8px 16px",
                    background: "var(--color-bg)",
                    borderBottom: "2px solid var(--color-border)",
                  }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", textAlign: "center" }}>●</div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>Field / Description</div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>Severity</div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>Suggested Action</div>
                  </div>
                  {outcome.anomaly_results.map((a, i) => (
                    <AnomalyRow key={i} anomaly={a} idx={i} />
                  ))}
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {Object.entries(groupedAnomalies || {}).map(([groupName, anoms]) => {
                    const isHitlPending = outcome.hitl_needed && outcome.hitl_request && outcome.hitl_request.status === "pending";
                    return (
                      <div key={groupName} style={{
                        border: "1px solid var(--color-border-light)",
                        borderRadius: 8,
                        background: "rgba(255, 255, 255, 0.4)",
                        overflow: "hidden"
                      }}>
                        {/* Group Header */}
                        <div style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "10px 16px",
                          background: "var(--color-bg)",
                          borderBottom: "1px solid var(--color-border-light)"
                        }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span style={{ fontSize: 13, fontWeight: 700, color: "var(--color-primary)" }}>{groupName}</span>
                            <span style={{
                              fontSize: 10,
                              fontWeight: 700,
                              background: "rgba(15, 23, 42, 0.08)",
                              color: "var(--color-text-secondary)",
                              padding: "2px 8px",
                              borderRadius: 10
                            }}>
                              {anoms.length} issue{anoms.length !== 1 ? "s" : ""}
                            </span>
                          </div>
                          {isHitlPending && (
                            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                              <button
                                onClick={(e) => { e.stopPropagation(); applyGroupAction(groupName, "approve"); }}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 4,
                                  padding: "4px 10px",
                                  borderRadius: 6,
                                  fontSize: 11,
                                  fontWeight: 700,
                                  background: "rgba(16,185,129,0.08)",
                                  color: "var(--color-success)",
                                  border: "1px solid rgba(16,185,129,0.15)",
                                  cursor: "pointer",
                                  transition: "all 0.15s ease",
                                }}
                              >
                                <Icon name="check" size={10} /> Approve
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); applyGroupAction(groupName, "reject"); }}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 4,
                                  padding: "4px 10px",
                                  borderRadius: 6,
                                  fontSize: 11,
                                  fontWeight: 700,
                                  background: "rgba(239,68,68,0.08)",
                                  color: "var(--color-error)",
                                  border: "1px solid rgba(239,68,68,0.15)",
                                  cursor: "pointer",
                                  transition: "all 0.15s ease",
                                }}
                              >
                                ✗ Reject
                              </button>
                              
                              <select
                                onChange={(e) => { applyGroupAction(groupName, "forward", e.target.value); e.target.value = ""; }}
                                defaultValue=""
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  padding: "4px 8px",
                                  borderRadius: 6,
                                  fontSize: 11,
                                  fontWeight: 700,
                                  background: "rgba(99,102,241,0.08)",
                                  color: "var(--color-primary)",
                                  border: "1px solid rgba(99,102,241,0.15)",
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
                          )}
                        </div>

                        {/* Group Anomaly List */}
                        <div style={{ display: "flex", flexDirection: "column" }}>
                          {anoms.map((a, idx) => (
                            <AnomalyRow key={idx} anomaly={a} idx={idx} />
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Compliance veto reason */}
          {outcome.compliance_veto && outcome.compliance_reason && (
            <div style={{
              marginBottom: 20,
              padding: "12px 16px",
              background: "rgba(239,68,68,0.06)",
              border: "1px solid rgba(239,68,68,0.2)",
              borderRadius: "var(--radius)",
              display: "flex",
              gap: 10,
              alignItems: "flex-start",
            }}>
              <Icon name="shield" size={16} style={{ color: "var(--color-error)", flexShrink: 0, marginTop: 1 }} />
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--color-error)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>Compliance Veto Reason</div>
                <div style={{ fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.5 }}>{outcome.compliance_reason}</div>
              </div>
            </div>
          )}

          {/* HITL Action Box (Requirement) */}
          {outcome.hitl_needed && outcome.hitl_request && (
            <div style={{
              marginTop: 20,
              marginBottom: 20,
              padding: "16px 20px",
              background: "rgba(15, 23, 42, 0.02)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)",
            }}>
              {outcome.hitl_request.status === "pending" ? (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span className="badge" style={{ background: "rgba(99, 102, 241, 0.12)", color: "var(--color-primary)", fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 12 }}>
                        ESCALATED ACTION REQUIRED
                      </span>
                    </div>
                    <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                      Assigned: {outcome.hitl_request.assigned_role?.toUpperCase() || "HR"}
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 6 }}>
                        Suggested Remediation Action
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
                          cursor: "pointer",
                          outline: "none",
                        }}
                      >
                        {AVAILABLE_ACTIONS.map(act => (
                          <option key={act} value={act}>
                            {act.replace(/_/g, " ")}
                          </option>
                        ))}
                        {proposedAction && !AVAILABLE_ACTIONS.includes(proposedAction) && (
                          <option value={proposedAction}>
                            {proposedAction.replace(/_/g, " ")} (Proposed)
                          </option>
                        )}
                      </select>
                    </div>
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 6 }}>
                        Confidence Score
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: confidence >= 0.8 ? "var(--color-error)" : "var(--color-warning)", marginTop: 6 }}>
                        {(confidence * 100).toFixed(0)}% Match
                      </div>
                    </div>
                  </div>

                  <textarea
                    className="input"
                    value={responseText}
                    onChange={(e) => setResponseText(e.target.value)}
                    placeholder="Enter operator resolution comments..."
                    disabled={submitting}
                    rows={2}
                    style={{ width: "100%", borderRadius: 6, padding: "8px 12px", border: "1px solid var(--color-border)", fontSize: 12, marginBottom: 12, background: "#fff" }}
                  />

                  <div style={{ display: "flex", gap: 10 }}>
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => handleAction("approve")}
                      disabled={submitting}
                      style={{
                        padding: "0 16px",
                        height: 32,
                        borderRadius: 6,
                        fontWeight: 600,
                        background: selectedAction !== proposedAction
                          ? "linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%)"
                          : "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                        color: "#fff",
                        border: "none",
                        display: "flex",
                        alignItems: "center",
                        gap: 6
                      }}
                    >
                      {submitting ? (
                        <div className="spinner" style={{ width: 12, height: 12, borderColor: "#fff" }} />
                      ) : (
                        <Icon name={selectedAction !== proposedAction ? "edit" : "check"} size={12} />
                      )}
                      {selectedAction !== proposedAction ? "Submit Modified Action" : "Approve Action"}
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleAction("reject")}
                      disabled={submitting}
                      style={{
                        padding: "0 16px",
                        height: 32,
                        borderRadius: 6,
                        fontWeight: 600,
                        background: "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)",
                        color: "#fff",
                        border: "none",
                        display: "flex",
                        alignItems: "center",
                        gap: 6
                      }}
                    >
                      {submitting ? <div className="spinner" style={{ width: 12, height: 12, borderColor: "#fff" }} /> : "✗"}
                      Reject Action
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <span className="badge" style={{
                      background: outcome.hitl_request.metadata?.action === "approve"
                        ? "rgba(16, 185, 129, 0.12)"
                        : outcome.hitl_request.metadata?.action === "modify"
                        ? "rgba(99, 102, 241, 0.12)"
                        : "rgba(239, 68, 68, 0.12)",
                      color: outcome.hitl_request.metadata?.action === "approve"
                        ? "var(--color-success)"
                        : outcome.hitl_request.metadata?.action === "modify"
                        ? "var(--color-primary)"
                        : "var(--color-error)",
                      fontWeight: 700,
                      fontSize: 10,
                      padding: "2px 8px",
                      borderRadius: 10,
                      display: "flex",
                      alignItems: "center",
                      gap: 4
                    }}>
                      {outcome.hitl_request.metadata?.action === "reject" ? "✗" : <Icon name={outcome.hitl_request.metadata?.action === "modify" ? "edit" : "check"} size={10} />}
                      DECISION: {outcome.hitl_request.metadata?.action?.toUpperCase() || "RESOLVED"}
                    </span>
                    {outcome.hitl_request.resolved_at && (
                      <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                        {formatTime(outcome.hitl_request.resolved_at)}
                      </span>
                    )}
                  </div>
                  {outcome.hitl_request.metadata?.modified_action && (
                    <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 6 }}>
                      Remediation Action: <code style={{ fontSize: 11, background: "var(--color-bg)", padding: "2px 6px", borderRadius: 4, color: "var(--color-primary)", border: "1px solid var(--color-border)" }}>{outcome.hitl_request.metadata.modified_action.replace(/_/g, " ")}</code>
                    </div>
                  )}
                  {outcome.hitl_request.response && (
                    <div style={{
                      fontSize: 12,
                      color: "var(--color-text-secondary)",
                      background: "rgba(255,255,255,0.4)",
                      padding: "8px 12px",
                      borderRadius: 6,
                      border: "1px solid var(--color-border-light)",
                      fontStyle: "italic"
                    }}>
                      Operator notes: "{outcome.hitl_request.response}"
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Executed actions + retrieved policies */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {outcome.executed_actions.length > 0 && (
              <div>
                <div className="scan-section-label">Executed Actions</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                  {outcome.executed_actions.map((a, i) => (
                    <span key={i} className="scan-action-chip">{a.replace(/_/g, " ")}</span>
                  ))}
                </div>
              </div>
            )}
            {outcome.retrieved_policies.length > 0 && (
              <div>
                <div className="scan-section-label">Referenced Policies</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                  {outcome.retrieved_policies.map((p, i) => (
                    <span key={i} className="scan-policy-chip">
                      <Icon name="doc" size={10} />
                      {p.split(/[\\/]/).pop()}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Scheduler Status Bar ──────────────────────────────────────────────────────

function SchedulerBar({
  scheduler,
  scanning,
  onScanNow,
}: {
  scheduler: SchedulerStatus | null;
  scanning: boolean;
  onScanNow: () => void;
}) {
  return (
    <div className="scan-scheduler-bar">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, flexWrap: "wrap" }}>
        {/* Status pill */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{
            width: 8, height: 8, borderRadius: "50%",
            background: scheduler?.running ? "var(--color-success)" : "var(--color-text-muted)",
            boxShadow: scheduler?.running ? "0 0 0 3px rgba(16,185,129,0.2)" : undefined,
            animation: scheduler?.running ? "pulse 2s ease-in-out infinite" : undefined,
          }} />
          <span style={{ fontSize: 12, fontWeight: 600, color: scheduler?.running ? "var(--color-success)" : "var(--color-text-muted)" }}>
            {scheduler?.running ? "Scheduler Active" : "Scheduler Paused"}
          </span>
        </div>

        {scheduler && (
          <>
            <span className="scan-stat-chip">
              <Icon name="clock" size={11} />
              Every {formatInterval(scheduler.interval_seconds)}
            </span>
            <span className="scan-stat-chip">
              <Icon name="refresh" size={11} />
              {scheduler.run_count} run{scheduler.run_count !== 1 ? "s" : ""}
            </span>
            {scheduler.last_run_at && (
              <span className="scan-stat-chip">
                <Icon name="check" size={11} />
                Last: {relativeTime(scheduler.last_run_at)}
              </span>
            )}
            {scheduler.last_error && (
              <span className="scan-stat-chip" style={{ background: "var(--color-error-bg)", color: "var(--color-error)" }}>
                <Icon name="warning" size={11} />
                Error
              </span>
            )}
          </>
        )}
      </div>

      <button
        className="btn btn-primary"
        onClick={onScanNow}
        disabled={scanning}
        style={{ display: "flex", alignItems: "center", gap: 8, borderRadius: 8, height: 38, padding: "0 20px" }}
      >
        {scanning ? (
          <><div className="spinner" style={{ width: 14, height: 14, borderColor: "rgba(255,255,255,0.3)", borderTopColor: "#fff" }} /> Scanning…</>
        ) : (
          <><Icon name="scan" size={14} /> Scan Now</>
        )}
      </button>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function ScanOutcomes() {
  const [outcomes, setOutcomes] = useState<ScanOutcome[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [scanToast, setScanToast] = useState("");
  const [filter, setFilter] = useState<"all" | "anomalies" | "clean" | "error">("all");

  const fetchOutcomes = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.alerts.scanOutcomes();
      setOutcomes(res.data.outcomes || []);
      setScheduler(res.data.scheduler || null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchOutcomes(); }, [fetchOutcomes]);

  const handleScanNow = async () => {
    setScanning(true);
    setScanToast("");
    try {
      const res = await api.alerts.triggerScan();
      const summary = res.data.result_summary || "Scan completed.";
      setScanToast(summary);
      await fetchOutcomes();
      setTimeout(() => setScanToast(""), 8000);
    } catch (e) {
      setError(`Scan failed: ${e}`);
    } finally {
      setScanning(false);
    }
  };

  const handleMarkRead = async (id: string) => {
    try {
      await api.alerts.markRead(id);
      setOutcomes((prev) => prev.map((o) => o.id === id ? { ...o, alert_status: "read" } : o));
    } catch { /* silently ignore */ }
  };

  // Apply filter
  const filtered = outcomes.filter((o) => {
    if (filter === "anomalies") return o.total_anomalies > 0;
    if (filter === "clean") return o.total_anomalies === 0 && o.status === "completed";
    if (filter === "error") return o.status === "error";
    return true;
  });

  const newCount = outcomes.filter((o) => o.alert_status === "new").length;
  const totalAnomalies = outcomes.reduce((s, o) => s + o.total_anomalies, 0);

  return (
    <div className="scan-outcomes-page">
      {/* Page header */}
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{
                width: 36, height: 36, borderRadius: 8, background: "rgba(99,102,241,0.1)",
                display: "inline-flex", alignItems: "center", justifyContent: "center",
              }}>
                <Icon name="scan" size={18} style={{ color: "var(--color-primary)" }} />
              </span>
              Anomaly Scan Outcomes
            </h1>
            <p className="page-desc">
              End-to-end results of scheduled and manual workforce anomaly scans — what was checked, what was found, and why.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {newCount > 0 && (
              <span style={{ fontSize: 11, fontWeight: 700, background: "var(--color-error)", color: "#fff", padding: "3px 10px", borderRadius: 12 }}>
                {newCount} new
              </span>
            )}
            <button className="btn btn-secondary btn-sm" onClick={fetchOutcomes} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Icon name="refresh" size={13} /> Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Scheduler status bar + Scan Now */}
      <SchedulerBar scheduler={scheduler} scanning={scanning} onScanNow={handleScanNow} />

      {/* Stats row */}
      {outcomes.length > 0 && (
        <div className="stats-grid" style={{ marginBottom: 20, gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))" }}>
          <div className="stat-card">
            <div className="stat-label">Total Scans</div>
            <div className="stat-value">{outcomes.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Anomalies Found</div>
            <div className="stat-value" style={{ color: totalAnomalies > 0 ? "var(--color-warning)" : "var(--color-success)" }}>
              {totalAnomalies}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Clean Scans</div>
            <div className="stat-value" style={{ color: "var(--color-success)" }}>
              {outcomes.filter((o) => o.total_anomalies === 0 && o.status === "completed").length}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Compliance Vetoes</div>
            <div className="stat-value" style={{ color: outcomes.some((o) => o.compliance_veto) ? "var(--color-error)" : "var(--color-text-muted)" }}>
              {outcomes.filter((o) => o.compliance_veto).length}
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {scanToast && (
        <div style={{
          marginBottom: 16, padding: "12px 16px",
          background: "var(--color-success-bg)", border: "1px solid rgba(16,185,129,0.3)",
          borderRadius: "var(--radius)", fontSize: 13, color: "var(--color-success-text)",
          display: "flex", alignItems: "flex-start", gap: 10, lineHeight: 1.5,
        }}>
          <Icon name="check" size={16} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>{scanToast}</div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <Icon name="warning" size={16} />
          <span style={{ flex: 1 }}>{error}</span>
          <button className="btn btn-sm" onClick={() => setError("")}>Dismiss</button>
        </div>
      )}

      {/* Filter tabs */}
      {outcomes.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
          {([
            { key: "all", label: `All (${outcomes.length})` },
            { key: "anomalies", label: `With Anomalies (${outcomes.filter((o) => o.total_anomalies > 0).length})` },
            { key: "clean", label: `Clean (${outcomes.filter((o) => o.total_anomalies === 0 && o.status === "completed").length})` },
            { key: "error", label: `Errors (${outcomes.filter((o) => o.status === "error").length})` },
          ] as const).map(({ key, label }) => (
            <button
              key={key}
              className={`btn btn-sm ${filter === key ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setFilter(key)}
              style={{ borderRadius: 20, padding: "4px 14px" }}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="card">
          <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12, padding: 48, justifyContent: "center" }}>
            <div className="spinner" />
            <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>Loading scan outcomes…</span>
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="scan-empty-state">
          <div className="scan-empty-icon">
            <Icon name="scan" size={32} style={{ color: "var(--color-primary)", opacity: 0.5 }} />
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)", marginBottom: 6 }}>
            {outcomes.length === 0 ? "No Scans Run Yet" : "No Results Match Filter"}
          </div>
          <div style={{ fontSize: 13, color: "var(--color-text-muted)", maxWidth: 360, textAlign: "center", lineHeight: 1.6, marginBottom: 20 }}>
            {outcomes.length === 0
              ? "Click \"Scan Now\" to run an immediate anomaly detection scan across all HR datasets, or wait for the scheduler to trigger one automatically."
              : "Try changing the filter to see more results."}
          </div>
          {outcomes.length === 0 && (
            <button
              className="btn btn-primary"
              onClick={handleScanNow}
              disabled={scanning}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 24px", borderRadius: 10 }}
            >
              {scanning ? <div className="spinner" style={{ width: 14, height: 14, borderColor: "rgba(255,255,255,0.3)", borderTopColor: "#fff" }} /> : <Icon name="scan" size={16} />}
              {scanning ? "Scanning…" : "Run First Scan"}
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {filtered.map((outcome) => (
            <ScanCard key={outcome.id} outcome={outcome} onMarkRead={handleMarkRead} onRefresh={fetchOutcomes} />
          ))}
        </div>
      )}
    </div>
  );
}
