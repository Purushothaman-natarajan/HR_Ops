import type { AppRole } from "../types";

type Page = "dashboard" | "query" | "hitl" | "trace" | "tracequery" | "rl" | "cost" | "policies";

interface Props {
  onNavigate: (page: Page) => void;
  role: AppRole;
}

interface FeatureCard {
  id: Page;
  title: string;
  desc: string;
  color: string;
  icon: string;
  roles: AppRole[];
}

const features: FeatureCard[] = [
  {
    id: "query",
    title: "Query Agent",
    desc: "Ask HR policy questions, execute actions, run anomaly detection, or check compliance",
    color: "#6366f1",
    icon: "\u2192",
    roles: ["admin", "hr", "employee"],
  },
  {
    id: "hitl",
    title: "HITL Requests",
    desc: "Review and respond to human-in-the-loop escalations from the agent system",
    color: "#f59e0b",
    icon: "\u2691",
    roles: ["admin", "hr"],
  },
  {
    id: "trace",
    title: "Trace Viewer",
    desc: "Inspect detailed execution traces from graph runs with timing and cost data",
    color: "#10b981",
    icon: "\u2630",
    roles: ["admin"],
  },
  {
    id: "tracequery",
    title: "Trace Compare",
    desc: "Compare multiple trace runs side-by-side to debug agent behavior",
    color: "#3b82f6",
    icon: "\u2261",
    roles: ["admin"],
  },
  {
    id: "rl",
    title: "RL Dashboard",
    desc: "Monitor LinUCB bandit learning progress, action distribution, and rewards",
    color: "#8b5cf6",
    icon: "\u25B3",
    roles: ["admin"],
  },
  {
    id: "cost",
    title: "Cost Monitor",
    desc: "Track LLM usage costs per agent with budget alerts and optimization insights",
    color: "#ec4899",
    icon: "\u0024",
    roles: ["admin", "hr"],
  },
];

export function Dashboard({ onNavigate, role }: Props) {
  const visibleFeatures = features.filter((f) => f.roles.includes(role));

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="page-title">Dashboard</h1>
            <p className="page-desc">Overview of your Self-Healing HR Ops Platform</p>
          </div>
          <span className={`badge ${role === "admin" ? "badge-info" : role === "hr" ? "badge-info" : "badge-warning"}`}>
            {role === "admin" ? "Admin Mode" : role === "hr" ? "HR Mode" : "Employee Mode"}
          </span>
        </div>
      </div>

      <h2 className="section-title" style={{ marginBottom: 16 }}>
        Quick Actions
      </h2>
      <div className="dashboard-grid">
        {visibleFeatures.map((f) => (
          <div key={f.id} className="feature-card" onClick={() => onNavigate(f.id)}>
            <div className="feature-card-icon" style={{ background: `${f.color}15`, color: f.color }}>
              {f.icon}
            </div>
            <div className="feature-card-title">{f.title}</div>
            <div className="feature-card-desc">{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
