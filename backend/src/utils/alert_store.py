import threading
from datetime import datetime, timezone
import uuid


class AlertStore:
    def __init__(self):
        self._alerts = []
        self._lock = threading.Lock()
        self._cache_outcomes = None

    def clear_cache(self):
        with self._lock:
            self._cache_outcomes = None

    def add_alert(self, query: str, trigger_type: str, result: dict):
        with self._lock:
            # Drop duplicates logic for scheduled or manual anomaly scans
            if trigger_type in ("scheduled", "manual") and self._alerts:
                latest_alert = self._alerts[0]
                latest_result = latest_alert.get("result") or {}
                
                # Helper to get unique anomaly fingerprint set
                def get_anomaly_fingerprints(res_dict):
                    anom_list = res_dict.get("anomaly_results", [])
                    fingerprints = set()
                    for a in anom_list:
                        if isinstance(a, dict):
                            eid = a.get("supporting_data", {}).get("employee_id", "") or a.get("supporting_data", {}).get("Employee_ID", "")
                            atype = a.get("anomaly_type", "")
                            desc = a.get("description", "")
                            fingerprints.add((eid, atype, desc))
                        elif hasattr(a, "supporting_data"):
                            eid = a.supporting_data.get("employee_id", "") or a.supporting_data.get("Employee_ID", "")
                            atype = a.anomaly_type if hasattr(a, "anomaly_type") else ""
                            desc = a.description if hasattr(a, "description") else ""
                            fingerprints.add((eid, atype, desc))
                    return fingerprints

                new_fingerprints = get_anomaly_fingerprints(result)
                
                # Check all existing alerts in the store
                for idx, existing_alert in enumerate(self._alerts):
                    if existing_alert.get("trigger_type") in ("scheduled", "manual"):
                        existing_result = existing_alert.get("result") or {}
                        existing_fingerprints = get_anomaly_fingerprints(existing_result)
                        
                        if new_fingerprints == existing_fingerprints:
                            # Update timestamp and result of the existing one to show it was refreshed
                            existing_alert["created_at"] = datetime.now(timezone.utc).isoformat()
                            existing_alert["status"] = "new"
                            existing_alert["result"] = result
                            
                            # Move it to the front of the list
                            alert_to_move = self._alerts.pop(idx)
                            self._alerts.insert(0, alert_to_move)
                            self._cache_outcomes = None
                            
                            import logging
                            logging.getLogger("hr_ops.alert_store").info(
                                "Dropped duplicate scan outcome for alert_id=%s. Updated timestamp and moved to top.", existing_alert["id"]
                            )
                            return existing_alert

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
            self._cache_outcomes = None
            return alert

    def get_alerts(self):
        with self._lock:
            return list(self._alerts)

    def mark_read(self, alert_id: str):
        with self._lock:
            for alert in self._alerts:
                if alert["id"] == alert_id:
                    alert["status"] = "read"
                    self._cache_outcomes = None
                    return True
            return False

    def get_scan_outcomes(self) -> list[dict]:
        """Return a formatted list of scan outcome objects for the Scan Outcomes UI."""
        with self._lock:
            if self._cache_outcomes is not None:
                return self._cache_outcomes

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

                # Dynamic lookup of HITL request state from agui_store
                hitl_req = result.get("hitl_request")
                hitl_info = None
                if hitl_req:
                    interaction_id = hitl_req.get("interaction_id")
                    if interaction_id:
                        from backend.src.utils.agui_store import agui_store
                        req_obj = agui_store._requests.get(interaction_id)
                        resp_obj = agui_store._responses.get(interaction_id)
                        
                        status_val = req_obj.status if req_obj else hitl_req.get("status", "pending")
                        response_val = resp_obj.response if resp_obj else ""
                        resolved_at_val = (
                            resp_obj.resolved_at.isoformat()
                            if resp_obj and hasattr(resp_obj.resolved_at, "isoformat")
                            else (str(resp_obj.resolved_at) if resp_obj else "")
                        )
                        metadata_val = resp_obj.metadata if resp_obj else {}
                        
                        hitl_info = {
                            "interaction_id": interaction_id,
                            "query": req_obj.query if req_obj else hitl_req.get("query", ""),
                            "status": status_val,
                            "created_at": req_obj.created_at.isoformat() if req_obj and hasattr(req_obj.created_at, "isoformat") else hitl_req.get("created_at", ""),
                            "assigned_role": req_obj.assigned_role if req_obj else hitl_req.get("assigned_role", "hr_manager"),
                            "session_id": req_obj.session_id if req_obj else hitl_req.get("session_id", ""),
                            "response": response_val,
                            "resolved_at": resolved_at_val,
                            "metadata": metadata_val,
                            "context": req_obj.context if req_obj else hitl_req.get("context", {}),
                        }

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
                    "hitl_needed": bool(result.get("hitl_needed", False)),
                    "hitl_request": hitl_info,
                })
            self._cache_outcomes = outcomes
            return outcomes


alert_store = AlertStore()

