import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { TraceViewer } from "./TraceViewer";
import { ActivityPanel, LiveActivityPanel } from "./ActivityPanel";
import { Icon } from "./Icons";
import type { IconName } from "./Icons";
import type { ConversationMessage, TraceEvent, ConversationSession } from "../types";

type Mode = "standard" | "advanced";

const MODE_TEMPLATES: Record<Mode, { description: string; placeholder: string; examples: string[] }> = {
  standard: {
    description: "Ask focused questions against the stored leave, attendance, compensation, and compliance policies.",
    placeholder: "Ask about leave, attendance, compensation, or compliance policy...",
    examples: [
      "How many annual leave days accrue each month, and how many can carry forward?",
      "When is a medical certificate required for sick leave?",
      "What approvals are needed for remote work beyond 3 days per week?",
    ],
  },
  advanced: {
    description: "Use RL routing for policy checks, compliance review, HRIS actions, and anomaly investigations.",
    placeholder: "Ask for routing, compliance review, anomaly detection, or an employee action...",
    examples: [
      "Review whether a retroactive salary adjustment for EMP0001 is allowed under compensation policy.",
      "Check if sharing EMP0002 HR records with an external vendor is compliant.",
      "Investigate employees with more than 3 unscheduled absences this quarter and explain the policy risk.",
    ],
  },
};

interface ChatInterfaceProps {
  /** When scoping queries to a specific employee (employee role). */
  employeeId?: string;
}

/** Multi-turn conversation chat with session management, mode selector, and inline ratings.
 *
 * Self-contained component that creates/manages sessions via api.conversation.*.
 * Shows 👍/👎 buttons per assistant message for RL feedback.
 *
 * @example
 * <ChatInterface />
 */
interface NodeEvent {
  node: string;
  agent_role: string;
  duration_ms: number;
  output_text: string;
  input_text: string;
  cost_usd: number;
  model_used: string;
  activities?: Array<{
    type: string;
    label: string;
    detail: string;
    status: string;
    duration_ms?: number;
    metadata?: Record<string, unknown>;
  }>;
  reasoning?: string;
  retrieved_docs?: Array<{ source: string; score: number; chunk: string }>;
  tool_call?: Record<string, unknown>;
}

const NODE_ICONS: Record<string, IconName> = {
  supervisor: "supervisor",
  triage: "triage",
  policy: "policy",
  action: "action",
  anomaly: "anomaly",
  compliance: "compliance",
  parallel_check: "parallel",
  hitl: "hitl",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function ChatInterface({ employeeId = "" }: ChatInterfaceProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [mode, setMode] = useState<Mode>("standard");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);
  const [showTrace, setShowTrace] = useState(false);
  const [totalCost, setTotalCost] = useState(0);
  const [ratedTurns, setRatedTurns] = useState<Record<number, 1 | 0 | -1>>({});
  const [liveEvents, setLiveEvents] = useState<NodeEvent[]>([]);
  const esRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const modeTemplate = MODE_TEMPLATES[mode];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveEvents]);

  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, []);

  const handleSend = useCallback(() => {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setError("");
    setLiveEvents([]);

    const userMsg: ConversationMessage = { role: "user", content: q };
    setMessages((prev) => [...prev, userMsg]);

    setLoading(true);

    // Close any previous EventSource
    esRef.current?.close();

    const url = sessionId
      ? api.conversation.streamSendUrl(sessionId, q)
      : api.conversation.streamStartUrl(q, mode);

    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("node_complete", (e: MessageEvent) => {
      try {
        const eventData: NodeEvent = JSON.parse(e.data);
        setLiveEvents((prev) => [...prev, eventData]);
      } catch {
        // ignore parse errors
      }
    });

    es.addEventListener("complete", (e: MessageEvent) => {
      try {
        const eventData = JSON.parse(e.data);
        const response = eventData.response || "";
        const newSessionId: string = eventData.session_id || "";
        const cost: number = eventData.total_cost_usd || 0;
        const events: TraceEvent[] = eventData.trace_events || [];

        setSessionId((prev) => prev || newSessionId);

        // Capture the live events that were displayed during streaming
        const currentLiveEvents = [...liveEvents];

        const assistantMsg: ConversationMessage = {
          role: "assistant",
          content: response,
          node: mode,
          liveEvents: currentLiveEvents,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setTotalCost((prev) => prev + cost);
        setLiveEvents([]);
        if (events.length > 0) {
          setTraceEvents(events);
        }
      } catch {
        setError("Failed to parse response");
      } finally {
        setLoading(false);
        es.close();
        esRef.current = null;
      }
    });

    es.addEventListener("error", () => {
      // EventSource auto-reconnects on network errors; if already closed ignore
      if (es.readyState === EventSource.CLOSED) {
        setError("Connection lost. Please try again.");
        setLoading(false);
        esRef.current = null;
      }
    });

    // Handle non-SSE error events from our backend
    es.addEventListener("error_event", (e: MessageEvent) => {
      try {
        const errData = JSON.parse(e.data);
        setError(errData.message || "An error occurred");
      } catch {
        setError("An error occurred");
      }
      setLoading(false);
      es.close();
      esRef.current = null;
    });
  }, [input, loading, sessionId, mode, employeeId]);

  const handleRating = async (turnIndex: number, rating: 1 | 0 | -1) => {
    if (ratedTurns[turnIndex] !== undefined) return;
    const msg = messages[turnIndex];
    if (!msg || msg.role !== "assistant") return;
    try {
      await api.feedback.submit(sessionId || "unknown", msg.node || "unknown", rating);
      setRatedTurns((prev) => ({ ...prev, [turnIndex]: rating }));
    } catch {
      // silently fail
    }
  };

  const handleNewSession = () => {
    esRef.current?.close();
    esRef.current = null;
    setSessionId(null);
    setMessages([]);
    setTraceEvents([]);
    setLiveEvents([]);
    setTotalCost(0);
    setRatedTurns({});
    setError("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-page">
      <div className="chat-header">
        <div className="chat-header-left">
          <h1 className="page-title" style={{ margin: 0 }}>Query Agent</h1>
          {sessionId && (
            <span className="chat-session-badge">
              Session: {sessionId}
            </span>
          )}
        </div>
        <div className="chat-header-right">
          {!sessionId && (
            <div className="chat-mode-selector">
              <span className="chat-mode-label">Mode:</span>
              <select
                className="input"
                style={{ width: 130, padding: "4px 8px", fontSize: 12 }}
                value={mode}
                onChange={(e) => setMode(e.target.value as Mode)}
              >
                <option value="standard">Standard</option>
                <option value="advanced">Advanced</option>
              </select>
              <span className={`badge ${mode === "advanced" ? "badge-warning" : "badge-info"}`}>
                {mode === "advanced" ? "RL + Triggers" : "Basic"}
              </span>
            </div>
          )}
          {sessionId && (
            <button className="btn btn-sm btn-secondary" onClick={handleNewSession}>
              New Session
            </button>
          )}
        </div>
      </div>

      <div className="chat-container">
        <div className="chat-messages">
          {messages.length === 0 && !loading && (
            <div className="chat-welcome">
              <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>HR Ops Assistant</div>
              <div style={{ fontSize: 13, color: "var(--color-text-muted)", maxWidth: 400 }}>
                {modeTemplate.description}
              </div>
              <div className="chat-examples">
                {modeTemplate.examples.map((ex) => (
                  <button
                    key={ex}
                    className="btn btn-sm btn-secondary"
                    onClick={() => {
                      setInput(ex);
                    }}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`chat-bubble chat-bubble-${msg.role}`}>
              <div className="chat-bubble-role">
                {msg.role === "user" ? "You" : `Agent${msg.node ? ` (${msg.node})` : ""}`}
              </div>
              {msg.role === "assistant" && msg.liveEvents && msg.liveEvents.length > 0 && (
                <ActivityPanel
                  events={msg.liveEvents.map((e) => ({
                    ...e,
                    cost_usd: e.cost_usd,
                  }))}
                  totalCost={msg.cost}
                  compact
                />
              )}
              <div className="chat-bubble-content">{msg.content}</div>
              {msg.role === "assistant" && (
                <div className="chat-bubble-actions">
                  <button
                    className={`chat-rating-btn${ratedTurns[i] === 1 ? " rated" : ""}`}
                    onClick={() => handleRating(i, 1)}
                    disabled={ratedTurns[i] !== undefined}
                    title="Useful"
                  >
                    <Icon name={ratedTurns[i] === 1 ? "check" : "thumbs-up"} size={16} />
                  </button>
                  <button
                    className={`chat-rating-btn${ratedTurns[i] === 0 ? " rated" : ""}`}
                    onClick={() => handleRating(i, 0)}
                    disabled={ratedTurns[i] !== undefined}
                    title="Somewhat useful"
                  >
                    <Icon name={ratedTurns[i] === 0 ? "check" : "shrug"} size={16} />
                  </button>
                  <button
                    className={`chat-rating-btn${ratedTurns[i] === -1 ? " rated" : ""}`}
                    onClick={() => handleRating(i, -1)}
                    disabled={ratedTurns[i] !== undefined}
                    title="Not useful"
                  >
                    <Icon name={ratedTurns[i] === -1 ? "check" : "thumbs-down"} size={16} />
                  </button>
                  {msg.cost !== undefined && (
                    <span className="chat-cost-badge">${msg.cost.toFixed(5)}</span>
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="chat-bubble chat-bubble-assistant">
              <div className="chat-bubble-role">Agent</div>
              <LiveActivityPanel
                events={liveEvents}
                isProcessing={loading}
              />
              {liveEvents.length === 0 && (
                <div className="chat-loading">
                  <div className="spinner" />
                  <span>Starting...</span>
                </div>
              )}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="card" style={{ margin: "0 16px 8px", borderLeft: "4px solid var(--color-error)" }}>
            <div className="card-body" style={{ padding: "12px 16px", display: "flex", alignItems: "flex-start", gap: 12 }}>
              <Icon name="warning" size={20} style={{ flexShrink: 0 }} />
              <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                {error}
              </div>
              <button className="btn btn-sm" style={{ flexShrink: 0 }} onClick={() => setError("")}>
                OK
              </button>
            </div>
          </div>
        )}

        <div className="chat-input-bar">
          <div className="chat-input-row">
            <input
              type="text"
              className="input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={modeTemplate.placeholder}
              disabled={loading}
            />
            <button className="btn btn-primary" onClick={handleSend} disabled={loading || !input.trim()}>
              {loading ? "..." : "Send"}
            </button>
          </div>
          <div className="chat-input-footer">
            {totalCost > 0 && <span className="chat-cost-badge">Total: ${totalCost.toFixed(5)}</span>}
            {traceEvents.length > 0 && (
              <button
                className="btn btn-sm btn-secondary"
                onClick={() => setShowTrace(!showTrace)}
              >
                {showTrace ? "Hide Trace" : `Trace (${traceEvents.length})`}
              </button>
            )}
          </div>
        </div>
      </div>

      {showTrace && traceEvents.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-header">
            <span className="card-title">Execution Trace</span>
            <span className="badge badge-info">{traceEvents.length} events</span>
          </div>
          <div className="card-body" style={{ padding: 12 }}>
            <TraceViewer events={traceEvents} />
          </div>
        </div>
      )}
    </div>
  );
}
