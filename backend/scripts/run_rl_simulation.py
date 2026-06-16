#!/usr/bin/env python
"""2-cycle RL simulation — LinUCB routing bandit + AnomalyActionBandit.

Cycle 1 : Training (reward signal for correct routing)
Cycle 2 : Evaluation (accuracy measurement)

Also runs 2 cycles for the AnomalyActionBandit with realistic anomaly contexts
and prints a cumulative reward table and action distribution shift.

Run:
    python -m backend.scripts.run_rl_simulation
"""

import sys
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging  # noqa: E402

from backend.src.intelligence.rl_layer import rl_agent, anomaly_bandit  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scripts.rl_simulation")

# ─── Routing bandit scenarios ─────────────────────────────────────────────────

ROUTING_SCENARIOS = [
    {"query": "How many annual leave days accrue per month?", "classification": "policy", "expected": "policy"},
    {"query": "What approvals are needed for remote work beyond 3 days?", "classification": "policy", "expected": "policy"},
    {"query": "Escalate off-cycle salary adjustment for EMP0003.", "classification": "action", "expected": "action"},
    {"query": "Investigate employees with 3+ unscheduled absences.", "classification": "anomaly", "expected": "anomaly"},
    {"query": "Check if sharing HR records with a vendor is compliant.", "classification": "compliance", "expected": "compliance"},
    {"query": "Review whether retroactive salary adjustment is allowed.", "classification": "compliance", "expected": "compliance"},
    {"query": "Generate payroll anomaly report for Q1.", "classification": "anomaly", "expected": "anomaly"},
    {"query": "What is the PIP process for low performers?", "classification": "policy", "expected": "policy"},
]

# ─── Anomaly bandit scenarios ─────────────────────────────────────────────────

ANOMALY_SCENARIOS = [
    {
        "context": {"anomaly_type": "payroll_high_outlier", "confidence_score": 0.95, "severity": 0.9, "recommended_action": "escalate_hr_review"},
        "expected": "escalate_hr_review",
    },
    {
        "context": {"anomaly_type": "leave_overrun", "confidence_score": 0.92, "severity": 0.85, "recommended_action": "escalate_hr_review"},
        "expected": "escalate_hr_review",
    },
    {
        "context": {"anomaly_type": "leave_peer_outlier", "confidence_score": 0.74, "severity": 0.6, "recommended_action": "request_manager_review"},
        "expected": "request_manager_review",
    },
    {
        "context": {"anomaly_type": "compliance_low_performance", "confidence_score": 0.80, "severity": 0.72, "recommended_action": "initiate_pip"},
        "expected": "initiate_pip",
    },
    {
        "context": {"anomaly_type": "leave_hoarding", "confidence_score": 0.70, "severity": 0.55, "recommended_action": "send_notification"},
        "expected": "send_notification",
    },
    {
        "context": {"anomaly_type": "compliance_attrition_risk", "confidence_score": 0.76, "severity": 0.62, "recommended_action": "request_manager_review"},
        "expected": "request_manager_review",
    },
]


def _bar(value: float, width: int = 20) -> str:
    filled = int(value * width)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {value:.1%}"


def simulate_routing_bandit() -> float:
    """Run 2 routing cycles; return cycle-2 accuracy."""
    logger.info("")
    logger.info("=" * 65)
    logger.info("  ROUTING BANDIT — LinUCB (4 arms: policy/action/anomaly/compliance)")
    logger.info("=" * 65)

    cum_rewards = []

    for cycle in range(1, 3):
        label = "Training" if cycle == 1 else "Evaluation"
        logger.info("")
        logger.info("  [Cycle %d: %s]", cycle, label)
        correct = 0
        cycle_reward = 0.0
        for i, s in enumerate(ROUTING_SCENARIOS):
            ctx = {"classification": s["classification"], "query": s["query"]}
            action = rl_agent.select_action(ctx)
            reward = 1.0 if action == s["expected"] else 0.0
            rl_agent.update(ctx, action, reward)
            cycle_reward += reward
            if reward > 0:
                correct += 1
            status = "OK" if reward > 0 else "XX"
            logger.info("    [%s] Q=%-35s exp=%-12s got=%-12s",
                        status, s["query"][:35], s["expected"], action)
        cum_rewards.append(cycle_reward)
        acc = correct / len(ROUTING_SCENARIOS) * 100
        logger.info("    Cycle %d accuracy: %.0f%%  cumulative_reward=%.1f", cycle, acc, cycle_reward)

    rl_agent.save()
    logger.info("")
    logger.info("  Reward per cycle: %s", cum_rewards)
    logger.info("  Delta (C2-C1): %+.1f", cum_rewards[1] - cum_rewards[0])

    return cum_rewards[1] / len(ROUTING_SCENARIOS)


def simulate_anomaly_bandit() -> float:
    """Run 2 anomaly action cycles; return cycle-2 accuracy."""
    logger.info("")
    logger.info("=" * 65)
    logger.info("  ANOMALY ACTION BANDIT — LinUCB (6 arms)")
    logger.info("=" * 65)

    action_distribution: list[Counter] = []
    cum_rewards = []

    for cycle in range(1, 3):
        label = "Training" if cycle == 1 else "Evaluation"
        logger.info("")
        logger.info("  [Cycle %d: %s]", cycle, label)
        correct = 0
        dist: Counter = Counter()
        cycle_reward = 0.0
        for s in ANOMALY_SCENARIOS:
            action = anomaly_bandit.select_action(s["context"])
            reward = 1.0 if action == s["expected"] else (0.3 if "review" in action else 0.0)
            anomaly_bandit.update(s["context"], action, reward)
            cycle_reward += reward
            dist[action] += 1
            if action == s["expected"]:
                correct += 1
            status = "OK" if action == s["expected"] else "~~"
            logger.info("    [%s] type=%-30s exp=%-25s got=%s",
                        status, s["context"]["anomaly_type"][:30], s["expected"], action)
        acc = correct / len(ANOMALY_SCENARIOS) * 100
        cum_rewards.append(cycle_reward)
        action_distribution.append(dist)
        logger.info("    Cycle %d accuracy: %.0f%%  reward=%.2f", cycle, acc, cycle_reward)

    anomaly_bandit.save()

    # Print action distribution shift
    logger.info("")
    logger.info("  Action Distribution Shift (Cycle 1 -> Cycle 2):")
    all_actions = set(list(action_distribution[0].keys()) + list(action_distribution[1].keys()))
    for act in sorted(all_actions):
        c1 = action_distribution[0].get(act, 0)
        c2 = action_distribution[1].get(act, 0)
        delta = c2 - c1
        logger.info("    %-28s  C1=%d  C2=%d  delta=%+d", act, c1, c2, delta)

    logger.info("")
    logger.info("  Cumulative rewards: %s   Delta: %+.2f", cum_rewards, cum_rewards[1] - cum_rewards[0])

    return cum_rewards[1] / len(ANOMALY_SCENARIOS)


def main():
    logger.info("HR Ops RL Simulation — 2 cycles each for routing + anomaly bandits")

    routing_acc = simulate_routing_bandit()
    anomaly_acc = simulate_anomaly_bandit()

    logger.info("")
    logger.info("=" * 65)
    logger.info("  FINAL SUMMARY")
    logger.info("  Routing Bandit  cycle-2 accuracy: %s", _bar(routing_acc))
    logger.info("  Anomaly Bandit  cycle-2 accuracy: %s", _bar(anomaly_acc))
    logger.info("=" * 65)

    return 0


if __name__ == "__main__":
    sys.exit(main())
