"""HC-06 -- daily_period_limit validator."""

from typing import Any, Dict, List, Optional

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def _make_violation(teacher_id, day, count, limit) -> ConstraintViolation:
    return ConstraintViolation(
        code=META.code,
        validation_key=META.validation_key,
        severity=META.severity,
        message_en=(
            f"Teacher {teacher_id} has {count} sessions on day {day}, exceeding daily limit {limit}"
        ),
        message_ar=(
            f"المعلم {teacher_id} لديه {count} حصص في اليوم {day} متجاوزاً الحد {limit}"
        ),
        refs={
            "teacher_id": teacher_id,
            "day_of_week": day,
            "count": count,
            "limit": limit,
        },
        tier="placement",
    )


def validate(
    ctx: ConstraintContext, candidate: Optional[Dict[str, Any]] = None
) -> List[ConstraintViolation]:
    limit = int(ctx.settings.get("max_daily_periods", 6))
    counter: Dict[Any, int] = {}
    sessions = list(ctx.sessions)
    if candidate is not None:
        sessions.append(candidate)
    for s in sessions:
        teacher_id = s.get("teacher_id")
        day = s.get("day_of_week")
        if teacher_id is None or day is None:
            continue
        counter[(teacher_id, day)] = counter.get((teacher_id, day), 0) + 1

    violations: List[ConstraintViolation] = []
    if candidate is not None:
        teacher_id = candidate.get("teacher_id")
        day = candidate.get("day_of_week")
        if teacher_id is not None and day is not None:
            count = counter.get((teacher_id, day), 0)
            if count > limit:
                violations.append(_make_violation(teacher_id, day, count, limit))
        return violations

    for (teacher_id, day), count in counter.items():
        if count > limit:
            violations.append(_make_violation(teacher_id, day, count, limit))
    return violations


META = ValidatorMeta(
    code="HC-06",
    validation_key="daily_period_limit",
    severity=ConflictSeverity.HIGH,
    tier="placement",
    fn=validate,
)
