#!/usr/bin/env python
"""Weekly DSPy MIPROv2 optimization — triggered by cron (0 3 * * 0)."""

import logging

from backend.src.intelligence.dspy_optimizer import (
    load_optimized_module,
    optimize_triage,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("scripts.dspy_optimization")


def main():
    logger.info("Starting DSPy optimization...")
    compiled = optimize_triage(minibatch=True)
    loaded = load_optimized_module("triage")
    if loaded:
        logger.info("Optimization verified — module loads successfully.")
    else:
        logger.warning("Optimization completed but module failed to load.")
    logger.info("DSPy optimization complete.")


if __name__ == "__main__":
    main()
