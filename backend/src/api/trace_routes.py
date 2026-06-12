from fastapi import APIRouter, HTTPException

from backend.src.utils.trace_store import trace_store

router = APIRouter(prefix="/trace", tags=["trace"])


@router.get("/runs")
def list_runs(limit: int = 50):
    runs = trace_store.list_runs(limit)
    return {"runs": runs, "count": len(runs)}


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    run = trace_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/compare")
def compare_runs(run_ids: str):
    ids = [rid.strip() for rid in run_ids.split(",") if rid.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 run_ids")
    runs = trace_store.compare(ids)
    return {"run_ids": ids, "runs": runs, "compared": len(runs)}
