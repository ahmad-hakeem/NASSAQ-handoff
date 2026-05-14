"""School-type domain normalization.

Single canonical source of truth for the deprecated → canonical mapping
of the ``schools.school_type`` column. The platform historically exposed
two distinct dropdown options for the same business category:

    * "أهلية"  (canonical, stored as ``"private"``)
    * "خاصة"   (deprecated synonym, stored as ``"special"`` /
                ``"special_needs"`` depending on entry point)

Any new write must be normalized to the canonical value at the API
boundary before persistence so historical fragmentation cannot continue.
The matching Alembic migration backfills existing rows. This helper is
intentionally permissive on input (accepts the deprecated value during
the transition window) but always emits the canonical value, and it
leaves unrelated school-type values such as ``"public"``,
``"international"``, ``"independent_teacher"`` and
``"independent_teacher_workspace"`` untouched.
"""
from typing import Optional

DEPRECATED_PRIVATE_ALIASES = frozenset({
    "special",
    "special_needs",
    "خاصة",
})

CANONICAL_PRIVATE = "private"


def normalize_school_type(value: Optional[str]) -> Optional[str]:
    """Map deprecated school-type aliases to their canonical value.

    Returns ``None`` unchanged so callers can pass through optional
    fields without forcing a default. Non-deprecated values are
    returned as-is so this helper is safe to apply unconditionally on
    every write path.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    trimmed = value.strip()
    if trimmed in DEPRECATED_PRIVATE_ALIASES:
        return CANONICAL_PRIVATE
    return trimmed or None
