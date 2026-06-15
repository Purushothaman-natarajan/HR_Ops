"""Tests the API endpoints using FastAPI TestClient."""


from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


class TestHealth:
    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_has_status(self):
        r = client.get("/health")
        data = r.json()
        assert data.get("success") is True
        assert data.get("data", {}).get("status") == "ok"


class TestRoot:
    def test_root_returns_200(self):
        r = client.get("/")
        assert r.status_code == 200

    def test_root_has_message(self):
        r = client.get("/")
        data = r.json()
        assert data.get("success") is True
        assert "message" in data.get("data", {})


class TestGraphRun:
    def test_policy_query(self):
        r = client.post("/graph/run", json={"query": "What is the leave policy?"})
        if r.status_code == 503:
            data = r.json()
            assert data.get("success") is False
        else:
            assert r.status_code == 200

    def test_action_query(self):
        r = client.post(
            "/graph/run", json={"query": "Update salary for EMP0001 to 75000"}
        )
        if r.status_code == 503:
            data = r.json()
            assert data.get("success") is False
        else:
            assert r.status_code == 200

    def test_empty_query_returns_error(self):
        r = client.post("/graph/run", json={"query": ""})
        assert r.status_code == 400
        body = r.json()
        assert body.get("success") is False


class TestAGUI:
    def test_pending_list(self):
        r = client.get("/agui/pending")
        assert r.status_code == 200
        assert "pending" in str(r.json())


class TestTrace:
    def test_runs_list(self):
        r = client.get("/trace/runs")
        assert r.status_code == 200
        data = r.json().get("data", {})
        assert "runs" in data


class TestDebug:
    def test_requests_list(self):
        r = client.get("/debug/requests")
        assert r.status_code == 200
        data = r.json().get("data", {})
        assert "requests" in data


_TEST_POLICY_CONTENT = b"# Test Policy\n\nThis is a test policy for unit testing."
_TEST_POLICY_FILENAME = "test_policy_upload.md"
_TEST_POLICY_ID = "test_policy_upload"


class TestPolicies:
    def test_list_policies(self):
        r = client.get("/policies")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        policies = body["data"]["policies"]
        assert isinstance(policies, list)
        assert len(policies) >= 4

    def test_get_policy_found(self):
        r = client.get("/policies/leave_policy")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["id"] == "leave_policy"
        assert "content" in body["data"]

    def test_get_policy_not_found(self):
        r = client.get("/policies/nonexistent_policy_xyz")
        assert r.status_code == 404
        assert r.json()["success"] is False

    def test_download_policy(self):
        r = client.get("/policies/leave_policy/download")
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_download_policy_not_found(self):
        r = client.get("/policies/nonexistent_policy_xyz/download")
        assert r.status_code == 404
        assert r.json()["success"] is False

    def test_upload_and_delete_policy(self):
        r = client.post(
            "/policies/upload",
            files={"file": (_TEST_POLICY_FILENAME, _TEST_POLICY_CONTENT, "text/markdown")},
            data={"title": "Test Policy Upload"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert body["data"]["id"] == _TEST_POLICY_ID

        r = client.get(f"/policies/{_TEST_POLICY_ID}")
        assert r.status_code == 200
        assert "Test Policy" in r.json()["data"]["content"]

        r = client.delete(f"/policies/{_TEST_POLICY_ID}")
        assert r.status_code == 200
        assert r.json()["success"] is True

        r = client.get(f"/policies/{_TEST_POLICY_ID}")
        assert r.status_code == 404

    def test_upload_unsupported_type(self):
        r = client.post(
            "/policies/upload",
            files={"file": ("test.exe", b"fake", "application/x-msdownload")},
        )
        assert r.status_code == 400
        assert r.json()["success"] is False

    def test_delete_not_found(self):
        r = client.delete("/policies/nonexistent_policy_xyz")
        assert r.status_code == 404
        assert r.json()["success"] is False

    def test_update_title(self):
        r = client.put("/policies/leave_policy", json={"title": "Updated Leave Policy Title"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True

        r = client.get("/policies/leave_policy")
        content = r.json()["data"]["content"]
        assert content.startswith("# Updated Leave Policy Title")

        r = client.put("/policies/leave_policy", json={"title": "Leave Policy"})
        assert r.status_code == 200

    def test_update_not_found(self):
        r = client.put("/policies/nonexistent_policy_xyz", json={"title": "Whatever"})
        assert r.status_code == 404
        assert r.json()["success"] is False


class TestDatabaseAPI:
    def test_database_status(self):
        r = client.get("/database/status")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "employees_count" in body["data"]

    def test_database_upload_csv(self):
        csv_content = b"Employee_ID,Employee_Name,Age,Country,Department,Position,Salary,Joining_Date\nEMP9999,Test Upload,30,USA,HR,Intern,5000,2026-01-01\n"
        r = client.post(
            "/database/upload",
            files={"file": ("test_employees.csv", csv_content, "text/csv")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "filename" in body["data"]
        assert body["data"]["status"]["employees_count"] == 1

        # Verify query can read from the uploaded table
        from backend.src.tools.api_mocks import execute_db_query
        res = execute_db_query("SELECT Employee_Name FROM employees WHERE Employee_ID = 'EMP9999';")
        assert res.get("success") is True
        assert res.get("rows")[0]["Employee_Name"] == "Test Upload"

        # Re-seed the original database to keep it clean for subsequent tests
        import subprocess
        subprocess.run(["python", "backend/scripts/enhance_and_seed.py"], check=True)

    def test_database_upload_unsupported(self):
        r = client.post(
            "/database/upload",
            files={"file": ("test.txt", b"some text", "text/plain")},
        )
        assert r.status_code == 400
        assert r.json()["success"] is False

