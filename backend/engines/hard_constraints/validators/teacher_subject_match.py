"""HC-11 -- teacher_subject_match validator."""

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
    teacher_id = candidate.get("teacher_id")
    subject_id = candidate.get("subject_id")
    if not teacher_id or not subject_id:
        return []
    teacher = ctx.resources.get("teachers", {}).get(teacher_id)
    if not teacher:
        return []
    quals = teacher.get("qualifications") or []
    if not quals:
        return []
    if subject_id in quals:
        return []
    return [ConstraintViolation(
        code="HC-11",
        validation_key="teacher_subject_match",
        severity=ConflictSeverity.MEDIUM,
        message_en=f"Teacher {teacher_id} not qualified for subject {subject_id}",
        message_ar=f"المعلم {teacher_id} غير مؤهل لتدريس {subject_id}",
        refs={"teacher_id": teacher_id, "subject_id": subject_id},
        tier="placement",
    )]


META = ValidatorMeta(
    code="HC-11",
    validation_key="teacher_subject_match",
    severity=ConflictSeverity.MEDIUM,
    tier="placement",
    fn=validate,
)
