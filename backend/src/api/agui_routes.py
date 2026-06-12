from fastapi import APIRouter, HTTPException

from backend.src.utils.agui_models import InteractionResponse
from backend.src.utils.agui_store import agui_store

router = APIRouter(prefix="/agui", tags=["agui"])


@router.get("/pending")
def get_pending():
    return {"pending": agui_store.get_pending()}


@router.post("/respond/{interaction_id}")
def respond(interaction_id: str, resp: InteractionResponse):
    success = agui_store.respond(interaction_id, resp.response, resp.metadata)
    if not success:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return {"status": "resolved", "interaction_id": interaction_id}


@router.get("/response/{interaction_id}")
def get_response(interaction_id: str):
    resp = agui_store.get_response(interaction_id)
    if not resp:
        raise HTTPException(status_code=404, detail="Response not found")
    return resp


@router.get("/status/{interaction_id}")
def get_status(interaction_id: str):
    expired = agui_store.is_expired(interaction_id)
    return {"interaction_id": interaction_id, "expired": expired, "pending_count": agui_store.pending_count}
