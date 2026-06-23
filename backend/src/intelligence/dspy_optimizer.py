"""DSPy optimizer: compiles and loads optimized prompts for triage, RAG, and narrative."""

import logging
from pathlib import Path

import dspy
from dspy.teleprompt import MIPROv2

from backend.src.core.exceptions import ConfigurationError
from backend.src.intelligence.metrics.hr_metrics import approval_rate
from backend.src.intelligence.signatures.triage_signature import TriageSignature

logger = logging.getLogger("hr_ops.dspy")

_OPTIMIZED_DIR = Path("dspy_optimized")


def _ensure_llm():
    """Configure the DSPy language model using available API keys."""
    from backend.src.core.settings import settings

    if settings.openai_api_key:
        lm = dspy.LM("openai/gpt-4o-mini", api_key=settings.openai_api_key)
    elif settings.groq_api_key:
        lm = dspy.LM("groq/llama-3.1-8b-instant", api_key=settings.groq_api_key)
    else:
        raise ConfigurationError("No API key configured for DSPy — set OPENAI_API_KEY or GROQ_API_KEY")
    dspy.configure(lm=lm)


def build_training_data() -> list[dspy.Example]:
    """Return a small set of labelled HR query examples for DSPy optimization, augmented by feedback logs."""
    examples = [
        dspy.Example(
            query="How many annual leave days accrue each month, and how many can carry forward?",
            classification="policy",
        ).with_inputs("query"),
        dspy.Example(
            query="When is a medical certificate required for sick leave?",
            classification="policy",
        ).with_inputs("query"),
        dspy.Example(
            query="What approvals are needed for remote work beyond 3 days per week?",
            classification="policy",
        ).with_inputs("query"),
        dspy.Example(
            query="Review whether a retroactive salary adjustment for EMP0001 is allowed under compensation policy.",
            classification="compliance",
        ).with_inputs("query"),
        dspy.Example(
            query="Check if sharing EMP0002 HR records with an external vendor is compliant.",
            classification="compliance",
        ).with_inputs("query"),
        dspy.Example(
            query="Investigate employees with more than 3 unscheduled absences this quarter and explain the policy risk.",
            classification="anomaly",
        ).with_inputs("query"),
        dspy.Example(
            query="Escalate an off-cycle salary adjustment request for EMP0003 for VP-level approval.",
            classification="action",
        ).with_inputs("query"),
        dspy.Example(
            query="Look up EMP0004 before reviewing eligibility for a spot award under the compensation policy.",
            classification="action",
        ).with_inputs("query"),
    ]

    persist_path = Path("backend/data/feedback_history.jsonl")
    if persist_path.exists():
        try:
            import json
            additional_count = 0
            with open(persist_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line.strip())
                    source = entry.get("source")
                    reward = entry.get("reward", 0.0)
                    context = entry.get("context", {})
                    query_text = context.get("query")
                    # We care about positive feedback or approved HITL actions for routing classification
                    if query_text and source in ("hitl", "explicit") and reward > 0:
                        action = entry.get("action")
                        valid_actions = {"policy", "action", "anomaly", "compliance"}
                        if action in valid_actions:
                            examples.append(
                                dspy.Example(
                                    query=query_text,
                                    classification=action,
                                ).with_inputs("query")
                            )
                            additional_count += 1
            logger.info("Augmented DSPy training set with %d examples from feedback history", additional_count)
        except Exception as e:
            logger.warning("Failed to augment DSPy training data: %s", e)

    return examples


def optimize_triage(minibatch: bool = True) -> dspy.Module:
    """Compile the TriageSignature using MIPROv2 and save the optimized module."""
    _ensure_llm()
    trainset = build_training_data()
    if minibatch and len(trainset) > 4:
        trainset = trainset[:4]
    optimizer = MIPROv2(metric=approval_rate, num_candidates=6, init_temperature=0.5)
    compiled = optimizer.compile(TriageSignature(), trainset=trainset, num_trials=3)
    _OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)
    compiled.save(str(_OPTIMIZED_DIR / "triage_signature.json"))
    logger.info("DSPy triage optimization complete")
    return compiled


def load_optimized_module(name: str = "triage") -> dspy.Module | None:
    """Load a previously optimized DSPy module from disk, or return None."""
    path = _OPTIMIZED_DIR / f"{name}_signature.json"
    if path.exists():
        try:
            module = dspy.Module()
            module.load(str(path))
            logger.info("Loaded optimized module: %s", name)
            return module
        except Exception as e:
            logger.warning("Failed to load optimized module %s: %s", name, e)
    return None
