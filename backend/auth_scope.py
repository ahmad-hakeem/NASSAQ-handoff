"""
Canonical request-scope adapter (Task #155).

This module exposes the *school-id* half of the canonical AI Insights
authorization contract introduced in Task #154 so that non-AI route modules
(directory, search, attendance alerts/statistics, academics options) can
share the same fail-closed semantic and the same safe-Arabic denial message
without each module re-implementing tenant resolution and re-deriving the
same `tenant_id else broad-query` foot-gun.

There is still exactly one tri-state resolver for AI Insights
(`routes.ai_routes_mod.resolve_ai_insights_scope`) — this module does NOT
introduce a parallel contract; it exposes the school-id-or-403 sub-contract
that the AI Insights resolver itself depends on internally.

Failure mode: any inability to resolve the caller's school/workspace id
raises `HTTPException(403, AI_INSIGHTS_SCOPE_DENIED_AR)`. Never returns
`None`, never returns an empty filter, never silently degrades into a
broad/unscoped query.
"""
from typing import Optional

from fastapi import HTTPException

from dependencies import UserRole


AI_INSIGHTS_SCOPE_DENIED_AR = "تعذّر التحقق من صلاحياتك للوصول إلى هذه البيانات"


def independent_workspace_id(current_user: dict) -> Optional[str]:
    """Return the synthetic per-user workspace id `itw_{user_id}` when the
    caller is an `independent_teacher`, otherwise `None`.

    This mirrors the `itw_{user_id}` convention used by
    `resolve_ai_insights_scope` and the legacy local helpers in
    `routes.academics_student_routes` and `routes.class_management_routes`,
    consolidating them into a single source of truth.
    """
    role = current_user.get("role", "")
    account_type = current_user.get("account_type", "")
    if role != UserRole.INDEPENDENT_TEACHER.value and account_type != "independent_teacher":
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
    resolves — never returns `None`, never returns an empty string. Callers
    must use the returned id as a non-optional filter; the foot-gun pattern
    `{"school_id": sid} if sid else {}` MUST NOT reappear at any caller of
    this function.
    """
    school_id = current_user.get("tenant_id") or independent_workspace_id(current_user)
    if not school_id:
        raise HTTPException(status_code=403, detail=AI_INSIGHTS_SCOPE_DENIED_AR)
    return school_id
