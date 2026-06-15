"""FastAPI middleware for per-endpoint request latency histograms (p50/p95/p99)."""

import logging
import math
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("hr_ops.metrics")


class MetricsStore:
    """Thread-safe in-memory store for endpoint latency histograms."""

    def __init__(self):
        self._lock = __import__("threading").Lock()
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._counts: dict[str, int] = defaultdict(int)
        self._error_counts: dict[str, int] = defaultdict(int)
        self._max_samples = 10_000

    def record(self, method: str, path: str, status_code: int, duration_ms: float):
        key = f"{method} {path}"
        with self._lock:
            samples = self._latencies[key]
            samples.append(duration_ms)
            if len(samples) > self._max_samples:
                samples.pop(0)
            self._counts[key] += 1
            if status_code >= 500:
                self._error_counts[key] += 1

    def _percentile(self, sorted_data: list[float], p: float) -> float:
        if not sorted_data:
            return 0.0
        k = (p / 100.0) * (len(sorted_data) - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_data[int(k)]
        d0 = sorted_data[int(f)] * (c - k)
        d1 = sorted_data[int(c)] * (k - f)
        return d0 + d1

    def snapshot(self) -> dict:
        with self._lock:
            result = {}
            for key in list(self._latencies.keys()):
                samples = sorted(self._latencies[key])
                result[key] = {
                    "count": self._counts.get(key, 0),
                    "errors": self._error_counts.get(key, 0),
                    "error_rate_pct": round(
                        (self._error_counts.get(key, 0) / max(self._counts.get(key, 0), 1)) * 100, 2
                    ),
                    "p50_ms": round(self._percentile(samples, 50), 2),
                    "p95_ms": round(self._percentile(samples, 95), 2),
                    "p99_ms": round(self._percentile(samples, 99), 2),
                    "min_ms": round(samples[0], 2) if samples else 0.0,
                    "max_ms": round(samples[-1], 2) if samples else 0.0,
                    "avg_ms": round(sum(samples) / len(samples), 2) if samples else 0.0,
                }
            return result

    @property
    def total_requests(self) -> int:
        return sum(self._counts.values())

    @property
    def total_errors(self) -> int:
        return sum(self._error_counts.values())


metrics_store = MetricsStore()


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records per-endpoint latency and error metrics."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics_store.record(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=elapsed_ms,
        )
        return response
