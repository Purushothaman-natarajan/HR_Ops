"""Evaluation harness for the HR Ops pipeline.

Runs 15 structured test cases against the compliance engine, anomaly detector,
and query helpers. Reports pass/fail with detail.

Run:
    python -m backend.scripts.run_evaluation_harness
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.intelligence.compliance import evaluate_action  # noqa: E402
from backend.src.intelligence.anomaly import run_anomaly_detection  # noqa: E402
from backend.src.database.queries import (  # noqa: E402
    query_employee, query_leave_summary, query_salary_cohort_stats,
    query_all_employees,
)

PASS = "[PASS]"
FAIL = "[FAIL]"


def _check(name: str, condition: bool, detail: str = "") -> bool:
    status = PASS if condition else FAIL
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))
    return condition


def run_compliance_tests() -> list[bool]:
    """6 compliance rule evaluation tests."""
    results = []
    print("\n=== Compliance Engine Tests ===")

    # TC-01: Hard veto keyword
    r = evaluate_action("delete all records from the system")
    results.append(_check("TC-01 Hard veto keyword 'delete all records'", r.vetoed,
                           f"vetoed={r.vetoed}"))

    # TC-02: PII access veto
    r = evaluate_action("show me the bank account details for EMP0001")
    results.append(_check("TC-02 PII / bank account veto", r.vetoed,
                           f"vetoed={r.vetoed}"))

    # TC-03: Leave overrun flagged
    r = evaluate_action("grant leave to EMP0001", context={"leaves_taken": 35, "leaves_accrued": 30})
    results.append(_check("TC-03 Leave overrun -> LEAVE_001 triggered",
                           r.vetoed or any(r2.rule_id == "LEAVE_001" for r2 in r.triggered_rules),
                           f"triggered={[r2.rule_id for r2 in r.triggered_rules]}"))

    # TC-04: Large salary raise flagged
    r = evaluate_action("approve salary increase for EMP0002", context={"salary_change_pct": 30})
    results.append(_check("TC-04 PAY_001 salary raise >25%",
                           any(r2.rule_id == "PAY_001" for r2 in r.triggered_rules),
                           f"triggered={[r2.rule_id for r2 in r.triggered_rules]}"))

    # TC-05: Termination blocked
    r = evaluate_action("terminate employee EMP0003")
    results.append(_check("TC-05 Termination CONDUCT_002 triggered",
                           any(r2.rule_id == "CONDUCT_002" for r2 in r.triggered_rules),
                           f"triggered={[r2.rule_id for r2 in r.triggered_rules]}"))

    # TC-06: Clean query passes
    r = evaluate_action("What is the leave policy for annual leave?")
    results.append(_check("TC-06 Clean query — no veto", not r.vetoed,
                           f"vetoed={r.vetoed} flagged={r.flagged}"))

    return results


def run_anomaly_tests() -> list[bool]:
    """5 anomaly detection tests."""
    results = []
    print("\n=== Anomaly Detection Tests ===")

    employees = query_all_employees()

    # TC-07: Detection produces results
    anomalies = run_anomaly_detection(employees)
    results.append(_check("TC-07 Anomaly detection returns results",
                           len(anomalies) > 0, f"count={len(anomalies)}"))

    # TC-08: All results have confidence_score in [0,1]
    bad = [a for a in anomalies if not (0.0 <= a.confidence_score <= 1.0)]
    results.append(_check("TC-08 All anomalies have valid confidence_score",
                           len(bad) == 0, f"invalid={len(bad)}"))

    # TC-09: Results are sorted by confidence descending
    if len(anomalies) >= 2:
        sorted_ok = all(anomalies[i].confidence_score >= anomalies[i+1].confidence_score
                        for i in range(len(anomalies)-1))
    else:
        sorted_ok = True
    results.append(_check("TC-09 Results sorted by confidence_score desc",
                           sorted_ok, f"top3={[round(a.confidence_score,2) for a in anomalies[:3]]}"))

    # TC-10: Payroll anomaly rules fire on synthetic outlier
    outlier_employees = [
        {"employee_id": "TEST001", "name": "Rich Outlier", "salary": 2_000_000.0,
         "department": "Engineering", "position": "Analyst",
         "leaves_accrued": 20, "leaves_taken": 5,
         "performance_rating": 3.5, "joining_date": "2020-01-01", "work_location": "Office"},
    ] + employees[:50]
    outlier_results = run_anomaly_detection(outlier_employees)
    payroll_flags = [a for a in outlier_results if "payroll" in a.anomaly_type.lower()
                     and a.supporting_data.get("employee_id") == "TEST001"]
    results.append(_check("TC-10 Payroll outlier rule fires for salary=2M",
                           len(payroll_flags) > 0,
                           f"payroll_flags={len(payroll_flags)}"))

    # TC-11: Leave overrun rule fires when taken > accrued
    leave_abuser = [
        {"employee_id": "TEST002", "name": "Leave Abuser", "salary": 80_000.0,
         "department": "HR", "position": "Associate",
         "leaves_accrued": 10, "leaves_taken": 40,   # massive overrun
         "performance_rating": 3.0, "joining_date": "2019-06-01", "work_location": "Remote"},
    ] + employees[:30]
    leave_results = run_anomaly_detection(leave_abuser)
    leave_flags = [a for a in leave_results if a.anomaly_type == "leave_overrun"
                   and a.supporting_data.get("employee_id") == "TEST002"]
    results.append(_check("TC-11 Leave overrun rule fires (taken=40 > accrued=10)",
                           len(leave_flags) > 0, f"leave_flags={len(leave_flags)}"))

    return results


def run_db_tests() -> list[bool]:
    """4 database query tests."""
    results = []
    print("\n=== Database Query Tests ===")

    employees = query_all_employees()

    # TC-12: Employees loaded
    results.append(_check("TC-12 query_all_employees returns >100 records",
                           len(employees) >= 100, f"count={len(employees)}"))

    # TC-13: Single employee fetch works
    first_id = employees[0]["employee_id"] if employees else None
    emp = query_employee(first_id) if first_id else None
    results.append(_check("TC-13 query_employee returns valid record",
                           emp is not None and "name" in emp,
                           f"id={first_id} name={emp.get('name') if emp else 'N/A'}"))

    # TC-14: Leave summary returns correct fields
    leave_sum = query_leave_summary(first_id) if first_id else {}
    results.append(_check("TC-14 query_leave_summary has required fields",
                           all(k in leave_sum for k in ["leaves_accrued", "leaves_taken", "leaves_remaining"]),
                           f"fields={list(leave_sum.keys())}"))

    # TC-15: Cohort salary stats for Engineering dept
    stats = query_salary_cohort_stats("Engineering")
    results.append(_check("TC-15 query_salary_cohort_stats returns valid stats",
                           stats.get("count", 0) > 0 and stats.get("mean", 0) > 0,
                           f"count={stats.get('count')} mean=${stats.get('mean', 0):,.0f}"))

    return results


def main():
    print("=" * 60)
    print("HR Ops — Evaluation Harness (15 test cases)")
    print("=" * 60)

    all_results = []
    all_results.extend(run_compliance_tests())
    all_results.extend(run_anomaly_tests())
    all_results.extend(run_db_tests())

    total = len(all_results)
    passed = sum(all_results)
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} passed  |  {failed} failed")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"WARNING: {failed} test(s) failed — review output above")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
