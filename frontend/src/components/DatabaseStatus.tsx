import { useState, useEffect, useRef } from "react";
import { api } from "../api/client";
import { useAuth } from "../hooks/useAuth";

interface DatabaseInfo {
  connected: boolean;
  employees_count: number;
  attendance_count?: number;
  payroll_count?: number;
  leaves_count?: number;
  performance_count?: number;
  database_url?: string;
  error?: string;
}

export function DatabaseStatus() {
  const { role } = useAuth();
  const [info, setInfo] = useState<DatabaseInfo | null>(null);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState("");
  const [uploadError, setUploadError] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchStatus = () => {
    api.database.status()
      .then((r) => setInfo(r.data))
      .catch(() => setError("unavailable"));
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const statusColor =
    error || (info && !info.connected)
      ? "var(--color-error)"
      : info && info.connected && info.employees_count > 0
        ? "var(--color-success)"
        : "#999";

  const handleIngest = async (file: File) => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    const allowed = [".csv", ".db", ".sqlite", ".sqlite3"];
    if (!allowed.includes(ext)) {
      setUploadError(`Unsupported file format "${ext}". Allowed: ${allowed.join(", ")}`);
      setUploadSuccess("");
      return;
    }

    setUploading(true);
    setUploadError("");
    setUploadSuccess("");

    try {
      const res = await api.database.upload(file);
      setUploadSuccess(res.data.message || "Database ingested successfully.");
      setInfo(res.data.status);
    } catch (err) {
      setUploadError(String(err));
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <div
        className="status-indicator"
        onClick={() => setShowModal(true)}
        style={{ cursor: "pointer", transition: "opacity 0.2s" }}
        title="View database details and tables"
      >
        <span className="status-dot" style={{ background: statusColor }} />
        <span className="status-text">
          {error
            ? "DB: Offline"
            : info && !info.connected
              ? "DB: Disconnected"
              : info
                ? `DB: ${info.employees_count.toLocaleString()} employees`
                : "DB: Checking..."}
        </span>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <h3 className="modal-title">Active Database Status</h3>
              <button
                className="btn btn-sm btn-secondary"
                style={{ minWidth: "auto", padding: "2px 8px" }}
                onClick={() => setShowModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              {error ? (
                <div className="alert alert-error" style={{ marginBottom: 12 }}>
                  Database connection failed or offline.
                </div>
              ) : !info ? (
                <div style={{ display: "flex", justifyContent: "center", padding: 20 }}>
                  <div className="spinner" />
                </div>
              ) : (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 13, display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ color: "var(--color-text-secondary)" }}>Connection Status:</span>
                      <span
                        style={{
                          fontWeight: 600,
                          color: info.connected ? "var(--color-success)" : "var(--color-error)",
                        }}
                      >
                        {info.connected ? "Connected" : "Disconnected"}
                      </span>
                    </div>
                    {info.database_url && (
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--color-text-muted)",
                          fontFamily: "var(--font-mono)",
                          background: "var(--color-bg)",
                          padding: "6px 10px",
                          borderRadius: 4,
                          wordBreak: "break-all",
                        }}
                      >
                        URL: {info.database_url}
                      </div>
                    )}
                  </div>

                  <h4
                    style={{
                      fontSize: 11,
                      textTransform: "uppercase",
                      letterSpacing: 0.5,
                      color: "var(--color-text-muted)",
                      marginBottom: 8,
                      fontWeight: 600,
                    }}
                  >
                    Table Record Counts
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
                    <div
                      style={{
                        display: "flex",
                        justify: "space-between",
                        fontSize: 13,
                        borderBottom: "1px solid var(--color-border)",
                        paddingBottom: 6,
                      }}
                    >
                      <span style={{ color: "var(--color-text-secondary)" }}>Employees (employees)</span>
                      <span style={{ fontWeight: 600 }}>{info.employees_count.toLocaleString()}</span>
                    </div>
                    {info.attendance_count !== undefined && (
                      <div
                        style={{
                          display: "flex",
                          justify: "space-between",
                          fontSize: 13,
                          borderBottom: "1px solid var(--color-border)",
                          paddingBottom: 6,
                        }}
                      >
                        <span style={{ color: "var(--color-text-secondary)" }}>Attendance Logs (attendance)</span>
                        <span style={{ fontWeight: 600 }}>{info.attendance_count.toLocaleString()}</span>
                      </div>
                    )}
                    {info.payroll_count !== undefined && (
                      <div
                        style={{
                          display: "flex",
                          justify: "space-between",
                          fontSize: 13,
                          borderBottom: "1px solid var(--color-border)",
                          paddingBottom: 6,
                        }}
                      >
                        <span style={{ color: "var(--color-text-secondary)" }}>Payroll Records (payroll)</span>
                        <span style={{ fontWeight: 600 }}>{info.payroll_count.toLocaleString()}</span>
                      </div>
                    )}
                    {info.leaves_count !== undefined && (
                      <div
                        style={{
                          display: "flex",
                          justify: "space-between",
                          fontSize: 13,
                          borderBottom: "1px solid var(--color-border)",
                          paddingBottom: 6,
                        }}
                      >
                        <span style={{ color: "var(--color-text-secondary)" }}>Leaves Tracked (leaves)</span>
                        <span style={{ fontWeight: 600 }}>{info.leaves_count.toLocaleString()}</span>
                      </div>
                    )}
                    {info.performance_count !== undefined && (
                      <div
                        style={{
                          display: "flex",
                          justify: "space-between",
                          fontSize: 13,
                          borderBottom: "1px solid var(--color-border)",
                          paddingBottom: 6,
                        }}
                      >
                        <span style={{ color: "var(--color-text-secondary)" }}>Performance Evaluations</span>
                        <span style={{ fontWeight: 600 }}>{info.performance_count.toLocaleString()}</span>
                      </div>
                    )}
                  </div>

                  {(role === "admin" || role === "hr") && (
                    <div
                      style={{
                        paddingTop: 16,
                        borderTop: "1px solid var(--color-border)",
                      }}
                    >
                      <h4
                        style={{
                          fontSize: 11,
                          textTransform: "uppercase",
                          letterSpacing: 0.5,
                          color: "var(--color-text-muted)",
                          marginBottom: 6,
                          fontWeight: 600,
                        }}
                      >
                        Ingest Custom DB or CSV
                      </h4>
                      <p style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: 10, lineHeight: 1.4 }}>
                        Upload a raw CSV (leaves, locations, performance rating, and managers are auto-generated if
                        missing) or a structured SQLite database to replace the engine's active data store.
                      </p>
                      <div
                        className={`upload-zone${dragOver ? " active" : ""}`}
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragOver(true);
                        }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={(e) => {
                          e.preventDefault();
                          setDragOver(false);
                          if (e.dataTransfer.files[0]) handleIngest(e.dataTransfer.files[0]);
                        }}
                        onClick={() => fileInputRef.current?.click()}
                        style={{ padding: "20px 12px", borderStyle: "dashed" }}
                      >
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept=".csv,.db,.sqlite,.sqlite3"
                          hidden
                          onChange={(e) => e.target.files?.[0] && handleIngest(e.target.files[0])}
                        />
                        {uploading ? (
                          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                            <div className="spinner" style={{ width: 16, height: 16 }} />
                            <span style={{ fontSize: 12 }}>Ingesting &amp; updating active schema...</span>
                          </div>
                        ) : (
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>Click to upload DB/CSV</div>
                            <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                              Supports .csv, .db, .sqlite (Max 50MB)
                            </div>
                          </div>
                        )}
                      </div>
                      {uploadSuccess && (
                        <div
                          style={{
                            color: "var(--color-success)",
                            fontSize: 12,
                            marginTop: 10,
                            textAlign: "center",
                            fontWeight: 500,
                          }}
                        >
                          ✓ {uploadSuccess}
                        </div>
                      )}
                      {uploadError && (
                        <div
                          style={{
                            color: "var(--color-error)",
                            fontSize: 12,
                            marginTop: 10,
                            textAlign: "center",
                            fontWeight: 500,
                          }}
                        >
                          ✗ {uploadError}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

