"""HC-12 -- teacher_class_assignment validator."""

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
    class_id = candidate.get("class_id")
    subject_id = candidate.get("subject_id")
    if not teacher_id or not class_id or not subject_id:
        return []
    assignments = ctx.resources.get("teacher_assignments", set())
    if (teacher_id, class_id, subject_id) in assignments:
        return []
    return [ConstraintViolation(
        code="HC-12",
        validation_key="teacher_class_assignment",
        severity=ConflictSeverity.HIGH,
        message_en=f"Teacher {teacher_id} not assigned to class {class_id} for subject {subject_id}",
        message_ar=f"المعلم {teacher_id} غير مسند للفصل {class_id} في المادة {subject_id}",
        refs={"teacher_id": teacher_id, "class_id": class_id, "subject_id": subject_id},
        tier="placement",
    )]


META = ValidatorMeta(
    code="HC-12",
    validation_key="teacher_class_assignment",
    severity=ConflictSeverity.HIGH,
    tier="placement",
    fn=validate,
)
