import { useState, useEffect } from "react";
import { api } from "../api/client";
import { Icon } from "./Icons";

interface IntegrationsConfig {
  database: {
    type: string;
    connection_string: string;
    connected: boolean;
  };
  chat_hook: {
    enabled: boolean;
    webhook_url: string;
    events: string[];
  };
}

const ALL_EVENTS = ["leave_request", "escalation", "policy_update", "anomaly_detected", "compliance_check"];

export function IntegrationsManager() {
  const [config, setConfig] = useState<IntegrationsConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Editable form state
  const [dbType, setDbType] = useState("sqlite");
  const [connStr, setConnStr] = useState("");
  const [hookEnabled, setHookEnabled] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [events, setEvents] = useState<string[]>(["leave_request", "escalation"]);

  useEffect(() => {
    api.integrations.get()
      .then((r) => {
        setConfig(r.data);
        setDbType(r.data.database?.type || "sqlite");
        setConnStr(r.data.database?.connection_string || "");
        setHookEnabled(r.data.chat_hook?.enabled || false);
        setWebhookUrl(r.data.chat_hook?.webhook_url || "");
        setEvents(r.data.chat_hook?.events || ["leave_request", "escalation"]);
      })
      .catch(() => setError("Failed to load integrations config"))
      .finally(() => setLoading(false));
  }, []);

  const toggleEvent = (ev: string) => {
    setEvents((prev) => prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev]);
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const res = await api.integrations.update({
        database: { type: dbType, connection_string: connStr },
        chat_hook: { enabled: hookEnabled, webhook_url: webhookUrl, events },
      });
      setConfig(res.data);
      setSuccess("Integrations configuration saved successfully.");
    } catch (e) {
      setError(`Failed to save: ${e}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 780, margin: "0 auto", padding: "24px 0" }}>
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: "var(--color-text)", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
          <Icon name="settings" size={22} style={{ opacity: 0.8 }} />
          Settings &amp; Integrations
        </h2>
        <p style={{ fontSize: 13, color: "var(--color-text-secondary)", marginTop: 6, marginBottom: 0 }}>
          Configure external database connections and chat webhook integrations for the HR Ops Platform.
        </p>
      </div>

      {/* Database Integration */}
      <div className="card" style={{ marginBottom: 20, padding: "20px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <Icon name="cache" size={18} style={{ color: "var(--color-accent)" }} />
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: "var(--color-text)" }}>Database Connection</h3>
          <span style={{
            marginLeft: "auto",
            fontSize: 11,
            fontWeight: 600,
            padding: "2px 8px",
            borderRadius: 12,
            background: config?.database?.connected ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
            color: config?.database?.connected ? "var(--color-success)" : "var(--color-error)",
          }}>
            {config?.database?.connected ? "● Connected" : "○ Disconnected"}
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-secondary)", display: "block", marginBottom: 6 }}>
              Database Type
            </label>
            <select
              className="input"
              value={dbType}
              onChange={(e) => setDbType(e.target.value)}
              style={{ width: "100%" }}
            >
              <option value="sqlite">SQLite (Local file)</option>
              <option value="postgresql">PostgreSQL</option>
              <option value="mysql">MySQL</option>
              <option value="mssql">Microsoft SQL Server</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-secondary)", display: "block", marginBottom: 6 }}>
              Connection String / File Path
            </label>
            <input
              className="input"
              type="text"
              value={connStr}
              onChange={(e) => setConnStr(e.target.value)}
              placeholder="sqlite:///./backend/data/hr_ops.db  or  postgresql://user:pass@host/db"
              style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: 12 }}
            />
            <p style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4, marginBottom: 0 }}>
              For SQLite: <code>sqlite:///./path/to/file.db</code> &nbsp;|&nbsp; For PostgreSQL: <code>postgresql://user:pass@host:5432/dbname</code>
            </p>
          </div>
        </div>
      </div>

      {/* Chat Webhook Integration */}
      <div className="card" style={{ marginBottom: 20, padding: "20px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <Icon name="arrow" size={18} style={{ color: "var(--color-accent)" }} />
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: "var(--color-text)" }}>Chat Webhook</h3>
          <label style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
            <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>Enabled</span>
            <div
              onClick={() => setHookEnabled(!hookEnabled)}
              style={{
                width: 36,
                height: 20,
                borderRadius: 10,
                background: hookEnabled ? "var(--color-accent)" : "var(--color-border)",
                position: "relative",
                cursor: "pointer",
                transition: "background 0.2s",
              }}
            >
              <div style={{
                position: "absolute",
                top: 2,
                left: hookEnabled ? 18 : 2,
                width: 16,
                height: 16,
                borderRadius: "50%",
                background: "#fff",
                transition: "left 0.2s",
                boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
              }} />
            </div>
          </label>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14, opacity: hookEnabled ? 1 : 0.5, transition: "opacity 0.2s" }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-secondary)", display: "block", marginBottom: 6 }}>
              Webhook URL
            </label>
            <input
              className="input"
              type="url"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              disabled={!hookEnabled}
              placeholder="https://hooks.slack.com/services/T00/B00/xxxx"
              style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: 12 }}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-secondary)", display: "block", marginBottom: 8 }}>
              Events to Notify
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {ALL_EVENTS.map((ev) => (
                <button
                  key={ev}
                  disabled={!hookEnabled}
                  onClick={() => toggleEvent(ev)}
                  className={`btn btn-sm ${events.includes(ev) ? "btn-primary" : "btn-secondary"}`}
                  style={{ fontSize: 11, opacity: hookEnabled ? 1 : 0.6 }}
                >
                  {ev.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 12 }}>
        {error && (
          <span style={{ fontSize: 12, color: "var(--color-error)", flex: 1 }}>✗ {error}</span>
        )}
        {success && (
          <span style={{ fontSize: 12, color: "var(--color-success)", flex: 1 }}>✓ {success}</span>
        )}
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving}
          style={{ minWidth: 140 }}
        >
          {saving ? (
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div className="spinner" style={{ width: 14, height: 14 }} />
              Saving...
            </span>
          ) : (
            <>
              <Icon name="check" size={14} />
              Save Integrations
            </>
          )}
        </button>
      </div>
    </div>
  );
}
