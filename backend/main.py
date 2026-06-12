import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import settings
from backend.src.utils.api_logger import RequestLog

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


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/")
def root():
    return {"message": "Self-Healing HR Ops Platform", "version": "1.0.0"}


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
