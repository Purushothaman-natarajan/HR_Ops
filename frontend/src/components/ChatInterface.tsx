import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { TraceViewer } from "./TraceViewer";
import type { ConversationMessage, TraceEvent, ConversationSession } from "../types";

type Mode = "standard" | "advanced";

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
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setError("");

    const userMsg: ConversationMessage = { role: "user", content: q };
    setMessages((prev) => [...prev, userMsg]);

    setLoading(true);
    try {
      let res: Awaited<ReturnType<typeof api.conversation.send>>;
      if (!sessionId) {
        res = await api.conversation.start(q, mode, employeeId);
        setSessionId(res.data.session_id);
      } else {
        res = await api.conversation.send(sessionId, q, employeeId);
      }
      const d = res.data as ConversationSession & { total_cost_usd?: number; trace_events?: TraceEvent[]; mode?: string };
      const assistantMsg: ConversationMessage = {
        role: "assistant",
        content: d.response || "",
        node: d.mode || mode,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setTotalCost((prev) => prev + (d.total_cost_usd || 0));
      if (d.trace_events) {
        setTraceEvents(d.trace_events);
      }
    } catch (e) {
      const msg = String(e);
      const isModelError =
        msg.toLowerCase().includes("model") ||
        msg.toLowerCase().includes("litellm") ||
        msg.toLowerCase().includes("api key") ||
        msg.toLowerCase().includes("ai model");
      if (isModelError) {
        setError("⚠️ " + msg + "\n\nPlease contact the administrator to fix this issue.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId, mode]);

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
    setSessionId(null);
    setMessages([]);
    setTraceEvents([]);
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
                Ask HR policy questions, request employee actions, or explore workforce data.
              </div>
              <div className="chat-examples">
                {[
                  "What is the leave policy?",
                  "Update salary for EMP0001 to 75000",
                  "Check for anomalies in payroll",
                ].map((ex) => (
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
              <div className="chat-bubble-content">{msg.content}</div>
              {msg.role === "assistant" && (
                <div className="chat-bubble-actions">
                  <button
                    className={`chat-rating-btn${ratedTurns[i] === 1 ? " rated" : ""}`}
                    onClick={() => handleRating(i, 1)}
                    disabled={ratedTurns[i] !== undefined}
                    title="Useful"
                  >
                    {ratedTurns[i] === 1 ? "\u2713" : "\uD83D\uDC4D"}
                  </button>
                  <button
                    className={`chat-rating-btn${ratedTurns[i] === 0 ? " rated" : ""}`}
                    onClick={() => handleRating(i, 0)}
                    disabled={ratedTurns[i] !== undefined}
                    title="Somewhat useful"
                  >
                    {ratedTurns[i] === 0 ? "\u2713" : "\uD83E\uDD37"}
                  </button>
                  <button
                    className={`chat-rating-btn${ratedTurns[i] === -1 ? " rated" : ""}`}
                    onClick={() => handleRating(i, -1)}
                    disabled={ratedTurns[i] !== undefined}
                    title="Not useful"
                  >
                    {ratedTurns[i] === -1 ? "\u2713" : "\uD83D\uDC4E"}
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
              <div className="chat-loading">
                <div className="spinner" />
                <span>Processing...</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="card" style={{ margin: "0 16px 8px", borderLeft: "4px solid var(--color-error)" }}>
            <div className="card-body" style={{ padding: "12px 16px", display: "flex", alignItems: "flex-start", gap: 12 }}>
              <span style={{ fontSize: 20, flexShrink: 0 }}>{"\u26A0\uFE0F"}</span>
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
              placeholder="Type your HR request..."
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
