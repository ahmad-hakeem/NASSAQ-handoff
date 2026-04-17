"""HC-15 -- academic_structure_match validator."""

from typing import List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def validate(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    classes = ctx.resources.get("classes", {})
    violations: List[ConstraintViolation] = []
    for s in ctx.sessions:
        cid = s.get("class_id")
        sid = s.get("subject_id")
        if not cid or not sid:
            continue
        cls = classes.get(cid)
        if not cls:
            continue
        curriculum = cls.get("curriculum_subject_ids")
        if not curriculum:
            continue
        if sid not in curriculum:
            violations.append(ConstraintViolation(
                code="HC-15",
                validation_key="academic_structure_match",
                severity=ConflictSeverity.MEDIUM,
                message_en=f"Subject {sid} not in curriculum for class {cid}",
                message_ar=f"المادة {sid} ليست ضمن منهج الفصل {cid}",
                refs={"class_id": cid, "subject_id": sid},
                tier="full",
            ))
    return violations


META = ValidatorMeta(
    code="HC-15",
    validation_key="academic_structure_match",
    severity=ConflictSeverity.MEDIUM,
    tier="full",
    fn=validate,
)
