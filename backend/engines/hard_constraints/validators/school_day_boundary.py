"""HC-04 -- school_day_boundary validator."""

from typing import List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def _slot_period(ts):
    # time_slots rows are not uniform across schools: real-school slots
    # store the period index under ``slot_number`` (with no
    # ``period_number``/``period`` key at all), while the engine derives
    # candidate ``period_number`` via the same triple fallback
    # (see SmartSchedulingEngine._build_constraint_context). Resolve the
    # boundary the same way so the allowed set is never silently empty.
    return ts.get("period_number") or ts.get("period") or ts.get("slot_number")


def validate(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    if candidate is None:
        return []
    period = candidate.get("period_number")
    allowed = ctx.settings.get("active_period_range")
    if allowed is None:
        allowed = {_slot_period(ts) for ts in ctx.time_slots}
        allowed.discard(None)
    else:
        allowed = set(allowed)
    # Fail open when no boundary is resolvable (no time slots / no period
    # info) rather than rejecting every candidate — mirrors the
    # working_days (HC-07) validator. An empty allowed set must never be
    # treated as "no period is valid".
    if not allowed or period in allowed:
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
