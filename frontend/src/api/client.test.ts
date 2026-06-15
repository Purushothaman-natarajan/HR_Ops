import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, getApiMetrics, clearApiMetrics } from './client';

describe('API Metrics', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    clearApiMetrics();
    // Mock fetch to simulate successful responses
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok', environment: 'test', role: 'admin' }),
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('should initially have no metrics', () => {
    expect(getApiMetrics()).toEqual([]);
  });

  it('should record a metric on a successful API call', async () => {
    await api.health();

    const metrics = getApiMetrics();
    expect(metrics).toHaveLength(1);
    expect(metrics[0]).toMatchObject({
      path: '/health',
      method: 'GET',
      status: 200,
    });
    expect(typeof metrics[0].duration_ms).toBe('number');
    expect(typeof metrics[0].timestamp).toBe('number');
  });

  it('should clear metrics when clearApiMetrics is called', async () => {
    await api.health();
    expect(getApiMetrics()).toHaveLength(1);

    clearApiMetrics();
    expect(getApiMetrics()).toHaveLength(0);
  });

  it('should record multiple metrics', async () => {
    await api.health();
    await api.health();
    await api.health();

    expect(getApiMetrics()).toHaveLength(3);
  });

  it('should enforce MAX_METRICS limit (500)', async () => {
    // Generate 505 calls
    const calls = Array(505).fill(0).map(() => api.health());
    await Promise.all(calls);

    const metrics = getApiMetrics();
    expect(metrics).toHaveLength(500); // Should be capped at 500
  });

  it('should record a metric on a failed API call (HTTP Error)', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({ message: 'Failed' }),
    });

    try {
      await api.health();
    } catch (e) {
      // Expected to throw
    }

    const metrics = getApiMetrics();
    expect(metrics).toHaveLength(1);
    expect(metrics[0]).toMatchObject({
      path: '/health',
      method: 'GET',
      status: 500,
    });
  });

  it('should record a metric on network error (fetch rejects)', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    try {
      await api.health();
    } catch (e) {
      // Expected to throw
    }

    const metrics = getApiMetrics();
    expect(metrics).toHaveLength(1);
    expect(metrics[0]).toMatchObject({
      path: '/health',
      method: 'GET',
      status: 0, // status should be 0 on network error
    });
  });
});
