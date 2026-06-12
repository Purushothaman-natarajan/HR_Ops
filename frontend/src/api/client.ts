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

  debug: {
    requests: (limit = 50) =>
      request<{ requests: unknown[] }>(`/debug/requests?limit=${limit}`),
    replay: (id: string) =>
      request(`/debug/replay/${id}`, { method: "POST" }),
  },
};
