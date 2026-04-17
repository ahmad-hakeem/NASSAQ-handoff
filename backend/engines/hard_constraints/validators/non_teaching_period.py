"""HC-05 -- non_teaching_period validator."""

from typing import List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def validate(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    if candidate is None:
        return []
    day = candidate.get("day_of_week")
    period = candidate.get("period_number")
    for ts in ctx.time_slots:
        if ts.get("day_of_week") == day and ts.get("period_number") == period:
            if ts.get("is_break") or ts.get("is_prayer"):
                return [ConstraintViolation(
                    code="HC-05",
                    validation_key="non_teaching_period",
                    severity=ConflictSeverity.HIGH,
                    message_en=f"Cannot place session during non-teaching period {day}/{period}",
                    message_ar=f"لا يمكن وضع حصة في فترة غير دراسية {day}/{period}",
                    refs={"day_of_week": day, "period_number": period},
                    tier="placement",
                )]
    return []


META = ValidatorMeta(
    code="HC-05",
    validation_key="non_teaching_period",
    severity=ConflictSeverity.HIGH,
    tier="placement",
    fn=validate,
)
