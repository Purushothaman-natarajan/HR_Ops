import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import settings
from backend.src.utils.api_logger import RequestLog
from backend.src.api.graph_routes import router as graph_router
from backend.src.api.agui_routes import router as agui_router
from backend.src.api.trace_routes import router as trace_router
from backend.src.api.debug_routes import router as debug_router

logger = logging.getLogger("hr_ops")

app = FastAPI(title="HR Ops Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLog, log_level=settings.log_level)

app.include_router(graph_router)
app.include_router(agui_router)
app.include_router(trace_router)
app.include_router(debug_router)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/")
def root():
    return {"message": "Self-Healing HR Ops Platform", "version": "1.0.0"}


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
