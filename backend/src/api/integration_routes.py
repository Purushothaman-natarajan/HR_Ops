from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from fastapi import APIRouter, Request

from backend.config.settings import settings
from backend.src.core.response import (
    error_response,
    get_correlation_id,
    success_response,
)

logger = logging.getLogger("hr_ops.integration_routes")
router = APIRouter(prefix="/integrations", tags=["integrations"])

CONFIG_FILE = Path("./backend/data/integrations_config.json")

DEFAULT_CONFIG = {
    "database": {
        "type": "sqlite",
        "connection_string": "sqlite:///./backend/data/hr_ops.db",
        "connected": True
    },
    "chat_hook": {
        "enabled": False,
        "webhook_url": "",
        "events": ["leave_request", "escalation"]
    }
}

def _admin_required(correlation_id: str):
    """Check if the configured app role is 'admin'; return an error response if not."""
    role = os.environ.get("APP_ROLE") or settings.roles_config.get("app_role", "admin")
    if role != "admin":
        return error_response(
            message="Admin access required",
            correlation_id=correlation_id,
            status_code=403,
        )
    return None

def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to load integrations config, returning default")
        return DEFAULT_CONFIG

def _save_config(config: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

@router.get("")
async def api_get_integrations(request: Request):
    """Get active integrations configuration."""
    correlation_id = get_correlation_id(request)
    denied = _admin_required(correlation_id)
    if denied:
        return denied
    config = _load_config()
    return success_response(data=config, correlation_id=correlation_id)

@router.post("")
async def api_update_integrations(body: dict, request: Request):
    """Update integrations configuration."""
    correlation_id = get_correlation_id(request)
    denied = _admin_required(correlation_id)
    if denied:
        return denied
        
    db_config = body.get("database", {})
    chat_config = body.get("chat_hook", {})
    
    # Simple validation
    if "type" not in db_config or "connection_string" not in db_config:
        return error_response(
            message="Database integration requires 'type' and 'connection_string'",
            correlation_id=correlation_id,
            status_code=400
        )
        
    config = {
        "database": {
            "type": db_config.get("type", "sqlite"),
            "connection_string": db_config.get("connection_string", ""),
            "connected": db_config.get("connected", True)
        },
        "chat_hook": {
            "enabled": chat_config.get("enabled", False),
            "webhook_url": chat_config.get("webhook_url", ""),
            "events": chat_config.get("events", ["leave_request", "escalation"])
        }
    }
    
    _save_config(config)
    return success_response(data=config, correlation_id=correlation_id, message="Integrations configuration updated")
