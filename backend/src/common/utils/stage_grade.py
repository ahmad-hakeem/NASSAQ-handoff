"""
Stage / grade hierarchy validator.

Canonical stages: ``primary`` (1–6), ``middle`` (7–9), ``high`` (10–12).
Mirrors ``frontend/src/utils/stageGrade.js`` so a payload that the frontend
filter accepts is also accepted by the backend, and vice versa.

Used as the real security/data-integrity boundary on every create/update
flow that takes ``(stage, grade_id)`` as a pair (student creation, bulk
import, class creation/update). The frontend cascading dropdown is a UX
convenience only — server-side validation here is fail-closed.

The grade row is ALWAYS loaded under the resolved tenant
(``school_id``) so a client cannot smuggle a grade id from another
workspace into validation.
"""

from typing import Optional, Mapping, Any
from fastapi import HTTPException

from engines.sql_utils import gd_find_one


CANONICAL_STAGES = ("primary", "middle", "high")

_TOKEN_MAP = {
    "primary": "primary", "elementary": "primary", "pri": "primary",
    "middle": "middle", "intermediate": "middle", "mid": "middle",
    "high": "high", "secondary": "high", "sec": "high",
    "ابتدائي": "primary", "الابتدائي": "primary",
    "المرحلة الابتدائية": "primary",
    "متوسط": "middle", "المتوسط": "middle",
    "المرحلة المتوسطة": "middle",
    "ثانوي": "high", "الثانوي": "high",
    "المرحلة الثانوية": "high",
}


def _from_grade_number(n: Any) -> Optional[str]:
    try:
        num = int(n)
    except (TypeError, ValueError):
        return None
    if num < 1:
        return None
    if num <= 6:
        return "primary"
    if num <= 9:
        return "middle"
    if num <= 12:
        return "high"
    return None


def normalize_stage(value: Any) -> Optional[str]:
    """Coerce any stage-ish input to one of ``primary|middle|high|None``."""
    if value is None:
        return None

    if isinstance(value, Mapping):
        return (
            normalize_stage(value.get("stage"))
            or normalize_stage(value.get("stage_id"))
            or normalize_stage(value.get("education_level"))
            or _from_grade_number(value.get("grade"))
            or _from_grade_number(value.get("grade_number"))
            or _from_grade_number(value.get("order"))
        )

    if isinstance(value, (int, float)):
        return _from_grade_number(value)

    raw = str(value).strip()
    if not raw:
        return None
    if raw.isdigit():
        return _from_grade_number(raw)

    lower = raw.lower()
    if lower in _TOKEN_MAP:
        return _TOKEN_MAP[lower]
    if raw in _TOKEN_MAP:
        return _TOKEN_MAP[raw]

    if "primary" in lower or "elementary" in lower or "ابتدائ" in raw:
        return "primary"
    if "middle" in lower or "intermediate" in lower or "متوسط" in raw:
        return "middle"
    if "high" in lower or "secondary" in lower or "ثانوي" in raw:
        return "high"
    return None


async def validate_stage_grade_pair(
    session,
    school_id: str,
    stage: Optional[str],
    grade_id: Optional[str],
    *,
    require_stage: bool = False,
) -> None:
    """
    Verify that ``grade_id`` belongs to ``stage`` under the resolved
    tenant. Raises HTTP 422 with a safe Arabic message on mismatch and
    HTTP 404 when the grade does not belong to the tenant.

    Behaviour:
      * If ``grade_id`` is empty → returns silently (other validators
        decide whether grade is required).
      * The grade row is loaded scoped to ``school_id`` — a foreign-tenant
        grade id resolves to "not found" rather than crossing boundaries.
      * If neither the row's ``stage`` nor its ``grade`` number can be
        normalized, validation is permissive (we don't block writes on
        legacy rows that pre-date the stage column being populated).
    """
    if not grade_id:
        return

    target_stage = normalize_stage(stage)
    if require_stage and not target_stage:
        raise HTTPException(status_code=422, detail="المرحلة التعليمية مطلوبة")

    row = await gd_find_one(
        session, "grade_levels",
        {"id": grade_id, "school_id": school_id},
    )
    if not row:
        # Numeric-id fallback: the dropdown source `/classes/options/grades`
        # falls back to digit-string ids ("1".."12") for schools that have
        # not populated `grade_levels` yet. The id is not a tenant-bound
        # identifier in that mode (it's the grade number), so we still
        # enforce the stage↔number bucket but cannot enforce tenant row
        # presence. Anything that is neither a tenant row nor a known
        # grade number is rejected as not-found (fail-closed).
        number_stage = _from_grade_number(grade_id)
        if number_stage is None:
            raise HTTPException(status_code=404, detail="الصف غير موجود في هذه المدرسة")
        if target_stage and number_stage != target_stage:
            raise HTTPException(
                status_code=422,
                detail="الصف لا ينتمي للمرحلة التعليمية المختارة",
            )
        return

    if not target_stage:
        return  # No stage to compare against.

    row_stage = normalize_stage(row)
    if row_stage is None:
        return  # Legacy row without a derivable stage → don't block.

    if row_stage != target_stage:
        raise HTTPException(
            status_code=422,
            detail="الصف لا ينتمي للمرحلة التعليمية المختارة",
        )
