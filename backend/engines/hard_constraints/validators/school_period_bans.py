"""SCH-PB -- school_period_bans validator.

Adapter for school-level rule_key bans (no_first_period / no_last_period /
no_period_n) seeded into ``ctx.settings['school_period_bans']`` by the
engine before placement. Not seeded in ``timetable_hard_constraints`` —
this validator is opted-in by the engine when banning rows exist.
"""

from typing import Any, Dict, List, Optional

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def _check(record: Dict[str, Any], session: Dict[str, Any]) -> bool:
    if session.get("period_number") != record.get("period_number"):
        return False
    rec_subject = record.get("subject_id")
    if rec_subject is None:
        return True
    return session.get("subject_id") == rec_subject


def _make_violation(record: Dict[str, Any], session: Dict[str, Any]) -> ConstraintViolation:
    return ConstraintViolation(
        code=META.code,
        validation_key=META.validation_key,
        severity=META.severity,
        message_en=(
            f"Subject {session.get('subject_id')} blocked from period "
            f"{record.get('period_number')} by school rule {record.get('rule_key')}"
        ),
        message_ar=(
            f"المادة {session.get('subject_id')} ممنوعة في الحصة "
            f"{record.get('period_number')} بحسب القاعدة المدرسية {record.get('rule_key')}"
        ),
        refs={
            "rule_key": record.get("rule_key"),
            "subject_id": session.get("subject_id"),
            "period_number": record.get("period_number"),
            "session_id": session.get("id"),
        },
        tier="placement",
    )


def validate(
    ctx: ConstraintContext, candidate: Optional[Dict[str, Any]] = None
) -> List[ConstraintViolation]:
    bans = ctx.settings.get("school_period_bans", []) or []
    if not bans:
        return []
    targets = [candidate] if candidate is not None else list(ctx.sessions)
    violations: List[ConstraintViolation] = []
    for session in targets:
        if not session:
            continue
        for record in bans:
            if _check(record, session):
                violations.append(_make_violation(record, session))
    return violations


META = ValidatorMeta(
    code="SCH-PB",
    validation_key="school_period_bans",
    severity=ConflictSeverity.HIGH,
    tier="placement",
    fn=validate,
)
