"""
Independent-Teacher — Workspace Collaborator envelope (§6.7, Task #210).

The ONE sanctioned cross-tenant data path between two Independent-
Teacher workspaces. A row links exactly one host workspace's class to
exactly one collaborator workspace; while ``status='accepted'`` the
collaborator may read (and, when ``scope.mode='write'``, mutate) data
scoped to that single ``class_id`` only.

HTTP surfaces:

  * ``POST   /independent-teacher/workspace-collaborators``
      Host IT only, requires Tier-A MFA + ``workspace.collab_manage``.
      Mints a ``workspace_collaborators`` row and a one-shot signed
      token (raw token returned exactly once). Idempotent on the
      ``(host_school_id, class_id, collaborator_email)`` pending slot.

  * ``POST   /independent-teacher/workspace-collaborators/{id}/cancel``
      Host IT only, Tier-A MFA. Pending-only (409 otherwise).

  * ``DELETE /independent-teacher/workspace-collaborators/{id}``
      Host OR collaborator IT, Tier-A MFA. Revokes an accepted link.

  * ``GET    /independent-teacher/workspace-collaborators?class_id=...``
      Host view: list invitations + active links for a class the caller
      hosts. Cross-workspace class id → 404 (§8 inv. 3).

  * ``GET    /independent-teacher/workspace-collaborators/shared-with-me``
      Collaborator view: list active links pointing at the caller.

  * ``POST   /independent-teacher/workspace-collaborators/accept``
      Authenticated IT (the invited collaborator). Requires Tier-A MFA.
      Verifies the token + binds the row to the caller's workspace and
      flips status pending → accepted. Cross-tenant replay 400.

All cross-workspace by-id lookups return ``404`` (never 403/200) per
§8 invariant 3.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
import re

from pydantic import BaseModel, Field, field_validator

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import (
    audit_engine,
    db,
    get_current_user,
    require_recent_mfa_403,
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from middleware.rbac import Permission
from utils.tokens import (
    mint_collab_invitation_token,
    verify_collab_invitation_token,
)


logger = logging.getLogger("nassaq.it_collab")

router = APIRouter()


# -- Audit actions --------------------------------------------------------

AUDIT_COLLAB_INVITED = "INDEPENDENT_TEACHER_COLLAB_INVITED"
AUDIT_COLLAB_CANCELLED = "INDEPENDENT_TEACHER_COLLAB_CANCELLED"
AUDIT_COLLAB_ACCEPTED = "INDEPENDENT_TEACHER_COLLAB_ACCEPTED"
AUDIT_COLLAB_REVOKED = "INDEPENDENT_TEACHER_COLLAB_REVOKED"


# -- Safe Arabic copy -----------------------------------------------------

_MSG_INTERNAL = "تعذّر إنشاء دعوة المتعاون — حاول لاحقًا."
_MSG_CLASS_NOT_FOUND = "الفصل غير موجود."
_MSG_COLLAB_NOT_FOUND = "الدعوة غير موجودة."
_MSG_COLLAB_BAD_STATE = "لا يمكن تنفيذ هذا الإجراء بحالة الدعوة الحالية."
_MSG_COLLAB_INVALID_TOKEN = "رابط الدعوة غير صالح أو منتهي الصلاحية."
_MSG_COLLAB_SELF = "لا يمكنك دعوة مساحتك ذاتها للتعاون."
_MSG_COLLAB_PERMISSION = "لا تملك صلاحية إدارة المتعاونين."
_MSG_COLLAB_EMAIL_REQUIRED = "البريد الإلكتروني للمتعاون مطلوب."
_MSG_COLLAB_EMAIL_MISMATCH = "هذه الدعوة موجّهة إلى بريد إلكتروني مختلف."
_MSG_COLLAB_NEEDS_IT = "حساب المتعاون يجب أن يكون لمعلم مستقل."
_MSG_COLLAB_NOT_FOUND_USER = (
    "لم نعثر على حساب معلم مستقل بهذا البريد الإلكتروني."
)


# -- Request / response models -------------------------------------------

ScopeMode = Literal["read", "write"]


class CollabScope(BaseModel):
    mode: ScopeMode = "read"


# Lenient pattern — we accept .test / .invalid / .local domains so QA
# fixtures and synthetic IT workspaces (`it-…@t.test`) can use this
# envelope. Real deliverability is enforced upstream when the host
# actually sends the token to the collaborator.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class CreateCollabRequest(BaseModel):
    class_id: str = Field(min_length=1, max_length=64)
    collaborator_email: str = Field(min_length=3, max_length=320)
    scope: CollabScope = Field(default_factory=CollabScope)

    @field_validator("collaborator_email")
    @classmethod
    def _email_shape(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError(_MSG_COLLAB_EMAIL_REQUIRED)
        return v


class AcceptCollabRequest(BaseModel):
    token: str = Field(min_length=10, max_length=4096)

    @field_validator("token")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


# -- Helpers --------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


def _require_collab_manage(current_user: dict) -> None:
    perms = current_user.get("permissions") or []
    # Permissions may be unset on the JWT (FastAPI doesn't carry them).
    # Fall back to the role mapping when so.
    if Permission.WORKSPACE_COLLAB_MANAGE.value in perms:
        return
    from middleware.rbac import ROLE_PERMISSIONS
    role_perms = ROLE_PERMISSIONS.get(current_user.get("role") or "", [])
    if Permission.WORKSPACE_COLLAB_MANAGE.value in role_perms:
        return
    raise HTTPException(status_code=403, detail=_MSG_COLLAB_PERMISSION)


_recent_mfa_403_dep = require_recent_mfa_403()


def _serialise(row: dict, *, raw_token: Optional[str] = None) -> dict:
    """Public-safe projection of a workspace_collaborators row."""
    out = {
        "id": row["id"],
        "host_school_id": row["host_school_id"],
        "collaborator_school_id": row.get("collaborator_school_id"),
        "class_id": row["class_id"],
        "collaborator_email": row.get("collaborator_email"),
        "collaborator_user_id": row.get("collaborator_user_id"),
        "scope": row.get("scope") or {"mode": "read"},
        "status": row["status"],
        "sent_at": row.get("sent_at"),
        "accepted_at": row.get("accepted_at"),
        "revoked_at": row.get("revoked_at"),
        "expires_at": row.get("expires_at"),
        "created_by": row.get("created_by"),
    }
    if raw_token is not None:
        out["token"] = raw_token
    return out


async def _load_host_class(class_id: str, host_school_id: str) -> Dict[str, Any]:
    """Tenant-pinned class lookup. Cross-tenant → 404 (§8 inv. 3)."""
    cls = await gd_find_one(db.session, "classes", {
        "id": class_id, "school_id": host_school_id,
    })
    if not cls:
        raise HTTPException(status_code=404, detail=_MSG_CLASS_NOT_FOUND)
    return cls


# -- Endpoint: POST create -----------------------------------------------

@router.post("/independent-teacher/workspace-collaborators")
async def create_collab_invitation(
    payload: CreateCollabRequest,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
):
    _require_collab_manage(current_user)

    host_school_id = (
        require_request_school_id(current_user)
        or independent_workspace_id(current_user)
    )

    # 404 on cross-workspace class id BEFORE any other branch.
    await _load_host_class(payload.class_id, host_school_id)

    email = payload.collaborator_email.lower()

    # Caller can't invite themselves to their own workspace.
    if (current_user.get("email") or "").lower() == email:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_SELF)

    # The invited email MUST already belong to an Independent-Teacher
    # account. We refuse non-IT and unknown emails up front so the host
    # gets a clear Arabic error instead of issuing a token that could
    # never be accepted. The lookup is global by design (users.email is
    # globally unique) — cross-tenant info disclosure is not a concern
    # because the host already knows the email they typed in.
    invited_user = await gd_find_one(db.session, "users", {"email": email})
    if not invited_user:
        raise HTTPException(status_code=404, detail=_MSG_COLLAB_NOT_FOUND_USER)
    if invited_user.get("role") != "independent_teacher":
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_NEEDS_IT)
    # Belt-and-braces: also block inviting a user whose resolved
    # workspace happens to equal the host's. Should be unreachable
    # given the email check above, but defensive.
    invited_ws = independent_workspace_id(invited_user)
    if invited_ws == host_school_id:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_SELF)

    # Idempotency: pending invite for this (host, class, email) wins.
    existing = await gd_find_one(db.session, "workspace_collaborators", {
        "host_school_id": host_school_id,
        "class_id": payload.class_id,
        "collaborator_email": email,
        "status": "pending",
    })
    if existing:
        return {**_serialise(existing), "reused": True}

    # Reject if this triple is already accepted (active link). The host
    # must revoke first before re-inviting.
    accepted = await gd_find_one(db.session, "workspace_collaborators", {
        "host_school_id": host_school_id,
        "class_id": payload.class_id,
        "collaborator_email": email,
        "status": "accepted",
    })
    if accepted:
        raise HTTPException(status_code=409, detail=_MSG_COLLAB_BAD_STATE)

    raw_token, t_hash, expires_at = mint_collab_invitation_token(
        host_school_id, payload.class_id, email,
    )
    now = _utcnow()
    row = {
        "id": str(uuid.uuid4()),
        "host_school_id": host_school_id,
        "collaborator_school_id": None,
        "class_id": payload.class_id,
        "collaborator_email": email,
        "collaborator_user_id": None,
        "token_hash": t_hash,
        "scope": {"mode": payload.scope.mode},
        "status": "pending",
        "sent_at": now.isoformat(),
        "accepted_at": None,
        "revoked_at": None,
        "expires_at": expires_at.isoformat(),
        "created_by": current_user["id"],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    try:
        async with db.session.begin_nested():
            await gd_insert(db.session, "workspace_collaborators", row)
            await audit_engine.log(
                action=AUDIT_COLLAB_INVITED,
                performed_by=current_user["id"],
                tenant_id=host_school_id,
                entity_type="workspace_collaborator",
                entity_id=row["id"],
                details={
                    "host_school_id": host_school_id,
                    "class_id": payload.class_id,
                    "collaborator_email": email,
                    "scope": row["scope"],
                },
                actor_role=current_user.get("role"),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("create_collab_invitation failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)
    return {**_serialise(row, raw_token=raw_token), "reused": False}


# -- Endpoint: POST cancel (pending) -------------------------------------

@router.post("/independent-teacher/workspace-collaborators/{collab_id}/cancel")
async def cancel_collab_invitation(
    collab_id: str,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
):
    _require_collab_manage(current_user)

    host_school_id = (
        require_request_school_id(current_user)
        or independent_workspace_id(current_user)
    )

    # Cross-workspace by-id lookup must 404, not 403.
    row = await gd_find_one(db.session, "workspace_collaborators", {
        "id": collab_id, "host_school_id": host_school_id,
    })
    if not row:
        raise HTTPException(status_code=404, detail=_MSG_COLLAB_NOT_FOUND)
    if row.get("status") != "pending":
        raise HTTPException(status_code=409, detail=_MSG_COLLAB_BAD_STATE)

    now_iso = _utcnow_iso()
    await gd_update_one(
        db.session, "workspace_collaborators",
        {"id": collab_id},
        {"status": "cancelled", "updated_at": now_iso},
    )
    await audit_engine.log(
        action=AUDIT_COLLAB_CANCELLED,
        performed_by=current_user["id"],
        tenant_id=host_school_id,
        entity_type="workspace_collaborator",
        entity_id=collab_id,
        details={"host_school_id": host_school_id, "class_id": row["class_id"]},
        actor_role=current_user.get("role"),
    )
    refreshed = await gd_find_one(db.session, "workspace_collaborators", {"id": collab_id})
    return _serialise(refreshed or {**row, "status": "cancelled"})


# -- Endpoint: DELETE revoke (accepted or pending) -----------------------

@router.delete("/independent-teacher/workspace-collaborators/{collab_id}")
async def revoke_collab(
    collab_id: str,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
):
    """Either side may revoke an active link or cancel a pending one."""
    caller_ws = (
        require_request_school_id(current_user)
        or independent_workspace_id(current_user)
    )

    # Cross-workspace by-id → 404 unless the caller owns *either* side.
    row = await gd_find_one(db.session, "workspace_collaborators", {"id": collab_id})
    if not row or (
        row.get("host_school_id") != caller_ws
        and row.get("collaborator_school_id") != caller_ws
    ):
        raise HTTPException(status_code=404, detail=_MSG_COLLAB_NOT_FOUND)

    # Hosts revoking still need the manage permission; collaborators
    # always may withdraw their side without it.
    if row.get("host_school_id") == caller_ws:
        _require_collab_manage(current_user)

    if row.get("status") not in {"pending", "accepted"}:
        raise HTTPException(status_code=409, detail=_MSG_COLLAB_BAD_STATE)

    now_iso = _utcnow_iso()
    new_status = "cancelled" if row.get("status") == "pending" else "revoked"
    await gd_update_one(
        db.session, "workspace_collaborators",
        {"id": collab_id},
        {"status": new_status, "revoked_at": now_iso, "updated_at": now_iso},
    )
    await audit_engine.log(
        action=AUDIT_COLLAB_REVOKED if new_status == "revoked" else AUDIT_COLLAB_CANCELLED,
        performed_by=current_user["id"],
        tenant_id=caller_ws,
        entity_type="workspace_collaborator",
        entity_id=collab_id,
        details={
            "host_school_id": row["host_school_id"],
            "collaborator_school_id": row.get("collaborator_school_id"),
            "class_id": row["class_id"],
            "side": "host" if row["host_school_id"] == caller_ws else "collaborator",
        },
        actor_role=current_user.get("role"),
    )
    refreshed = await gd_find_one(db.session, "workspace_collaborators", {"id": collab_id})
    return _serialise(refreshed or {**row, "status": new_status})


# -- Endpoint: GET host view ---------------------------------------------

@router.get("/independent-teacher/workspace-collaborators")
async def list_class_collaborators(
    class_id: str = Query(..., min_length=1, max_length=64),
    current_user: dict = Depends(_require_independent_teacher),
):
    host_school_id = (
        require_request_school_id(current_user)
        or independent_workspace_id(current_user)
    )
    # 404 on cross-workspace class id.
    await _load_host_class(class_id, host_school_id)

    rows = await gd_find(db.session, "workspace_collaborators", {
        "host_school_id": host_school_id,
        "class_id": class_id,
    }) or []
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return {"items": [_serialise(r) for r in rows]}


# -- Endpoint: GET collaborator view -------------------------------------

@router.get("/independent-teacher/workspace-collaborators/shared-with-me")
async def list_shared_with_me(
    current_user: dict = Depends(_require_independent_teacher),
):
    caller_ws = independent_workspace_id(current_user)
    if not caller_ws:
        return {"items": []}
    rows = await gd_find(db.session, "workspace_collaborators", {
        "collaborator_school_id": caller_ws,
        "status": "accepted",
    }) or []
    return {"items": [_serialise(r) for r in rows]}


# -- Endpoint: GET public preview ----------------------------------------

@router.get("/public/workspace-collaborators/preview")
async def preview_collab_invitation(token: str = Query(..., min_length=10, max_length=4096)):
    """Unauthenticated landing-page preview. Decodes the token, returns a
    minimal projection (host workspace name, class name, invited email,
    status, expiry) so the FE can render "<host> has invited you to
    co-teach <class>" before asking the collaborator to sign in.

    Never trusts JWT claims for state — the row's token_hash is the
    one-shot guard. Returns 400 on tampered / expired / replayed tokens
    so the public surface is uniform.
    """
    import jwt as _jwt
    from dependencies import JWT_SECRET, JWT_ALGORITHM
    try:
        claims = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except _jwt.PyJWTError:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)
    host_school_id = claims.get("host")
    class_id = claims.get("cls")
    invited_email = (claims.get("email") or "").lower()
    if not host_school_id or not class_id or not invited_email:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)
    row = await gd_find_one(db.session, "workspace_collaborators", {
        "host_school_id": host_school_id,
        "class_id": class_id,
        "collaborator_email": invited_email,
        "status": "pending",
    })
    if not row or not verify_collab_invitation_token(
        token, row["token_hash"],
        host_school_id=host_school_id,
        class_id=class_id,
        collaborator_email=invited_email,
    ):
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)
    cls = await gd_find_one(db.session, "classes", {"id": class_id}) or {}
    school = await gd_find_one(db.session, "schools", {"id": host_school_id}) or {}
    return {
        "invited_email": invited_email,
        "class_name": cls.get("name"),
        "host_workspace_name": school.get("name"),
        "scope": row.get("scope") or {"mode": "read"},
        "expires_at": row.get("expires_at"),
        "status": row.get("status"),
    }


# -- Endpoint: POST accept ------------------------------------------------

@router.post("/independent-teacher/workspace-collaborators/accept")
async def accept_collab_invitation(
    payload: AcceptCollabRequest,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
):
    """The invited collaborator (also an IT) accepts the token, binding
    their workspace to the host class for read/write co-teaching.
    """
    caller_email = (current_user.get("email") or "").lower()
    if not caller_email:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)
    caller_ws = independent_workspace_id(current_user)
    if not caller_ws:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_NEEDS_IT)

    # Decode the token claims to find the row WITHOUT trusting them as
    # authentication — the row's token_hash is the single-use guard.
    import jwt as _jwt
    from dependencies import JWT_SECRET, JWT_ALGORITHM
    try:
        claims = _jwt.decode(
            payload.token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
        )
    except _jwt.PyJWTError:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)
    host_school_id = claims.get("host")
    class_id = claims.get("cls")
    invited_email = (claims.get("email") or "").lower()
    if not host_school_id or not class_id or not invited_email:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)

    # The accepting caller must match the invited email.
    if caller_email != invited_email:
        raise HTTPException(status_code=403, detail=_MSG_COLLAB_EMAIL_MISMATCH)

    # Cannot accept an invitation pointing at the same workspace.
    if caller_ws == host_school_id:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_SELF)

    row = await gd_find_one(db.session, "workspace_collaborators", {
        "host_school_id": host_school_id,
        "class_id": class_id,
        "collaborator_email": invited_email,
        "status": "pending",
    })
    if not row:
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)

    if not verify_collab_invitation_token(
        payload.token, row["token_hash"],
        host_school_id=host_school_id,
        class_id=class_id,
        collaborator_email=invited_email,
    ):
        raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)

    expires_at = row.get("expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except ValueError:
            expires_at = None
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < _utcnow():
            raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)

    now_iso = _utcnow_iso()
    try:
        async with db.session.begin_nested():
            updated = await gd_update_one(
                db.session, "workspace_collaborators",
                {"id": row["id"], "status": "pending"},
                {
                    "status": "accepted",
                    "collaborator_school_id": caller_ws,
                    "collaborator_user_id": current_user["id"],
                    "accepted_at": now_iso,
                    "updated_at": now_iso,
                },
            )
            if not updated:
                raise HTTPException(status_code=400, detail=_MSG_COLLAB_INVALID_TOKEN)
            await audit_engine.log(
                action=AUDIT_COLLAB_ACCEPTED,
                performed_by=current_user["id"],
                tenant_id=host_school_id,
                entity_type="workspace_collaborator",
                entity_id=row["id"],
                details={
                    "host_school_id": host_school_id,
                    "collaborator_school_id": caller_ws,
                    "class_id": class_id,
                    "scope": row.get("scope") or {"mode": "read"},
                },
                actor_role=current_user.get("role"),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("accept_collab_invitation failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    refreshed = await gd_find_one(db.session, "workspace_collaborators", {"id": row["id"]})
    return _serialise(refreshed or row)
