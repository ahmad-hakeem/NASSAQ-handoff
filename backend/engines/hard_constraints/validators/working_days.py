"""HC-07 -- working_days validator."""

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
    allowed = ctx.settings.get("working_days")
    if allowed is None:
        allowed = {ts.get("day_of_week") for ts in ctx.time_slots if ts.get("day_of_week")}
    else:
        allowed = set(allowed)
    if not allowed or day in allowed:
        return []
    return [ConstraintViolation(
        code="HC-07",
        validation_key="working_days",
        severity=ConflictSeverity.HIGH,
        message_en=f"Day {day} is not a working day",
        message_ar=f"اليوم {day} ليس يوم عمل",
        refs={"day_of_week": day},
        tier="placement",
    )]


META = ValidatorMeta(
    code="HC-07",
    validation_key="working_days",
    severity=ConflictSeverity.HIGH,
    tier="placement",
    fn=validate,
)
