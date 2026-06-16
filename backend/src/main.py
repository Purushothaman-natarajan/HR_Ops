from __future__ import annotations

"""FastAPI application entry point for the HR Ops Platform.

Sets up the ASGI app with CORS, request logging middleware, exception
handlers for HR-specific and generic errors, and includes all API routers.
"""

import asyncio
import os
import warnings

warnings.filterwarnings("ignore", message="The default value of `allowed_objects`")

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from backend.src.core.settings import settings
from backend.src.api.agui_routes import router as agui_router
from backend.src.api.alert_routes import router as alert_router
from backend.src.api.auth_routes import router as auth_router
from backend.src.api.conversation_routes import router as conversation_router
from backend.src.api.database_routes import router as database_router
from backend.src.api.debug_routes import router as debug_router
from backend.src.api.feedback_routes import router as feedback_router
from backend.src.api.graph_routes import router as graph_router
from backend.src.api.integration_routes import router as integration_router
from backend.src.api.policy_routes import router as policy_router
from backend.src.api.trace_routes import router as trace_router
from backend.src.api.vector_routes import router as vector_router
from backend.src.api.webhook_routes import router as webhook_router
from backend.src.core.exceptions import HROpsBaseError
from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)
from backend.src.middleware.metrics_middleware import RequestMetricsMiddleware, metrics_store
from backend.src.core.api_logger import RequestLog
from backend.src.utils.docs_page import get_redoc_html
from backend.src.core.logger import get_logger
from backend.src.utils.model_router import close_nvidia_http_client
from backend.src.services import policy_service
from backend.src.services.scheduler import scheduler
from backend.src.services.db_schema_store import (
    get_schema_prompt as _warmup_schema,
    warmup_schema_understanding as _warmup_schema_understanding,
)

logger = get_logger("hr_ops")


# Configure detailed logging for backend flow
import logging
for name in [
    "hr_ops.api", "hr_ops.conversation_routes", "hr_ops.graph",
    "hr_ops.model_router", "hr_ops.nodes.policy", "hr_ops.nodes.action",
    "hr_ops.nodes.anomaly", "hr_ops.nodes.compliance", "hr_ops.supervisor",
    "hr_ops.standard_orchestrator", "hr_ops.conversation_service",
    "hr_ops.guardrails", "hr_ops.tools"
]:
    l = logging.getLogger(name)
    l.setLevel(logging.DEBUG)


def _warmup_embeddings():
    """Pre-warm the NVIDIA embedding model on startup to avoid cold-start latency on first request.

    This helper is synchronous by design and is executed in a thread from the async lifespan
    to avoid blocking or conflicting with the ASGI event loop.
    """
    try:
        # Skip warmup if no NVIDIA API key configured — avoids blocking startup
        if not settings.nvidia_api_key:
            logger.info("NVIDIA API key not configured, skipping embedding warmup")
            return

        from backend.src.infrastructure.nvidia_embeddings import NVIDIAEmbeddings
        cfg = settings.embed_config.get("embedding", {})
        model_name = cfg.get("model_name", "nvidia/nv-embed-v1")
        logger.info("Warming up NVIDIA embedding model: %s", model_name)
        embedder = NVIDIAEmbeddings(model=model_name)
        # run a quick synchronous warmup call
        embedder.embed_query("warmup")
        logger.info("NVIDIA embedding model warmup complete: %s", model_name)
    except Exception as e:
        logger.warning("NVIDIA embedding warmup failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: warmup models on startup, clean up clients on shutdown."""
    logger.info("Starting HR Ops Platform")
    # Schedule long-running startup tasks (warmup, migration) in background
    # threads so the application can become responsive quickly.
    loop = asyncio.get_running_loop()
    loop.create_task(asyncio.to_thread(_warmup_embeddings))
    loop.create_task(asyncio.to_thread(_warmup_schema))  # cache DB schema for Text-to-SQL
    loop.create_task(_warmup_schema_understanding())     # generate LLM schema understanding
    if settings.startup_reindex:
        loop.create_task(policy_service._migrate_if_needed())
    else:
        logger.info("Skipping policy reindex on startup (STARTUP_REINDEX=false)")

    # Auto-start the anomaly scanner (runs every hour by default).
    # The scheduler task needs the running event loop, so it must start here.
    scheduler.start()
    logger.info(
        "Anomaly scheduler started (interval=%ds)", scheduler.interval_seconds
    )

    logger.info("HR Ops Platform started successfully")
    yield

    # Graceful shutdown
    scheduler.stop()
    logger.info("Anomaly scheduler stopped")
    await close_nvidia_http_client()
    logger.info("Shutdown complete")


app = FastAPI(
    title="HR Ops Platform",
    version="1.0.0",
    redoc_url=None,
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLog, log_level=settings.log_level)
app.add_middleware(RequestMetricsMiddleware)

app.include_router(graph_router)
app.include_router(agui_router)
app.include_router(alert_router)
app.include_router(trace_router)
app.include_router(debug_router)
app.include_router(policy_router)
app.include_router(conversation_router)
app.include_router(feedback_router)
app.include_router(vector_router)
app.include_router(database_router)
app.include_router(auth_router)
app.include_router(integration_router)
app.include_router(webhook_router)


@app.exception_handler(HROpsBaseError)
async def hr_ops_exception_handler(request: Request, exc: HROpsBaseError):
    """Handle HR Ops domain exceptions with structured JSON error responses."""
    correlation_id = get_correlation_id(request)
    logger.warning(
        "HROpsError: %s | detail=%s | correlation_id=%s",
        exc.message,
        exc.detail,
        correlation_id,
    )
    return error_response(
        message=exc.message,
        correlation_id=correlation_id,
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled exceptions; returns 500 with correlation ID."""
    correlation_id = get_correlation_id(request)
    logger.exception(
        "Unhandled exception: %s | correlation_id=%s", exc, correlation_id
    )
    return error_response(
        message="Internal server error",
        correlation_id=correlation_id,
        status_code=500,
    )


@app.get("/health")
def health():
    """Health-check endpoint returning app status, environment, and role.

    ---
    Request:
        GET /health

    Response 200:
        {
          "success": true,
          "data": {
            "status": "ok",
            "environment": "development",
            "role": "admin"
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    role = os.environ.get("APP_ROLE") or settings.roles_config.get("app_role", "admin")
    return success_response(
        data={"status": "ok", "environment": settings.environment, "role": role}
    )


@app.get("/")
def root():
    """Root endpoint returning the platform name and version.

    ---
    Request:
        GET /

    Response 200:
        {
          "success": true,
          "data": {
            "message": "Self-Healing HR Ops Platform",
            "version": "1.0.0"
          },
          "message": "OK",
          "correlation_id": "abc123"
        }
    """
    return success_response(
        data={"message": "Self-Healing HR Ops Platform", "version": "1.0.0"}
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_custom():
    """Self-hosted API documentation page (offline-friendly, no CDN dependency)."""
    return HTMLResponse(content=get_redoc_html())





if __name__ == "__main__":
    uvicorn.run(
        "backend.src.main:app", host="0.0.0.0", port=8000, reload=True, log_config=None
    )
