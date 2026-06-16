"""Tests the multi-turn conversation orchestrator."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class TestConversationStart:
    def test_start_standard(self):
        r = client.post("/conversation/start", json={"query": "What is the leave policy?"})
        # Accept either 200 (NVIDIA available) or 503/500 (model unavailable/auth error without env keys)
        if r.status_code in (503, 500):
            body = r.json()
            assert body["success"] is False
        else:
            assert r.status_code == 200

    def test_start_advanced(self):
        r = client.post("/conversation/start", json={"query": "What is the leave policy?", "mode": "advanced"})
        if r.status_code in (503, 500):
            body = r.json()
            assert body["success"] is False
        else:
            assert r.status_code == 200

    def test_start_empty_query(self):
        r = client.post("/conversation/start", json={"query": ""})
        assert r.status_code == 400
        assert r.json()["success"] is False

    def test_start_invalid_mode(self):
        r = client.post("/conversation/start", json={"query": "test", "mode": "invalid"})
        assert r.status_code == 400
        assert r.json()["success"] is False


class TestConversationSend:
    def test_send_invalid_session(self):
        r = client.post("/conversation/nonexistent_session/send", json={"query": "test"})
        assert r.status_code == 404
        assert r.json()["success"] is False

    def test_send_empty_query(self):
        r = client.post("/conversation/nonexistent_session/send", json={"query": ""})
        assert r.status_code == 400


class TestConversationGet:
    def test_get_session_not_found(self):
        r = client.get("/conversation/nonexistent")
        assert r.status_code == 404

    def test_list_sessions(self):
        r = client.get("/conversation")
        assert r.status_code == 200
        body = r.json()
        assert "sessions" in body["data"]


class TestConversationDelete:
    def test_delete_not_found(self):
        r = client.delete("/conversation/nonexistent")
        assert r.status_code == 404
