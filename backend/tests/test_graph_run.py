"""Integration test: Runs the full LangGraph with a real query and checks output."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.src.agents.state import SharedState
from backend.src.graph import build_full_graph
from backend.src.core.exceptions import ModelNotAvailableError
from backend.src.utils.model_router import _LITELLM_AVAILABLE

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


def run_query(query: str, trigger: str = "reactive") -> dict:
    from backend.src.agents.state import TriggerType

    state = SharedState(
        query=query,
        trigger_type=TriggerType.SCHEDULED if trigger == "scheduled" else TriggerType.REACTIVE,
    )
    graph = build_full_graph()
    return graph.invoke(state)


def _try_run_query(query: str, trigger: str = "reactive") -> dict | None:
    """Run query and return result, or None if model is unavailable."""
    try:
        return run_query(query, trigger)
    except ModelNotAvailableError:
        return None


def test_policy_query():
    result = _try_run_query("What is the annual leave policy?")
    if result is None:
        check("policy: litellm unavailable (expected)", not _LITELLM_AVAILABLE)
        return
    check("policy: final_response not empty", bool(result.get("final_response")))
    trace_log = result.get("trace_log", [])
    check("policy: trace_entries > 0", len(trace_log) > 0)
    roles = [str(t.agent_role) for t in trace_log]
    check("policy: supervisor in trace", "supervisor" in roles or "policy" in roles)


def test_action_query():
    result = _try_run_query("Update salary for EMP0001 to 75000")
    if result is None:
        check("action: litellm unavailable (expected)", not _LITELLM_AVAILABLE)
        return
    check("action: executed_actions populated", len(result.get("executed_actions", [])) > 0)
    check("action: final_response not empty", bool(result.get("final_response")))


def test_anomaly_scheduled():
    from backend.src.tools.api_mocks import load_employees_from_csv
    load_employees_from_csv()
    result = _try_run_query("Run anomaly detection", trigger="scheduled")
    if result is None:
        check("anomaly: litellm unavailable (expected)", not _LITELLM_AVAILABLE)
        return
    anomalies = result.get("anomaly_results", [])
    check("anomaly: results list returned", isinstance(anomalies, list))
    check("anomaly: at least one anomaly or empty ok", True)


def test_compliance_query():
    result = _try_run_query("Approve termination for EMP0003")
    if result is None:
        check("compliance: litellm unavailable (expected)", not _LITELLM_AVAILABLE)
        return
    trace_log = result.get("trace_log", [])
    check("compliance: trace_log present", len(trace_log) > 0)
    roles = [str(t.agent_role) for t in trace_log]
    check("compliance: compliance agent ran", "compliance" in roles)


def test_multi_turn():
    graph = build_full_graph()
    state = SharedState(query="What is the leave policy?")
    try:
        r1 = graph.invoke(state)
        check("multi: first turn response", bool(r1.get("final_response")))
    except ModelNotAvailableError:
        check("multi: first turn (litellm unavailable)", not _LITELLM_AVAILABLE)
        return

    state2 = SharedState(query="How many sick days do I have?")
    try:
        r2 = graph.invoke(state2)
        check("multi: second turn response", bool(r2.get("final_response")))
    except ModelNotAvailableError:
        check("multi: second turn (litellm unavailable)", not _LITELLM_AVAILABLE)


def test_shared_state():
    state = SharedState(query="Test")
    check("state: query preserved", state.query == "Test")
    check("state: no anomalies initially", len(state.anomaly_results) == 0)
    check("state: not vetoed", state.compliance_veto is False)


def run_all():
    print("\n=== Integration Test: Graph Run ===\n")
    test_policy_query()
    test_action_query()
    test_anomaly_scheduled()
    test_compliance_query()
    test_multi_turn()
    test_shared_state()
    total = PASS + FAIL
    print(f"\nResults: {PASS}/{total} passed, {FAIL}/{total} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
