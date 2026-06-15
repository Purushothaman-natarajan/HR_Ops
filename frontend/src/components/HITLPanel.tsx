import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { Icon } from "./Icons";
import type { PendingItem } from "../types";

/** HITL (human-in-the-loop) escalation panel for pending agent requests.
 *
 * Fetches pending interactions via api.hitl.list() and allows
 * approve/reject actions via api.hitl.respond().
 *
 * @example
 * <HITLPanel />
 */
export function HITLPanel() {
  const [items, setItems] = useState<PendingItem[]>([]);
  const [loading, setLoading] = useState(true);

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
  }, [fetchItems]);

  const handleAction = async (id: string, action: "approve" | "reject", responseText: string) => {
    try {
      await api.hitl.respond(id, action, responseText);
      setItems((prev) => prev.filter((item) => item.interaction_id !== id));
    } catch (e) {
      console.warn("HITLPanel: respond failed", e);
    }
  };

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="spinner" />
          <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>Loading pending items...</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="page-title">Human-in-the-Loop</h1>
            <p className="page-desc">Review and respond to agent escalations requiring human judgment</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={fetchItems}>
            Refresh
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">
          <Icon name="check" size={48} className="empty-state-icon" />
          <div className="empty-state-text">No pending HITL requests. All clear!</div>
        </div>
      ) : (
        <>
          <div className="hitl-filters">
            <span className="badge badge-warning" style={{ fontSize: 13 }}>
              {items.length} pending request{items.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="hitl-list">
            {items.map((item) => (
              <HitlItemCard key={item.interaction_id} item={item} onAction={handleAction} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/** Internal card component rendering a single pending HITL interaction with approve/reject controls.
 *
 * @example
 * <HitlItemCard item={item} onAction={(id, action, resp) => handle(id, action, resp)} />
 */
function HitlItemCard({
  item,
  onAction,
}: {
  item: PendingItem;
  onAction: (id: string, action: "approve" | "reject", response: string) => void;
}) {
  const [responseText, setResponseText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handle = async (action: "approve" | "reject") => {
    setSubmitting(true);
    await onAction(item.interaction_id, action, responseText || "Processed by operator.");
    setSubmitting(false);
  };

  return (
    <div className="hitl-card card">
      <div className="card-body">
        <div className="hitl-card-header">
          <span className="badge badge-warning">{item.assigned_role || "agent"}</span>
          <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
            {new Date(item.created_at).toLocaleString()}
          </span>
        </div>
        <div className="hitl-card-query">{item.query}</div>
        <textarea
          className="input hitl-textarea"
          value={responseText}
          onChange={(e) => setResponseText(e.target.value)}
          placeholder="Optional response / notes..."
          disabled={submitting}
          rows={2}
        />
        <div className="hitl-actions">
          <button className="btn btn-success" onClick={() => handle("approve")} disabled={submitting}>
            {submitting ? "..." : "Approve"}
          </button>
          <button className="btn btn-danger" onClick={() => handle("reject")} disabled={submitting}>
            {submitting ? "..." : "Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}
