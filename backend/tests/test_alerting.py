import pytest
from unittest.mock import patch, PropertyMock
from backend.src.utils.alerting import check_alert_rules

@pytest.fixture
def mock_settings():
    with patch("backend.src.utils.alerting.settings") as mock_settings:
        mock_settings.embed_config = {"alerting": {"p99_threshold_ms": 1000, "error_rate_threshold_pct": 5.0}}
        yield mock_settings

def test_no_alerts_when_under_thresholds(mock_settings):
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 500, "error_rate_pct": 1.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 0

def test_ignores_low_count(mock_settings):
    metrics = {
        "/api/v1/users": {"count": 4, "p99_ms": 2000, "error_rate_pct": 10.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 0

def test_p99_latency_alert(mock_settings):
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 1500, "error_rate_pct": 1.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 1
    assert alerts[0]["rule"] == "p99_latency"
    assert alerts[0]["endpoint"] == "/api/v1/users"
    assert alerts[0]["value"] == 1500

def test_error_rate_alert(mock_settings):
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 500, "error_rate_pct": 6.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 1
    assert alerts[0]["rule"] == "error_rate"
    assert alerts[0]["endpoint"] == "/api/v1/users"
    assert alerts[0]["value"] == 6.0

def test_multiple_alerts_same_endpoint(mock_settings):
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 1500, "error_rate_pct": 6.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 2
    rules = [a["rule"] for a in alerts]
    assert "p99_latency" in rules
    assert "error_rate" in rules

def test_multiple_endpoints(mock_settings):
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 500, "error_rate_pct": 6.0},
        "/api/v1/auth": {"count": 100, "p99_ms": 1500, "error_rate_pct": 1.0},
        "/api/v1/status": {"count": 100, "p99_ms": 100, "error_rate_pct": 0.0},
        "/api/v1/low_traffic": {"count": 2, "p99_ms": 5000, "error_rate_pct": 50.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 2
    endpoints = [a["endpoint"] for a in alerts]
    assert "/api/v1/users" in endpoints
    assert "/api/v1/auth" in endpoints
    assert "/api/v1/status" not in endpoints
    assert "/api/v1/low_traffic" not in endpoints
