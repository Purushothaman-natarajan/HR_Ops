import threading
from datetime import datetime, timezone
import uuid


class AlertStore:
    def __init__(self):
        self._alerts = []
        self._lock = threading.Lock()

    def add_alert(self, query: str, trigger_type: str, result: dict):
        with self._lock:
            alert = {
                "id": str(uuid.uuid4())[:8],
                "query": query,
                "trigger_type": trigger_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
                "status": "new",
            }
            self._alerts.insert(0, alert)
            # Keep only the latest 100 alerts
            if len(self._alerts) > 100:
                self._alerts.pop()
            return alert

    def get_alerts(self):
        with self._lock:
            return list(self._alerts)

    def mark_read(self, alert_id: str):
        with self._lock:
            for alert in self._alerts:
                if alert["id"] == alert_id:
                    alert["status"] = "read"
                    return True
            return False

    def get_scan_outcomes(self) -> list[dict]:
        """Return a formatted list of scan outcome objects for the Scan Outcomes UI."""
        with self._lock:
            outcomes = []
            for alert in self._alerts:
                result = alert.get("result") or {}
                anomaly_results = result.get("anomaly_results", [])
                # Normalise anomaly_results — may be a list of dicts or objects
                parsed_anomalies = []
                for a in anomaly_results:
                    if isinstance(a, dict):
                        parsed_anomalies.append(a)

                total_detected = sum(
                    1 for a in parsed_anomalies if a.get("detected", False)
                )

                outcomes.append({
                    "id": alert["id"],
                    "trigger_type": alert.get("trigger_type", "manual"),
                    "created_at": alert.get("created_at", ""),
                    "status": "error" if result.get("error") else "completed",
                    "final_response": result.get("final_response", ""),
                    "anomaly_results": parsed_anomalies,
                    "total_anomalies": total_detected,
                    "compliance_veto": bool(result.get("compliance_veto", False)),
                    "compliance_reason": result.get("compliance_reason", ""),
                    "executed_actions": result.get("executed_actions", []),
                    "retrieved_policies": result.get("retrieved_policies", []),
                    "total_cost_usd": result.get("total_cost_usd", 0.0),
                    "alert_status": alert.get("status", "new"),
                })
            return outcomes


alert_store = AlertStore()

