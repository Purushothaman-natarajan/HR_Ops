from __future__ import annotations

"""Feedback and reinforcement-learning reward service.

Buffers explicit (user) and implicit (compliance / auto) rewards,
flushes them in batches to the RL bandit agent, and exposes aggregated
per-arm statistics for monitoring.
"""

import logging
import uuid
from datetime import datetime, timezone
from threading import Lock

from backend.src.core.settings import settings
from backend.src.intelligence.rl_layer import anomaly_bandit, rl_agent

logger = logging.getLogger("hr_ops.feedback_service")


class FeedbackStore:
    """Thread-safe buffer that collects reward signals and flushes them to the RL agent.

    Supports explicit ratings, automatic compliance/action rewards, and
    HITL (human-in-the-loop) feedback. Flush occurs when the buffer
    reaches the configured rl_batch_size.
    """
    def __init__(self):
        self._buffer: list[dict] = []
        self._history: list[dict] = []
        self._lock = Lock()

    def record_feedback(
        self,
        session_id: str,
        action: str,
        rating: float,
        context: dict,
        source: str = "explicit",
    ) -> dict:
        """Append a single feedback entry to the buffer and flush if batch size is reached.

        Args:
            session_id: Session or interaction identifier.
            action: Arm / action name selected.
            rating: Reward value (e.g. 1.0, -0.5, 0.3).
            context: Optional contextual metadata dict.
            source: Origin label — 'explicit', 'compliance', 'auto', 'hitl'.

        Returns:
            The created feedback entry dict.
        """
        entry = {
            "id": str(uuid.uuid4())[:12],
            "session_id": session_id,
            "action": action,
            "reward": rating,
            "source": source,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        should_flush = False
        with self._lock:
            self._buffer.append(entry)
            logger.debug(
                "Feedback recorded: action=%s reward=%.2f source=%s buffer=%d/%d",
                action, rating, source, len(self._buffer), settings.rl_batch_size,
            )
            should_flush = len(self._buffer) >= settings.rl_batch_size
        if should_flush:
            self._flush()
        return entry

    def record_auto_rewards(self, run_result: dict, session_id: str = ""):
        """Derive and record implicit rewards from a graph run result.

        Applies a negative reward (-0.5) when compliance_veto is True,
        and a positive reward (0.3) when actions were executed.
        """
        rl_context = run_result.get("rl_context", {})
        if run_result.get("compliance_veto"):
            self.record_feedback(
                session_id=session_id,
                action=run_result.get("rl_selected_action", "compliance"),
                rating=-0.5,
                context=rl_context,
                source="compliance",
            )
        if run_result.get("executed_actions"):
            self.record_feedback(
                session_id=session_id,
                action=run_result.get("rl_selected_action", "action"),
                rating=0.3,
                context=rl_context,
                source="auto",
            )

    def record_hitl_reward(self, interaction_id: str, action: str, trigger_agent: str = "policy", rl_context: dict | None = None) -> dict | None:
        """Record a human-in-the-loop reward: +0.5 for approve, -0.3 otherwise."""
        rating = 0.5 if action == "approve" else -0.3
        return self.record_feedback(
            session_id=interaction_id,
            action=trigger_agent,
            rating=rating,
            context=rl_context or {},
            source="hitl",
        )

    def record_anomaly_bandit_reward(
        self,
        anomaly_context: dict,
        selected_action: str,
        reward: float,
        session_id: str = "",
    ) -> None:
        """Record a reward for the AnomalyActionBandit and flush immediately.

        Args:
            anomaly_context: Feature dict (confidence_score, severity, anomaly_type, etc.)
            selected_action:  The action the bandit chose.
            reward:           Scalar reward signal (positive=good, negative=bad).
            session_id:       Optional session ID for tracing.
        """
        anomaly_bandit.update(anomaly_context, selected_action, reward)
        try:
            anomaly_bandit.save()
        except Exception as exc:
            logger.warning("AnomalyBandit save failed: %s", exc)
        # Also add to main feedback history for monitoring
        entry = {
            "id": str(__import__("uuid").uuid4())[:12],
            "session_id": session_id,
            "action": f"anomaly:{selected_action}",
            "reward": reward,
            "source": "anomaly_bandit",
            "context": anomaly_context,
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
        with self._lock:
            self._history.append(entry)
        logger.debug("AnomalyBandit reward recorded: action=%s reward=%.3f", selected_action, reward)

    def _flush(self):
        """Send all buffered feedback entries to the RL agent, save its state, and clear the buffer."""
        with self._lock:
            buffer_copy = list(self._buffer)
            self._buffer.clear()
        if not buffer_copy:
            return
        logger.info("Flushing %d feedback entries to RL agent", len(buffer_copy))
        for entry in buffer_copy:
            rl_agent.update(entry.get("context", {}), entry["action"], entry["reward"])
        rl_agent.save()
        with self._lock:
            self._history.extend(buffer_copy)
        logger.info("RL agent updated and saved")

    @property
    def buffer_size(self) -> int:
        """Return the number of entries currently buffered (pending RL flush)."""
        with self._lock:
            return len(self._buffer)

    def list_feedback(self, limit: int = 50) -> list[dict]:
        """Return the most recent feedback entries from history and buffer combined."""
        with self._lock:
            combined = list(reversed(self._history + self._buffer))
            return combined[:limit]

    def get_stats(self) -> dict:
        """Aggregate per-arm reward statistics across all buffered and historic entries.

        Returns:
            Dict with per_arm list, buffer_size, total_feedbacks, and RL config values.
        """
        with self._lock:
            all_entries = self._history + self._buffer
            arms: dict[str, dict] = {}
            for entry in all_entries:
                arm = entry["action"]
                if arm not in arms:
                    arms[arm] = {"total_reward": 0.0, "count": 0, "source": entry["source"]}
                arms[arm]["total_reward"] += entry["reward"]
                arms[arm]["count"] += 1
            per_arm = []
            for name, info in arms.items():
                per_arm.append({
                    "arm": name,
                    "total_reward": round(info["total_reward"], 4),
                    "count": info["count"],
                    "avg_reward": round(info["total_reward"] / info["count"], 4) if info["count"] else 0,
                    "source": info["source"],
                })
            return {
                "per_arm": per_arm,
                "buffer_size": len(self._buffer),
                "total_feedbacks": len(all_entries),
                "rl_batch_size": settings.rl_batch_size,
                "rl_alpha": settings.rl_alpha,
                "rl_gamma": settings.rl_gamma,
            }


feedback_store = FeedbackStore()
