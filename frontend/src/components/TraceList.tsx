import { useState, useEffect, useMemo } from "react";
import { api } from "../api/client";
import { TraceViewer } from "./TraceViewer";
import { Icon } from "./Icons";
import type { TraceEvent } from "../types";

interface TraceRun {
  run_id: string;
  query: string;
  timestamp: string;
  duration_ms?: number;
  cost_usd?: number;
  trace_events?: TraceEvent[];
  final_response?: string;
  session_id?: string;
  turn_number?: number;
}

type SortKey = "timestamp" | "cost" | "duration";
type SortDir = "desc" | "asc";
type SourceFilter = "all" | "graph" | "conversation";

function isConversationRun(run: TraceRun): boolean {
  return run.run_id.startsWith("conv_");
}

function formatDuration(ms?: number): string {
  if (!ms) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatCost(cost?: number): string {
  if (cost == null) return "—";
  if (cost === 0) return "$0";
  if (cost < 0.001) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(5)}`;
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

function shortId(id: string): string {
  return id.length > 10 ? id.slice(0, 10) : id;
}

export function TraceList() {
  const [runs, setRuns] = useState<TraceRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.trace.runs();
      setRuns((res.data.runs || []) as TraceRun[]);
    } catch (e) {
      setError(String(e));
      setRuns([]);
    } finally {
      setLoading(false);
    }
  };

  const filtered = useMemo(() => {
    let list = [...runs];

    if (sourceFilter !== "all") {
      list = list.filter((r) =>
        sourceFilter === "conversation" ? isConversationRun(r) : !isConversationRun(r)
      );
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (r) =>
          r.query.toLowerCase().includes(q) ||
          r.run_id.toLowerCase().includes(q)
      );
    }

    list.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "timestamp") {
        cmp = (a.timestamp || "").localeCompare(b.timestamp || "");
      } else if (sortKey === "cost") {
        cmp = (a.cost_usd ?? 0) - (b.cost_usd ?? 0);
      } else if (sortKey === "duration") {
        cmp = (a.duration_ms ?? 0) - (b.duration_ms ?? 0);
      }
      return sortDir === "desc" ? -cmp : cmp;
    });

    return list;
  }, [runs, search, sortKey, sortDir, sourceFilter]);

  const toggleExpand = (runId: string) => {
    setExpandedId((prev) => (prev === runId ? null : runId));
  };

  if (loading) {
    return (
      <div className="card">
        <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="spinner" />
          <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>Loading traces...</span>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="page-header" style={{ flexShrink: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 className="page-title">Trace Viewer</h1>
            <p className="page-desc">Inspect execution traces from graph runs and conversations</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={fetchRuns}>
            <Icon name="refresh" size={13} /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 12, flexShrink: 0 }}>
          <span>Failed to load traces: {error}</span>
        </div>
      )}

      {runs.length === 0 ? (
        <div className="empty-state">
          <Icon name="cloud" size={48} className="empty-state-icon" />
          <div className="empty-state-text">No trace runs found. Execute a query to generate traces.</div>
        </div>
      ) : (
        <>
          {/* Filter bar */}
          <div className="trace-filter-bar">
            <div className="trace-filter-search">
              <Icon name="query" size={14} />
              <input
                className="input"
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <select
              className="input trace-filter-select"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value as SourceFilter)}
            >
              <option value="all">All</option>
              <option value="graph">Graph</option>
              <option value="conversation">Conv</option>
            </select>
            <select
              className="input trace-filter-select"
              value={`${sortKey}-${sortDir}`}
              onChange={(e) => {
                const [key, dir] = e.target.value.split("-") as [SortKey, SortDir];
                setSortKey(key);
                setSortDir(dir);
              }}
            >
              <option value="timestamp-desc">Newest</option>
              <option value="timestamp-asc">Oldest</option>
              <option value="cost-desc">Cost ↓</option>
              <option value="cost-asc">Cost ↑</option>
              <option value="duration-desc">Slow</option>
              <option value="duration-asc">Fast</option>
            </select>
            <span className="trace-filter-count">
              {filtered.length}/{runs.length}
            </span>
          </div>

          {/* Table container */}
          <div className="trace-table-container">
            {filtered.length === 0 ? (
              <div className="empty-state" style={{ padding: 24 }}>
                <div className="empty-state-text">No runs match your filters.</div>
              </div>
            ) : (
              <table className="trace-data-table">
                <thead>
                  <tr>
                    <th className="th-query">Query</th>
                    <th className="th-source">Src</th>
                    <th className="th-duration">Duration</th>
                    <th className="th-cost">Cost</th>
                    <th className="th-events">Evts</th>
                    <th className="th-time">Time</th>
                    <th className="th-expand"></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((run) => {
                    const isExpanded = expandedId === run.run_id;
                    const source = isConversationRun(run) ? "conversation" : "graph";
                    const eventCount = run.trace_events?.length ?? 0;

                    return (
                      <TraceRow
                        key={run.run_id}
                        run={run}
                        source={source}
                        eventCount={eventCount}
                        isExpanded={isExpanded}
                        onToggle={() => toggleExpand(run.run_id)}
                      />
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function TraceRow({
  run,
  source,
  eventCount,
  isExpanded,
  onToggle,
}: {
  run: TraceRun;
  source: string;
  eventCount: number;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className={`trace-row${isExpanded ? " trace-row-active" : ""}`}
        onClick={onToggle}
      >
        <td className="td-query" title={run.query}>
          <div className="trace-row-query">
            <span className="trace-row-id">{shortId(run.run_id)}</span>
            <span className="trace-row-text">{run.query}</span>
          </div>
        </td>
        <td className="td-source">
          <span className={`trace-src-badge trace-src-${source}`}>
            {source === "conversation" ? "Conv" : "Graph"}
          </span>
        </td>
        <td className="td-duration">{formatDuration(run.duration_ms)}</td>
        <td className="td-cost">{formatCost(run.cost_usd)}</td>
        <td className="td-events">{eventCount || "—"}</td>
        <td className="td-time">{formatTime(run.timestamp)}</td>
        <td className="td-expand">
          <Icon
            name={isExpanded ? "chevron-up" : "chevron-down"}
            size={14}
            className="trace-expand-icon"
          />
        </td>
      </tr>
      {isExpanded && (
        <tr className="trace-detail-row">
          <td colSpan={7}>
            <div className="trace-detail">
              <div className="trace-detail-header">
                <div className="trace-detail-meta">
                  <span className="trace-detail-id">
                    <Icon name="trace" size={12} /> {run.run_id}
                  </span>
                  <span>{formatDuration(run.duration_ms)}</span>
                  <span>{formatCost(run.cost_usd)}</span>
                  <span>{eventCount} event{eventCount !== 1 ? "s" : ""}</span>
                  <span>{formatTime(run.timestamp)}</span>
                </div>
              </div>

              {run.final_response && (
                <div className="trace-detail-response">
                  <div className="trace-response-label">Response</div>
                  <div className="trace-response-box">{run.final_response}</div>
                </div>
              )}

              {eventCount > 0 ? (
                <TraceViewer events={run.trace_events} />
              ) : (
                <div className="trace-no-events">No trace events recorded for this run.</div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
