import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { api, getApiMetrics, clearApiMetrics } from './client';

describe('API Metrics Client', () => {
  beforeEach(() => {
    // Clear metrics before each test
    clearApiMetrics();
    // Mock the global fetch
    globalThis.fetch = vi.fn();
    // Mock performance.now to have predictable durations
    vi.spyOn(performance, 'now').mockReturnValueOnce(100).mockReturnValueOnce(250);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should start with empty metrics', () => {
    const metrics = getApiMetrics();
    expect(metrics).toEqual([]);
  });

  it('should record a metric on successful API call', async () => {
    const mockResponse = { status: 'ok' };
    (globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    });

    await api.health();

    const metrics = getApiMetrics();
    expect(metrics).toHaveLength(1);
    expect(metrics[0]).toMatchObject({
      path: '/health',
      method: 'GET',
      duration_ms: 150, // 250 - 100
      status: 200,
    });
    // Timestamp should be close to now
    expect(metrics[0].timestamp).toBeGreaterThan(Date.now() - 1000);
    expect(metrics[0].timestamp).toBeLessThanOrEqual(Date.now());
  });

  it('should record a metric on failed API call (HTTP error)', async () => {
    (globalThis.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({ message: 'Server crashed' }),
    });

    await expect(api.health()).rejects.toThrow('Server crashed');

    const metrics = getApiMetrics();
    expect(metrics).toHaveLength(1);
    expect(metrics[0]).toMatchObject({
      path: '/health',
      method: 'GET',
      duration_ms: 150,
      status: 500,
    });
  });

  it('should record a metric on network error', async () => {
    (globalThis.fetch as any).mockRejectedValueOnce(new Error('Network error'));

    await expect(api.health()).rejects.toThrow('Network error');

    const metrics = getApiMetrics();
    expect(metrics).toHaveLength(1);
    expect(metrics[0]).toMatchObject({
      path: '/health',
      method: 'GET',
      duration_ms: 150,
      status: 0, // 0 for network errors where no response status is received
    });
  });

  it('should enforce MAX_METRICS limit (500)', async () => {
    // Fill up to max
    const MAX_METRICS = 500;

    // We bypass fetch for speed and call the unexported recordMetric indirectly
    // To do that, we mock performance to always return standard values
    // to not clutter the test, and mock fetch to return immediately.
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok' }),
    });

    // Make 501 calls
    const calls = [];
    for (let i = 0; i < MAX_METRICS + 1; i++) {
        calls.push(api.health());
    }
    await Promise.all(calls);

    const metrics = getApiMetrics();
    expect(metrics).toHaveLength(MAX_METRICS);
    // Since we made 501 calls, the first call should be evicted.
    // The length should be exactly 500.
    expect(metrics.length).toBe(MAX_METRICS);
  });

  it('should clear metrics', async () => {
    (globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok' }),
    });

    await api.health();
    expect(getApiMetrics()).toHaveLength(1);

    clearApiMetrics();
    expect(getApiMetrics()).toHaveLength(0);
  });

  it('should handle POST requests correctly in metrics', async () => {
      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ session_id: '123' }),
      });

      await api.conversation.start("hello");

      const metrics = getApiMetrics();
      expect(metrics).toHaveLength(1);
      expect(metrics[0]).toMatchObject({
        path: '/conversation/start',
        method: 'POST',
        status: 201,
      });
  });
});
