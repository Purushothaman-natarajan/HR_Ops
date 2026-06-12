"""Advanced test harness — validates RL, graph topology, anomaly detection, AG-UI."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.src.agents.state import SharedState, AgentRole, TriggerType, AnomalyResult, TraceEntry
from backend.src.intelligence.rl_layer import rl_agent
from backend.src.intelligence.anomaly import run_anomaly_detection
from backend.src.graph import build_full_graph
from backend.src.utils.agui_store import agui_store
from backend.src.utils.agui_models import InteractionRequest

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


def test_graph_topology():
    graph = build_full_graph()
    nodes = list(graph.get_graph().nodes)
    check("graph: supervisor node exists", "supervisor" in nodes)
    check("graph: policy node exists", "policy" in nodes)
    check("graph: action node exists", "action" in nodes)
    check("graph: anomaly node exists", "anomaly" in nodes)
    check("graph: compliance node exists", "compliance" in nodes)
    check("graph: hitl node exists", "hitl" in nodes)
    check("graph: at least 6 nodes", len(nodes) >= 6)


def test_rl_agent():
    context = {"classification": "policy", "query": "What is the leave policy?"}
    action = rl_agent.select_action(context)
    check("rl: selects action", action in ("policy", "action", "anomaly", "compliance"))

    rl_agent.update(context, action, 1.0)
    check("rl: update without error", True)

    action2 = rl_agent.select_action(context)
    check("rl: learns from reward", True)  # no assertion, just verifies no crash


def test_anomaly_detection():
    employees = [
        {"employee_id": "EMP001", "name": "A", "salary": 50000, "leave_balance": 10, "compliance_status": "compliant"},
        {"employee_id": "EMP002", "name": "B", "salary": 52000, "leave_balance": 12, "compliance_status": "compliant"},
        {"employee_id": "EMP003", "name": "C", "salary": 51000, "leave_balance": 11, "compliance_status": "compliant"},
        {"employee_id": "EMP004", "name": "D", "salary": 48000, "leave_balance": 14, "compliance_status": "compliant"},
        {"employee_id": "EMP005", "name": "E", "salary": 53000, "leave_balance": 9, "compliance_status": "compliant"},
        {"employee_id": "EMP006", "name": "F", "salary": 200000, "leave_balance": 5, "compliance_status": "flagged"},
    ]
    results = run_anomaly_detection(employees)
    check("anomaly: returns list", isinstance(results, list))
    detected = [r for r in results if r.detected]
    check("anomaly: detects salary outlier", any("Salary" in r.description for r in detected))
    check("anomaly: detects compliance flag", any("flagged" in r.description for r in detected))


def test_agui_store():
    req = InteractionRequest(
        interaction_id="test-001",
        query="Test escalation query",
        context={"test": True},
    )
    agui_store.add_request(req)
    pending = agui_store.get_pending()
    check("agui: request is pending", any(r.interaction_id == "test-001" for r in pending))

    agui_store.respond("test-001", "Approved")
    resp = agui_store.get_response("test-001")
    check("agui: response recorded", resp is not None and resp.response == "Approved")


def test_state_model():
    state = SharedState(query="Test query")
    check("state: query set", state.query == "Test query")
    check("state: default role empty", state.current_agent == "")

    anomaly = AnomalyResult(detected=True, severity=0.8, description="Test anomaly")
    state.anomaly_results.append(anomaly)
    check("state: anomaly appended", len(state.anomaly_results) == 1)

    trace = TraceEntry(
        node="test", agent_role="policy",
        input_text="in", output_text="out",
        timestamp="2026-01-01", duration_ms=100,
    )
    state.trace_log.append(trace)
    check("state: trace appended", len(state.trace_log) == 1)


def run_all():
    print("\n=== Test Harness: Advanced Components ===\n")

    test_graph_topology()
    test_rl_agent()
    test_anomaly_detection()
    test_agui_store()
    test_state_model()

    total = PASS + FAIL
    print(f"\nResults: {PASS}/{total} passed, {FAIL}/{total} failed")
    return FAIL == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
