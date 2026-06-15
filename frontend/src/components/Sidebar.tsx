import type { AppRole } from "../types";

type Page = "dashboard" | "query" | "hitl" | "trace" | "tracequery" | "rl" | "cost" | "policies" | "performance";

interface Props {
  activePage: Page;
  onNavigate: (page: Page) => void;
  role: AppRole;
  onLogout: () => void;
}

interface NavItem {
  id: Page;
  label: string;
  icon: string;
  section: string;
  roles: AppRole[];
}

const navItems: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: "\u2302", section: "Main", roles: ["admin", "hr", "employee"] },
  { id: "query", label: "Query Agent", icon: "\u2192", section: "Main", roles: ["admin", "hr", "employee"] },
  { id: "hitl", label: "HITL Requests", icon: "\u2691", section: "Main", roles: ["admin", "hr"] },
  { id: "trace", label: "Trace Viewer", icon: "\u2630", section: "Observability", roles: ["admin"] },
  { id: "tracequery", label: "Trace Compare", icon: "\u2261", section: "Observability", roles: ["admin"] },
  { id: "policies", label: "Policy Manager", icon: "\u25A1", section: "Knowledge", roles: ["admin", "hr", "employee"] },
  { id: "rl", label: "RL Dashboard", icon: "\u25B3", section: "Insights", roles: ["admin"] },
  { id: "cost", label: "Cost Monitor", icon: "\u0024", section: "Insights", roles: ["admin", "hr"] },
  { id: "performance", label: "Performance", icon: "\u26A1", section: "Observability", roles: ["admin"] },
];

const sectionOrder = ["Main", "Observability", "Knowledge", "Insights"];

const ROLE_LABELS: Record<AppRole, string> = {
  admin: "Admin",
  hr: "HR",
  employee: "Employee",
};

export function Sidebar({ activePage, onNavigate, role, onLogout }: Props) {
  const visibleSections = sectionOrder.filter((section) => {
    const itemsInSection = navItems.filter((item) => item.section === section);
    return itemsInSection.some((item) => item.roles.includes(role));
  });

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">HR</div>
          <span>HR Ops Platform</span>
        </div>
        <div className="sidebar-subtitle">Self-Healing Multi-Agent System</div>
      </div>

      <nav className="sidebar-nav">
        {visibleSections.map((section) => (
          <div key={section}>
            <div className="sidebar-section-label">{section}</div>
            {navItems
              .filter((item) => item.section === section && item.roles.includes(role))
              .map((item) => (
                <button
                  key={item.id}
                  className={`sidebar-item${activePage === item.id ? " active" : ""}`}
                  onClick={() => onNavigate(item.id)}
                >
                  <span className="sidebar-icon">{item.icon}</span>
                  {item.label}
                  {role === "employee" && item.id === "policies" && (
                    <span className="sidebar-suffix">(View)</span>
                  )}
                </button>
              ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-role-badge">
          <span className={`badge ${role === "admin" ? "badge-info" : role === "hr" ? "badge-info" : "badge-warning"}`}>
            {ROLE_LABELS[role]}
          </span>
        </div>
        <div style={{ fontSize: 11, color: "var(--color-sidebar-text)", padding: "0 10px" }}>
          v1.0.0
        </div>
        <button className="btn btn-sm btn-secondary" onClick={onLogout} style={{ marginTop: 8, width: "100%" }}>
          Sign Out
        </button>
      </div>
    </aside>
  );
}
