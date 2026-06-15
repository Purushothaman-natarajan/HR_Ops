"""Parallel check node: runs anomaly detection and compliance check concurrently after the main agent completes."""

import asyncio
import logging

from backend.src.agents.nodes.anomaly_node import anomaly_node
from backend.src.agents.nodes.compliance_node import compliance_node
from backend.src.agents.state import SharedState

logger = logging.getLogger("hr_ops.nodes.parallel_check")


async def parallel_check_node(state: SharedState) -> dict:
    """Run anomaly detection and compliance check in parallel after the main agent.

    Both checks are independent and can safely run concurrently. Results are merged
    back into state without overwriting the main agent's final_response or previous traces.
    """
    results = await asyncio.gather(
        anomaly_node(state), compliance_node(state),
        return_exceptions=True,
    )

    anom_result = results[0] if isinstance(results[0], dict) else {"anomaly_results": [], "trace_log": []}
    comp_result = results[1] if isinstance(results[1], dict) else {"compliance_veto": False, "compliance_reason": "", "trace_log": []}

    if isinstance(results[0], Exception):
        logger.error("Anomaly node failed in parallel_check: %s", results[0])
    if isinstance(results[1], Exception):
        logger.error("Compliance node failed in parallel_check: %s", results[1])

    combined_trace = anom_result.get("trace_log", []) + comp_result.get("trace_log", [])

    logger.debug(
        "Parallel check complete: anomalies=%d, compliance_veto=%s",
        len(anom_result.get("anomaly_results", [])),
        comp_result.get("compliance_veto", False),
    )

    # Merge hitl_needed from both checks (either can trigger escalation)
    hitl_from_anomaly = anom_result.get("hitl_needed", False) if isinstance(anom_result, dict) else False
    hitl_from_compliance = comp_result.get("hitl_needed", False) if isinstance(comp_result, dict) else False

    return {
        "anomaly_results": anom_result.get("anomaly_results", []) if isinstance(anom_result, dict) else [],
        "compliance_veto": comp_result.get("compliance_veto", False) if isinstance(comp_result, dict) else False,
        "compliance_reason": comp_result.get("compliance_reason", "") if isinstance(comp_result, dict) else "",
        "hitl_needed": state.hitl_needed or hitl_from_anomaly or hitl_from_compliance,
        "trace_log": state.trace_log + combined_trace,
    }
