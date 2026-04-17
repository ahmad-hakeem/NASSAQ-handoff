"""HC-01 -- teacher_overlap validator."""

from typing import Any, Dict, List, Optional

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def _slot_key(session: Dict[str, Any]):
    return (
        session.get("teacher_id"),
        session.get("day_of_week"),
        session.get("period_number"),
    )


def _make_violation(session_ids: List[str], teacher_id, day, period) -> ConstraintViolation:
    return ConstraintViolation(
        code=META.code,
        validation_key=META.validation_key,
        severity=META.severity,
        message_en=f"Teacher {teacher_id} is booked twice on day {day} period {period}",
        message_ar=f"المعلم {teacher_id} لديه تعارض في اليوم {day} الحصة {period}",
        refs={
            "session_ids": session_ids,
            "teacher_id": teacher_id,
            "day_of_week": day,
            "period_number": period,
        },
        tier="placement",
    )


def validate(
    ctx: ConstraintContext, candidate: Optional[Dict[str, Any]] = None
) -> List[ConstraintViolation]:
    if candidate is not None:
        if not candidate.get("teacher_id"):
            return []
        key = _slot_key(candidate)
        for s in ctx.sessions:
            if s.get("id") and s.get("id") == candidate.get("id"):
                continue
            if _slot_key(s) == key:
                return [_make_violation(
                    [s.get("id"), candidate.get("id")], key[0], key[1], key[2]
                )]
        return []

    groups: Dict[Any, List[Dict[str, Any]]] = {}
    for s in ctx.sessions:
        if not s.get("teacher_id"):
            continue
        groups.setdefault(_slot_key(s), []).append(s)

    violations: List[ConstraintViolation] = []
    for key, group in groups.items():
        if len(group) > 1:
            ids = [g.get("id") for g in group]
            violations.append(_make_violation(ids, key[0], key[1], key[2]))
    return violations


META = ValidatorMeta(
    code="HC-01",
    validation_key="teacher_overlap",
    severity=ConflictSeverity.CRITICAL,
    tier="placement",
    fn=validate,
)
