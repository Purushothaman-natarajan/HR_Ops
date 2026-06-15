import { useState } from "react";
import { useAuth } from "../hooks/useAuth";
import type { AppRole } from "../types";

const ROLES: { value: AppRole; label: string }[] = [
  { value: "admin", label: "Admin" },
  { value: "hr", label: "HR" },
  { value: "employee", label: "Employee" },
];

export function LoginPage() {
  const { login } = useAuth();
  const [role, setRole] = useState<AppRole>("admin");
  const [password, setPassword] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!password) {
      setError("Password is required");
      return;
    }
    if (role === "employee" && !employeeId) {
      setError("Employee ID is required for Employee role");
      return;
    }
    setLoading(true);
    try {
      await login(role, password, employeeId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">HR</div>
        <h1 className="login-title">HR Ops Platform</h1>
        <p className="login-subtitle">Self-Healing Multi-Agent System</p>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <label className="login-label">Role</label>
            <select
              className="input"
              value={role}
              onChange={(e) => setRole(e.target.value as AppRole)}
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          {role === "employee" && (
            <div className="login-field">
              <label className="login-label">Employee ID</label>
              <input
                className="input"
                type="text"
                placeholder="e.g. 1"
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
              />
            </div>
          )}

          <div className="login-field">
            <label className="login-label">Password</label>
            <input
              className="input"
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          <button
            type="submit"
            className="btn btn-primary login-btn"
            disabled={loading}
          >
            {loading ? <span className="spinner" /> : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
