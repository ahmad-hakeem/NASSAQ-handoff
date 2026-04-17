"""HC-04 -- school_day_boundary validator."""

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
    period = candidate.get("period_number")
    allowed = ctx.settings.get("active_period_range")
    if allowed is None:
        allowed = {ts.get("period_number") for ts in ctx.time_slots if ts.get("period_number") is not None}
    else:
        allowed = set(allowed)
    if period in allowed:
        return []
    return [ConstraintViolation(
        code="HC-04",
        validation_key="school_day_boundary",
        severity=ConflictSeverity.HIGH,
        message_en=f"Period {period} is outside the school day boundary",
        message_ar=f"الحصة {period} خارج حدود اليوم الدراسي",
        refs={"period_number": period},
        tier="placement",
    )]


META = ValidatorMeta(
    code="HC-04",
    validation_key="school_day_boundary",
    severity=ConflictSeverity.HIGH,
    tier="placement",
    fn=validate,
)
