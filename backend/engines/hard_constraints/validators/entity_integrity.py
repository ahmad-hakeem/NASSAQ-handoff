"""HC-16 -- entity_integrity validator."""

from typing import Any, Dict, List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def _check(ctx: ConstraintContext, session: Dict[str, Any]) -> List[ConstraintViolation]:
    violations: List[ConstraintViolation] = []
    fk_map = [
        ("teacher_id", "teachers"),
        ("class_id", "classes"),
        ("subject_id", "subjects"),
    ]
    for field, bucket in fk_map:
        value = session.get(field)
        if value is None:
            violations.append(ConstraintViolation(
                code="HC-16", validation_key="entity_integrity",
                severity=ConflictSeverity.CRITICAL,
                message_en=f"Missing {field}",
                message_ar=f"الحقل {field} مفقود",
                refs={"field": field, "value": None},
                tier="placement",
            ))
            continue
        if value not in ctx.resources.get(bucket, {}):
            violations.append(ConstraintViolation(
                code="HC-16", validation_key="entity_integrity",
                severity=ConflictSeverity.CRITICAL,
                message_en=f"Orphan {field}={value}",
                message_ar=f"مرجع غير صالح {field}={value}",
                refs={"field": field, "value": value},
                tier="placement",
            ))
    room_id = session.get("room_id")
    if room_id is not None and room_id not in ctx.resources.get("rooms", {}):
        violations.append(ConstraintViolation(
            code="HC-16", validation_key="entity_integrity",
            severity=ConflictSeverity.CRITICAL,
            message_en=f"Orphan room_id={room_id}",
            message_ar=f"مرجع قاعة غير صالح={room_id}",
            refs={"field": "room_id", "value": room_id},
            tier="placement",
        ))
    return violations


def validate(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    if candidate is not None:
        return _check(ctx, candidate)
    out: List[ConstraintViolation] = []
    for s in ctx.sessions:
        out.extend(_check(ctx, s))
    return out


META = ValidatorMeta(
    code="HC-16",
    validation_key="entity_integrity",
    severity=ConflictSeverity.CRITICAL,
    tier="placement",
    fn=validate,
)
