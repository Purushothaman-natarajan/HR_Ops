"""Anomaly node: runs automated anomaly detection on employee data and generates a narrative."""

import logging
from datetime import datetime, timezone

from backend.src.agents.state import Activity, SharedState, TraceEntry
from backend.src.intelligence.anomaly import run_anomaly_detection
from backend.src.tools.api_mocks import _EMPLOYEES
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.nodes.anomaly")


async def _generate_narrative(anomalies: list) -> str:
    """Produce a human-readable narrative summary from a list of anomaly results."""
    if not anomalies:
        return "No anomalies detected."
    prompt = (
        "The following HR anomalies were found:\n"
        + "\n".join(f"- {a.description} (severity: {a.severity:.2f})" for a in anomalies)
        + "\n\nProvide a concise narrative summary for HR management."
    )
    narrative, _ = await llm_call("narrative", prompt, max_tokens=512)
    return narrative


async def anomaly_node(state: SharedState) -> dict:
    """Run anomaly detection on employee data and return a narrative summary."""
    start = datetime.now(timezone.utc)
    activities = []
    employees = list(_EMPLOYEES.values()) if _EMPLOYEES else []

    activities.append(Activity(
        type="search", label="Running anomaly detection on employee data",
        detail=f"Analyzing {len(employees)} employee records (IQR salary, Z-score leave, compliance flags)",
        status="running",
    ))
    results = run_anomaly_detection(employees)
    anomaly_count = len(results) if results else 0
    activities[-1].status = "completed"
    activities[-1].detail = f"Found {anomaly_count} anomalies across {len(employees)} employees"
    activities[-1].metadata = {"anomaly_count": anomaly_count, "employee_count": len(employees)}

    activities.append(Activity(
        type="llm_call", label="Generating anomaly narrative",
        detail=f"Summarizing {anomaly_count} anomalies for HR management",
        status="running",
    ))
    narrative = await _generate_narrative(results)
    activities[-1].status = "completed"
    activities[-1].detail = f"Generated {len(narrative)}-char narrative"

    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    # Escalate to HITL if any anomaly has severity >= 0.8
    has_severe = any(getattr(a, "severity", 0) >= 0.8 for a in results) if results else False
    return {
        "anomaly_results": results,
        "hitl_needed": has_severe,
        "final_response": narrative,
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="anomaly_node", agent_role="anomaly",
                input_text=state.query, output_text=narrative,
                timestamp=start, duration_ms=elapsed,
                activities=activities,
            )
        ],
    }
