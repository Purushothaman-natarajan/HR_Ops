from __future__ import annotations

"""Reusable response serialisers for graph execution results.

Transforms raw SharedState / TraceEntry / AnomalyResult objects into
plain dicts for JSON API responses.
"""

from typing import Any

from backend.src.agents.state import AnomalyResult, TraceEntry


def _serialize_trace_events(trace_log: Any) -> list[dict]:
    if not isinstance(trace_log, list):
        return []
    return [
        {
            "node": t.node,
            "agent_role": str(t.agent_role),
            "input_text": t.input_text[:300],
            "output_text": t.output_text[:300],
            "timestamp": str(t.timestamp) if hasattr(t, "timestamp") else "",
            "duration_ms": t.duration_ms,
            "cost_usd": t.cost_usd,
            "cache_hit": t.cache_hit,
            "model_used": t.model_used,
            "reasoning": t.reasoning,
            "alternatives": t.alternatives,
            "retrieved_docs": t.retrieved_docs[:3],
            "tool_call": t.tool_call,
        }
        for t in trace_log
        if isinstance(t, TraceEntry)
    ]


def _serialize_anomaly_results(anomalies: Any) -> list[dict]:
    if not isinstance(anomalies, list):
        return []
    return [
        {
            "detected": a.detected,
            "severity": a.severity,
            "description": a.description,
            "anomaly_field": a.anomaly_field,
            "suggested_action": a.suggested_action,
        }
        for a in anomalies
        if isinstance(a, AnomalyResult)
    ]


def serialize_graph_result(
    result: dict,
    run_id: str = "",
    langfuse_trace_id: str = "",
) -> dict:
    """Convert a raw graph.invoke() result into a compact JSON-safe dict for API responses.

    Filters trace events and anomaly results to valid typed instances,
    truncates long text fields to 300 characters, and includes counts.

    Args:
        result: Raw output dict from graph execution.
        run_id: Optional run identifier.
        langfuse_trace_id: Optional Langfuse trace identifier.

    Returns:
        Dict with keys run_id, query, final_response, trace_events, etc.
    """
    trace_log = result.get("trace_log", [])
    anomalies = result.get("anomaly_results", [])
    events = _serialize_trace_events(trace_log)
    total_cost = result.get("total_cost_usd", 0.0)

    return {
        "run_id": run_id,
        "langfuse_trace_id": langfuse_trace_id,
        "query": result.get("query", ""),
        "final_response": result.get("final_response", ""),
        "compliance_veto": result.get("compliance_veto", False),
        "compliance_reason": result.get("compliance_reason", ""),
        "retrieved_policies": result.get("retrieved_policies", [])[:3],
        "executed_actions": result.get("executed_actions", [])[:3],
        "total_cost_usd": total_cost,
        "cost_usd": total_cost,
        "duration_ms": sum(e.get("duration_ms", 0) for e in events),
        "trace_events": events,
        "anomaly_results": _serialize_anomaly_results(anomalies),
    }
