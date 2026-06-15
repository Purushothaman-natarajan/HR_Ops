"""FastAPI middleware for logging HTTP request/response metadata with timing and request IDs."""

import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLog(BaseHTTPMiddleware):
    """FastAPI middleware that logs every request's method, path, status, duration, and body snippet."""

    def __init__(self, app, log_level: str = "INFO"):
        super().__init__(app)
        self.logger = logging.getLogger("hr_ops.api")
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        )
        if not self.logger.handlers:
            self.logger.addHandler(handler)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Intercept an incoming request, time its execution, log the result, and attach an X-Request-ID header."""
        request_id = str(uuid.uuid4())[:12]
        start = time.perf_counter()
        content_type = request.headers.get("content-type", "")
        body = ""
        if "multipart/form-data" not in content_type and "application/octet-stream" not in content_type:
            try:
                body_bytes = await request.body()
                body = body_bytes.decode("utf-8", errors="replace")[:1024]
            except Exception:
                body = "<body read error>"

        response = await call_next(request)
        elapsed = time.perf_counter() - start

        self.logger.info(
            "req_id=%s method=%s path=%s status=%s elapsed_ms=%.1f body=%r",
            request_id, request.method, request.url.path, response.status_code, elapsed * 1000, body,
        )
        response.headers["X-Request-ID"] = request_id
        return response
