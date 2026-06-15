import type { AppRole } from "../types";
import { Icon } from "./Icons";
import type { IconName } from "./Icons";

type Page = "dashboard" | "query" | "hitl" | "trace" | "tracequery" | "rl" | "cost" | "policies" | "performance";

interface Props {
  activePage: Page;
  onNavigate: (page: Page) => void;
  role: AppRole;
  onLogout: () => void;
  isOpen: boolean;
}

interface NavItem {
  id: Page;
  label: string;
  icon: IconName;
  section: string;
  roles: AppRole[];
}

const navItems: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard", section: "Main", roles: ["admin", "hr", "employee"] },
  { id: "query", label: "Query Agent", icon: "query", section: "Main", roles: ["admin", "hr", "employee"] },
  { id: "hitl", label: "HITL Requests", icon: "hitl", section: "Main", roles: ["admin", "hr"] },
  { id: "trace", label: "Trace Viewer", icon: "trace", section: "Observability", roles: ["admin"] },
  { id: "tracequery", label: "Trace Compare", icon: "trace-compare", section: "Observability", roles: ["admin"] },
  { id: "policies", label: "Policy Manager", icon: "policy", section: "Knowledge", roles: ["admin", "hr", "employee"] },
  { id: "rl", label: "RL Dashboard", icon: "rl", section: "Insights", roles: ["admin"] },
  { id: "cost", label: "Cost Monitor", icon: "cost", section: "Insights", roles: ["admin", "hr"] },
  { id: "performance", label: "Performance", icon: "performance", section: "Observability", roles: ["admin"] },
];

const sectionOrder = ["Main", "Observability", "Knowledge", "Insights"];

const ROLE_LABELS: Record<AppRole, string> = {
  admin: "Admin",
  hr: "HR",
  employee: "Employee",
};

export function Sidebar({ activePage, onNavigate, role, onLogout, isOpen }: Props) {
  const visibleSections = sectionOrder.filter((section) => {
    const itemsInSection = navItems.filter((item) => item.section === section);
    return itemsInSection.some((item) => item.roles.includes(role));
  });

  return (
    <aside className={`sidebar${isOpen ? " open" : ""}`}>
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <span>HR Buddy</span>
        </div>
        <div className="sidebar-subtitle">Your AI-Powered HR Assistant</div>
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
                  <Icon name={item.icon} size={16} className="sidebar-icon" />
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
