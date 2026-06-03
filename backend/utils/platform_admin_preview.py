"""
Platform-admin principal preview eligibility for schools / workspaces.

Single source of truth for:
  * filtering /user-roles preview entries
  * guarding POST /role-switch/switch
  * annotating GET /schools rows for the Command Center UI
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict

# Lifecycle statuses that must never impersonate as school_principal.
NON_PREVIEW_STATUSES = frozenset({"archived", "pending_hard_delete"})

IT_SCHOOL_TYPES = frozenset({
    "independent_teacher",
    "independent_teacher_workspace",
})

# Machine codes returned to the frontend (stable contract).
REASON_INDEPENDENT_TEACHER_WORKSPACE = "independent_teacher_workspace"
REASON_ARCHIVED = "archived"
REASON_PENDING_HARD_DELETE = "pending_hard_delete"
REASON_NO_ACTIVE_PRINCIPAL = "no_active_principal"

MSG_INDEPENDENT_TEACHER_WORKSPACE = (
    "عذرًا، لا يمكن فتح هذا الحساب من هذا المسار حاليًا لأنه يمثل مساحة معلم مستقل "
    "وليس مدرسة. يرجى استخدام مسار إدارة المعلمين المستقلين أو مراجعة إدارة النظام."
)
MSG_ARCHIVED = (
    "عذرًا، لا يمكن فتح هذا الحساب من هذا المسار حاليًا لأن المدرسة مؤرشفة "
    "ولا تدعم المعاينة كلوحة مدرسة. يرجى مراجعة إدارة النظام أو استخدام المسار المناسب."
)
MSG_PENDING_HARD_DELETE = (
    "عذرًا، لا يمكن فتح هذا الحساب من هذا المسار حاليًا لأنه قيد الإجراء للحذف "
    "ولا يدعم المعاينة كلوحة مدرسة. يرجى مراجعة إدارة النظام."
)
MSG_NO_ACTIVE_PRINCIPAL = (
    "لا يوجد مدير مدرسة نشط في هذه المدرسة — يرجى إضافة مدير قبل المعاينة."
)
MSG_GENERIC_BLOCKED = (
    "عذرًا، لا يمكن فتح هذا الحساب من هذا المسار حاليًا لأن نوعه لا يدعم "
    "المعاينة كلوحة مدرسة. يرجى مراجعة إدارة النظام أو استخدام المسار المناسب."
)


class PreviewEligibility(TypedDict):
    entity_kind: str  # "standard_school" | "independent_teacher_workspace"
    can_preview_as_principal: bool
    preview_block_reason: Optional[str]
    preview_block_message_ar: Optional[str]


def is_independent_teacher_workspace(school: Dict[str, Any]) -> bool:
    """True when the row is an IT synthetic tenant, not a real school."""
    sid = (school.get("id") or "").strip()
    if sid.startswith("itw_"):
        return True
    school_type = (school.get("school_type") or "").strip().lower()
    return school_type in IT_SCHOOL_TYPES


def assess_principal_preview_eligibility(
    school: Dict[str, Any],
    *,
    active_principal_count: Optional[int] = None,
) -> PreviewEligibility:
    """Return preview metadata for a schools-table row."""
    if is_independent_teacher_workspace(school):
        return PreviewEligibility(
            entity_kind="independent_teacher_workspace",
            can_preview_as_principal=False,
            preview_block_reason=REASON_INDEPENDENT_TEACHER_WORKSPACE,
            preview_block_message_ar=MSG_INDEPENDENT_TEACHER_WORKSPACE,
        )

    status = (school.get("status") or "").strip().lower()
    if status == "archived":
        return PreviewEligibility(
            entity_kind="standard_school",
            can_preview_as_principal=False,
            preview_block_reason=REASON_ARCHIVED,
            preview_block_message_ar=MSG_ARCHIVED,
        )
    if status == "pending_hard_delete":
        return PreviewEligibility(
            entity_kind="standard_school",
            can_preview_as_principal=False,
            preview_block_reason=REASON_PENDING_HARD_DELETE,
            preview_block_message_ar=MSG_PENDING_HARD_DELETE,
        )

    if active_principal_count is not None and active_principal_count == 0:
        return PreviewEligibility(
            entity_kind="standard_school",
            can_preview_as_principal=False,
            preview_block_reason=REASON_NO_ACTIVE_PRINCIPAL,
            preview_block_message_ar=MSG_NO_ACTIVE_PRINCIPAL,
        )

    return PreviewEligibility(
        entity_kind="standard_school",
        can_preview_as_principal=True,
        preview_block_reason=None,
        preview_block_message_ar=None,
    )


def should_exclude_from_preview_list(school: Dict[str, Any]) -> bool:
    """Used by /user-roles — excludes IT workspaces and terminal lifecycle rows."""
    if is_independent_teacher_workspace(school):
        return True
    status = (school.get("status") or "").strip().lower()
    return status in NON_PREVIEW_STATUSES


def assert_principal_preview_allowed(
    school: Dict[str, Any],
    *,
    active_principal_count: int,
) -> None:
    """Raise HTTPException-compatible detail string when preview must be blocked."""
    from fastapi import HTTPException

    meta = assess_principal_preview_eligibility(
        school,
        active_principal_count=active_principal_count,
    )
    if meta["can_preview_as_principal"]:
        return
    reason = meta["preview_block_reason"]
    message = meta["preview_block_message_ar"] or MSG_GENERIC_BLOCKED
    status_code = 422 if reason == REASON_NO_ACTIVE_PRINCIPAL else 403
    raise HTTPException(status_code=status_code, detail=message)
