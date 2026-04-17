"""HardConstraintRegistry — central dispatch for the 17 hard constraints."""

import logging
from typing import Dict, List, Optional

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.hard_constraints.validators import (
    academic_structure_match,
    block_publish_on_conflict,
    class_overlap,
    daily_period_limit,
    entity_integrity,
    no_consecutive_subject,
    non_teaching_period,
    resource_single_booking,
    room_overlap,
    schedule_completeness,
    school_day_boundary,
    school_period_bans,
    subject_weekly_periods,
    teacher_class_assignment,
    teacher_overlap,
    teacher_subject_match,
    teacher_weekly_load,
    working_days,
)

logger = logging.getLogger(__name__)


VALIDATION_REGISTRY: Dict[str, ValidatorMeta] = {
    meta.validation_key: meta
    for meta in [
        teacher_overlap.META,
        class_overlap.META,
        room_overlap.META,
        school_day_boundary.META,
        non_teaching_period.META,
        daily_period_limit.META,
        working_days.META,
        teacher_weekly_load.META,
        subject_weekly_periods.META,
        no_consecutive_subject.META,
        teacher_subject_match.META,
        teacher_class_assignment.META,
        resource_single_booking.META,
        schedule_completeness.META,
        academic_structure_match.META,
        entity_integrity.META,
        block_publish_on_conflict.META,
        school_period_bans.META,
    ]
}


def _dispatch(ctx: ConstraintContext, tier: str, candidate=None) -> List[ConstraintViolation]:
    violations: List[ConstraintViolation] = []
    active = ctx.active_validation_keys or set()
    for key, meta in VALIDATION_REGISTRY.items():
        if meta.tier != tier:
            continue
        if key not in active:
            continue
        try:
            if tier == "placement":
                result = meta.fn(ctx, candidate)
            else:
                result = meta.fn(ctx)
        except NotImplementedError:
            logger.warning("%s validator not yet implemented; skipping", meta.code)
            continue
        if result:
            violations.extend(result)
    return violations


def validate_placement(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    return _dispatch(ctx, "placement", candidate)


def validate_full(ctx: ConstraintContext) -> List[ConstraintViolation]:
    return _dispatch(ctx, "full")


__all__ = [
    "VALIDATION_REGISTRY",
    "validate_placement",
    "validate_full",
    "ConstraintContext",
    "ConstraintViolation",
    "ValidatorMeta",
]
