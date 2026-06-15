#!/usr/bin/env python
"""2-cycle LinUCB feedback loop simulation with before/after diagnostics."""

import logging

from backend.src.intelligence.rl_layer import rl_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("scripts.rl_simulation")

SCENARIOS = [
    {"query": "What is the leave policy?", "classification": "policy", "expected": "policy"},
    {"query": "Update salary for EMP0001 to 75000", "classification": "action", "expected": "action"},
    {"query": "Check for anomalies in payroll", "classification": "anomaly", "expected": "anomaly"},
    {"query": "Is EMP0002 compliant?", "classification": "compliance", "expected": "compliance"},
    {"query": "How many sick days do I have?", "classification": "policy", "expected": "policy"},
    {"query": "Approve termination for EMP0003", "classification": "compliance", "expected": "compliance"},
]


def simulate():
    logger.info("=== RL Simulation: Cycle 1 (Learning) ===")
    for i, scenario in enumerate(SCENARIOS):
        context = {"classification": scenario["classification"], "query": scenario["query"]}
        action = rl_agent.select_action(context)
        reward = 1.0 if action == scenario["expected"] else 0.0
        rl_agent.update(context, action, reward)
        logger.info(
            "  [%d] query=%-40s expected=%-10s selected=%-10s reward=%.1f",
            i + 1, scenario["query"][:40], scenario["expected"], action, reward,
        )

    logger.info("=== RL Simulation: Cycle 2 (Evaluation) ===")
    correct = 0
    for i, scenario in enumerate(SCENARIOS):
        context = {"classification": scenario["classification"], "query": scenario["query"]}
        action = rl_agent.select_action(context)
        is_correct = action == scenario["expected"]
        if is_correct:
            correct += 1
        logger.info(
            "  [%d] query=%-40s expected=%-10s selected=%-10s %s",
            i + 1, scenario["query"][:40], scenario["expected"], action,
            "✅" if is_correct else "❌",
        )

    accuracy = correct / len(SCENARIOS) * 100
    logger.info("=== Accuracy: %.1f%% (%d/%d) ===", accuracy, correct, len(SCENARIOS))
    rl_agent.save()
    logger.info("Bandit saved to data/rl_bandit.pkl")


if __name__ == "__main__":
    simulate()
