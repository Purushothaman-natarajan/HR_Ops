import { useState } from "react";
import { QueryInput } from "./components/QueryInput";
import { HITLPanel } from "./components/HITLPanel";
import { TraceViewer } from "./components/TraceViewer";
import { TraceQueryPanel } from "./components/TraceQueryPanel";
import { RLDashboard } from "./components/RLDashboard";
import { CostDashboard } from "./components/CostDashboard";
import { api, TraceEvent } from "./api/client";

function App() {
  const [activeTab, setActiveTab] = useState("query");
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [response, setResponse] = useState("");
  const [runId, setRunId] = useState("");
  const [cost, setCost] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleQuery = async (query: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.graph.run(query);
      setEvents(res.trace_events);
      setResponse(res.final_response);
      setRunId(res.run_id);
      setCost(res.total_cost_usd);
      if (res.anomaly_results && res.anomaly_results.length > 0) {
        setEvents((prev) => [
          ...prev,
          ...res.anomaly_results.map((a) => ({
            node: "anomaly_detection",
            agent_role: "anomaly",
            input_text: `Anomaly in ${a.anomaly_field}`,
            output_text: a.description,
            duration_ms: 0,
          })),
        ]);
      }
      if (res.compliance_veto) {
        setEvents((prev) => [
          ...prev,
          {
            node: "compliance_veto",
            agent_role: "compliance",
            input_text: "Compliance check",
            output_text: res.compliance_reason,
            duration_ms: 0,
          },
        ]);
      }
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
            {response && (
              <div style={{ padding: "8px 16px" }}>
                <div style={{ padding: 12, background: "#f0fdf4", borderRadius: 8, marginBottom: 8 }}>
                  <strong>Response:</strong> {response}
                  {runId && <span style={{ marginLeft: 12, color: "#666", fontSize: 12 }}>Run: {runId}</span>}
                  {cost > 0 && <span style={{ marginLeft: 12, color: "#666", fontSize: 12 }}>Cost: ${cost.toFixed(5)}</span>}
                </div>
              </div>
            )}
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
