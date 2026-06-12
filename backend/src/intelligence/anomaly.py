import logging
import statistics
from typing import Any

from backend.src.agents.state import AnomalyResult

logger = logging.getLogger("hr_ops.anomaly")


def _z_score_outliers(values: list[float], threshold: float = 2.0) -> list[int]:
    if len(values) < 3:
        return []
    mean = statistics.mean(values)
    stdev = statistics.stdev(values) or 1
    return [i for i, v in enumerate(values) if abs((v - mean) / stdev) > threshold]


def _iqr_outliers(values: list[float]) -> list[int]:
    if len(values) < 4:
        return []
    sorted_v = sorted(values)
    q1 = sorted_v[len(sorted_v) // 4]
    q3 = sorted_v[(3 * len(sorted_v)) // 4]
    iqr = q3 - q1 or 1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return [i for i, v in enumerate(values) if v < lower or v > upper]


def detect_salary_anomalies(employees: list[dict]) -> list[AnomalyResult]:
    salaries = [e["salary"] for e in employees if e.get("salary")]
    outlier_indices = _iqr_outliers(salaries)
    results: list[AnomalyResult] = []
    for i in outlier_indices:
        emp = employees[i]
        results.append(
            AnomalyResult(
                detected=True,
                severity=min(abs(emp["salary"] - statistics.median(salaries)) / statistics.median(salaries), 1.0),
                description=f"Salary outlier: {emp['name']} earns ${emp['salary']:.2f}",
                anomaly_field="salary",
                suggested_action="Review and verify salary adjustment",
                supporting_data={"employee_id": emp["employee_id"], "salary": emp["salary"]},
            )
        )
    return results


def detect_leave_anomalies(employees: list[dict]) -> list[AnomalyResult]:
    balances = [e["leave_balance"] for e in employees if e.get("leave_balance") is not None]
    outlier_indices = _z_score_outliers(balances)
    results: list[AnomalyResult] = []
    for i in outlier_indices:
        emp = employees[i]
        results.append(
            AnomalyResult(
                detected=True,
                severity=0.7,
                description=f"Leave balance anomaly: {emp['name']} has {emp['leave_balance']} days",
                anomaly_field="leave_balance",
                suggested_action="Audit leave records for this employee",
                supporting_data={"employee_id": emp["employee_id"], "leave_balance": emp["leave_balance"]},
            )
        )
    return results


def detect_compliance_anomalies(employees: list[dict]) -> list[AnomalyResult]:
    results: list[AnomalyResult] = []
    for emp in employees:
        if emp.get("compliance_status") == "flagged":
            results.append(
                AnomalyResult(
                    detected=True,
                    severity=0.9,
                    description=f"Compliance flagged: {emp['name']} ({emp['employee_id']})",
                    anomaly_field="compliance_status",
                    suggested_action="Initiate compliance review immediately",
                    supporting_data={"employee_id": emp["employee_id"]},
                )
            )
    return results


def run_anomaly_detection(employees: list[dict]) -> list[AnomalyResult]:
    results: list[AnomalyResult] = []
    results.extend(detect_salary_anomalies(employees))
    results.extend(detect_leave_anomalies(employees))
    results.extend(detect_compliance_anomalies(employees))
    logger.info("Anomaly detection: %d anomalies found", len(results))
    return results
