from fastapi import APIRouter

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/requests")
def list_requests(limit: int = 50):
    return {"requests": [], "count": 0, "message": "Request log query endpoint"}


@router.post("/replay/{request_id}")
def replay_request(request_id: str):
    return {"request_id": request_id, "replayed": True, "message": "Replay a previous request through the graph"}
