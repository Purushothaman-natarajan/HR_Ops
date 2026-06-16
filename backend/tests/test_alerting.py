import pytest
from unittest.mock import patch

from backend.src.utils.alerting import check_alert_rules

def test_check_alert_rules_ignore_low_count():
    metrics = {
        "/api/v1/users": {"count": 4, "p99_ms": 15000, "error_rate_pct": 50.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 0

def test_check_alert_rules_no_alerts():
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 500, "error_rate_pct": 1.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 0

def test_check_alert_rules_p99_alert():
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 15000, "error_rate_pct": 1.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 1
    assert alerts[0]["rule"] == "p99_latency"
    assert alerts[0]["endpoint"] == "/api/v1/users"
    assert alerts[0]["value"] == 15000
    assert alerts[0]["threshold"] == 10000

def test_check_alert_rules_error_rate_alert():
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 500, "error_rate_pct": 15.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 1
    assert alerts[0]["rule"] == "error_rate"
    assert alerts[0]["endpoint"] == "/api/v1/users"
    assert alerts[0]["value"] == 15.0
    assert alerts[0]["threshold"] == 10.0

def test_check_alert_rules_multiple_alerts_single_endpoint():
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 15000, "error_rate_pct": 15.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 2
    rules = [a["rule"] for a in alerts]
    assert "p99_latency" in rules
    assert "error_rate" in rules

def test_check_alert_rules_multiple_endpoints():
    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 15000, "error_rate_pct": 1.0},
        "/api/v1/auth": {"count": 100, "p99_ms": 500, "error_rate_pct": 15.0},
        "/api/v1/health": {"count": 100, "p99_ms": 100, "error_rate_pct": 0.0},
        "/api/v1/ignored": {"count": 2, "p99_ms": 20000, "error_rate_pct": 100.0}
    }
    alerts = check_alert_rules(metrics)
    assert len(alerts) == 2
    endpoints = [a["endpoint"] for a in alerts]
    assert "/api/v1/users" in endpoints
    assert "/api/v1/auth" in endpoints

@patch('backend.src.utils.alerting.settings')
def test_check_alert_rules_custom_settings(mock_settings):
    # Mock embed_config to return custom alerting thresholds
    mock_settings.embed_config = {
        "alerting": {
            "p99_threshold_ms": 5000,
            "error_rate_threshold_pct": 5.0
        }
    }

    metrics = {
        "/api/v1/users": {"count": 100, "p99_ms": 6000, "error_rate_pct": 6.0}
    }
    alerts = check_alert_rules(metrics)

    assert len(alerts) == 2

    p99_alert = next(a for a in alerts if a["rule"] == "p99_latency")
    assert p99_alert["threshold"] == 5000
    assert p99_alert["value"] == 6000

    error_rate_alert = next(a for a in alerts if a["rule"] == "error_rate")
    assert error_rate_alert["threshold"] == 5.0
    assert error_rate_alert["value"] == 6.0
