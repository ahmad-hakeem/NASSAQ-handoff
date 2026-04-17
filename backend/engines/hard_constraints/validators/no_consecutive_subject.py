"""HC-10 -- no_consecutive_subject validator."""

from collections import defaultdict
from typing import List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def validate(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    overrides = ctx.settings.get("hard_constraint_overrides", {}).get("HC-10", {})
    if overrides.get("disabled"):
        return []

    by_key = defaultdict(set)
    for s in ctx.sessions:
        cid = s.get("class_id")
        sid = s.get("subject_id")
        day = s.get("day_of_week")
        per = s.get("period_number")
        if cid is None or sid is None or day is None or per is None:
            continue
        by_key[(cid, sid, day)].add(per)

    if candidate is not None:
        cid = candidate.get("class_id")
        sid = candidate.get("subject_id")
        day = candidate.get("day_of_week")
        per = candidate.get("period_number")
        if cid is not None and sid is not None and day is not None and per is not None:
            existing = by_key.get((cid, sid, day), set())
            if (per - 1) in existing or (per + 1) in existing:
                return [ConstraintViolation(
                    code="HC-10", validation_key="no_consecutive_subject",
                    severity=ConflictSeverity.MEDIUM,
                    message_en=f"Consecutive {sid} for class {cid} on {day}",
                    message_ar=f"المادة {sid} للفصل {cid} في حصص متتالية يوم {day}",
                    refs={"class_id": cid, "subject_id": sid, "day_of_week": day, "period_number": per},
                    tier="placement",
                )]
            return []

    violations: List[ConstraintViolation] = []
    for (cid, sid, day), periods in by_key.items():
        sorted_p = sorted(periods)
        for i in range(len(sorted_p) - 1):
            if sorted_p[i + 1] == sorted_p[i] + 1:
                violations.append(ConstraintViolation(
                    code="HC-10", validation_key="no_consecutive_subject",
                    severity=ConflictSeverity.MEDIUM,
                    message_en=f"Consecutive {sid} for class {cid} on {day} at periods {sorted_p[i]}-{sorted_p[i+1]}",
                    message_ar=f"المادة {sid} للفصل {cid} يوم {day} في حصص متتالية",
                    refs={"class_id": cid, "subject_id": sid, "day_of_week": day, "periods": [sorted_p[i], sorted_p[i+1]]},
                    tier="placement",
                ))
                break
    return violations


META = ValidatorMeta(
    code="HC-10",
    validation_key="no_consecutive_subject",
    severity=ConflictSeverity.MEDIUM,
    tier="placement",
    fn=validate,
)
