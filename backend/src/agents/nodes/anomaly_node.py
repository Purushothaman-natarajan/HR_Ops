"""Anomaly node: runs the 18-rule statistical pipeline and routes by confidence score.

Routing logic:
  - confidence >= 0.85  → auto-escalate to Action Agent
  - 0.65 <= confidence < 0.85 → queue HITL for human review
  - confidence < 0.65   → log and continue without escalation

Episodic memory:
  - Recalls similar past incidents to warm-start the narrative.
  - Stores all critical (>=0.75 severity) anomalies for future recall.
"""

import logging
from datetime import datetime, timezone

from backend.src.agents.state import Activity, SharedState, TraceEntry
from backend.src.database.queries import query_all_employees
from backend.src.intelligence.anomaly import run_anomaly_detection
from backend.src.memory.episodic_memory import episodic_memory
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.nodes.anomaly")

# Thresholds for RL bandit action routing
_CONFIDENCE_ESCALATE = 0.85   # auto-execute action via Action Agent
_CONFIDENCE_HITL = 0.65       # queue for human review


async def _generate_narrative(anomalies: list, past_context: str = "") -> str:
    """Produce a human-readable narrative summary from a list of anomaly results."""
    if not anomalies:
        return "No anomalies detected in the current employee dataset."

    anomaly_lines = "\n".join(
        f"- [{a.anomaly_type}] {a.description} "
        f"(confidence: {a.confidence_score:.0%}, severity: {a.severity:.2f}, "
        f"action: {a.recommended_action})"
        for a in anomalies[:20]  # top 20 for prompt budget
    )
    past_section = f"\n\nRelated Past Incidents for context:\n{past_context}" if past_context else ""
    prompt = (
        "You are an HR analytics AI. The following anomalies were detected in employee data:\n"
        f"{anomaly_lines}{past_section}\n\n"
        "Provide a concise executive narrative (3-5 sentences) for HR management, "
        "highlighting the most critical issues and recommended next steps."
    )
    narrative, _ = await llm_call("narrative", prompt, max_tokens=512)
    return narrative


async def anomaly_node(state: SharedState) -> dict:
    """Run statistical anomaly detection on live DB data and route by confidence."""
    start = datetime.now(timezone.utc)
    activities = []

    # ── 1. Load employees from DB ────────────────────────────────────────────
    activities.append(Activity(
        type="search", label="Loading employee records from database",
        detail="Fetching all employees for anomaly sweep",
        status="running",
    ))
    employees = query_all_employees()
    activities[-1].status = "completed"
    activities[-1].detail = f"Loaded {len(employees)} employees from DB"

    # ── 2. Run 18-rule anomaly pipeline ─────────────────────────────────────
    activities.append(Activity(
        type="search", label="Running 18-rule statistical anomaly pipeline",
        detail="Payroll Z-score+IQR, leave-abuse patterns, compliance violations",
        status="running",
    ))
    results = run_anomaly_detection(employees)
    anomaly_count = len(results)

    # Bucket anomalies by routing decision
    auto_escalate = [a for a in results if a.confidence_score >= _CONFIDENCE_ESCALATE]
    hitl_queue = [a for a in results if _CONFIDENCE_HITL <= a.confidence_score < _CONFIDENCE_ESCALATE]
    low_conf = [a for a in results if a.confidence_score < _CONFIDENCE_HITL]

    activities[-1].status = "completed"
    activities[-1].detail = (
        f"Found {anomaly_count} anomalies: "
        f"{len(auto_escalate)} auto-escalate, "
        f"{len(hitl_queue)} HITL, "
        f"{len(low_conf)} informational"
    )
    activities[-1].metadata = {
        "anomaly_count": anomaly_count,
        "auto_escalate": len(auto_escalate),
        "hitl_queue": len(hitl_queue),
        "low_conf": len(low_conf),
        "employee_count": len(employees),
    }

    # ── 3. Episodic memory recall ────────────────────────────────────────────
    past_context = ""
    try:
        past_incidents = episodic_memory.recall_similar_incidents(state.query, k=3)
        if past_incidents:
            past_context = "\n".join(f"• {inc['content']}" for inc in past_incidents)
            activities.append(Activity(
                type="search", label="Recalled similar past incidents",
                detail=f"Found {len(past_incidents)} related episodes",
                status="completed",
                metadata={"recalled": len(past_incidents)},
            ))
    except Exception as e:
        logger.warning("Episodic memory recall failed: %s", e)

    # ── 4. Generate narrative ────────────────────────────────────────────────
    activities.append(Activity(
        type="llm_call", label="Generating anomaly narrative",
        detail=f"Summarising {anomaly_count} anomalies for HR management",
        status="running",
    ))
    narrative = await _generate_narrative(results, past_context)
    activities[-1].status = "completed"
    activities[-1].detail = f"Generated {len(narrative)}-char narrative"

    # ── 5. Store critical anomalies to episodic memory ───────────────────────
    try:
        for anomaly in results:
            if anomaly.severity >= 0.75:
                episodic_memory.store_incident(
                    trigger_type=anomaly.anomaly_type or "anomaly",
                    query=anomaly.description,
                    result_summary=(
                        f"Action: {anomaly.recommended_action} | "
                        f"Confidence: {anomaly.confidence_score:.0%} | "
                        f"Data: {anomaly.supporting_data}"
                    ),
                    severity=anomaly.severity,
                )
    except Exception as e:
        logger.warning("Episodic memory store failed: %s", e)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    # hitl_needed if there are any HITL-bucket or auto-escalate anomalies
    needs_hitl = bool(hitl_queue or auto_escalate)

    return {
        "anomaly_results": results,
        "hitl_needed": needs_hitl,
        "final_response": narrative,
        "rl_context": {
            **state.rl_context,
            "anomaly_count": anomaly_count,
            "auto_escalate_count": len(auto_escalate),
            "hitl_count": len(hitl_queue),
        },
        "trace_log": (state.trace_log or []) + [
            TraceEntry(
                node="anomaly_node", agent_role="anomaly",
                input_text=state.query, output_text=narrative,
                timestamp=start, duration_ms=elapsed,
                activities=activities,
                metadata={
                    "anomaly_count": anomaly_count,
                    "auto_escalate": len(auto_escalate),
                    "hitl_queue": len(hitl_queue),
                },
            )
        ],
    }
