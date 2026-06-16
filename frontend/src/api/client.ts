import type { APIResponse, GraphRunResponse, PendingItem, PolicyDocument, ConversationSession, FeedbackEntry, TraceRunSummary, TraceRunDetail } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "";

interface APIMetric {
  path: string;
  method: string;
  duration_ms: number;
  status: number;
  timestamp: number;
}

const apiMetrics: APIMetric[] = [];
const MAX_METRICS = 500;

function recordMetric(path: string, method: string, duration_ms: number, status: number) {
  apiMetrics.push({ path, method, duration_ms, status, timestamp: Date.now() });
  if (apiMetrics.length > MAX_METRICS) apiMetrics.shift();
}

export function getApiMetrics(): APIMetric[] {
  return [...apiMetrics];
}

export function clearApiMetrics() {
  apiMetrics.length = 0;
}

function getAuthToken(): string | null {
  try {
    const raw = localStorage.getItem("hr_ops_auth");
    if (raw) {
      const parsed = JSON.parse(raw);
      return parsed.token ?? null;
    }
  } catch { /* ignore */ }
  return null;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  const isFormData = options?.body instanceof FormData;
  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const start = performance.now();
  let status = 0;
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { ...headers, ...(options?.headers as Record<string, string> | undefined) },
      ...options,
    });
    status = res.status;
    const duration = performance.now() - start;
    recordMetric(path, options?.method || "GET", duration, status);
    if (!res.ok) {
      let msg = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const body = await res.json();
        if (body?.message) msg = body.message;
      } catch { /* ignore parse failures */ }
      throw new Error(msg);
    }
    return res.json();
  } catch (err) {
    const duration = performance.now() - start;
    if (!status) recordMetric(path, options?.method || "GET", duration, 0);
    throw err;
  }
}

export const api = {
  auth: {
    /** Login with role and password. Returns JWT token.
     *
     * @example
     * const res = await api.auth.login("admin", "admin");
     * // res.data.token
     */
    login: (role: string, password: string, employee_id = "") =>
      request<APIResponse<{ token: string; role: string; employee_id: string }>>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ role, password, employee_id }),
      }),
  },

  /** Fetch backend health status.
   *
   * @example
   * const res = await api.health();
   * // res.data.status === "ok"
   * // res.data.role === "admin"
   */
  health: () => request<APIResponse<{ status: string; environment: string; role: string }>>("/health"),

  agui: {
    /** List pending HITL interactions waiting for human response.
     *
     * @example
     * const res = await api.agui.pending();
     * // res.data.pending[0].interaction_id
     */
    pending: () =>
      request<APIResponse<{ pending: Array<{ interaction_id: string; query: string }> }>>("/agui/pending"),

    /** Submit a human response to a HITL interaction.
     *
     * @example
     * const res = await api.agui.respond("int_abc123", "Approved");
     * // res.data.status === "resolved"
     */
    respond: (id: string, response: string) =>
      request<APIResponse<{ status: string; interaction_id: string }>>(`/agui/respond/${id}`, {
        method: "POST",
        body: JSON.stringify({ interaction_id: id, response }),
      }),

    /** Check whether a HITL interaction has expired.
     *
     * @example
     * const res = await api.agui.status("int_abc123");
     * // res.data.expired === false
     */
    status: (id: string) =>
      request<APIResponse<{ interaction_id: string; expired: boolean }>>(`/agui/status/${id}`),
  },

  trace: {
    /** List recent graph execution runs.
     *
     * @example
     * const res = await api.trace.runs();
     * // res.data.runs[0].run_id
     */
    runs: () => request<APIResponse<{ runs: TraceRunSummary[] }>>("/trace/runs"),

    /** Get full detail for a single trace run by ID.
     *
     * @example
     * const res = await api.trace.get("run_abc123");
     * // res.data.run_id
     */
    get: (id: string) => request<APIResponse<TraceRunDetail>>(`/trace/runs/${id}`),

    /** Compare two or more trace runs side-by-side.
     *
     * @example
     * const res = await api.trace.compare(["run_a", "run_b"]);
     * // res.data[0].run_id
     */
    compare: (ids: string[]) =>
      request<APIResponse<unknown[]>>(`/trace/compare?run_ids=${ids.join(",")}`),
  },

  graph: {
    /** Execute the full LangGraph pipeline with a single query.
     *
     * @example
     * const res = await api.graph.run("What is the leave policy?");
     * // res.data.final_response
     * // res.data.trace_events.length
     */
    run: (query: string) =>
      request<APIResponse<GraphRunResponse>>("/graph/run", {
        method: "POST",
        body: JSON.stringify({ query }),
      }),
  },

  conversation: {
    /** Create a new conversation session and run the first turn.
     *
     * @example
     * const res = await api.conversation.start("What is leave policy?", "advanced");
     * // res.data.session_id
     * // res.data.response
     */
    start: (query: string, mode: string = "standard", employee_id?: string) =>
      request<APIResponse<ConversationSession>>("/conversation/start", {
        method: "POST",
        body: JSON.stringify({ query, mode, employee_id }),
      }),

    /** SSE streaming URL to start a new session and stream node events.
     *
     * @example
     * const es = new EventSource(api.conversation.streamStartUrl("What is leave policy?", "advanced"));
     * // es.addEventListener("node_complete", ...)
     * // es.addEventListener("complete", ...)
     */
    streamStartUrl: (query: string, mode: string = "standard") =>
      `${BASE_URL}/conversation/stream/start?query=${encodeURIComponent(query)}&mode=${encodeURIComponent(mode)}`,

    /** SSE streaming URL to send a follow-up message and stream node events.
     *
     * @example
     * const es = new EventSource(api.conversation.streamSendUrl("sess_abc123", "What about sick leave?"));
     */
    streamSendUrl: (sessionId: string, query: string) =>
      `${BASE_URL}/conversation/${encodeURIComponent(sessionId)}/stream/send?query=${encodeURIComponent(query)}`,

    /** Send a follow-up message within an existing session.
     *
     * @example
     * const res = await api.conversation.send("sess_abc123", "What about sick leave?");
     * // res.data.turn_number === 2
     */
    send: (sessionId: string, query: string, employee_id?: string) =>
      request<APIResponse<ConversationSession>>(`/conversation/${sessionId}/send`, {
        method: "POST",
        body: JSON.stringify({ query, employee_id }),
      }),

    /** Retrieve a session's full message history.
     *
     * @example
     * const res = await api.conversation.get("sess_abc123");
     * // res.data.messages.length
     */
    get: (sessionId: string) =>
      request<APIResponse<ConversationSession>>(`/conversation/${sessionId}`),

    /** Delete a session and its entire message history.
     *
     * @example
     * await api.conversation.delete("sess_abc123");
     */
    delete: (sessionId: string) =>
      request<APIResponse<{ id: string }>>(`/conversation/${sessionId}`, { method: "DELETE" }),

    /** List recent conversation sessions with summary metadata.
     *
     * @example
     * const res = await api.conversation.list();
     * // res.data.sessions[0].message_count === 4
     */
    list: () =>
      request<APIResponse<{ sessions: ConversationSession[] }>>("/conversation"),
  },

  feedback: {
    /** Submit explicit user feedback with a thumbs-up (1) or thumbs-down (-1) rating.
     *
     * @example
     * const res = await api.feedback.submit("sess_abc123", "policy", 1);
     * // res.data.buffer_size
     */
    submit: (sessionId: string, action: string, rating: number, context?: Record<string, unknown>) =>
      request<APIResponse<{ recorded: string; buffer_size: number; rl_batch_size: number }>>("/feedback", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, action, rating, context }),
      }),

    /** List recent feedback entries, newest first.
     *
     * @example
     * const res = await api.feedback.list(10);
     * // res.data.feedback[0].reward
     */
    list: (limit = 50) =>
      request<APIResponse<{ feedback: FeedbackEntry[] }>>(`/feedback?limit=${limit}`),

    /** Get per-arm reward statistics and RL configuration.
     *
     * @example
     * const res = await api.feedback.stats();
     * // res.data.per_arm[0].avg_reward
     */
    stats: () =>
      request<APIResponse<{
        per_arm: { arm: string; total_reward: number; count: number; avg_reward: number; source: string }[];
        buffer_size: number;
        total_feedbacks: number;
        rl_batch_size: number;
      }>>("/feedback/stats"),
  },

  rl: {
    /** Inspect the internal LinUCB bandit agent state.
     *
     * @example
     * const res = await api.rl.state();
     * // res.data.arms.policy.pulls
     */
    state: () =>
      request<APIResponse<{
        arms: Record<string, { theta: number[]; pulls: number; reward: number }>;
        config: { batch_size: number; alpha: number; gamma: number };
        pending_feedbacks: number;
      }>>("/feedback/rl/state"),
  },

  policies: {
    /** List all policy files with their metadata.
     *
     * @example
     * const res = await api.policies.list();
     * // res.data.policies[0].title
     */
    list: () => request<APIResponse<{ policies: PolicyDocument[]; embedded_count?: number }>>("/policies"),

    /** Retrieve a single policy's metadata and full text content.
     *
     * @example
     * const res = await api.policies.get("leave_policy.md");
     * // res.data.content
     */
    get: (id: string) => request<APIResponse<PolicyDocument>>(`/policies/${id}`),

    /** Upload a new policy file (admin only). Accepts .pdf, .md, .txt.
     *
     * @example
     * const file = new File(["..."], "policy.md", { type: "text/markdown" });
     * const res = await api.policies.upload(file, "My Policy");
     */
    upload: (file: File, title?: string) => {
      const fd = new FormData();
      fd.append("file", file);
      if (title) fd.append("title", title);
      return request<APIResponse<PolicyDocument>>("/policies/upload", { method: "POST", body: fd });
    },

    /** Update a policy's title (admin only).
     *
     * @example
     * const res = await api.policies.update("leave_policy.md", { title: "Updated Title" });
     */
    update: (id: string, data: Partial<Pick<PolicyDocument, "title">>) =>
      request<APIResponse<PolicyDocument>>(`/policies/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),

    /** Delete a policy file (admin only).
     *
     * @example
     * await api.policies.delete("leave_policy.md");
     */
    delete: (id: string) =>
      request<APIResponse<{ id: string }>>(`/policies/${id}`, { method: "DELETE" }),

    /** Get the download URL for a policy file.
     *
     * @example
     * const url = api.policies.downloadUrl("leave_policy.md");
     * // url === "/policies/leave_policy.md/download"
     */
    downloadUrl: (id: string) => `${BASE_URL}/policies/${id}/download`,
  },

  hitl: {
    /** List pending HITL escalation requests.
     *
     * @example
     * const res = await api.hitl.list();
     * // res.data.pending[0].interaction_id
     */
    list: () => request<APIResponse<{ pending: PendingItem[] }>>("/agui/pending"),

    /** Approve or reject a HITL escalation request.
     *
     * @example
     * await api.hitl.respond("req_abc123", "approve", "Looks correct");
     */
    respond: (id: string, action: string, response_text: string) =>
      request<APIResponse<{ status: string }>>(`/agui/respond/${id}`, {
        method: "POST",
        body: JSON.stringify({ interaction_id: id, response: response_text, metadata: { action } }),
      }),
  },

  vectorStore: {
    /** Return vector store collection info, document count, and embedding model.
     *
     * @example
     * const res = await api.vectorStore.status();
     * // res.data.document_count === 12
     */
    status: () =>
      request<APIResponse<{
        available: boolean;
        collection: string;
        document_count: number;
        chunk_count: number;
        embedding_model: string;
        dimension: number;
        persist_dir: string;
        error?: string;
      }>>("/vector-store/status"),
  },

  database: {
    /** Return SQLite database connection status and table counts.
     *
     * @example
     * const res = await api.database.status();
     * // res.data.connected === true
     * // res.data.employees_count === 30000
     */
    status: () =>
      request<APIResponse<{
        connected: boolean;
        database_url?: string;
        employees_count: number;
        attendance_count: number;
        payroll_count: number;
        leaves_count: number;
        performance_count: number;
        error?: string;
      }>>("/database/status"),

    /** Upload a CSV or SQLite DB file to replace/enhance the active database.
     *
     * @example
     * const file = new File(["..."], "employees.csv");
     * const res = await api.database.upload(file);
     */
    upload: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return request<APIResponse<{
        filename: string;
        message: string;
        status: {
          connected: boolean;
          database_url?: string;
          employees_count: number;
          attendance_count: number;
          payroll_count: number;
          leaves_count: number;
          performance_count: number;
        };
      }>>("/database/upload", { method: "POST", body: fd });
    },
  },

  integrations: {
    get: () =>
      request<APIResponse<{
        database: { type: string; connection_string: string; connected: boolean };
        chat_hook: { enabled: boolean; webhook_url: string; events: string[] };
      }>>("/integrations"),
    update: (data: {
      database: { type: string; connection_string: string; connected?: boolean };
      chat_hook: { enabled: boolean; webhook_url: string; events: string[] };
    }) =>
      request<APIResponse<{
        database: { type: string; connection_string: string; connected: boolean };
        chat_hook: { enabled: boolean; webhook_url: string; events: string[] };
      }>>("/integrations", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  alerts: {
    getScheduler: () =>
      request<APIResponse<{ interval_seconds: number; running: boolean }>>("/alerts/scheduler"),
    updateScheduler: (interval_seconds: number, running?: boolean) =>
      request<APIResponse<{ interval_seconds: number; running: boolean }>>("/alerts/scheduler", {
        method: "POST",
        body: JSON.stringify({ interval_seconds, running }),
      }),
  },

  debug: {
    /** List recent API request entries stored for debugging.
     *
     * @example
     * const res = await api.debug.requests(10);
     */
    requests: (limit = 50) =>
      request<APIResponse<{ requests: unknown[] }>>(`/debug/requests?limit=${limit}`),

    /** Re-play a previous request through the graph for debugging.
     *
     * @example
     * const res = await api.debug.replay("req_abc123");
     * // res.data.replayed === true
     */
    replay: (id: string) =>
      request<APIResponse<{ request_id: string; query: string; replayed: boolean; result: unknown }>>(`/debug/replay/${id}`, { method: "POST" }),
  },
};
