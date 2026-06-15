"""Tests the feedback service and RL feedback endpoints."""

from fastapi.testclient import TestClient
from backend.main import app
from backend.src.services.feedback_service import feedback_store
from backend.src.intelligence.rl_layer import rl_agent

client = TestClient(app)


class TestFeedbackDirect:
    def test_submit_positive(self):
        r = client.post("/feedback", json={
            "session_id": "test_sess", "action": "policy", "rating": 1, "context": {}
        })
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["recorded"]

    def test_submit_negative(self):
        r = client.post("/feedback", json={
            "session_id": "test_sess", "action": "action", "rating": -1, "context": {}
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_submit_missing_action(self):
        r = client.post("/feedback", json={"session_id": "test", "rating": 1})
        assert r.status_code == 400

    def test_submit_invalid_rating(self):
        r = client.post("/feedback", json={"session_id": "test", "action": "policy", "rating": 99})
        assert r.status_code == 400


class TestFeedbackList:
    def test_list_feedback(self):
        r = client.get("/feedback")
        assert r.status_code == 200
        body = r.json()
        assert "feedback" in body["data"]

    def test_feedback_stats(self):
        r = client.get("/feedback/stats")
        assert r.status_code == 200
        body = r.json()
        assert "per_arm" in body["data"]
        assert "buffer_size" in body["data"]
        assert "total_feedbacks" in body["data"]


class TestRlState:
    def test_rl_state(self):
        r = client.get("/feedback/rl/state")
        assert r.status_code == 200
        body = r.json()
        assert "arms" in body["data"]
        assert "config" in body["data"]
        assert "pending_feedbacks" in body["data"]


class TestFeedbackBatch:
    def test_batch_flush(self):
        # Clear any residual entries from previous tests
        feedback_store._buffer.clear()

        before_total = feedback_store.get_stats()["total_feedbacks"]
        for i in range(3):
            client.post("/feedback", json={
                "session_id": "batch_test",
                "action": "policy",
                "rating": 1,
                "context": {},
            })

        # Default batch_size is 10; 3 < 10 so no flush yet
        stats = feedback_store.get_stats()
        assert stats["buffer_size"] == 3
        assert stats["total_feedbacks"] == before_total + 3

        # Submit 7 more to reach 10 and trigger flush
        for i in range(7):
            client.post("/feedback", json={
                "session_id": "batch_test",
                "action": "policy",
                "rating": 1,
                "context": {},
            })

        stats = feedback_store.get_stats()
        assert stats["buffer_size"] == 0
        assert stats["total_feedbacks"] == before_total + 10
        rl_state = rl_agent.get_state()
        policy_reward = rl_state["arms"]["policy"]["reward"]
        assert policy_reward > 0, f"Expected positive reward, got {policy_reward}"
