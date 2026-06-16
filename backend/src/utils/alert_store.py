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
                "status": "new"
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

alert_store = AlertStore()
