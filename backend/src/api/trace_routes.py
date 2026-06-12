from fastapi import APIRouter

router = APIRouter(prefix="/trace", tags=["trace"])


@router.get("/runs")
def list_runs():
    return {"runs": [], "message": "Trace query endpoint — returns aggregated trace data"}


@router.get("/runs/{trace_id}")
def get_run(trace_id: str):
    return {"trace_id": trace_id, "events": [], "message": "Detailed trace for a single run"}


@router.get("/compare")
def compare_runs(trace_ids: str):
    ids = trace_ids.split(",")
    return {"trace_ids": ids, "comparison": {}, "message": "Compare two or more traces"}
