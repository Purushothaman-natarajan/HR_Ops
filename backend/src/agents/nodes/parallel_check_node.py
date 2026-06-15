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
    back into state without overwriting the main agent's final_response.
    """
    anom_result, comp_result = await asyncio.gather(
        anomaly_node(state), compliance_node(state)
    )

    combined_trace = anom_result.get("trace_log", []) + comp_result.get("trace_log", [])

    logger.debug(
        "Parallel check complete: anomalies=%d, compliance_veto=%s",
        len(anom_result.get("anomaly_results", [])),
        comp_result.get("compliance_veto", False),
    )

    return {
        "anomaly_results": anom_result.get("anomaly_results", []),
        "compliance_veto": comp_result.get("compliance_veto", False),
        "compliance_reason": comp_result.get("compliance_reason", ""),
        "trace_log": combined_trace,
    }
