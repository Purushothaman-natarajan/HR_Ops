const BASE_URL = "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  agui: {
    pending: () =>
      request<{ pending: Array<{ interaction_id: string; query: string }> }>("/agui/pending"),
    respond: (id: string, response: string) =>
      request(`/agui/respond/${id}`, {
        method: "POST",
        body: JSON.stringify({ interaction_id: id, response }),
      }),
    status: (id: string) =>
      request<{ interaction_id: string; expired: boolean }>(`/agui/status/${id}`),
  },

  trace: {
    runs: () => request<{ runs: unknown[] }>("/trace/runs"),
    get: (id: string) => request(`/trace/runs/${id}`),
    compare: (ids: string[]) =>
      request(`/trace/compare?trace_ids=${ids.join(",")}`),
  },

  graph: {
    run: (query: string) =>
      request<GraphRunResponse>("/graph/run", {
        method: "POST",
        body: JSON.stringify({ query }),
      }),
  },

  debug: {
    requests: (limit = 50) =>
      request<{ requests: unknown[] }>(`/debug/requests?limit=${limit}`),
    replay: (id: string) =>
      request(`/debug/replay/${id}`, { method: "POST" }),
  },
};

export interface TraceEvent {
  node: string;
  agent_role: string;
  input_text: string;
  output_text: string;
  duration_ms: number;
  cost_usd?: number;
  cache_hit?: boolean;
  model_used?: string;
}

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
  anomaly_results: Array<{
    detected: boolean;
    severity: number;
    description: string;
    anomaly_field: string;
    suggested_action: string;
  }>;
}
