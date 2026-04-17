"""HC-03 -- room_overlap validator."""

from typing import Any, Dict, List, Optional

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def _slot_key(session: Dict[str, Any]):
    return (
        session.get("room_id"),
        session.get("day_of_week"),
        session.get("period_number"),
    )


def _make_violation(session_ids, room_id, day, period) -> ConstraintViolation:
    return ConstraintViolation(
        code=META.code,
        validation_key=META.validation_key,
        severity=META.severity,
        message_en=f"Room {room_id} is double-booked on day {day} period {period}",
        message_ar=f"القاعة {room_id} لديها تعارض في اليوم {day} الحصة {period}",
        refs={
            "session_ids": session_ids,
            "room_id": room_id,
            "day_of_week": day,
            "period_number": period,
        },
        tier="placement",
    )


def validate(
    ctx: ConstraintContext, candidate: Optional[Dict[str, Any]] = None
) -> List[ConstraintViolation]:
    if candidate is not None:
        if not candidate.get("room_id"):
            return []
        key = _slot_key(candidate)
        for s in ctx.sessions:
            if not s.get("room_id"):
                continue
            if s.get("id") and s.get("id") == candidate.get("id"):
                continue
            if _slot_key(s) == key:
                return [_make_violation(
                    [s.get("id"), candidate.get("id")], key[0], key[1], key[2]
                )]
        return []

    groups: Dict[Any, List[Dict[str, Any]]] = {}
    for s in ctx.sessions:
        if not s.get("room_id"):
            continue
        groups.setdefault(_slot_key(s), []).append(s)

    violations: List[ConstraintViolation] = []
    for key, group in groups.items():
        if len(group) > 1:
            ids = [g.get("id") for g in group]
            violations.append(_make_violation(ids, key[0], key[1], key[2]))
    return violations


META = ValidatorMeta(
    code="HC-03",
    validation_key="room_overlap",
    severity=ConflictSeverity.CRITICAL,
    tier="placement",
    fn=validate,
)
