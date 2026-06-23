import os
from pathlib import Path
import json
import pytest
import sys
from unittest.mock import MagicMock

# Mock dspy module globally to prevent loading litellm dependencies during tests
mock_dspy = MagicMock()
class MockExample:
    def __init__(self, query, classification):
        self.query = query
        self.classification = classification
    def with_inputs(self, *args):
        return self

mock_dspy.Example = MockExample
mock_dspy.Signature = MagicMock
sys.modules['dspy'] = mock_dspy
sys.modules['dspy.teleprompt'] = MagicMock()

from backend.src.services.feedback_service import feedback_store
from backend.src.intelligence.dspy_optimizer import build_training_data


@pytest.fixture
def clean_feedback_history():
    """Backup, clear, and restore feedback history file for isolation."""
    history_file = Path("backend/data/feedback_history.jsonl")
    backup_file = Path("backend/data/feedback_history.jsonl.bak")
    
    # Backup
    if history_file.exists():
        history_file.rename(backup_file)
        
    yield
    
    # Restore
    if history_file.exists():
        history_file.unlink()
    if backup_file.exists():
        backup_file.rename(history_file)


def test_feedback_persistence_and_dspy_integration(clean_feedback_history):
    history_file = Path("backend/data/feedback_history.jsonl")
    assert not history_file.exists()

    # 1. Record some mock feedback (one positive, one negative, one HITL positive)
    # Target query needs to be parsed by dspy_optimizer
    entry1 = feedback_store.record_feedback(
        session_id="session_dspy_test",
        action="policy",
        rating=1.0,
        context={"query": "What is the policy for carry forward leaves?"},
        source="explicit"
    )
    
    entry2 = feedback_store.record_feedback(
        session_id="session_dspy_test",
        action="action",
        rating=-0.5,
        context={"query": "Update employee 1 salary"},
        source="compliance" # compliance sources are negative, not included in training data
    )

    entry3 = feedback_store.record_feedback(
        session_id="session_dspy_test",
        action="compliance",
        rating=1.0,
        context={"query": "Verify standard safety procedure compliance"},
        source="hitl"
    )

    # 2. Check file persistence
    assert history_file.exists()
    
    with open(history_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line.strip()) for line in f if line.strip()]
        
    assert len(lines) == 3
    assert lines[0]["id"] == entry1["id"]
    assert lines[0]["reward"] == 1.0
    assert lines[1]["reward"] == -0.5
    assert lines[2]["reward"] == 1.0

    # 3. Call build_training_data and verify it contains the augmented examples
    examples = build_training_data()
    
    # Extract only the dynamically added examples
    dynamic_queries = [e.query for e in examples[8:]] # first 8 are the seed examples
    assert "What is the policy for carry forward leaves?" in dynamic_queries
    assert "Verify standard safety procedure compliance" in dynamic_queries
    assert "Update employee 1 salary" not in dynamic_queries # was not source in ("hitl", "explicit") and reward > 0

    # Verify classification mappings
    dynamic_examples = {e.query: e.classification for e in examples[8:]}
    assert dynamic_examples["What is the policy for carry forward leaves?"] == "policy"
    assert dynamic_examples["Verify standard safety procedure compliance"] == "compliance"
