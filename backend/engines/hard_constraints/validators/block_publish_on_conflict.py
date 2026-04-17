"""HC-17 -- block_publish_on_conflict validator (Task 1 stub)."""

from typing import List

from engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from engines.smart_scheduling_engine import ConflictSeverity


def validate(ctx: ConstraintContext, candidate=None) -> List[ConstraintViolation]:
    return []


META = ValidatorMeta(
    code="HC-17",
    validation_key="block_publish_on_conflict",
    severity=ConflictSeverity.HIGH,
    tier="full",
    fn=validate,
)
