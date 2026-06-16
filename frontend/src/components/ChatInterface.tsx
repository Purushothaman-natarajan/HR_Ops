import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import { api } from "../api/client";
import { TraceViewer } from "./TraceViewer";
import { ActivityPanel, LiveActivityPanel } from "./ActivityPanel";
import { Icon } from "./Icons";
import type { ConversationMessage, TraceEvent } from "../types";

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
      "Find all employees named John and show their department.",
    ],
  },
};

interface ChatInterfaceProps {
  /** When scoping queries to a specific employee (employee role). */
  employeeId?: string;
  /** Session ID to resume from (e.g., passed from HITL panel). */
  resumeSessionId?: string;
  /** Mode to use when resuming a session. */
  resumeMode?: Mode;
  /** Called once after the resumed session is loaded, so parent can clear the resume state. */
  onMounted?: () => void;
}

/** Multi-turn conversation chat with session management, source citations, and inline ratings. */
type NodeEvent = TraceEvent;

/** Source citation chip — shows file name, score, and expandable chunk text. */
function SourceCitation({ doc }: { doc: { source: string; score: number; chunk: string } }) {
  const [expanded, setExpanded] = useState(false);
  const filename = doc.source.split(/[\\/]/).pop() || doc.source;
  const scoreLabel = doc.score != null && isFinite(doc.score) && doc.score > 0
    ? `${(doc.score * 100).toFixed(0)}%`
    : null;

  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "4px 10px",
        cursor: "pointer",
        transition: "all 0.15s",
        maxWidth: expanded ? 420 : "none",
      }}
      onClick={() => setExpanded(!expanded)}
      title={`Click to ${expanded ? "collapse" : "expand"} source chunk`}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Icon name="doc" size={12} style={{ color: "var(--color-accent)", flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text)" }}>{filename}</span>
        {scoreLabel && (
          <span style={{ fontSize: 10, color: "var(--color-text-muted)", marginLeft: 2 }}>{scoreLabel}</span>
        )}
        <Icon
          name="arrow"
          size={10}
          style={{ color: "var(--color-text-muted)", marginLeft: "auto", transform: expanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.15s" }}
        />
      </div>
      {expanded && doc.chunk && (
        <div style={{
          marginTop: 6,
          fontSize: 11,
          color: "var(--color-text-secondary)",
          lineHeight: 1.6,
          maxHeight: 200,
          overflowY: "auto",
          borderTop: "1px solid var(--color-border)",
          paddingTop: 6,
          whiteSpace: "pre-wrap",
        }}>
          {doc.chunk.slice(0, 600)}{doc.chunk.length > 600 ? "…" : ""}
        </div>
      )}
    </div>
  );
}

/** Sources panel shown below an assistant message. */
function SourcesPanel({ events }: { events: NodeEvent[] }) {
  const allDocs = events
    .flatMap((e) => e.retrieved_docs || [])
    .filter((d) => d.source);

  // Deduplicate by source file
  const seen = new Set<string>();
  const uniqueDocs = allDocs.filter((d) => {
    const key = d.source;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  if (uniqueDocs.length === 0) return null;

  return (
    <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--color-border)" }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "var(--color-text-muted)", letterSpacing: "0.06em", marginBottom: 6 }}>
        SOURCES ({uniqueDocs.length})
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {uniqueDocs.map((doc, i) => (
          <SourceCitation key={i} doc={doc} />
        ))}
      </div>
    </div>
  );
}

function TraceCollapsible({ events }: { events: NodeEvent[] }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="trace-collapsible">
      <button
        type="button"
        className="trace-collapsible-trigger"
        onClick={() => setIsOpen(!isOpen)}
        title={isOpen ? "Collapse execution trace" : "Expand execution trace"}
      >
        <Icon name="trace" size={12} className="trace-trigger-icon" />
        <span className="trace-trigger-text">
          EXECUTION TRACE ({events.length} event{events.length !== 1 ? "s" : ""})
        </span>
        <Icon
          name="chevron-down"
          size={12}
          className={`trace-trigger-arrow ${isOpen ? "open" : ""}`}
        />
      </button>
      {isOpen && (
        <div className="trace-collapsible-content">
          <TraceViewer events={events} />
        </div>
      )}
    </div>
  );
}

export function ChatInterface({
  employeeId = "",
  resumeSessionId,
  resumeMode,
  onMounted,
}: ChatInterfaceProps) {
  const [sessionId, setSessionId] = useState<string | null>(resumeSessionId || null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [mode, setMode] = useState<Mode>(resumeMode || "standard");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);
  const [showTrace, setShowTrace] = useState(false);
  const [totalCost, setTotalCost] = useState(0);
  const [ratedTurns, setRatedTurns] = useState<Record<number, 1 | 0 | -1>>({});
  const [liveEvents, setLiveEvents] = useState<NodeEvent[]>([]);
  const liveEventsRef = useRef<NodeEvent[]>([]);
  const [resumeLoading, setResumeLoading] = useState(!!resumeSessionId);
  const esRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const modeTemplate = MODE_TEMPLATES[mode];

  // Load resumed session history when resumeSessionId changes
  useEffect(() => {
    if (!resumeSessionId) return;
    setSessionId(resumeSessionId);
    setResumeLoading(true);
    setMessages([]);
    setTraceEvents([]);
    setLiveEvents([]);
    setRatedTurns({});
    setError("");
    setShowTrace(false);
    
    api.conversation.get(resumeSessionId)
      .then((res) => {
        const msgs = res.data.messages || [];
        setMessages(msgs);
        if (res.data.mode) setMode(res.data.mode as Mode);
        setTotalCost(res.data.total_cost ?? res.data.total_cost_usd ?? 0);
      })
      .catch(() => {
        setError(`Could not load session "${resumeSessionId}". Starting fresh.`);
        setSessionId(null);
      })
      .finally(() => {
        setResumeLoading(false);
        onMounted?.();
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeSessionId]);

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
    liveEventsRef.current = [];
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
        liveEventsRef.current.push(eventData);
        setLiveEvents([...liveEventsRef.current]);
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

        // Capture the trace events from completion payload, falling back to streamed events
        const currentLiveEvents = events.length > 0 ? events : [...liveEventsRef.current];

        const assistantMsg: ConversationMessage = {
          role: "assistant",
          content: response,
          node: mode,
          liveEvents: currentLiveEvents,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setTotalCost((prev) => prev + cost);
        setLiveEvents([]);
        liveEventsRef.current = [];
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

  if (resumeLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 300, gap: 12 }}>
        <div className="spinner" />
        <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>Loading session {resumeSessionId?.slice(0, 12)}…</span>
      </div>
    );
  }

  return (
    <div className="chat-page">
      <div className="chat-header">
        <div className="chat-header-left">
          <h1 className="page-title" style={{ margin: 0 }}>Query Agent</h1>
          {sessionId && (
            <span className="chat-session-badge">
              Session: {sessionId.slice(0, 14)}…
            </span>
          )}
          {resumeSessionId && sessionId === resumeSessionId && (
            <span className="badge badge-warning" style={{ fontSize: 10 }}>RESUMED</span>
          )}
        </div>
        <div className="chat-header-right">
          {!sessionId && (
            <div className="chat-mode-selector-pill">
              <button
                type="button"
                className={`mode-pill-btn ${mode === "standard" ? "active" : ""}`}
                onClick={() => setMode("standard")}
                title="Focused questions on leave, attendance, compensation and policies"
              >
                <Icon name="doc" size={13} />
                <span>Standard</span>
              </button>
              <button
                type="button"
                className={`mode-pill-btn ${mode === "advanced" ? "active" : ""}`}
                onClick={() => setMode("advanced")}
                title="RL routing, compliance veto checks and anomaly investigation actions"
              >
                <Icon name="rl" size={13} />
                <span>Advanced</span>
                <span className="pill-badge-sparkle">RL</span>
              </button>
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
                  events={msg.liveEvents}
                  totalCost={msg.cost}
                  compact
                />
              )}
              <div className={`chat-bubble-content${msg.role === "assistant" ? " markdown" : ""}`}>
                {msg.role === "assistant" ? (
                  <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{msg.content}</ReactMarkdown>
                ) : (
                  msg.content
                )}
              </div>
              {/* Source Citations — shown for each assistant message that has retrieved docs */}
              {msg.role === "assistant" && msg.liveEvents && msg.liveEvents.length > 0 && (
                <SourcesPanel events={msg.liveEvents} />
              )}
              {msg.role === "assistant" && msg.liveEvents && msg.liveEvents.length > 0 && (
                <TraceCollapsible events={msg.liveEvents} />
              )}
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
