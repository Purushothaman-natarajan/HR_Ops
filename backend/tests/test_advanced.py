"""Advanced test suite — validates RL, graph topology, anomaly detection, AG-UI."""

from datetime import datetime, timezone

from backend.src.agents.state import (
    AnomalyResult,
    SharedState,
    TraceEntry,
)
from backend.src.graph import build_full_graph
from backend.src.intelligence.anomaly import run_anomaly_detection
from backend.src.intelligence.rl_layer import rl_agent
from backend.src.utils.agui_models import InteractionRequest
from backend.src.utils.agui_store import agui_store


class TestGraphTopology:
    def test_supervisor_node_exists(self):
        graph = build_full_graph()
        nodes = list(graph.get_graph().nodes)
        assert "supervisor" in nodes

    def test_all_agent_nodes_exist(self):
        graph = build_full_graph()
        nodes = list(graph.get_graph().nodes)
        for node in ("policy", "action", "anomaly", "compliance", "hitl"):
            assert node in nodes

    def test_minimum_nodes(self):
        graph = build_full_graph()
        nodes = list(graph.get_graph().nodes)
        assert len(nodes) >= 6


class TestRLAgent:
    def test_selects_valid_action(self):
        context = {
            "classification": "policy",
            "query": "What is the leave policy?",
        }
        action = rl_agent.select_action(context)
        assert action in ("policy", "action", "anomaly", "compliance")

    def test_update_without_error(self):
        context = {
            "classification": "policy",
            "query": "What is the leave policy?",
        }
        action = rl_agent.select_action(context)
        rl_agent.update(context, action, 1.0)


class TestAnomalyDetection:
    def test_returns_list(self):
        employees = [
            {
                "employee_id": "EMP001",
                "name": "A",
                "salary": 50000,
                "leave_balance": 10,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP002",
                "name": "B",
                "salary": 52000,
                "leave_balance": 12,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP003",
                "name": "C",
                "salary": 51000,
                "leave_balance": 11,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP004",
                "name": "D",
                "salary": 48000,
                "leave_balance": 14,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP005",
                "name": "E",
                "salary": 53000,
                "leave_balance": 9,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP006",
                "name": "F",
                "salary": 200000,
                "leave_balance": 5,
                "compliance_status": "flagged",
            },
        ]
        results = run_anomaly_detection(employees)
        assert isinstance(results, list)

    def test_detects_salary_outlier(self):
        employees = [
            {
                "employee_id": "EMP001",
                "name": "A",
                "salary": 50000,
                "leave_balance": 10,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP002",
                "name": "B",
                "salary": 52000,
                "leave_balance": 12,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP003",
                "name": "C",
                "salary": 51000,
                "leave_balance": 11,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP004",
                "name": "D",
                "salary": 48000,
                "leave_balance": 14,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP005",
                "name": "E",
                "salary": 53000,
                "leave_balance": 9,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP006",
                "name": "F",
                "salary": 200000,
                "leave_balance": 5,
                "compliance_status": "flagged",
            },
        ]
        results = run_anomaly_detection(employees)
        detected = [r for r in results if r.detected]
        assert any("Salary" in r.description for r in detected)

    def test_detects_compliance_flag(self):
        employees = [
            {
                "employee_id": "EMP001",
                "name": "A",
                "salary": 50000,
                "leave_balance": 10,
                "compliance_status": "compliant",
            },
            {
                "employee_id": "EMP006",
                "name": "F",
                "salary": 200000,
                "leave_balance": 5,
                "compliance_status": "flagged",
            },
        ]
        results = run_anomaly_detection(employees)
        detected = [r for r in results if r.detected]
        assert any("flagged" in r.description for r in detected)


class TestAGUIStore:
    def test_request_is_pending(self):
        req = InteractionRequest(
            interaction_id="test-001",
            query="Test escalation query",
            context={"test": True},
        )
        agui_store.add_request(req)
        pending = agui_store.get_pending()
        assert any(r.interaction_id == "test-001" for r in pending)

    def test_response_recorded(self):
        agui_store.add_request(
            InteractionRequest(
                interaction_id="test-002",
                query="Test",
                context={},
            )
        )
        agui_store.respond("test-002", "Approved")
        resp = agui_store.get_response("test-002")
        assert resp is not None
        assert resp.response == "Approved"


class TestStateModel:
    def test_query_set(self):
        state = SharedState(query="Test query")
        assert state.query == "Test query"

    def test_default_role_empty(self):
        state = SharedState(query="Test query")
        assert state.current_agent == ""

    def test_anomaly_appended(self):
        state = SharedState(query="Test")
        anomaly = AnomalyResult(
            detected=True, severity=0.8, description="Test anomaly"
        )
        state.anomaly_results.append(anomaly)
        assert len(state.anomaly_results) == 1

    def test_trace_appended(self):
        state = SharedState(query="Test")
        trace = TraceEntry(
            node="test",
            agent_role="policy",
            input_text="in",
            output_text="out",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            duration_ms=100,
        )
        state.trace_log.append(trace)
        assert len(state.trace_log) == 1
