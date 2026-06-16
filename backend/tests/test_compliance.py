import pytest
from unittest.mock import patch

from backend.src.intelligence.compliance import (
    evaluate_action,
    check_veto,
    validate_policy_reference,
)

def test_evaluate_action_hard_veto_keyword():
    # Test hard veto keyword match
    report = evaluate_action("Delete all records from employees table")
    assert report.vetoed
    assert not report.compliant
    assert report.veto_reason == "Hard-veto keyword 'delete all records' is unconditionally blocked."

def test_evaluate_action_leave_overrun():
    # Test condition: leaves_taken > leaves_accrued
    report = evaluate_action("grant leave request", {"leaves_taken": 15, "leaves_accrued": 10})
    assert report.vetoed
    assert not report.compliant
    assert "LEAVE_001" in [r.rule_id for r in report.triggered_rules]

    # Test condition: leaves_taken <= leaves_accrued (not triggered)
    report = evaluate_action("grant leave request", {"leaves_taken": 8, "leaves_accrued": 10})
    assert not report.vetoed
    assert "LEAVE_001" not in [r.rule_id for r in report.triggered_rules]

def test_evaluate_action_salary_change():
    # Test condition: salary_change_pct > 25
    report = evaluate_action("salary increase requested", {"salary_change_pct": 30})
    assert report.vetoed
    assert "PAY_001" in [r.rule_id for r in report.triggered_rules]

    # Test condition: salary_change_pct <= 25
    report = evaluate_action("salary increase requested", {"salary_change_pct": 10})
    assert not report.vetoed
    assert "PAY_001" not in [r.rule_id for r in report.triggered_rules]

def test_evaluate_action_privacy_keyword():
    # Test keyword matching without numeric conditions
    report = evaluate_action("Please retrieve the bank account details of this employee")
    assert report.vetoed
    assert "PRIVACY_001" in [r.rule_id for r in report.triggered_rules]

def test_check_veto_shim():
    # Allowed
    allowed, reason = check_veto("EMP123", "Look up leave policy")
    assert allowed
    assert reason == ""

    # Blocked by hard veto keyword
    allowed, reason = check_veto("EMP123", "manipulate attendance records")
    assert not allowed
    assert "attendance" in reason.lower()

def test_validate_policy_reference():
    is_valid, msg = validate_policy_reference(True)
    assert is_valid
    assert msg == ""

    is_valid, msg = validate_policy_reference(False)
    assert not is_valid
    assert "Policy reference is required" in msg
