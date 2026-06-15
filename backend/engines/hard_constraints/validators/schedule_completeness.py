"""HC-14 -- schedule_completeness validator."""

from collections import Counter, defaultdict
from typing import List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def validate(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    counts = Counter((s.get("class_id"), s.get("subject_id")) for s in ctx.sessions)
    missing_by_class = defaultdict(list)
    for demand in ctx.demands:
        cid = demand.get("class_id")
        sid = demand.get("subject_id")
        expected = demand.get("weekly_periods", 0)
        actual = counts.get((cid, sid), 0)
        if actual < expected:
            missing_by_class[cid].append({
                "subject_id": sid,
                "expected": expected,
                "actual": actual,
                "missing": expected - actual,
            })

    violations: List[ConstraintViolation] = []
    for cid, missing in missing_by_class.items():
        # Incompleteness (a class missing some required periods) is often
        # unavoidable real-world infeasibility — teacher availability and
        # other hard constraints can prevent fitting every period. Per the
        # product decision it is surfaced as a non-blocking warning (MEDIUM)
        # rather than blocking publish; the missing periods are still shown
        # to principals as insights. Over-placement remains a hard error in
        # HC-09 (subject_weekly_periods).
        violations.append(ConstraintViolation(
            code="HC-14",
            validation_key="schedule_completeness",
            severity=ConflictSeverity.MEDIUM,
            message_en=f"Class {cid} schedule is incomplete",
            message_ar=f"جدول الفصل {cid} غير مكتمل",
            refs={"class_id": cid, "missing_subjects": missing},
            tier="full",
        ))
    return violations


META = ValidatorMeta(
    code="HC-14",
    validation_key="schedule_completeness",
    severity=ConflictSeverity.MEDIUM,
    tier="full",
    fn=validate,
)
