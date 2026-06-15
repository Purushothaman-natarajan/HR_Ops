/** A single step in a LangGraph execution trace, capturing one agent node invocation.
 *
 * @example
 * { node: "supervisor", agent_role: "supervisor", input_text: "What is leave policy?",
 *   output_text: "Routing to policy agent", duration_ms: 420, cost_usd: 0.0015,
 *   cache_hit: false, model_used: "gpt-4o-mini" }
 */
export interface TraceEvent {
  node: string;
  agent_role: string;
  input_text: string;
  output_text: string;
  duration_ms: number;
  cost_usd?: number;
  cache_hit?: boolean;
  model_used?: string;
  reasoning?: string;
  alternatives?: Array<{ agent: string; score: number }>;
  retrieved_docs?: Array<{ source: string; score: number; chunk: string }>;
  tool_call?: Record<string, unknown>;
  activities?: ActivityEvent[];
}

/** A sub-activity within a node execution (DB search, tool call, LLM call, etc.). */
export interface ActivityEvent {
  type: "search" | "tool_call" | "llm_call" | "decision" | "cache_check" | "rerank" | "guardrail";
  label: string;
  detail: string;
  status: "running" | "completed" | "failed";
  duration_ms?: number;
  metadata?: Record<string, unknown>;
}

/** Summary of a trace run for listing (GET /trace/runs). */
export interface TraceRunSummary {
  run_id: string;
  query: string;
  timestamp: string;
  duration_ms?: number;
  cost_usd?: number;
  trace_events?: TraceEvent[];
}

/** Full detail of a trace run (GET /trace/runs/{run_id}). */
export interface TraceRunDetail {
  run_id: string;
  query: string;
  final_response: string;
  total_cost_usd: number;
  trace_events: TraceEvent[];
  anomaly_results: AnomalyResult[];
}

/** Result of a single anomaly detection check (salary, leave, compliance).
 *
 * @example
 * { detected: true, severity: 0.85, description: "Salary outlier: EMP0012",
 *   anomaly_field: "salary", suggested_action: "Review compensation" }
 */
export interface AnomalyResult {
  detected: boolean;
  severity: number;
  description: string;
  anomaly_field: string;
  suggested_action: string;
}

/** Full response from a one-shot graph execution (POST /graph/run).
 *
 * @example
 * { run_id: "a1b2c3", langfuse_trace_id: "trace_abc", query: "What is leave policy?",
 *   final_response: "The leave policy allows 15 days...", compliance_veto: false,
 *   total_cost_usd: 0.0023, trace_events: [], anomaly_results: [] }
 */
export interface GraphRunResponse {
  run_id: string;
  langfuse_trace_id: string;
  query: string;
  final_response: string;
  compliance_veto: boolean;
  compliance_reason: string;
  retrieved_policies: string[];
  executed_actions: string[];
  total_cost_usd: number;
  trace_events: TraceEvent[];
  anomaly_results: AnomalyResult[];
}

/** A single message within a multi-turn conversation session.
 *
 * @example
 * { role: "user", content: "What is the leave policy?" }
 * { role: "assistant", content: "The leave policy allows 15 days...", node: "policy" }
 */
export interface ConversationMessage {
  role: "user" | "assistant" | "system";
  content: string;
  node?: string;
  cost?: number;
  liveEvents?: TraceEvent[];
}

/** A multi-turn conversation session with message history and metadata.
 *
 * @example
 * // After start/send (no full history returned):
 * { session_id: "sess_abc123", response: "The leave policy...", turn_number: 1, mode: "advanced",
 *   total_cost_usd: 0.0023, trace_events: [] }
 * // Full session from GET /conversation/{id}:
 * { session_id: "sess_abc123", messages: [{ role: "user", content: "..." }],
 *   turn_number: 3, mode: "advanced", total_cost: 0.0062,
 *   created_at: "2026-06-13T00:00:00", updated_at: "2026-06-13T00:05:00" }
 */
export interface ConversationSession {
  session_id: string;
  messages?: ConversationMessage[];
  turn_number: number;
  mode?: "standard" | "advanced";
  total_cost?: number;
  total_cost_usd?: number;
  response?: string;
  trace_events?: unknown[];
  created_at?: string;
  updated_at?: string;
  message_count?: number;
}

/** Application role used for UI gating.
 *
 * @example "admin"
 * @example "user"
 */
export type AppRole = "admin" | "hr" | "employee";

/** A single feedback rating entry recorded in the RL feedback buffer.
 *
 * @example
 * { id: "fb_abc123", session_id: "sess_abc", action: "policy", reward: 1.0,
 *   source: "explicit", timestamp: "2026-06-13T00:00:00" }
 */
export interface FeedbackEntry {
  id: string;
  session_id: string;
  action: string;
  reward: number;
  source: "explicit" | "hitl" | "compliance" | "auto";
  timestamp: string;
}

/** A policy document stored as a file on the backend.
 *
 * @example
 * { id: "leave_policy.md", filename: "leave_policy.md", title: "Leave Policy",
 *   content: "# Leave Policy\n\nEmployees are entitled...", content_type: "text/markdown",
 *   file_size: 2048, updated_at: "2026-06-12T10:00:00" }
 */
export interface PolicyDocument {
  id: string;
  filename: string;
  title: string;
  content: string;
  content_type: string;
  file_size: number;
  updated_at: string;
}

/** A pending HITL (human-in-the-loop) escalation from the agent system.
 *
 * @example
 * { interaction_id: "int_abc", query: "Anomaly detected: salary outlier for EMP0012",
 *   created_at: "2026-06-13T00:00:00", status: "pending", assigned_role: "hr_manager" }
 */
export interface PendingItem {
  interaction_id: string;
  query: string;
  created_at: string;
  status: string;
  assigned_role?: string;
  session_id?: string;
}

/** Standard API response envelope wrapping all backend responses.
 *
 * @example
 * { success: true, data: { status: "ok" }, message: "OK", correlation_id: "abc123" }
 */
export interface APIResponse<T = unknown> {
  success: boolean;
  data: T;
  message: string;
  correlation_id: string;
}
