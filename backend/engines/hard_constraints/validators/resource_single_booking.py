"""HC-13 -- resource_single_booking validator."""

from collections import defaultdict
from typing import List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def validate(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    bookings = defaultdict(list)
    for s in ctx.sessions:
        rid = s.get("required_resource_id")
        if not rid:
            continue
        key = (rid, s.get("day_of_week"), s.get("period_number"))
        bookings[key].append(s)

    if candidate is not None:
        rid = candidate.get("required_resource_id")
        if not rid:
            return []
        key = (rid, candidate.get("day_of_week"), candidate.get("period_number"))
        if bookings.get(key):
            return [ConstraintViolation(
                code="HC-13", validation_key="resource_single_booking",
                severity=ConflictSeverity.HIGH,
                message_en=f"Resource {rid} double-booked at {key[1]}/{key[2]}",
                message_ar=f"المورد {rid} محجوز مرتين في {key[1]}/{key[2]}",
                refs={"resource_id": rid, "day_of_week": key[1], "period_number": key[2]},
                tier="placement",
            )]
        return []

    violations: List[ConstraintViolation] = []
    for (rid, day, period), items in bookings.items():
        if len(items) > 1:
            violations.append(ConstraintViolation(
                code="HC-13", validation_key="resource_single_booking",
                severity=ConflictSeverity.HIGH,
                message_en=f"Resource {rid} double-booked at {day}/{period}",
                message_ar=f"المورد {rid} محجوز مرتين في {day}/{period}",
                refs={"resource_id": rid, "day_of_week": day, "period_number": period, "count": len(items)},
                tier="placement",
            ))
    return violations


META = ValidatorMeta(
    code="HC-13",
    validation_key="resource_single_booking",
    severity=ConflictSeverity.HIGH,
    tier="placement",
    fn=validate,
)
