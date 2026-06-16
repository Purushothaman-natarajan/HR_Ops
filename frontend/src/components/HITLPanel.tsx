import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { Icon } from "./Icons";
import type { PendingItem } from "../types";

/** HITL Panel — review pending escalations, approve/reject, and continue conversation from any item.
 *
 * - Lists all pending interactions with Approve / Reject controls
 * - Shows a "Continue in Chat" button that fires onContinueSession with the session_id
 * - Keeps a resolved log for the current session
 *
 * @example
 * <HITLPanel onContinueSession={(sid, mode) => navigateTo("query", sid)} />
 */
interface HITLPanelProps {
  onContinueSession?: (sessionId: string, mode?: "standard" | "advanced") => void;
}

interface ResolvedItem {
  interaction_id: string;
  query: string;
  action: "approve" | "reject";
  response: string;
  resolved_at: string;
  session_id?: string;
}

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
    // Poll every 15 seconds
    const t = setInterval(fetchItems, 15_000);
    return () => clearInterval(t);
  }, [fetchItems]);

  const handleAction = async (item: PendingItem, action: "approve" | "reject", responseText: string) => {
    try {
      await api.hitl.respond(item.interaction_id, action, responseText);
      setItems((prev) => prev.filter((i) => i.interaction_id !== item.interaction_id));
      setResolved((prev) => [
        {
          interaction_id: item.interaction_id,
          query: item.query,
          action,
          response: responseText || "Processed by operator.",
          resolved_at: new Date().toISOString(),
          session_id: item.session_id,
        },
        ...prev,
      ]);
    } catch (e) {
      console.warn("HITLPanel: respond failed", e);
    }
  };

  const tabBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: "6px 16px",
    borderRadius: 6,
    border: "none",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    background: active ? "var(--color-accent)" : "transparent",
    color: active ? "#fff" : "var(--color-text-secondary)",
    transition: "all 0.15s",
  });

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="page-title">Human-in-the-Loop</h1>
            <p className="page-desc">Review agent escalations, approve or reject, and resume conversations</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={fetchItems}>
            <Icon name="arrow" size={12} style={{ transform: "rotate(270deg)" }} />
            &nbsp;Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 20, background: "var(--color-surface)", borderRadius: 8, padding: 4, width: "fit-content" }}>
        <button style={tabBtnStyle(activeTab === "pending")} onClick={() => setActiveTab("pending")}>
          Pending
          {items.length > 0 && (
            <span style={{ marginLeft: 6, background: "var(--color-warning)", color: "#000", borderRadius: 10, padding: "1px 6px", fontSize: 10 }}>
              {items.length}
            </span>
          )}
        </button>
        <button style={tabBtnStyle(activeTab === "resolved")} onClick={() => setActiveTab("resolved")}>
          Resolved
          {resolved.length > 0 && (
            <span style={{ marginLeft: 6, background: "rgba(255,255,255,0.12)", borderRadius: 10, padding: "1px 6px", fontSize: 10 }}>
              {resolved.length}
            </span>
          )}
        </button>
      </div>

      {loading ? (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div className="spinner" />
            <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>Loading pending items...</span>
          </div>
        </div>
      ) : activeTab === "pending" ? (
        items.length === 0 ? (
          <div className="empty-state">
            <Icon name="check" size={48} className="empty-state-icon" />
            <div className="empty-state-text">No pending HITL requests. All clear!</div>
          </div>
        ) : (
          <div className="hitl-list">
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
          <div className="empty-state">
            <div className="empty-state-text">No resolved items in this session.</div>
          </div>
        ) : (
          <div className="hitl-list">
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

function HitlItemCard({
  item,
  onAction,
  onContinueSession,
}: {
  item: PendingItem;
  onAction: (item: PendingItem, action: "approve" | "reject", response: string) => void;
  onContinueSession?: (sessionId: string, mode?: "standard" | "advanced") => void;
}) {
  const [responseText, setResponseText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const ageSeconds = Math.round((Date.now() - new Date(item.created_at).getTime()) / 1000);
  const ageLabel = ageSeconds < 60 ? `${ageSeconds}s ago` : `${Math.round(ageSeconds / 60)}m ago`;

  const handle = async (action: "approve" | "reject") => {
    setSubmitting(true);
    await onAction(item, action, responseText || "Processed by operator.");
    setSubmitting(false);
  };

  return (
    <div className="hitl-card card" style={{ borderLeft: "4px solid var(--color-warning)" }}>
      <div className="card-body">
        <div className="hitl-card-header">
          <span className="badge badge-warning">{item.assigned_role || "agent"}</span>
          <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{ageLabel}</span>
          {item.session_id && (
            <code style={{ fontSize: 11, color: "var(--color-text-muted)", marginLeft: 4 }}>
              {item.session_id.slice(0, 12)}…
            </code>
          )}
        </div>
        <div className="hitl-card-query">{item.query}</div>
        <textarea
          className="input hitl-textarea"
          value={responseText}
          onChange={(e) => setResponseText(e.target.value)}
          placeholder="Optional response / decision notes..."
          disabled={submitting}
          rows={2}
        />
        <div className="hitl-actions">
          <button className="btn btn-success" onClick={() => handle("approve")} disabled={submitting}>
            {submitting ? "..." : "✓ Approve"}
          </button>
          <button className="btn btn-danger" onClick={() => handle("reject")} disabled={submitting}>
            {submitting ? "..." : "✗ Reject"}
          </button>
          {item.session_id && onContinueSession && (
            <button
              className="btn btn-secondary btn-sm"
              style={{ marginLeft: "auto", fontSize: 12 }}
              onClick={() => onContinueSession(item.session_id!, "advanced")}
            >
              <Icon name="arrow" size={12} />
              &nbsp;Continue in Chat
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
  return (
    <div className="hitl-card card" style={{ borderLeft: `4px solid ${item.action === "approve" ? "var(--color-success)" : "var(--color-error)"}` }}>
      <div className="card-body">
        <div className="hitl-card-header">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={`badge ${item.action === "approve" ? "badge-success" : "badge-error"}`}>
              {item.action === "approve" ? "✓ Approved" : "✗ Rejected"}
            </span>
            <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
              {new Date(item.resolved_at).toLocaleTimeString()}
            </span>
          </div>
          {item.session_id && onContinueSession && (
            <button
              className="btn btn-secondary btn-sm"
              style={{ fontSize: 12, padding: "2px 8px", height: "auto", display: "inline-flex", alignItems: "center", gap: 4 }}
              onClick={() => onContinueSession(item.session_id!, "advanced")}
            >
              <Icon name="arrow" size={10} />
              Resume
            </button>
          )}
        </div>
        <div className="hitl-card-query" style={{ opacity: 0.8 }}>{item.query}</div>
        {item.response && (
          <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 6, fontStyle: "italic" }}>
            "{item.response}"
          </div>
        )}
      </div>
    </div>
  );
}
