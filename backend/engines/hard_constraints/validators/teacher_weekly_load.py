"""HC-08 -- teacher_weekly_load validator."""

from collections import Counter
from typing import List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def validate(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    teachers = ctx.resources.get("teachers", {})
    counts = Counter(s.get("teacher_id") for s in ctx.sessions if s.get("teacher_id"))
    violations: List[ConstraintViolation] = []
    for teacher_id, count in counts.items():
        resource = teachers.get(teacher_id)
        if not resource:
            continue
        limit = resource.get("weekly_load")
        if limit is None:
            continue
        if count > limit:
            violations.append(ConstraintViolation(
                code="HC-08",
                validation_key="teacher_weekly_load",
                severity=ConflictSeverity.HIGH,
                message_en=f"Teacher {teacher_id} weekly load {count} exceeds limit {limit}",
                message_ar=f"النصاب الأسبوعي للمعلم {teacher_id} ({count}) يتجاوز الحد ({limit})",
                refs={"teacher_id": teacher_id, "count": count, "limit": limit},
                tier="full",
            ))
    return violations


META = ValidatorMeta(
    code="HC-08",
    validation_key="teacher_weekly_load",
    severity=ConflictSeverity.HIGH,
    tier="full",
    fn=validate,
)
