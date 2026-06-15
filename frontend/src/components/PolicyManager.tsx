import { useState, useEffect, useCallback, useRef } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import { api } from "../api/client";
import type { PolicyDocument, AppRole } from "../types";

/** Policy Knowledge Base manager with split-pane list/preview layout.
 *
 * Shows document list on the left, markdown preview on the right.
 * Upload modal with drag-and-drop for .pdf / .md / .txt files.
 * Includes edit title, delete, and live embedding status.
 *
 * @example
 * <PolicyManager role="admin" />
 */
export function PolicyManager({ role }: { role: AppRole }) {
  const [policies, setPolicies] = useState<PolicyDocument[]>([]);
  const [embeddedCount, setEmbeddedCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<PolicyDocument | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [showEdit, setShowEdit] = useState<PolicyDocument | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [embedding, setEmbedding] = useState<string | null>(null);

  const fetchPolicies = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.policies.list();
      setPolicies(res.data.policies);
      setEmbeddedCount(res.data.embedded_count ?? res.data.policies.length);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  const handleView = async (id: string) => {
    try {
      const res = await api.policies.get(id);
      setSelected(res.data);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleEdit = async (id: string, newTitle: string) => {
    setEmbedding(id);
    try {
      await api.policies.update(id, { title: newTitle });
      setShowEdit(null);
      setSelected((prev) => (prev?.id === id ? { ...prev, title: newTitle } : prev));
      fetchPolicies();
    } catch (e) {
      setError(String(e));
    } finally {
      setEmbedding(null);
    }
  };

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await api.policies.delete(id);
      setConfirmDelete(null);
      setSelected((prev) => (prev?.id === id ? null : prev));
      fetchPolicies();
    } catch (e) {
      setError(String(e));
    } finally {
      setDeleting(null);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const typeBadge = (ct: string) => {
    if (ct.includes("pdf")) return <span className="badge badge-pdf">PDF</span>;
    if (ct.includes("markdown") || ct.includes("md")) return <span className="badge badge-md">MD</span>;
    if (ct.includes("text")) return <span className="badge badge-txt">TXT</span>;
    return <span className="badge badge-info">{ct.split("/").pop()}</span>;
  };

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="page-title">Policy Manager</h1>
            <p className="page-desc">
              Upload, view, and manage HR policy documents (PDF, Markdown, TXT)
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {role === "employee" && (
              <span className="badge badge-warning">View Only</span>
            )}
            {(role === "admin" || role === "hr") && (
              <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
                + Upload Policy
              </button>
            )}
          </div>
        </div>
      </div>

      {role === "employee" && (
        <div className="alert" style={{ marginBottom: 16, background: "var(--color-warning-bg)", color: "#92400e", border: "1px solid #fde68a" }}>
          <span>View-only mode — policy editing is disabled.</span>
        </div>
      )}

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <span>{error}</span>
          <button className="btn btn-sm" style={{ marginLeft: "auto" }} onClick={() => setError("")}>
            Dismiss
          </button>
        </div>
      )}

      <div className="policy-layout">
        <div className="policy-list-panel">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Documents</span>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span className="badge badge-info">{policies.length} file{policies.length !== 1 ? "s" : ""}</span>
                <span className="badge badge-success">{embeddedCount} embedded</span>
              </div>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              {loading ? (
                <div className="empty-state">
                  <div className="spinner" />
                  <div className="empty-state-text" style={{ marginTop: 8 }}>Loading policies...</div>
                </div>
              ) : policies.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-text">No policies yet. Upload your first document.</div>
                </div>
              ) : (
                <div className="policy-table">
                  {policies.map((p) => (
                    <div
                      key={p.id}
                      className={`policy-row${selected?.id === p.id ? " selected" : ""}`}
                    >
                      <div className="policy-row-info" onClick={() => handleView(p.id)}>
                        <div className="policy-row-title">
                          {p.title}
                          {embedding === p.id && (
                            <span className="badge badge-warning" style={{ marginLeft: 6, fontSize: 10 }}>
                              Re-embedding...
                            </span>
                          )}
                        </div>
                        <div className="policy-row-meta">
                          {typeBadge(p.content_type)}
                          <span>{formatSize(p.file_size)}</span>
                          <span>{p.filename}</span>
                        </div>
                      </div>
                      <div className="policy-row-actions">
                        <a
                          className="btn btn-sm btn-secondary"
                          href={api.policies.downloadUrl(p.id)}
                          target="_blank"
                          rel="noreferrer"
                          title="Download"
                        >
                          Download
                        </a>
                        {(role === "admin" || role === "hr") && (
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => setShowEdit(p)}
                            title="Edit title"
                            disabled={embedding === p.id}
                          >
                            Edit
                          </button>
                        )}
                        {role === "admin" && (confirmDelete === p.id ? (
                          <div className="policy-confirm-delete">
                            <span style={{ fontSize: 12, color: "var(--color-error)" }}>
                              {deleting === p.id ? "Deleting..." : "Delete?"}
                            </span>
                            <button className="btn btn-sm btn-danger" onClick={() => handleDelete(p.id)} disabled={deleting === p.id}>
                              Yes
                            </button>
                            <button className="btn btn-sm btn-secondary" onClick={() => setConfirmDelete(null)} disabled={deleting === p.id}>
                              No
                            </button>
                          </div>
                        ) : (
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={() => setConfirmDelete(p.id)}
                            title="Delete"
                          >
                            Delete
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="policy-preview-panel">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Preview</span>
              {selected && (
                <span className="badge badge-info">{selected.content_type.split("/").pop()}</span>
              )}
            </div>
            <div className="card-body policy-preview-body">
              {!selected ? (
                <div className="empty-state">
                  <div className="empty-state-text">Select a policy to preview its content.</div>
                </div>
              ) : selected.content_type.includes("markdown") || selected.filename.endsWith(".md") ? (
                <div className="policy-markdown">
                  <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{selected.content}</ReactMarkdown>
                </div>
              ) : (
                <pre className="policy-pre">{selected.content}</pre>
              )}
            </div>
          </div>
        </div>
      </div>

      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onUploaded={() => {
            setShowUpload(false);
            fetchPolicies();
          }}
          onError={setError}
        />
      )}

      {showEdit && (
        <EditModal
          policy={showEdit}
          onClose={() => setShowEdit(null)}
          onSave={(newTitle) => handleEdit(showEdit.id, newTitle)}
          embedding={embedding === showEdit.id}
        />
      )}
    </div>
  );
}

/* Edit Title Modal */
function EditModal({
  policy,
  onClose,
  onSave,
  embedding,
}: {
  policy: PolicyDocument;
  onClose: () => void;
  onSave: (title: string) => void;
  embedding: boolean;
}) {
  const [title, setTitle] = useState(policy.title);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440 }}>
        <div className="modal-header">
          <h3 className="modal-title">Edit Policy Title</h3>
          <button className="btn btn-sm btn-secondary" onClick={onClose} disabled={embedding}>X</button>
        </div>
        <div className="modal-body">
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 8 }}>
            {policy.filename}
          </div>
          <div style={{ marginBottom: 12 }}>
            <label className="policy-field-label">Title</label>
            <input
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={embedding}
              autoFocus
            />
          </div>
          {embedding && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--color-text-muted)", fontSize: 13 }}>
              <div className="spinner" style={{ width: 14, height: 14 }} />
              Re-embedding document...
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={embedding}>Cancel</button>
          <button
            className="btn btn-primary"
            onClick={() => onSave(title)}
            disabled={!title.trim() || embedding || title === policy.title}
          >
            {embedding ? "Saving..." : "Save & Re-embed"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* Upload Modal */
function UploadModal({
  onClose,
  onUploaded,
  onError,
}: {
  onClose: () => void;
  onUploaded: () => void;
  onError: (msg: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const ALLOWED = [".md", ".pdf", ".txt"];
  const MAX_BYTES = 10 * 1024 * 1024;

  const validate = (f: File): string | null => {
    const ext = "." + f.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED.includes(ext)) return `Unsupported file type "${ext}". Allowed: ${ALLOWED.join(", ")}`;
    if (f.size > MAX_BYTES) return `File exceeds 10 MB limit (${(f.size / (1024 * 1024)).toFixed(1)} MB)`;
    return null;
  };

  const handleFile = (f: File) => {
    const err = validate(f);
    if (err) {
      onError(err);
      return;
    }
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, "").replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()));
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      await api.policies.upload(file, title || undefined);
      onUploaded();
    } catch (e) {
      onError(String(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Upload Policy Document</h3>
          <button className="btn btn-sm btn-secondary" onClick={onClose}>X</button>
        </div>
        <div className="modal-body">
          <div
            className={`upload-zone${dragOver ? " active" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); }}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".md,.pdf,.txt"
              hidden
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            />
            {file ? (
              <div>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{file.name}</div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                  {(file.size / 1024).toFixed(1)} KB &middot; {file.type || "unknown type"}
                </div>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 24, marginBottom: 4 }}>Upload</div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                  Drop a file here or click to browse
                </div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>
                  Supported: .md, .pdf, .txt &middot; Max 10 MB
                </div>
              </div>
            )}
          </div>

          <div style={{ marginTop: 12 }}>
            <label className="policy-field-label">Title (optional)</label>
            <input
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Auto-generated from filename if empty"
            />
          </div>

          {uploading && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, color: "var(--color-text-muted)", fontSize: 13 }}>
              <div className="spinner" style={{ width: 14, height: 14 }} />
              Uploading &amp; embedding document...
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={uploading}>Cancel</button>
          <button className="btn btn-primary" onClick={handleUpload} disabled={!file || uploading}>
            {uploading ? "Uploading & Indexing..." : "Upload"}
          </button>
        </div>
      </div>
    </div>
  );
}
