import { useState } from "react";
import { Icon } from "./Icons";
import type { IconName } from "./Icons";
import type { TraceEvent, ActivityEvent } from "../types";

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

const ACTIVITY_ICONS: Record<string, IconName> = {
  search: "search",
  tool_call: "action",
  llm_call: "policy",
  decision: "supervisor",
  cache_check: "cache",
  rerank: "policy",
  guardrail: "compliance",
};

const ACTIVITY_COLORS: Record<string, string> = {
  search: "#3b82f6",
  tool_call: "#f59e0b",
  llm_call: "#8b5cf6",
  decision: "#10b981",
  cache_check: "#06b6d4",
  rerank: "#ec4899",
  guardrail: "#ef4444",
};

const STATUS_ICONS: Record<string, IconName> = {
  running: "spinner",
  completed: "check",
  failed: "warning",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

interface ActivityItemProps {
  activity: ActivityEvent;
  isLast: boolean;
}

function ActivityItem({ activity, isLast }: ActivityItemProps) {
  const color = ACTIVITY_COLORS[activity.type] || "#6b7280";
  const icon = ACTIVITY_ICONS[activity.type] || "policy";
  const statusIcon = STATUS_ICONS[activity.status] || "check";

  return (
    <div className="activity-item">
      <div className="activity-connector" style={{ background: isLast ? "transparent" : color }} />
      <div className="activity-dot" style={{ background: color, boxShadow: `0 0 0 3px ${color}22` }}>
        <Icon name={icon} size={12} style={{ color: "#fff" }} />
      </div>
      <div className="activity-content">
        <div className="activity-header">
          <span className="activity-label">{activity.label}</span>
          <span className="activity-status" style={{ color }}>
            <Icon name={statusIcon} size={12} />
            {activity.status === "running" && <span className="spinner-sm" />}
          </span>
        </div>
        {activity.detail && (
          <div className="activity-detail">{activity.detail}</div>
        )}
        {activity.metadata && Object.keys(activity.metadata).length > 0 && (
          <div className="activity-meta">
            {Object.entries(activity.metadata).map(([key, value]) => (
              <span key={key} className="activity-meta-tag">
                {key}: {String(value)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface NodeFlowItemProps {
  event: TraceEvent;
  isLast: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}

function NodeFlowItem({ event, isLast, isExpanded, onToggle }: NodeFlowItemProps) {
  const icon = NODE_ICONS[event.node] || "supervisor";
  const activities = event.activities || [];
  const hasActivities = activities.length > 0;
  const docCount = event.retrieved_docs?.length || 0;
  const hasToolCall = event.tool_call && Object.keys(event.tool_call).length > 0;

  return (
    <div className={`flow-node ${isLast ? "flow-node-last" : ""}`}>
      <div className="flow-node-connector">
        <div className="flow-node-dot">
          <Icon name={icon} size={16} />
        </div>
        {!isLast && <div className="flow-node-line" />}
      </div>
      <div className="flow-node-body" onClick={hasActivities ? onToggle : undefined}>
        <div className="flow-node-header">
          <span className="flow-node-name">{event.agent_role || event.node}</span>
          <span className="flow-node-duration">{formatDuration(event.duration_ms)}</span>
          {hasActivities && (
            <Icon
              name={isExpanded ? "chevron-up" : "chevron-down"}
              size={14}
              className="flow-node-chevron"
            />
          )}
        </div>
        <div className="flow-node-summary">
          {event.cache_hit && <span className="flow-tag flow-tag-cache">cache hit</span>}
          {docCount > 0 && (
            <span className="flow-tag flow-tag-docs">
              <Icon name="search" size={10} /> {docCount} docs
            </span>
          )}
          {hasToolCall && (
            <span className="flow-tag flow-tag-tool">
              <Icon name="action" size={10} /> {(event.tool_call as Record<string, unknown>).tool as string || "tool"}
            </span>
          )}
          {event.output_text && (
            <span className="flow-node-preview">
              {event.output_text.length > 80
                ? event.output_text.slice(0, 80) + "..."
                : event.output_text}
            </span>
          )}
        </div>
        {isExpanded && hasActivities && (
          <div className="flow-node-activities">
            {activities.map((act, i) => (
              <ActivityItem
                key={i}
                activity={act}
                isLast={i === activities.length - 1}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface ActivityPanelProps {
  events: TraceEvent[];
  totalCost?: number;
  compact?: boolean;
}

export function ActivityPanel({ events, totalCost, compact = false }: ActivityPanelProps) {
  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set());

  const toggleNode = (index: number) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  if (!events || events.length === 0) return null;

  return (
    <div className={`activity-panel ${compact ? "activity-panel-compact" : ""}`}>
      <div className="activity-panel-header">
        <span className="activity-panel-title">Flow</span>
        <div className="activity-panel-meta">
          {events.length} nodes
          {totalCost !== undefined && totalCost > 0 && (
            <span className="activity-panel-cost">${totalCost.toFixed(5)}</span>
          )}
        </div>
      </div>
      <div className="activity-flow">
        {events.map((event, i) => (
          <NodeFlowItem
            key={i}
            event={event}
            isLast={i === events.length - 1}
            isExpanded={expandedNodes.has(i)}
            onToggle={() => toggleNode(i)}
          />
        ))}
      </div>
    </div>
  );
}

interface LiveActivityPanelProps {
  events: Array<{
    node: string;
    agent_role: string;
    duration_ms: number;
    output_text: string;
    activities?: ActivityEvent[];
    reasoning?: string;
    retrieved_docs?: Array<{ source: string; score: number; chunk: string }>;
    tool_call?: Record<string, unknown>;
  }>;
  isProcessing?: boolean;
}

export function LiveActivityPanel({ events, isProcessing = false }: LiveActivityPanelProps) {
  if (!events || events.length === 0) return null;

  return (
    <div className="activity-panel activity-panel-live">
      <div className="activity-panel-header">
        <span className="activity-panel-title">Processing</span>
        {isProcessing && <span className="spinner-sm" />}
      </div>
      <div className="activity-flow">
        {events.map((event, i) => {
          const icon = NODE_ICONS[event.node] || "supervisor";
          return (
            <div key={i} className="flow-node">
              <div className="flow-node-connector">
                <div className="flow-node-dot flow-node-dot-live">
                  <Icon name={icon} size={14} />
                </div>
                {i < events.length - 1 && <div className="flow-node-line" />}
              </div>
              <div className="flow-node-body">
                <div className="flow-node-header">
                  <span className="flow-node-name">{event.agent_role || event.node}</span>
                  <span className="flow-node-duration">{formatDuration(event.duration_ms)}</span>
                </div>
                {event.activities && event.activities.length > 0 && (
                  <div className="flow-node-activities">
                    {event.activities.map((act, j) => (
                      <ActivityItem
                        key={j}
                        activity={act}
                        isLast={j === event.activities!.length - 1}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {isProcessing && (
          <div className="flow-node">
            <div className="flow-node-connector">
              <div className="flow-node-dot flow-node-dot-active">
                <div className="spinner-sm" />
              </div>
            </div>
            <div className="flow-node-body">
              <div className="flow-node-header">
                <span className="flow-node-name flow-node-name-active">Processing...</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
