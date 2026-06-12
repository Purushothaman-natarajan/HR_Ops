import json
import logging
from pathlib import Path
from typing import Any

import dspy
from dspy.teleprompt import MIPROv2

from backend.src.intelligence.signatures.triage_signature import TriageSignature
from backend.src.intelligence.signatures.rag_signature import RAGSignature
from backend.src.intelligence.signatures.narrative_signature import NarrativeSignature
from backend.src.intelligence.metrics.hr_metrics import approval_rate

logger = logging.getLogger("hr_ops.dspy")

_OPTIMIZED_DIR = Path("dspy_optimized")


def _ensure_llm():
    try:
        from backend.config.settings import settings

        if settings.openai_api_key:
            lm = dspy.LM("openai/gpt-4o-mini", api_key=settings.openai_api_key)
        elif settings.groq_api_key:
            lm = dspy.LM("groq/llama-3.1-8b-instant", api_key=settings.groq_api_key)
        else:
            lm = dspy.LM("openai/gpt-4o-mini")
        dspy.configure(lm=lm)
    except Exception:
        dspy.configure(lm=dspy.LM("openai/gpt-4o-mini"))


def build_training_data() -> list[dspy.Example]:
    return [
        dspy.Example(query="What is the leave policy?", classification="policy").with_inputs("query"),
        dspy.Example(query="Update salary for EMP0001 to 75000", classification="action").with_inputs("query"),
        dspy.Example(query="Check for salary anomalies last month", classification="anomaly").with_inputs("query"),
        dspy.Example(query="Is employee EMP0002 compliant?", classification="compliance").with_inputs("query"),
        dspy.Example(query="How many sick days do I have?", classification="policy").with_inputs("query"),
        dspy.Example(query="Approve termination for EMP0003", classification="compliance").with_inputs("query"),
        dspy.Example(query="Run anomaly detection on payroll", classification="anomaly").with_inputs("query"),
        dspy.Example(query="Change department for EMP0004 to Engineering", classification="action").with_inputs("query"),
    ]


def optimize_triage(minibatch: bool = True) -> dspy.Module:
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
