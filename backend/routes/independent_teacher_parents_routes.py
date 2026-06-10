"""Independent-Teacher — workspace-scoped Parents directory (Task #849).

The shared admin ``GET /parents`` directory (``academics_student_routes``)
is gated to school admin roles and aggregates children from the
non-authoritative ``parents.student_ids`` / ``students.parent_id`` fields,
so an Independent-Teacher account either cannot reach it or sees empty /
zero-children rows. This router is the IT-only equivalent built on the
authoritative parent-identity model:

  * ``parents``         — the canonical parent profile row.
  * ``guardian_links``  — the authoritative link (``tenant_id ==
    itw_{user_id}``, ``is_active``) between a parent and a student.
  * ``users``           — the parent portal login account
    (``role == "parent"``, ``tenant_id == itw_{user_id}``).

Endpoints (all IT-only, every by-id read 404s cross-workspace per
spec §8 invariant 3):

  * ``GET /independent-teacher/parents``
      List every parent linked into the caller's workspace with a
      correct per-parent children count and portal-activation state,
      plus the set of students that still only carry pending parent
      contact info (no linked portal account yet).

  * ``GET /independent-teacher/parents/{parent_id}``
      Parent detail: profile, linked children, and portal-account
      state. Never returns password material.

  * ``PUT /independent-teacher/parents/{parent_id}/credentials``
      IT-only, Tier-A MFA step-up (403 envelope). Sets / rotates the
      parent portal login and returns the new password ONCE so the
      teacher can copy it. No email is sent and the stored hash is
      never exposed.

Materialising / linking a parent for a pending student is NOT a new
writer here — the FE calls the canonical
``POST /independent-teacher/students/{student_id}/invite-parent``
(``independent_teacher_invite_parent_routes``) which funnels through
``utils.it_parent_link.link_workspace_parent_to_student``.
"""
from __future__ import annotations

import logging
import secrets
import string
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import (
    audit_engine,
    db,
    get_current_user,
    hash_password,
    require_recent_mfa_403,
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one

logger = logging.getLogger("nassaq.it_parents")

router = APIRouter()


# -- Constants (must match utils.it_parent_link) --------------------------

_USER_PASSWORD_SENTINEL = "!invite-pending"
_INVALID_EMAIL_DOMAIN = "@invite.nassaq.invalid"

_AUDIT_CREDENTIALS = "INDEPENDENT_TEACHER_PARENT_CREDENTIALS"

# Portal-activation states surfaced to the FE.
_PORTAL_ACTIVE = "active"      # real login the parent can use today.
_PORTAL_PENDING = "pending"    # account exists but not yet activated.
_PORTAL_NONE = "none"          # no portal users row at all.


# -- Safe Arabic copy -----------------------------------------------------

_MSG_PARENT_NOT_FOUND = "ولي الأمر غير موجود"
_MSG_PASSWORD_TOO_SHORT = "كلمة المرور يجب أن تكون 6 أحرف على الأقل"
_MSG_EMAIL_TAKEN = "البريد الإلكتروني مستخدم بالفعل"
_MSG_INTERNAL = "تعذّر تحديث بيانات الدخول — حاول لاحقًا."


# -- Request models -------------------------------------------------------

class RotateCredentialsRequest(BaseModel):
    new_email: Optional[EmailStr] = None
    new_password: Optional[str] = Field(default=None, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _strip_pwd(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s or None


# -- Helpers --------------------------------------------------------------

async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


_recent_mfa_403_dep = require_recent_mfa_403()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_placeholder_email(email: Optional[str]) -> bool:
    return bool(email) and email.endswith(_INVALID_EMAIL_DOMAIN)


def _generate_password(length: int = 12) -> str:
    """Readable strong temporary password (no ambiguous chars)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _portal_state(user: Optional[Dict[str, Any]]) -> str:
    if not user:
        return _PORTAL_NONE
    if (
        user.get("is_active")
        and user.get("password_hash")
        and user.get("password_hash") != _USER_PASSWORD_SENTINEL
        and not _is_placeholder_email(user.get("email"))
    ):
        return _PORTAL_ACTIVE
    return _PORTAL_PENDING


async def _load_workspace_parent(parent_id: str, workspace_id: str) -> Dict[str, Any]:
    """Fetch a parent row pinned to the caller's workspace.

    Cross-workspace ids MUST 404 (never 403/200) so the API never
    confirms the existence of a foreign-tenant parent (spec §8 inv. 3).
    """
    parent = await gd_find_one(
        db.session, "parents",
        {"id": parent_id, "school_id": workspace_id},
    )
    if not parent:
        raise HTTPException(status_code=404, detail=_MSG_PARENT_NOT_FOUND)
    return parent


async def _resolve_workspace_parent_user(
    parent: Dict[str, Any],
    workspace_id: str,
    *,
    parent_ref: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find the parent portal ``users`` row scoped to this workspace.

    Lookup order (first match wins, all pinned to the workspace tenant):
      1. ``parent_ref`` from a guardian_links row (the materialised id).
      2. ``users.parent_id == parent.id``.
      3. ``users.email == parent.email`` (legacy fallback).
    """
    base = {"role": "parent", "tenant_id": workspace_id}
    if parent_ref:
        user = await gd_find_one(db.session, "users", {"id": parent_ref, **base})
        if user:
            return user
    user = await gd_find_one(
        db.session, "users", {"parent_id": parent["id"], **base},
    )
    if user:
        return user
    if parent.get("email"):
        user = await gd_find_one(
            db.session, "users", {"email": parent["email"], **base},
        )
        if user:
            return user
    return None


def _parent_ref_for(parent_id: str, links: List[Dict[str, Any]]) -> Optional[str]:
    for link in links:
        if link.get("parent_id") == parent_id and link.get("parent_ref"):
            return link.get("parent_ref")
    return None


# -- Endpoint: GET list ---------------------------------------------------

@router.get("/independent-teacher/parents")
async def list_workspace_parents(
    current_user: dict = Depends(_require_independent_teacher),
) -> Dict[str, Any]:
    """List parents linked into the caller's workspace + pending students."""
    workspace_id = require_request_school_id(current_user)

    links = await gd_find(
        db.session, "guardian_links",
        {"tenant_id": workspace_id, "is_active": True},
        limit=5000,
    )

    students = await gd_find(
        db.session, "students",
        {"school_id": workspace_id, "is_active": True},
        limit=5000,
    )
    student_by_id = {s["id"]: s for s in students if s.get("id")}

    # parent_id -> ordered, de-duplicated list of linked children.
    children_by_parent: Dict[str, List[Dict[str, Any]]] = {}
    seen_pair: set = set()
    for link in links:
        pid = link.get("parent_id")
        sid = link.get("student_id")
        if not pid or not sid:
            continue
        key = (pid, sid)
        if key in seen_pair:
            continue
        seen_pair.add(key)
        student = student_by_id.get(sid)
        if not student:
            # Link points at an inactive / removed student — skip so the
            # count reflects only live children.
            continue
        children_by_parent.setdefault(pid, []).append({
            "id": sid,
            "name": student.get("full_name") or link.get("student_name") or "",
            "class_name": student.get("class_name"),
        })

    parent_ids = list(children_by_parent.keys())
    parents: List[Dict[str, Any]] = []
    if parent_ids:
        parents = await gd_find(
            db.session, "parents",
            {"id": {"$in": parent_ids}, "school_id": workspace_id},
            limit=5000,
        )

    # Preload every workspace parent users row once (IT workspaces are
    # small) so per-parent resolution is in-memory.
    parent_users = await gd_find(
        db.session, "users",
        {"role": "parent", "tenant_id": workspace_id},
        limit=5000,
    )
    users_by_id = {u["id"]: u for u in parent_users if u.get("id")}
    users_by_parent_id = {
        u["parent_id"]: u for u in parent_users if u.get("parent_id")
    }
    users_by_email = {
        u["email"]: u for u in parent_users if u.get("email")
    }

    out_parents: List[Dict[str, Any]] = []
    for p in parents:
        pid = p["id"]
        ref = _parent_ref_for(pid, links)
        user = None
        if ref:
            user = users_by_id.get(ref)
        if not user:
            user = users_by_parent_id.get(pid)
        if not user and p.get("email"):
            user = users_by_email.get(p["email"])

        children = children_by_parent.get(pid, [])
        out_parents.append({
            "id": pid,
            "full_name": p.get("full_name") or "",
            "phone": p.get("phone"),
            "email": p.get("email"),
            "national_id": p.get("national_id"),
            "children": children,
            "children_count": len(children),
            "user_id": user.get("id") if user else None,
            "login_email": user.get("email") if user else None,
            "has_login_account": user is not None,
            "portal_state": _portal_state(user),
            "last_login": user.get("last_login") if user else None,
            "is_active": bool(user.get("is_active")) if user else False,
        })

    out_parents.sort(key=lambda r: (r["full_name"] or "").strip())

    # Pending students — active students that still only carry inline
    # pending parent contact info (no linked parent_id yet). The FE
    # offers a deliberate "materialise / link" action that calls the
    # canonical invite-parent endpoint.
    pending: List[Dict[str, Any]] = []
    for s in students:
        if s.get("parent_id"):
            continue
        name = s.get("pending_parent_name")
        phone = s.get("pending_parent_phone")
        email = s.get("pending_parent_email")
        if not (name or phone or email):
            continue
        pending.append({
            "student_id": s["id"],
            "student_name": s.get("full_name") or "",
            "class_name": s.get("class_name"),
            "pending_parent_name": name,
            "pending_parent_phone": phone,
            "pending_parent_email": email,
        })
    pending.sort(key=lambda r: (r["student_name"] or "").strip())

    return {
        "parents": out_parents,
        "pending": pending,
        "counts": {"linked": len(out_parents), "pending": len(pending)},
    }


# -- Endpoint: GET detail -------------------------------------------------

@router.get("/independent-teacher/parents/{parent_id}")
async def get_workspace_parent(
    parent_id: str,
    current_user: dict = Depends(_require_independent_teacher),
) -> Dict[str, Any]:
    workspace_id = require_request_school_id(current_user)
    parent = await _load_workspace_parent(parent_id, workspace_id)

    links = await gd_find(
        db.session, "guardian_links",
        {"tenant_id": workspace_id, "parent_id": parent_id, "is_active": True},
        limit=2000,
    )
    student_ids = [link["student_id"] for link in links if link.get("student_id")]
    students_by_id: Dict[str, Any] = {}
    if student_ids:
        rows = await gd_find(
            db.session, "students",
            {"id": {"$in": student_ids}, "school_id": workspace_id, "is_active": True},
            limit=2000,
        )
        students_by_id = {s["id"]: s for s in rows if s.get("id")}

    children: List[Dict[str, Any]] = []
    seen: set = set()
    for link in links:
        sid = link.get("student_id")
        if not sid or sid in seen:
            continue
        student = students_by_id.get(sid)
        if not student:
            continue
        seen.add(sid)
        children.append({
            "id": sid,
            "name": student.get("full_name") or link.get("student_name") or "",
            "class_name": student.get("class_name"),
            "relationship": link.get("relationship"),
            "is_primary": bool(link.get("is_primary")),
        })

    ref = _parent_ref_for(parent_id, links)
    user = await _resolve_workspace_parent_user(parent, workspace_id, parent_ref=ref)

    return {
        "id": parent_id,
        "full_name": parent.get("full_name") or "",
        "phone": parent.get("phone"),
        "email": parent.get("email"),
        "national_id": parent.get("national_id"),
        "children": children,
        "children_count": len(children),
        "user_account": {
            "user_id": user.get("id") if user else None,
            "login_email": user.get("email") if user else None,
            "has_login_account": user is not None,
            "portal_state": _portal_state(user),
            "last_login": user.get("last_login") if user else None,
            "is_active": bool(user.get("is_active")) if user else False,
            "must_change_password": bool(user.get("must_change_password")) if user else False,
        },
    }


# -- Endpoint: PUT rotate credentials -------------------------------------

@router.put("/independent-teacher/parents/{parent_id}/credentials")
async def rotate_workspace_parent_credentials(
    parent_id: str,
    payload: RotateCredentialsRequest,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
) -> Dict[str, Any]:
    """Set / rotate the parent portal login. Returns the password ONCE.

    No email is sent; the stored hash is never returned. The parent is
    forced to change the password on first login.
    """
    workspace_id = require_request_school_id(current_user)
    parent = await _load_workspace_parent(parent_id, workspace_id)

    if payload.new_password and len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail=_MSG_PASSWORD_TOO_SHORT)

    ref = None
    ref_link = await gd_find_one(
        db.session, "guardian_links",
        {"tenant_id": workspace_id, "parent_id": parent_id, "is_active": True},
    )
    if ref_link:
        ref = ref_link.get("parent_ref")

    user = await _resolve_workspace_parent_user(parent, workspace_id, parent_ref=ref)

    # Resolve the login email. A caller-supplied email wins; otherwise
    # reuse the existing real login email, then the parent profile email.
    new_email: Optional[str] = payload.new_email
    plaintext = payload.new_password or _generate_password()
    pwd_hash = hash_password(plaintext)
    now = _utcnow_iso()

    # Global uniqueness on users.email (excluding the row we will update).
    if new_email:
        dup = await gd_find_one(
            db.session, "users",
            {"email": new_email, "id": {"$ne": (user or {}).get("id", "")}},
        )
        if dup:
            raise HTTPException(status_code=400, detail=_MSG_EMAIL_TAKEN)

    account_created = False
    try:
        async with db.session.begin_nested():
            if user:
                updates: Dict[str, Any] = {
                    "password_hash": pwd_hash,
                    "must_change_password": True,
                    "is_active": True,
                    "last_password_change": now,
                    "updated_at": now,
                }
                # Only switch the login email when the caller supplies an
                # explicit, already-uniqueness-checked address. We never
                # auto-swap to parent.email here — that value is not
                # guaranteed globally unique and a collision would surface
                # as an opaque DB-level 500.
                if new_email and new_email != user.get("email"):
                    updates["email"] = new_email
                await gd_update_one(
                    db.session, "users", {"id": user["id"]}, updates,
                )
                final_email = updates.get("email", user.get("email"))
                final_user_id = user["id"]
            else:
                # No portal users row yet (legacy dedupe parent). Materialise
                # one pinned to this workspace. Fall back to a deterministic
                # placeholder email only when none is usable.
                final_user_id = str(uuid.uuid4())
                candidate_email = new_email or parent.get("email")
                if candidate_email:
                    collision = await gd_find_one(
                        db.session, "users", {"email": candidate_email},
                    )
                    if collision:
                        candidate_email = None
                final_email = (
                    candidate_email
                    or f"parent+{parent_id}{_INVALID_EMAIL_DOMAIN}"
                )
                await gd_insert(db.session, "users", {
                    "id": final_user_id,
                    "role": "parent",
                    "tenant_id": workspace_id,
                    "parent_id": parent_id,
                    "email": final_email,
                    "phone": parent.get("phone"),
                    "full_name": parent.get("full_name") or "",
                    "password_hash": pwd_hash,
                    "must_change_password": True,
                    "is_active": True,
                    "last_password_change": now,
                    "preferred_language": "ar",
                    "preferred_theme": "light",
                    "created_at": now,
                    "updated_at": now,
                })
                account_created = True

            # Keep the parent profile email aligned with a real login email.
            if new_email and new_email != parent.get("email"):
                await gd_update_one(
                    db.session, "parents", {"id": parent_id},
                    {"email": new_email, "updated_at": now},
                )

            await audit_engine.log(
                action=_AUDIT_CREDENTIALS,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="parent",
                entity_id=parent_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "user_id": current_user["id"],
                    "parent_id": parent_id,
                    "parent_user_id": final_user_id,
                    "account_created": account_created,
                    "email_changed": bool(new_email),
                },
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                actor_email=current_user.get("email"),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — last-line safety net.
        logger.warning(
            "rotate parent credentials failed parent=%s user=%s: %s",
            parent_id, current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    return {
        "success": True,
        "account_created": account_created,
        "login_email": final_email,
        # One-time plaintext — never stored, never logged.
        "password": plaintext,
        "must_change_password": True,
    }


__all__ = ["router"]
