"""Probabilistic trace sampling: 100% of errors, configurable % of successes."""

import logging
import random

from backend.src.core.settings import settings

logger = logging.getLogger("hr_ops.trace_sampling")


def should_sample(run_data: dict) -> bool:
    """Decide whether to store a trace run based on sampling rules.

    Errors (status >= 500 or compliance_veto) are always stored.
    Successful runs are sampled at the configured rate.

    Returns:
        True if the run should be persisted, False to discard.
    """
    sample_rate = settings.embed_config.get("trace_sampling", {}).get("success_sample_rate", 0.1)

    has_error = bool(run_data.get("compliance_veto", False))
    has_anomaly = len(run_data.get("anomaly_results", [])) > 0

    if has_error or has_anomaly:
        return True

    return random.random() < sample_rate
