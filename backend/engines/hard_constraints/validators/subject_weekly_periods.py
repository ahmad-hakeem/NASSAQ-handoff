"""HC-09 -- subject_weekly_periods informational validator.

Weekly subject counts are curriculum guidance, not a timetable integrity
constraint.  A mismatch is retained as a publish-time warning so principals
can review it, but it must never make an otherwise valid timetable
unpublishable.
"""

from typing import Any, Dict, List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def validate(ctx: ConstraintContext) -> List[ConstraintViolation]:
    counter: Dict[Any, int] = {}
    for s in ctx.sessions:
        cls = s.get("class_id")
        subj = s.get("subject_id")
        if not cls or not subj:
            continue
        counter[(cls, subj)] = counter.get((cls, subj), 0) + 1

    violations: List[ConstraintViolation] = []
    for demand in ctx.demands:
        cls = demand.get("class_id")
        subj = demand.get("subject_id")
        expected = int(demand.get("weekly_periods", 0))
        actual = counter.get((cls, subj), 0)
        if actual == expected:
            continue
        delta = actual - expected
        # Both over- and under-placement are planning signals.  Neither is a
        # timetable integrity failure, so both remain non-blocking MEDIUM
        # warnings.  Structural/resource validators (including teacher load)
        # continue to emit their own blocking severities.
        severity = META.severity
        violations.append(ConstraintViolation(
            code=META.code,
            validation_key=META.validation_key,
            severity=severity,
            message_en=(
                f"Class {cls} subject {subj}: expected {expected} weekly periods, found {actual}"
            ),
            message_ar=(
                f"الفصل {cls} المادة {subj}: المتوقع {expected} حصص أسبوعياً والفعلي {actual}"
            ),
            refs={
                "class_id": cls,
                "subject_id": subj,
                "expected": expected,
                "actual": actual,
                "delta": delta,
            },
            tier="full",
        ))
    return violations


META = ValidatorMeta(
    code="HC-09",
    validation_key="subject_weekly_periods",
    severity=ConflictSeverity.MEDIUM,
    tier="full",
    fn=validate,
)
