"""
Canonical request-scope adapter (Task #155, extended #178).

Single source of truth for:
  * Independent-teacher synthetic workspace id resolution.
  * Caller school/workspace id resolution (fail-closed).
  * Capability gate that denies Independent-Teacher accounts on routes
    reserved for full school tenants (Phase 0 of the IT phased spec).

Failure mode: any inability to resolve the caller's school/workspace id
raises `HTTPException(403, AI_INSIGHTS_SCOPE_DENIED_AR)`. Never returns
`None`, never returns an empty filter, never silently degrades into a
broad/unscoped query.
"""
from typing import Optional

from fastapi import Depends, HTTPException

from dependencies import UserRole, get_current_user


AI_INSIGHTS_SCOPE_DENIED_AR = "تعذّر التحقق من صلاحياتك للوصول إلى هذه البيانات"
INDEPENDENT_TEACHER_DENIED_AR = "هذه الميزة غير متاحة لحساب المعلم المستقل"


def is_independent_teacher(current_user: dict) -> bool:
    """True when the caller is an Independent-Teacher account.

    Checks both the canonical `role` field and the legacy `account_type`
    fallback so a token issued before role consolidation still matches.
    """
    role = (current_user.get("role") or "").lower()
    account_type = (current_user.get("account_type") or "").lower()
    if not account_type:
        data = current_user.get("data") or {}
        account_type = (data.get("account_type") or "").lower()
    return (
        role == UserRole.INDEPENDENT_TEACHER.value
        or account_type == "independent_teacher"
    )


def independent_workspace_id(current_user: dict) -> Optional[str]:
    """Return the synthetic per-user workspace id `itw_{user_id}` when the
    caller is an `independent_teacher`, otherwise `None`.

    This is the SOLE source of the `itw_{user_id}` convention; every
    historical inline copy in route modules has been retired and now
    delegates to this helper.
    """
    if not is_independent_teacher(current_user):
        return None
    user_id = current_user.get("id") or current_user.get("_id")
    if not user_id:
        return None
    return f"itw_{user_id}"


def require_request_school_id(current_user: dict) -> str:
    """Resolve the caller's school/workspace id, fail-closed on failure.

    Resolution order:
      1. `current_user["tenant_id"]` (school-affiliated users).
      2. `itw_{user_id}` workspace for `independent_teacher` callers.

    Raises `HTTPException(403, AI_INSIGHTS_SCOPE_DENIED_AR)` if neither
    resolves — never returns `None`, never returns an empty string.
    """
    school_id = current_user.get("tenant_id") or independent_workspace_id(current_user)
    if not school_id:
        raise HTTPException(status_code=403, detail=AI_INSIGHTS_SCOPE_DENIED_AR)
    return school_id


async def require_full_school_tenant(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """FastAPI capability gate: deny Independent-Teacher callers.

    Mounted via `dependencies=[Depends(require_full_school_tenant)]` on
    routers that are reserved for full school tenants (Phase 0 §4.B-2).
    Returns the current user dict on success so it can be reused as a
    sub-dependency.

    Defense-in-depth: denies on EITHER (a) IT role/account_type, OR
    (b) the caller's resolved tenant looks like an IT workspace
    (synthetic `itw_*` id, or a tenant_type/school_type marked as
    independent). This way an inconsistent token (e.g. role flipped
    after a manual edit but tenant still IT) cannot bypass the gate.
    """
    if is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    tenant_id = (current_user.get("tenant_id") or "")
    if isinstance(tenant_id, str) and tenant_id.startswith("itw_"):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    tenant_type = (
        (current_user.get("tenant_type") or "").lower()
        or (current_user.get("school_type") or "").lower()
    )
    if tenant_type in {"independent_teacher", "independent_workspace"}:
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


__all__ = [
    "AI_INSIGHTS_SCOPE_DENIED_AR",
    "INDEPENDENT_TEACHER_DENIED_AR",
    "is_independent_teacher",
    "independent_workspace_id",
    "require_request_school_id",
    "require_full_school_tenant",
]
