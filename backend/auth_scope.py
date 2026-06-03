"""
Canonical request-scope adapter (Task #155, extended #178, #183).

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

import jwt
from fastapi import Depends, HTTPException
from starlette.requests import HTTPConnection

from dependencies import UserRole, get_current_user, JWT_SECRET, JWT_ALGORITHM


AI_INSIGHTS_SCOPE_DENIED_AR = "تعذّر التحقق من صلاحياتك للوصول إلى هذه البيانات"
INDEPENDENT_TEACHER_DENIED_AR = "هذه الميزة غير متاحة لحساب المعلم المستقل"
WORKSPACE_NOT_MATERIALISED_AR = "يجب إكمال إنشاء مساحتك أولًا."

# Paths that an Independent-Teacher caller may hit BEFORE their workspace
# has been materialised by POST /independent-teacher/bootstrap. Everything
# else 409s with the safe Arabic message above.
_WORKSPACE_ALLOWLIST_PREFIXES = (
    "/auth/",                          # login, refresh, logout, me, mfa/*
    "/independent-teacher/bootstrap",  # the bootstrap call itself
    # Public/health surfaces are unauthenticated by design. An IT user
    # who happens to be logged in (bearer attached by the FE axios
    # interceptor) must NOT 409 here — otherwise the global axios
    # perimeter handler treats every background poll as a "finish
    # setup" signal and bounces the wizard back to step 1.
    "/public/",
    "/healthz",
    # Read-only reference data used by the unauthenticated registration
    # forms (subjects, education-levels, teacher-ranks, etc.). Same
    # rationale as /public/: the FE registration page may have a stale
    # IT bearer in localStorage, and a 409 here trips the global axios
    # perimeter handler and pops the "finish setup" dialog on top of
    # the public landing/register surfaces.
    "/teacher-registration/options/",
)


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


def is_independent_workspace_id(school_id: Optional[str]) -> bool:
    """True when ``school_id`` is an Independent-Teacher synthetic workspace
    id (the ``itw_{user_id}`` convention).

    This is the school_id-side counterpart to ``independent_workspace_id``
    (which derives the id from a user dict). Use it when only the resolved
    school/workspace id is available — e.g. the generic teacher-schedule
    read path — to branch into the IT direct-``schedule_sessions`` model
    without hard-coding the prefix at each call site.
    """
    return isinstance(school_id, str) and school_id.startswith("itw_")


def require_request_school_id(current_user: dict) -> str:
    """Resolve the caller's school/workspace id, fail-closed on failure.

    Resolution order:
      1. `current_user["tenant_id"]` (school-affiliated users).
      2. `itw_{user_id}` workspace for `independent_teacher` callers.

    Raises `HTTPException(403, AI_INSIGHTS_SCOPE_DENIED_AR)` if neither
    resolves — never returns `None`, never returns an empty string.
    """
    school_id = (
        current_user.get("tenant_id")
        or current_user.get("school_id")
        or independent_workspace_id(current_user)
    )
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


async def require_workspace_materialised(request: HTTPConnection) -> None:
    """Phase 1 (#183) — fail-closed gate for Independent-Teacher accounts.

    Mounted as a global dependency on the ``/api`` router so every
    authenticated route is checked. For non-IT callers and for the
    explicit allow-list (auth surface, MFA enrolment, ``/auth/me``,
    ``/auth/me/permissions``, and ``POST /independent-teacher/bootstrap``)
    this is a no-op. For an IT caller whose workspace has not yet been
    materialised — i.e. ``users.tenant_id`` is still NULL, encoded in
    the bearer JWT as ``tenant_id == None`` — every other route fails
    with a clean ``409`` and the safe Arabic message above. The
    bootstrap endpoint itself rotates the bearer JWT on success so
    subsequent calls carry the freshly-set ``tenant_id``.

    Lightweight by design: decodes the bearer payload only (signature
    is re-verified by the downstream ``get_current_user`` dep). No DB
    lookups on the hot path. Failures of decode / type-check fall
    through silently — the downstream auth dep will reject as usual.
    """
    method = (getattr(request, "method", "GET") or "").upper()
    if method == "OPTIONS":
        return  # CORS preflight

    raw_path = request.url.path or ""
    # Strip the global "/api" prefix so the allow-list matches the same
    # canonical paths used elsewhere in the codebase.
    relative = raw_path[len("/api"):] if raw_path.startswith("/api") else raw_path
    for prefix in _WORKSPACE_ALLOWLIST_PREFIXES:
        if relative == prefix or relative.startswith(prefix):
            return

    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return  # unauthenticated — downstream auth deps will reject

    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return  # downstream get_current_user will reject

    if payload.get("type") != "access":
        return

    role = (payload.get("role") or "").lower()
    if role != UserRole.INDEPENDENT_TEACHER.value:
        return  # passthrough for every non-IT role

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=409,
            detail=WORKSPACE_NOT_MATERIALISED_AR,
        )


__all__ = [
    "AI_INSIGHTS_SCOPE_DENIED_AR",
    "INDEPENDENT_TEACHER_DENIED_AR",
    "WORKSPACE_NOT_MATERIALISED_AR",
    "is_independent_teacher",
    "independent_workspace_id",
    "require_request_school_id",
    "require_full_school_tenant",
    "require_workspace_materialised",
]
