"""Basic alerting rules for p99 latency and error rate thresholds."""

import logging

from backend.src.core.settings import settings

logger = logging.getLogger("hr_ops.alerting")


def check_alert_rules(metrics_snapshot: dict) -> list[dict]:
    """Check per-endpoint metrics against configured alert thresholds.

    Args:
        metrics_snapshot: Dict from MetricsStore.snapshot() keyed by endpoint.

    Returns:
        List of alert dicts with keys: endpoint, rule, value, threshold.
    """
    alerts = []
    alert_config = settings.embed_config.get("alerting", {})

    p99_threshold = alert_config.get("p99_threshold_ms", 10000)
    error_rate_threshold = alert_config.get("error_rate_threshold_pct", 10.0)

    for endpoint, stats in metrics_snapshot.items():
        if stats.get("count", 0) < 5:
            continue

        p99 = stats.get("p99_ms", 0)
        if p99 > p99_threshold:
            alerts.append({
                "endpoint": endpoint,
                "rule": "p99_latency",
                "value": p99,
                "threshold": p99_threshold,
                "message": f"p99={p99:.0f}ms exceeds threshold of {p99_threshold}ms",
            })

        error_rate = stats.get("error_rate_pct", 0)
        if error_rate > error_rate_threshold:
            alerts.append({
                "endpoint": endpoint,
                "rule": "error_rate",
                "value": error_rate,
                "threshold": error_rate_threshold,
                "message": f"Error rate {error_rate:.1f}% exceeds threshold of {error_rate_threshold}%",
            })

    if alerts:
        for alert in alerts:
            logger.warning("ALERT %s: %s", alert["rule"], alert["message"])

    return alerts
