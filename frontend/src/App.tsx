import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { StatusIndicator } from "./components/StatusIndicator";
import { VectorDBStatus } from "./components/VectorDBStatus";
import { DatabaseStatus } from "./components/DatabaseStatus";
import { Dashboard } from "./components/Dashboard";
import { ChatInterface } from "./components/ChatInterface";
import { HITLPanel } from "./components/HITLPanel";
import { TraceQueryPanel } from "./components/TraceQueryPanel";
import { TraceList } from "./components/TraceList";
import { RLDashboard } from "./components/RLDashboard";
import { CostDashboard } from "./components/CostDashboard";
import { PolicyManager } from "./components/PolicyManager";
import { LoginPage } from "./components/LoginPage";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import type { AppRole } from "./types";

type Page = "dashboard" | "query" | "hitl" | "trace" | "tracequery" | "rl" | "cost" | "policies";

const ADMIN_PAGES: Page[] = ["dashboard", "query", "hitl", "trace", "tracequery", "rl", "cost", "policies"];
const HR_PAGES: Page[] = ["dashboard", "query", "hitl", "policies", "cost"];
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
      <div className="empty-state-icon" style={{ fontSize: 40, opacity: 0.5 }}>{"\uD83D\uDD12"}</div>
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

  if (!isAuthenticated || !role) {
    return <LoginPage />;
  }

  const allowedPages = getAllowedPages(role);
  const safePage = allowedPages.includes(activePage) ? activePage : allowedPages[0];

  return (
    <div className="app-layout">
      <Sidebar activePage={safePage} onNavigate={(p) => setActivePage(p)} role={role} onLogout={logout} />
      <main className="app-main">
        <div className="app-content">
          <div className="app-content-inner">
            <div className="status-bar">
              <StatusIndicator />
              <VectorDBStatus />
              <DatabaseStatus />
            </div>
            {(() => {
              if (!allowedPages.includes(activePage)) return <AccessDenied />;
              switch (activePage) {
                case "dashboard":
                  return <Dashboard onNavigate={setActivePage} role={role} />;
                case "query":
                  return <ChatInterface employeeId={role === "employee" ? employeeId : ""} />;
                case "hitl":
                  return <HITLPanel />;
                case "trace":
                  return <TraceList />;
                case "tracequery":
                  return <TraceQueryPanel />;
                case "rl":
                  return <RLDashboard />;
                case "cost":
                  return <CostDashboard />;
                case "policies":
                  return <PolicyManager role={role} />;
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
