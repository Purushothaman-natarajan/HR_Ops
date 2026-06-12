import logging
import time
import uuid
from datetime import datetime
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLog(BaseHTTPMiddleware):
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
        request_id = str(uuid.uuid4())[:12]
        start = time.perf_counter()
        body_bytes = await request.body()
        body = body_bytes.decode("utf-8", errors="replace")[:1024]

        response = await call_next(request)
        elapsed = time.perf_counter() - start

        self.logger.info(
            f"req_id={request_id} "
            f"method={request.method} "
            f"path={request.url.path} "
            f"status={response.status_code} "
            f"elapsed_ms={elapsed*1000:.1f} "
            f"body={body!r}"
        )
        response.headers["X-Request-ID"] = request_id
        return response
