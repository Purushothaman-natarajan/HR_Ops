import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Icon } from "./components/Icons";
import { StatusIndicator } from "./components/StatusIndicator";
import { VectorDBStatus } from "./components/VectorDBStatus";
import { DatabaseStatus } from "./components/DatabaseStatus";
import { SchedulerStatus } from "./components/SchedulerStatus";
import { Dashboard } from "./pages/Dashboard";
import { ChatInterface } from "./pages/ChatInterface";
import { HITLPanel } from "./pages/HITLPanel";
import { TraceQueryPanel } from "./pages/TraceQueryPanel";
import { TraceList } from "./pages/TraceList";
import { RLDashboard } from "./pages/RLDashboard";
import { CostDashboard } from "./pages/CostDashboard";
import { PerformanceDashboard } from "./pages/PerformanceDashboard";
import { PolicyManager } from "./pages/PolicyManager";
import { IntegrationsManager } from "./pages/IntegrationsManager";
import { ScanOutcomes } from "./pages/ScanOutcomes";
import { LoginPage } from "./pages/LoginPage";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import type { AppRole } from "./types";

type Page = "dashboard" | "query" | "hitl" | "trace" | "tracequery" | "rl" | "cost" | "policies" | "performance" | "settings" | "scans";

const ADMIN_PAGES: Page[] = ["dashboard", "query", "hitl", "trace", "tracequery", "rl", "cost", "policies", "performance", "settings", "scans"];
const HR_PAGES: Page[] = ["dashboard", "query", "hitl", "policies", "cost", "scans"];
const EMPLOYEE_PAGES: Page[] = ["dashboard", "query", "policies"];

function getAllowedPages(role: AppRole): Page[] {
  if (role === "admin") return ADMIN_PAGES;
  if (role === "hr") return HR_PAGES;
  return EMPLOYEE_PAGES;
}

/** Empty-state placeholder shown when a user role tries to access a page they cannot see. */
function AccessDenied() {
  return (
    <div className="empty-state">
      <Icon name="lock" size={40} className="empty-state-icon" style={{ opacity: 0.5 }} />
      <div className="empty-state-text" style={{ fontWeight: 600, color: "var(--color-text)", marginBottom: 4 }}>
        Access Restricted
      </div>
      <div className="empty-state-text">
        You do not have permission to view this section.
      </div>
    </div>
  );
}

function AppInner() {
  const { role, employeeId, isAuthenticated, logout } = useAuth();
  const [activePage, setActivePage] = useState<Page>("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [resumeSession, setResumeSession] = useState<{ sessionId: string; mode: "standard" | "advanced" } | null>(null);

  const handleContinueSession = (sessionId: string, mode: "standard" | "advanced" = "advanced") => {
    setResumeSession({ sessionId, mode });
    setActivePage("query");
    setSidebarOpen(false);
  };

  if (!isAuthenticated || !role) {
    return <LoginPage />;
  }

  const allowedPages = getAllowedPages(role);
  const safePage = allowedPages.includes(activePage) ? activePage : allowedPages[0];

  const handleNavigate = (p: Page) => {
    setActivePage(p);
    setSidebarOpen(false);
  };

  return (
    <div className="app-layout">
      <button className="mobile-menu-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
        <Icon name="dashboard" size={18} />
      </button>
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}
      <Sidebar activePage={safePage} onNavigate={handleNavigate} role={role} onLogout={logout} isOpen={sidebarOpen} />
      <main className="app-main">
        <div className="app-content">
          <div className="app-content-inner">
            <div className="status-bar">
              <StatusIndicator />
              <VectorDBStatus />
              <DatabaseStatus />
              <SchedulerStatus />
            </div>
            {(() => {
              if (!allowedPages.includes(activePage)) return <AccessDenied />;
              switch (activePage) {
                case "dashboard":
                  return <Dashboard onNavigate={setActivePage} role={role} />;
                case "query": {
                  const rs = resumeSession;
                  // Clear resumeSession after mounting so re-renders don't re-apply
                  const onMount = rs ? () => setResumeSession(null) : undefined;
                  return (
                    <ChatInterface
                      key="query-chat"
                      employeeId={role === "employee" ? employeeId : ""}
                      resumeSessionId={rs?.sessionId}
                      resumeMode={rs?.mode}
                      onMounted={onMount}
                    />
                  );
                }
                case "hitl":
                  return <HITLPanel onContinueSession={handleContinueSession} />;
                case "trace":
                  return <TraceList onContinueSession={handleContinueSession} />;
                case "tracequery":
                  return <TraceQueryPanel />;
                case "rl":
                  return <RLDashboard />;
                case "cost":
                  return <CostDashboard />;
                case "performance":
                  return <PerformanceDashboard />;
                case "policies":
                  return <PolicyManager role={role} />;
                case "settings":
                  return <IntegrationsManager />;
                case "scans":
                  return <ScanOutcomes />;
              }
            })()}
          </div>
        </div>
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}

export default App;
