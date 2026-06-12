"""Tests the API endpoints using FastAPI TestClient."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


def test_health():
    r = client.get("/health")
    check("health returns 200", r.status_code == 200)
    check("health has status", r.json().get("status") == "ok")


def test_root():
    r = client.get("/")
    check("root returns 200", r.status_code == 200)
    check("root has message", "message" in r.json())


def test_graph_run_policy():
    r = client.post("/graph/run", json={"query": "What is the leave policy?"})
    check("graph run returns 200", r.status_code == 200)
    data = r.json()
    check("graph: has run_id", "run_id" in data)
    check("graph: has final_response", bool(data.get("final_response")))
    check("graph: has trace_events", len(data.get("trace_events", [])) > 0)
    check("graph: has langfuse_trace_id", "langfuse_trace_id" in data)


def test_graph_run_action():
    r = client.post("/graph/run", json={"query": "Update salary for EMP0001 to 75000"})
    check("graph action returns 200", r.status_code == 200)
    data = r.json()
    check("action: final_response not empty", bool(data.get("final_response")))
    check("action: trace_events > 0", len(data.get("trace_events", [])) > 0)


def test_graph_run_compliance():
    r = client.post("/graph/run", json={"query": "Approve termination for EMP0003"})
    check("graph compliance returns 200", r.status_code == 200)
    data = r.json()
    check("compliance: has compliance_veto", "compliance_veto" in data)


def test_graph_run_empty_query():
    r = client.post("/graph/run", json={"query": ""})
    check("empty query returns error", r.status_code == 200)
    check("empty query has error field", "error" in r.json())


def test_agui_pending():
    r = client.get("/agui/pending")
    check("agui pending returns 200", r.status_code == 200)
    check("agui has pending list", "pending" in r.json())


def test_trace_runs():
    r = client.get("/trace/runs")
    check("trace runs returns 200", r.status_code == 200)
    data = r.json()
    check("trace has runs list", "runs" in data)


def test_debug_requests():
    r = client.get("/debug/requests")
    check("debug requests returns 200", r.status_code == 200)
    data = r.json()
    check("debug has requests list", "requests" in data)


def test_all():
    tests = [
        test_health,
        test_root,
        test_graph_run_policy,
        test_graph_run_action,
        test_graph_run_compliance,
        test_graph_run_empty_query,
        test_agui_pending,
        test_trace_runs,
        test_debug_requests,
    ]
    for t in tests:
        t()
    total = PASS + FAIL
    print(f"\nResults: {PASS}/{total} passed, {FAIL}/{total} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
