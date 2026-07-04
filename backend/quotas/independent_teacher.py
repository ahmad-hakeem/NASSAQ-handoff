"""
Independent-Teacher v1 workspace quotas (Phase 0 §4.B-5).

Enforced at the create-resource boundary so an IT account can never
materialise more than the allowed number of classes / students /
academic years per workspace. All errors are 409 with safe Arabic
messages; callers MUST NOT downgrade them to 200/500.
"""
from typing import Optional

from fastapi import HTTPException

from auth_scope import independent_workspace_id
from engines.sql_utils import gd_count

# v1 limits. Intentionally conservative — Phase 1 will revisit.
# Classes are UNLIMITED for IT workspaces (product decision 2026-07):
# MAX_CLASSES = None disables class enforcement AND signals "unlimited" to
# the surfaced quota views (they emit max_classes: null). The
# workspace_quota.max_classes DB column is NON-NULL, so seeds persist
# DB_DEFAULT_MAX_CLASSES instead of the None policy value.
MAX_CLASSES = None
DB_DEFAULT_MAX_CLASSES = 5
MAX_STUDENTS = 200
MAX_ACADEMIC_YEARS = 1
MAX_TERMS = 2
# Phase 2 §6.4 (Task #209) — light AI lesson-planning assistant.
# Daily generations per IT workspace; counter resets at UTC midnight in
# application code (mirrors workspace_quota.imports_today).
MAX_LESSON_PLANS_PER_DAY = 20

_MSG_CLASSES = (
    "بلغت الحد الأقصى لعدد الفصول في حسابك المستقل (٥). "
    "احذف فصلاً قبل إنشاء فصل جديد."
)
_MSG_STUDENTS = (
    "بلغت الحد الأقصى لعدد الطلاب في حسابك المستقل (٢٠٠). "
    "أرشف طالباً قبل إضافة طالب جديد."
)
_MSG_YEARS = (
    "حسابك المستقل يدعم عاماً دراسياً واحداً فقط. "
    "احذف العام الحالي قبل إنشاء عام جديد."
)
_MSG_TERMS = (
    "حسابك المستقل يدعم فصلين دراسيين كحد أقصى. "
    "احذف فصلاً قبل إنشاء فصل جديد."
)
_MSG_LESSON_PLANS_DAILY = (
    "بلغت الحد اليومي لتوليد خطط الدروس. حاول مرة أخرى غدًا."
)


def _workspace_id(current_user: dict) -> Optional[str]:
    """Return the IT workspace id, or None if the caller is not an IT."""
    return independent_workspace_id(current_user)


async def enforce_class_quota(session, current_user: dict) -> None:
    wsid = _workspace_id(current_user)
    if not wsid or MAX_CLASSES is None:
        return  # not an IT, or classes are unlimited — quota doesn't apply
    count = await gd_count(session, "classes", {"school_id": wsid, "is_active": {"$ne": False}})
    if count >= MAX_CLASSES:
        raise HTTPException(status_code=409, detail=_MSG_CLASSES)


async def enforce_student_quota(session, current_user: dict) -> None:
    wsid = _workspace_id(current_user)
    if not wsid:
        return
    count = await gd_count(
        session, "students", {"school_id": wsid, "is_active": {"$ne": False}}
    )
    if count >= MAX_STUDENTS:
        raise HTTPException(status_code=409, detail=_MSG_STUDENTS)


async def enforce_academic_year_quota(session, current_user: dict) -> None:
    """Cap on currently-active academic years only — historical/closed
    rows do not count against the IT workspace limit."""
    wsid = _workspace_id(current_user)
    if not wsid:
        return
    count = await gd_count(
        session,
        "academic_years",
        {
            "school_id": wsid,
            "$or": [
                {"is_current": True},
                {"status": {"$in": ["active", "published"]}},
            ],
        },
    )
    if count >= MAX_ACADEMIC_YEARS:
        raise HTTPException(status_code=409, detail=_MSG_YEARS)


async def enforce_term_quota(session, current_user: dict) -> None:
    """Cap on currently-active terms only — archived/closed terms are
    not counted."""
    wsid = _workspace_id(current_user)
    if not wsid:
        return
    count = await gd_count(
        session,
        "terms",
        {
            "school_id": wsid,
            "$or": [
                {"is_active": True},
                {"is_current": True},
                {"status": {"$in": ["active", "published"]}},
            ],
        },
    )
    if count >= MAX_TERMS:
        raise HTTPException(status_code=409, detail=_MSG_TERMS)


__all__ = [
    "MAX_CLASSES",
    "DB_DEFAULT_MAX_CLASSES",
    "MAX_STUDENTS",
    "MAX_ACADEMIC_YEARS",
    "MAX_TERMS",
    "MAX_LESSON_PLANS_PER_DAY",
    "enforce_class_quota",
    "enforce_student_quota",
    "enforce_academic_year_quota",
    "enforce_term_quota",
]
