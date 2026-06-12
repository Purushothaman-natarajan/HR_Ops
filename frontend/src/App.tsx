import { useState } from "react";
import { QueryInput } from "./components/QueryInput";
import { HITLPanel } from "./components/HITLPanel";
import { TraceViewer } from "./components/TraceViewer";
import { TraceQueryPanel } from "./components/TraceQueryPanel";
import { RLDashboard } from "./components/RLDashboard";
import { CostDashboard } from "./components/CostDashboard";
import { api } from "./api/client";

interface TraceEvent {
  node: string;
  agent_role: string;
  input_text: string;
  output_text: string;
  duration_ms: number;
  cost_usd?: number;
  cache_hit?: boolean;
}

function App() {
  const [activeTab, setActiveTab] = useState("query");
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleQuery = async (query: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.health();
      console.log("Backend health:", res);
      // real query would hit /graph/run endpoint
      setEvents([
        {
          node: "triage",
          agent_role: "supervisor",
          input_text: query,
          output_text: `Classified as policy (simulated — backend integration pending)`,
          duration_ms: 0,
        },
      ]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { key: "query", label: "Query" },
    { key: "hitl", label: "HITL" },
    { key: "trace", label: "Trace" },
    { key: "tracequery", label: "Trace Query" },
    { key: "rl", label: "RL" },
    { key: "cost", label: "Cost" },
  ];

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", fontFamily: "system-ui, sans-serif" }}>
      <header style={{ padding: "20px 16px 8px", borderBottom: "1px solid #e5e7eb" }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>HR Ops Platform</h1>
        <p style={{ margin: "4px 0 0", color: "#666", fontSize: 14 }}>
          Self-Healing Multi-Agent System
        </p>
      </header>

      <nav style={{ display: "flex", gap: 4, padding: "12px 16px", borderBottom: "1px solid #e5e7eb" }}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "6px 16px",
              borderRadius: 6,
              border: "none",
              background: activeTab === tab.key ? "#4f46e5" : "#f3f4f6",
              color: activeTab === tab.key ? "#fff" : "#374151",
              cursor: "pointer",
              fontWeight: activeTab === tab.key ? 600 : 400,
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main style={{ padding: 16 }}>
        {error && (
          <div style={{ padding: 12, background: "#fef2f2", color: "#991b1b", borderRadius: 6, marginBottom: 12 }}>
            {error}
          </div>
        )}

        {activeTab === "query" && (
          <>
            <QueryInput onSubmit={handleQuery} disabled={loading} />
            {loading && <p style={{ padding: "0 16px", color: "#666" }}>Processing...</p>}
            <TraceViewer events={events} />
          </>
        )}
        {activeTab === "hitl" && <HITLPanel />}
        {activeTab === "trace" && <TraceViewer events={events} />}
        {activeTab === "tracequery" && <TraceQueryPanel />}
        {activeTab === "rl" && <RLDashboard />}
        {activeTab === "cost" && <CostDashboard />}
      </main>
    </div>
  );
}

export default App;
