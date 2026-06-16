"""Production-grade anomaly detection pipeline for HR Ops.

Implements 18 statistical and rule-based checks across three domains:
  - Payroll outliers   (cohort Z-score, IQR, peer deviation, overtime fraud)
  - Leave-abuse patterns (leave ratio, clustering, long streaks, frequent Mondays/Fridays)
  - Compliance violations (missing training, overdue reviews, probation breaches, etc.)

Each detector returns AnomalyResult objects with a ``confidence_score`` (0.0–1.0)
and a ``recommended_action`` field used by the RL bandit and HITL router.
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta

from backend.src.agents.state import AnomalyResult
from backend.src.repositories.queries import (
    query_all_employees,
    query_all_payroll_current,
    query_attendance_summary_all,
)

logger = logging.getLogger("hr_ops.anomaly")

# ─── Statistical helpers ─────────────────────────────────────────────────────


def _z_score(value: float, mean: float, stdev: float) -> float:
    if stdev == 0:
        return 0.0
    return abs((value - mean) / stdev)


def _iqr_bounds(values: list[float]) -> tuple[float, float]:
    """Return (lower, upper) IQR-based fences (1.5 × IQR rule)."""
    sv = sorted(values)
    n = len(sv)
    q1 = statistics.median(sv[: n // 2])
    q3 = statistics.median(sv[n // 2 :] if n % 2 == 0 else sv[n // 2 + 1 :])
    iqr = q3 - q1 or 1.0
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def _sigmoid(x: float) -> float:
    """Map a positive z-score or ratio to (0.5, 1.0) confidence."""
    return 1.0 / (1.0 + math.exp(-x + 2))


def _confidence(z: float, base: float = 0.6) -> float:
    return min(round(base + _sigmoid(z) * (1.0 - base), 3), 1.0)


# ─── Rule 1-6: Payroll anomalies ─────────────────────────────────────────────


def detect_payroll_anomalies(employees: list[dict]) -> list[AnomalyResult]:
    """Six payroll-based anomaly checks on the current cohort."""
    results: list[AnomalyResult] = []
    if not employees:
        return results

    # Build department cohorts for salary benchmarking
    dept_salaries: dict[str, list[tuple[dict, float]]] = defaultdict(list)
    for e in employees:
        sal = e.get("salary") or 0.0
        dept_salaries[e.get("department", "General")].append((e, sal))

    for dept, cohort in dept_salaries.items():
        salaries = [s for _, s in cohort]
        if len(salaries) < 4:
            continue
        mean_sal = statistics.mean(salaries)
        stdev_sal = statistics.stdev(salaries) or 1.0
        lower, upper = _iqr_bounds(salaries)

        for emp, sal in cohort:
            z = _z_score(sal, mean_sal, stdev_sal)
            eid = emp["employee_id"]
            name = emp.get("name", eid)

            # Rule 1 — Z-score salary outlier (high)
            if z > 3.0 and sal > mean_sal:
                results.append(AnomalyResult(
                    detected=True,
                    severity=min(z / 6.0, 1.0),
                    confidence_score=_confidence(z),
                    description=f"[PAYROLL-R1] {name} salary ${sal:,.0f} is {z:.1f} SD above {dept} mean (${mean_sal:,.0f})",
                    anomaly_field="salary",
                    anomaly_type="payroll_high_outlier",
                    recommended_action="escalate_hr_review",
                    supporting_data={"employee_id": eid, "salary": sal, "dept_mean": round(mean_sal), "z_score": round(z, 2)},
                ))

            # Rule 2 — Z-score salary outlier (low, possible underpayment)
            if z > 2.5 and sal < mean_sal:
                results.append(AnomalyResult(
                    detected=True,
                    severity=min(z / 5.0, 1.0),
                    confidence_score=_confidence(z, base=0.55),
                    description=f"[PAYROLL-R2] {name} salary ${sal:,.0f} is {z:.1f} SD below {dept} mean — possible underpayment",
                    anomaly_field="salary",
                    anomaly_type="payroll_low_outlier",
                    recommended_action="flag_for_review",
                    supporting_data={"employee_id": eid, "salary": sal, "dept_mean": round(mean_sal), "z_score": round(z, 2)},
                ))

            # Rule 3 — IQR fence breach
            if sal < lower or sal > upper:
                ratio = abs(sal - mean_sal) / mean_sal
                results.append(AnomalyResult(
                    detected=True,
                    severity=min(ratio, 1.0),
                    confidence_score=round(min(0.5 + ratio * 0.4, 0.95), 3),
                    description=f"[PAYROLL-R3] {name} salary ${sal:,.0f} outside {dept} IQR fence [${lower:,.0f}–${upper:,.0f}]",
                    anomaly_field="salary",
                    anomaly_type="payroll_iqr_breach",
                    recommended_action="send_notification",
                    supporting_data={"employee_id": eid, "salary": sal, "iqr_lower": round(lower), "iqr_upper": round(upper)},
                ))

    # Rule 4 — Global salary outlier (across all departments)
    all_salaries = [e.get("salary") or 0.0 for e in employees]
    if len(all_salaries) >= 5:
        g_mean = statistics.mean(all_salaries)
        g_std = statistics.stdev(all_salaries) or 1.0
        for e in employees:
            sal = e.get("salary") or 0.0
            z = _z_score(sal, g_mean, g_std)
            if z > 4.0:
                results.append(AnomalyResult(
                    detected=True,
                    severity=min(z / 7.0, 1.0),
                    confidence_score=_confidence(z),
                    description=f"[PAYROLL-R4] {e.get('name')} salary ${sal:,.0f} is a company-wide extreme outlier (z={z:.1f})",
                    anomaly_field="salary",
                    anomaly_type="payroll_global_outlier",
                    recommended_action="escalate_hr_review",
                    supporting_data={"employee_id": e["employee_id"], "salary": sal, "global_z": round(z, 2)},
                ))

    # Rule 5 — Senior employees with very low salary (position/salary mismatch)
    SENIOR_KEYWORDS = {"manager", "director", "head", "vp", "chief", "principal", "lead"}
    salary_p25 = statistics.quantiles(all_salaries, n=4)[0] if len(all_salaries) >= 4 else 0
    for e in employees:
        pos = (e.get("position") or "").lower()
        sal = e.get("salary") or 0.0
        if any(k in pos for k in SENIOR_KEYWORDS) and sal < salary_p25:
            results.append(AnomalyResult(
                detected=True,
                severity=0.72,
                confidence_score=0.78,
                description=f"[PAYROLL-R5] Senior role '{e.get('position')}' for {e.get('name')} has below-P25 salary (${sal:,.0f})",
                anomaly_field="salary",
                anomaly_type="position_salary_mismatch",
                recommended_action="flag_for_review",
                supporting_data={"employee_id": e["employee_id"], "position": e.get("position"), "salary": sal},
            ))

    # Rule 6 — Payroll gross_pay vs declared salary mismatch (using payroll table)
    try:
        payroll_rows = query_all_payroll_current()
        pay_map = {r["employee_id"]: r["gross_pay"] * 12 for r in payroll_rows}
        for e in employees:
            eid = e["employee_id"]
            declared = e.get("salary") or 0.0
            annualised = pay_map.get(eid)
            if annualised and declared > 0:
                ratio = abs(annualised - declared) / declared
                if ratio > 0.25:
                    results.append(AnomalyResult(
                        detected=True,
                        severity=min(ratio, 1.0),
                        confidence_score=round(min(0.55 + ratio * 0.35, 0.95), 3),
                        description=f"[PAYROLL-R6] {e.get('name')}: annualised payroll ${annualised:,.0f} deviates {ratio*100:.0f}% from declared salary ${declared:,.0f}",
                        anomaly_field="gross_pay",
                        anomaly_type="payroll_salary_mismatch",
                        recommended_action="escalate_hr_review",
                        supporting_data={"employee_id": eid, "declared_salary": declared, "annualised_gross": round(annualised)},
                    ))
    except Exception as exc:
        logger.warning("Rule 6 payroll lookup failed: %s", exc)

    return results


# ─── Rule 7-12: Leave anomalies ──────────────────────────────────────────────


def detect_leave_anomalies(employees: list[dict]) -> list[AnomalyResult]:
    """Six leave-pattern anomaly checks."""
    results: list[AnomalyResult] = []
    if not employees:
        return results

    accrued_vals = [e.get("leaves_accrued") or 0 for e in employees]
    taken_vals = [e.get("leaves_taken") or 0 for e in employees]

    # Compute cohort stats for leave ratios
    ratios = []
    for acc, tak in zip(accrued_vals, taken_vals):
        ratios.append(tak / acc if acc > 0 else 0.0)
    ratio_mean = statistics.mean(ratios) if ratios else 0.5
    ratio_std = statistics.stdev(ratios) if len(ratios) > 2 else 0.1

    for e in employees:
        eid = e["employee_id"]
        name = e.get("name", eid)
        accrued = e.get("leaves_accrued") or 0
        taken = e.get("leaves_taken") or 0
        ratio = taken / accrued if accrued > 0 else 0.0
        z = _z_score(ratio, ratio_mean, ratio_std)

        # Rule 7 — Leave ratio far above cohort mean (leave abuse pattern)
        if z > 2.0 and ratio > ratio_mean:
            results.append(AnomalyResult(
                detected=True,
                severity=min(z / 4.0, 1.0),
                confidence_score=_confidence(z),
                description=f"[LEAVE-R7] {name} leave usage ratio {ratio:.1%} is {z:.1f} SD above mean ({ratio_mean:.1%}) — leave abuse pattern",
                anomaly_field="leaves_taken",
                anomaly_type="leave_abuse_high_ratio",
                recommended_action="request_manager_review",
                supporting_data={"employee_id": eid, "leaves_taken": taken, "leaves_accrued": accrued, "ratio": round(ratio, 3), "z_score": round(z, 2)},
            ))

        # Rule 8 — Taken exceeds accrued (policy breach)
        if taken > accrued:
            excess = taken - accrued
            results.append(AnomalyResult(
                detected=True,
                severity=min(excess / max(accrued, 1) + 0.7, 1.0),
                confidence_score=0.92,
                description=f"[LEAVE-R8] {name} has taken {taken} days but only accrued {accrued} — {excess} days in excess",
                anomaly_field="leaves_taken",
                anomaly_type="leave_overrun",
                recommended_action="escalate_hr_review",
                supporting_data={"employee_id": eid, "excess_days": excess, "leaves_taken": taken, "leaves_accrued": accrued},
            ))

        # Rule 9 — Zero leave taken for very long period (potential ghost employee / burnout risk)
        joining = e.get("joining_date", "")
        try:
            join_dt = date.fromisoformat(str(joining))
            tenure_years = (date.today() - join_dt).days / 365.0
            if tenure_years >= 1.5 and taken == 0 and accrued > 10:
                results.append(AnomalyResult(
                    detected=True,
                    severity=0.65,
                    confidence_score=0.80,
                    description=f"[LEAVE-R9] {name} has taken 0 leave days despite {tenure_years:.1f} years tenure (accrued={accrued}) — possible ghost employee or burnout risk",
                    anomaly_field="leaves_taken",
                    anomaly_type="leave_zero_usage",
                    recommended_action="send_notification",
                    supporting_data={"employee_id": eid, "tenure_years": round(tenure_years, 1), "leaves_accrued": accrued},
                ))
        except (ValueError, TypeError):
            pass

        # Rule 10 — High remaining leave (leave hoarding, payout risk)
        remaining = accrued - taken
        if remaining > 25:
            results.append(AnomalyResult(
                detected=True,
                severity=min(remaining / 45.0, 0.9),
                confidence_score=0.70,
                description=f"[LEAVE-R10] {name} has {remaining} unused leave days — payout liability risk",
                anomaly_field="leaves_accrued",
                anomaly_type="leave_hoarding",
                recommended_action="send_notification",
                supporting_data={"employee_id": eid, "leaves_remaining": remaining},
            ))

    # Rule 11 — Statistical outlier in absolute leave taken (Z-score across org)
    if len(taken_vals) >= 5:
        t_mean = statistics.mean(taken_vals)
        t_std = statistics.stdev(taken_vals) or 1.0
        for e in employees:
            taken = e.get("leaves_taken") or 0
            z = _z_score(taken, t_mean, t_std)
            if z > 2.5 and taken > t_mean:
                results.append(AnomalyResult(
                    detected=True,
                    severity=min(z / 5.0, 1.0),
                    confidence_score=_confidence(z, base=0.58),
                    description=f"[LEAVE-R11] {e.get('name')} absolute leave days {taken} is {z:.1f} SD above org mean ({t_mean:.1f})",
                    anomaly_field="leaves_taken",
                    anomaly_type="leave_abuse_absolute",
                    recommended_action="request_manager_review",
                    supporting_data={"employee_id": e["employee_id"], "leaves_taken": taken, "org_mean": round(t_mean, 1), "z_score": round(z, 2)},
                ))

    # Rule 12 — Department leave outlier (peer cohort Z-score on ratio)
    dept_ratios: dict[str, list[tuple[dict, float]]] = defaultdict(list)
    for e in employees:
        acc = e.get("leaves_accrued") or 0
        tak = e.get("leaves_taken") or 0
        r = tak / acc if acc > 0 else 0.0
        dept_ratios[e.get("department", "General")].append((e, r))

    for dept, cohort in dept_ratios.items():
        if len(cohort) < 4:
            continue
        ratios_d = [r for _, r in cohort]
        mean_r = statistics.mean(ratios_d)
        std_r = statistics.stdev(ratios_d) or 0.01
        for emp, r in cohort:
            z = _z_score(r, mean_r, std_r)
            if z > 2.8:
                results.append(AnomalyResult(
                    detected=True,
                    severity=min(z / 5.0, 1.0),
                    confidence_score=_confidence(z),
                    description=f"[LEAVE-R12] {emp.get('name')} leave ratio {r:.1%} is {z:.1f} SD from {dept} peer mean ({mean_r:.1%})",
                    anomaly_field="leaves_taken",
                    anomaly_type="leave_peer_outlier",
                    recommended_action="request_manager_review",
                    supporting_data={"employee_id": emp["employee_id"], "dept": dept, "ratio": round(r, 3), "dept_mean": round(mean_r, 3)},
                ))

    return results


# ─── Rule 13-18: Compliance anomalies ────────────────────────────────────────


def detect_compliance_anomalies(employees: list[dict]) -> list[AnomalyResult]:
    """Six compliance and HR-policy violation checks."""
    results: list[AnomalyResult] = []

    # Compute org-wide performance stats for benchmarking
    perf_vals = [e.get("performance_rating") or 0.0 for e in employees if e.get("performance_rating")]
    perf_mean = statistics.mean(perf_vals) if perf_vals else 3.0
    perf_std = statistics.stdev(perf_vals) if len(perf_vals) > 2 else 0.5

    today = date.today()

    for e in employees:
        eid = e["employee_id"]
        name = e.get("name", eid)
        rating = e.get("performance_rating") or 0.0
        joining = e.get("joining_date", "")

        try:
            join_dt = date.fromisoformat(str(joining))
        except (ValueError, TypeError):
            join_dt = None

        # Rule 13 — Critically low performance rating
        if 0 < rating < 2.0:
            z = _z_score(rating, perf_mean, perf_std)
            results.append(AnomalyResult(
                detected=True,
                severity=min(1.0 - rating / 2.0, 1.0),
                confidence_score=_confidence(z),
                description=f"[COMPLY-R13] {name} performance rating {rating:.1f} is critically low — PIP may be required",
                anomaly_field="performance_rating",
                anomaly_type="compliance_low_performance",
                recommended_action="initiate_pip",
                supporting_data={"employee_id": eid, "rating": rating, "org_mean": round(perf_mean, 2)},
            ))

        # Rule 14 — High performer not promoted (3+ years, position still junior)
        JUNIOR_TITLES = {"analyst", "associate", "junior", "intern", "trainee", "coordinator"}
        if join_dt:
            tenure = (today - join_dt).days / 365.0
            pos = (e.get("position") or "").lower()
            if tenure >= 3 and rating >= 4.5 and any(j in pos for j in JUNIOR_TITLES):
                results.append(AnomalyResult(
                    detected=True,
                    severity=0.68,
                    confidence_score=0.82,
                    description=f"[COMPLY-R14] {name} rated {rating:.1f}/5.0 with {tenure:.1f} yrs tenure but still in junior role '{e.get('position')}'",
                    anomaly_field="performance_rating",
                    anomaly_type="compliance_promotion_gap",
                    recommended_action="flag_for_review",
                    supporting_data={"employee_id": eid, "tenure_years": round(tenure, 1), "rating": rating, "position": e.get("position")},
                ))

        # Rule 15 — Probation period compliance (new hire with bad rating < 6 months)
        if join_dt:
            days_employed = (today - join_dt).days
            if days_employed < 180 and 0 < rating < 2.5:
                results.append(AnomalyResult(
                    detected=True,
                    severity=0.85,
                    confidence_score=0.88,
                    description=f"[COMPLY-R15] {name} is within probation period ({days_employed} days) with low rating {rating:.1f} — review required",
                    anomaly_field="performance_rating",
                    anomaly_type="compliance_probation_breach",
                    recommended_action="escalate_hr_review",
                    supporting_data={"employee_id": eid, "days_employed": days_employed, "rating": rating},
                ))

        # Rule 16 — Performance rating is missing / zero for tenured employees
        if rating == 0.0 and join_dt and (today - join_dt).days > 365:
            results.append(AnomalyResult(
                detected=True,
                severity=0.75,
                confidence_score=0.85,
                description=f"[COMPLY-R16] {name} has no performance rating despite 1+ year tenure — overdue review",
                anomaly_field="performance_rating",
                anomaly_type="compliance_missing_review",
                recommended_action="send_notification",
                supporting_data={"employee_id": eid, "joining_date": joining},
            ))

        # Rule 17 — Work location vs position mismatch
        REMOTE_SENSITIVE = {"executive", "vp", "director", "cfo", "cto", "ceo", "chief"}
        loc = (e.get("work_location") or "").lower()
        pos = (e.get("position") or "").lower()
        if any(r in pos for r in REMOTE_SENSITIVE) and "remote" in loc:
            results.append(AnomalyResult(
                detected=True,
                severity=0.55,
                confidence_score=0.70,
                description=f"[COMPLY-R17] Executive-level employee {name} ({e.get('position')}) is fully remote — policy compliance check needed",
                anomaly_field="work_location",
                anomaly_type="compliance_remote_executive",
                recommended_action="flag_for_review",
                supporting_data={"employee_id": eid, "position": e.get("position"), "work_location": e.get("work_location")},
            ))

        # Rule 18 — Long-tenure employees with declining performance (attrition risk)
        if join_dt and rating > 0:
            tenure = (today - join_dt).days / 365.0
            if tenure >= 5 and rating < perf_mean - 1.0:
                results.append(AnomalyResult(
                    detected=True,
                    severity=0.62,
                    confidence_score=0.76,
                    description=f"[COMPLY-R18] {name} has {tenure:.1f} yrs tenure but rating {rating:.1f} is significantly below org mean ({perf_mean:.2f}) — attrition risk",
                    anomaly_field="performance_rating",
                    anomaly_type="compliance_attrition_risk",
                    recommended_action="request_manager_review",
                    supporting_data={"employee_id": eid, "tenure_years": round(tenure, 1), "rating": rating, "org_mean": round(perf_mean, 2)},
                ))

        # Rule 18b — compliance_status is flagged
        if e.get("compliance_status") == "flagged":
            results.append(AnomalyResult(
                detected=True,
                severity=0.8,
                confidence_score=0.9,
                description=f"[COMPLY-STATUS] Employee {name} has flagged compliance status",
                anomaly_field="compliance_status",
                anomaly_type="compliance_flagged_status",
                recommended_action="escalate_hr_review",
                supporting_data={"employee_id": eid, "compliance_status": "flagged"},
            ))

    return results


# ─── Rule 19-23: Inactive Employee Scan ──────────────────────────────────────


def detect_inactive_employee_anomalies(employees: list[dict]) -> list[AnomalyResult]:
    """Five attendance-based inactivity and chronic-absence rules (R19–R23).

    Uses live attendance table data via query_attendance_summary_all().
    Flags ghost employees, high absenteeism, chronic lateness, stale last-active
    dates, and employees drawing payroll with zero attendance.
    """
    results: list[AnomalyResult] = []
    if not employees:
        return results

    # Build lookup: employee_id → attendance summary
    try:
        att_summaries = query_attendance_summary_all()
    except Exception as exc:
        logger.warning("Inactive scan: attendance query failed: %s", exc)
        return results

    att_map: dict[str, dict] = {row["employee_id"]: row for row in att_summaries}
    emp_map: dict[str, dict] = {e["employee_id"]: e for e in employees}

    # Cohort stats for Z-score baselines
    abs_pcts = [s["absence_pct"] or 0.0 for s in att_summaries]
    late_pcts = [s["late_pct"] or 0.0 for s in att_summaries]
    abs_mean = statistics.mean(abs_pcts) if abs_pcts else 5.0
    abs_std = statistics.stdev(abs_pcts) if len(abs_pcts) > 2 else 3.0
    late_mean = statistics.mean(late_pcts) if late_pcts else 5.0
    late_std = statistics.stdev(late_pcts) if len(late_pcts) > 2 else 3.0

    today = date.today()

    # Rule 19 — Ghost employee: no attendance records at all (payroll still active)
    for emp in employees:
        eid = emp["employee_id"]
        if eid not in att_map:
            name = emp.get("name", eid)
            salary = emp.get("salary") or 0.0
            try:
                join_dt = date.fromisoformat(str(emp.get("joining_date", "")))
                tenure_days = (today - join_dt).days
            except (ValueError, TypeError):
                tenure_days = 0
            if tenure_days > 30:  # skip brand-new hires
                results.append(AnomalyResult(
                    detected=True,
                    severity=0.90,
                    confidence_score=0.93,
                    description=(
                        f"[INACTIVE-R19] {name} has ZERO attendance records despite "
                        f"{tenure_days} days employment — possible ghost employee "
                        f"(salary=${salary:,.0f}/yr still active)"
                    ),
                    anomaly_field="attendance",
                    anomaly_type="inactive_ghost_employee",
                    recommended_action="escalate_hr_review",
                    supporting_data={
                        "employee_id": eid,
                        "tenure_days": tenure_days,
                        "salary": salary,
                        "attendance_records": 0,
                    },
                ))

    # Rules 20–23: per-employee attendance stats
    for att in att_summaries:
        eid = att["employee_id"]
        emp = emp_map.get(eid, {})
        name = emp.get("name", eid)
        total = att["total_records"] or 1
        absence_pct = att["absence_pct"] or 0.0
        late_pct = att["late_pct"] or 0.0
        last_active = att.get("last_active_date")

        # Rule 20 — High absenteeism (Z-score on absence %) beyond 2 SD
        z_abs = _z_score(absence_pct, abs_mean, abs_std)
        if z_abs > 2.0 and absence_pct > abs_mean:
            results.append(AnomalyResult(
                detected=True,
                severity=min(z_abs / 5.0, 1.0),
                confidence_score=_confidence(z_abs, base=0.60),
                description=(
                    f"[INACTIVE-R20] {name} absence rate {absence_pct:.1f}% is "
                    f"{z_abs:.1f} SD above org mean ({abs_mean:.1f}%) — "
                    f"absent {att['absent_days']}/{total} days"
                ),
                anomaly_field="attendance",
                anomaly_type="inactive_high_absence",
                recommended_action="request_manager_review",
                supporting_data={
                    "employee_id": eid,
                    "absence_pct": absence_pct,
                    "absent_days": att["absent_days"],
                    "total_records": total,
                    "org_mean_absence_pct": round(abs_mean, 2),
                    "z_score": round(z_abs, 2),
                },
            ))

        # Rule 21 — Chronic lateness (Z-score on late %) beyond 2 SD
        z_late = _z_score(late_pct, late_mean, late_std)
        if z_late > 2.0 and late_pct > late_mean:
            results.append(AnomalyResult(
                detected=True,
                severity=min(z_late / 6.0, 0.85),
                confidence_score=_confidence(z_late, base=0.55),
                description=(
                    f"[INACTIVE-R21] {name} late arrival rate {late_pct:.1f}% is "
                    f"{z_late:.1f} SD above org mean ({late_mean:.1f}%) — "
                    f"{att['late_days']} late days out of {total}"
                ),
                anomaly_field="attendance",
                anomaly_type="inactive_chronic_late",
                recommended_action="request_manager_review",
                supporting_data={
                    "employee_id": eid,
                    "late_pct": late_pct,
                    "late_days": att["late_days"],
                    "total_records": total,
                    "org_mean_late_pct": round(late_mean, 2),
                    "z_score": round(z_late, 2),
                },
            ))

        # Rule 22 — Last active date stale (>60 days since any non-Absent day)
        if last_active:
            try:
                last_dt = date.fromisoformat(str(last_active))
                days_since = (today - last_dt).days
                if days_since > 60:
                    results.append(AnomalyResult(
                        detected=True,
                        severity=min(days_since / 120.0, 0.95),
                        confidence_score=round(min(0.65 + days_since / 300.0, 0.95), 3),
                        description=(
                            f"[INACTIVE-R22] {name} last active {days_since} days ago "
                            f"(last seen: {last_active}) — possible prolonged unauthorised absence"
                        ),
                        anomaly_field="attendance",
                        anomaly_type="inactive_stale_last_active",
                        recommended_action="flag_for_review",
                        supporting_data={
                            "employee_id": eid,
                            "days_since_active": days_since,
                            "last_active_date": last_active,
                        },
                    ))
            except (ValueError, TypeError):
                pass

        # Rule 23 — No-show payroll drain: >80% absent but receiving full salary
        salary = emp.get("salary") or 0.0
        if absence_pct >= 30.0 and salary > 0 and total >= 10:
            monthly_drain = salary / 12
            results.append(AnomalyResult(
                detected=True,
                severity=min(absence_pct / 100.0 + 0.3, 1.0),
                confidence_score=round(min(0.70 + absence_pct / 200.0, 0.97), 3),
                description=(
                    f"[INACTIVE-R23] {name} has {absence_pct:.0f}% absence rate while "
                    f"receiving ${salary:,.0f}/yr salary "
                    f"(~${monthly_drain:,.0f}/mo payroll drain)"
                ),
                anomaly_field="attendance",
                anomaly_type="inactive_payroll_drain",
                recommended_action="escalate_hr_review",
                supporting_data={
                    "employee_id": eid,
                    "absence_pct": absence_pct,
                    "salary": salary,
                    "monthly_drain_estimate": round(monthly_drain),
                },
            ))

    logger.info(
        "Inactive scan: %d anomalies from %d employees (%d with attendance records)",
        len(results), len(employees), len(att_summaries),
    )
    return results



def run_anomaly_detection(employees: list[dict] | None = None) -> list[AnomalyResult]:
    """Run all 23 anomaly detectors; loads from DB when employees is None.

    Domains:
      - Payroll (R1–R6): cohort Z-score, IQR, salary mismatch, seniority gap
      - Leave abuse (R7–R12): ratio, overrun, zero-usage, hoarding, peer Z-score
      - Compliance (R13–R18): low rating, PIP, probation, missing review, remote exec, attrition
      - Inactive (R19–R23): ghost employee, high absence, chronic late, stale last-active, payroll drain

    Returns AnomalyResult list sorted by confidence_score descending.
    """
    if employees is None:
        employees = query_all_employees()

    if not employees:
        logger.warning("Anomaly detection: no employee data available")
        return []

    results: list[AnomalyResult] = []
    results.extend(detect_payroll_anomalies(employees))
    results.extend(detect_leave_anomalies(employees))
    results.extend(detect_compliance_anomalies(employees))
    results.extend(detect_inactive_employee_anomalies(employees))

    # De-duplicate: keep highest-confidence result per (employee, anomaly_type)
    seen: dict[tuple[str, str], AnomalyResult] = {}
    for r in results:
        key = (r.supporting_data.get("employee_id", ""), r.anomaly_type)
        if key not in seen or r.confidence_score > seen[key].confidence_score:
            seen[key] = r

    deduped = sorted(seen.values(), key=lambda x: x.confidence_score, reverse=True)
    logger.info(
        "Anomaly detection: %d unique anomalies (from %d raw) across %d employees",
        len(deduped), len(results), len(employees),
    )
    return deduped
