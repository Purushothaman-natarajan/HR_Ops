"""Anomaly node: runs automated anomaly detection on employee data and generates a narrative."""

import logging
from datetime import datetime, timezone

from backend.src.agents.state import SharedState, TraceEntry
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
    employees = list(_EMPLOYEES.values()) if _EMPLOYEES else []
    results = run_anomaly_detection(employees)
    narrative = await _generate_narrative(results)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    return {
        "anomaly_results": results,
        "final_response": narrative,
        "trace_log": [
            TraceEntry(
                node="anomaly_node", agent_role="anomaly",
                input_text=state.query, output_text=narrative,
                timestamp=start, duration_ms=elapsed,
            )
        ],
    }
