import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";

interface PendingItem {
  interaction_id: string;
  query: string;
}

export function useAGUI(pollIntervalMs = 5000) {
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchPending = useCallback(async () => {
    try {
      const data = await api.agui.pending();
      setPending(data.pending);
    } catch {
      // silent on poll errors
    }
  }, []);

  useEffect(() => {
    fetchPending();
    const interval = setInterval(fetchPending, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetchPending, pollIntervalMs]);

  const resolve = useCallback(
    async (interactionId: string, response: string) => {
      setLoading(true);
      try {
        await api.agui.respond(interactionId, response);
        setPending((prev) =>
          prev.filter((p) => p.interaction_id !== interactionId)
        );
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { pending, loading, resolve, refresh: fetchPending };
}
