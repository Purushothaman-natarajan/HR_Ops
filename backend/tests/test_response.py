from fastapi import Request
from fastapi.responses import JSONResponse
import json

from backend.src.core.response import (
    APIResponse,
    success_response,
    error_response,
    get_correlation_id,
)

class TestResponseCore:
    def test_api_response_init(self):
        resp = APIResponse(success=True, data={"key": "value"}, message="Test", correlation_id="123")
        assert resp.success is True
        assert resp.data == {"key": "value"}
        assert resp.message == "Test"
        assert resp.correlation_id == "123"

    def test_api_response_to_dict(self):
        resp = APIResponse(success=False, data=None, message="Error", correlation_id="456")
        expected = {
            "success": False,
            "data": None,
            "message": "Error",
            "correlation_id": "456",
        }
        assert resp.to_dict() == expected

    def test_success_response_defaults(self):
        resp = success_response()
        assert resp["success"] is True
        assert resp["data"] is None
        assert resp["message"] == "OK"
        assert resp["correlation_id"] == ""

    def test_success_response_custom(self):
        resp = success_response(data={"user_id": 1}, message="Created", correlation_id="req-789")
        assert resp["success"] is True
        assert resp["data"] == {"user_id": 1}
        assert resp["message"] == "Created"
        assert resp["correlation_id"] == "req-789"

    def test_error_response_defaults(self):
        resp = error_response()
        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 500

        body = json.loads(resp.body)
        assert body["success"] is False
        assert body["message"] == "An error occurred"
        assert body["data"] is None
        assert body["correlation_id"] == ""

    def test_error_response_custom(self):
        resp = error_response(
            message="Not Found",
            correlation_id="req-123",
            status_code=404,
            data={"error_code": "E404"}
        )
        assert isinstance(resp, JSONResponse)
        assert resp.status_code == 404

        body = json.loads(resp.body)
        assert body["success"] is False
        assert body["message"] == "Not Found"
        assert body["data"] == {"error_code": "E404"}
        assert body["correlation_id"] == "req-123"

    def test_get_correlation_id_none_request(self):
        corr_id = get_correlation_id(None)
        assert isinstance(corr_id, str)
        assert len(corr_id) == 12

    def test_get_correlation_id_with_header(self):
        scope = {
            "type": "http",
            "headers": [(b"x-correlation-id", b"custom-req-id")]
        }
        request = Request(scope)
        corr_id = get_correlation_id(request)
        assert corr_id == "custom-req-id"

    def test_get_correlation_id_without_header(self):
        scope = {
            "type": "http",
            "headers": [(b"host", b"localhost")]
        }
        request = Request(scope)
        corr_id = get_correlation_id(request)
        assert isinstance(corr_id, str)
        assert len(corr_id) == 12
