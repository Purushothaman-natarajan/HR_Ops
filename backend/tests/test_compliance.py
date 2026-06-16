import pytest
from unittest.mock import patch, PropertyMock

import backend.src.intelligence.compliance as compliance
from backend.src.intelligence.compliance import (
    _load_veto_rules,
    check_veto,
    validate_policy_reference,
)

@pytest.fixture(autouse=True)
def reset_hard_veto_rules():
    """Reset the global HARD_VETO_RULES before and after each test."""
    original_rules = compliance.HARD_VETO_RULES.copy()
    compliance.HARD_VETO_RULES.clear()
    yield
    compliance.HARD_VETO_RULES.clear()
    compliance.HARD_VETO_RULES.extend(original_rules)

@patch("backend.src.intelligence.compliance.settings")
def test_load_veto_rules_success(mock_settings):
    mock_settings.compliance_config = {"hard_veto_rules": ["cannot_approve_own", "cannot_bypass_manager"]}
    assert _load_veto_rules() == ["cannot_approve_own", "cannot_bypass_manager"]

@patch("backend.src.intelligence.compliance.settings")
def test_load_veto_rules_empty(mock_settings):
    mock_settings.compliance_config = {}
    assert _load_veto_rules() == []

@patch("backend.src.intelligence.compliance.settings")
def test_load_veto_rules_exception(mock_settings):
    # A cleaner and safer way to mock the exception is to mock `get` directly on the `compliance_config` mock
    mock_settings.compliance_config.get.side_effect = Exception("Config error")
    assert _load_veto_rules() == []

def test_check_veto_triggers():
    compliance.HARD_VETO_RULES.extend(["cannot_approve_own", "cannot_bypass_manager"])
    # rule "cannot_approve_own" key becomes "approve own"
    is_allowed, reason = check_veto("EMP123", "I want to approve own request")
    assert not is_allowed
    assert reason == "Hard veto: cannot_approve_own"

def test_check_veto_allows():
    compliance.HARD_VETO_RULES.extend(["cannot_approve_own"])
    is_allowed, reason = check_veto("EMP123", "I want to approve someone else's request")
    assert is_allowed
    assert reason == ""

def test_check_veto_loads_rules_if_empty():
    with patch("backend.src.intelligence.compliance._load_veto_rules") as mock_load:
        mock_load.return_value = ["cannot_fire_ceo"]
        is_allowed, reason = check_veto("EMP123", "fire ceo")
        assert not is_allowed
        assert reason == "Hard veto: cannot_fire_ceo"
        mock_load.assert_called_once()

        # Call again to ensure it doesn't load twice
        check_veto("EMP123", "Promote CEO")
        mock_load.assert_called_once()

def test_validate_policy_reference():
    is_valid, msg = validate_policy_reference(True)
    assert is_valid
    assert msg == ""

    is_valid, msg = validate_policy_reference(False)
    assert not is_valid
    assert "Policy reference is required" in msg
