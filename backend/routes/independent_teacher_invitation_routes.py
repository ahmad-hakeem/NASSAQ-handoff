"""
Independent-Teacher — Parent Invitation envelope (§6.2b).

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.2.
Task: #205 (IT-P2 §6.2b).

Three HTTP surfaces:

  * ``POST   /independent-teacher/students/{student_id}/invite-parent-invitation``
      IT-only, Tier-A MFA step-up. Mints a one-shot ``parent_invitations``
      row + signed token (``utils.tokens.mint_invitation_token``).
      Idempotent for the ``(workspace_school_id, student_id)`` pending
      slot — a second create while a row is ``pending`` returns the
      existing row instead of duplicating.

  * ``POST   /independent-teacher/parent-invitations/{id}/cancel``
      IT-only, Tier-A MFA step-up. Flips ``status: pending → cancelled``
      and writes an audit row. Cancelling a non-pending row → 409.

  * ``POST   /public/parent-invitations/accept``
      Unauthenticated (IP rate-limited via the existing ``rate_store``).
      Verifies token signature + hash + expiry + status, then atomically:
        * flips ``status: pending → accepted``,
        * dedupes the parent (same four-step rule as §5.6),
        * materialises the workspace ``users`` row (real email, with the
          deterministic ``.invalid`` placeholder fallback when the email
          collides with a global ``users`` row — closes the Task #203
          carryover for the dedupe paths),
        * inserts/activates the ``guardian_links`` row tagged
          ``tenant_id == workspace_school_id``,
        * returns a one-shot bearer token bound to the parent role so
          the FE can deep-link straight into the portal.

All three routes return ``404`` (never 403/200) for cross-workspace
ids per §8 invariant 3. The IT-create and IT-cancel routes emit the
canonical step-up envelope when MFA is missing.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import (
    audit_engine,
    create_access_token,
    db,
    get_current_user,
    require_recent_mfa_403,
)
from engines.sql_utils import gd_count, gd_find_one, gd_insert, gd_update_one
from middleware.rate_limiter import rate_store
from pg_models import ParentInvitation, Student
from utils.tokens import (
    mint_invitation_token,
    token_hash as _token_hash,
    verify_invitation_token,
)
from utils.trusted_proxy import extract_client_ip


logger = logging.getLogger("nassaq.it_invitation")

router = APIRouter()


# -- Audit actions --------------------------------------------------------

AUDIT_INVITATION_CREATED = "INDEPENDENT_TEACHER_INVITATION_CREATED"
AUDIT_INVITATION_CANCELLED = "INDEPENDENT_TEACHER_INVITATION_CANCELLED"
AUDIT_INVITATION_ACCEPTED = "INDEPENDENT_TEACHER_INVITATION_ACCEPTED"


# -- Safe Arabic copy -----------------------------------------------------

_MSG_INTERNAL = "تعذّر إنشاء الدعوة — حاول لاحقًا."
_MSG_INTERNAL_ACCEPT = "تعذّر قبول الدعوة — حاول لاحقًا."
_MSG_STUDENT_NOT_FOUND = "الطالب غير موجود"
_MSG_NEED_IDENTIFIER = "يلزم إدخال رقم الجوال أو البريد الإلكتروني"
_MSG_ALREADY_LINKED = "هذا الطالب مرتبط بولي أمر بالفعل."
_MSG_INVITATION_NOT_FOUND = "الدعوة غير موجودة"
_MSG_INVITATION_BAD_STATE = "لا يمكن إلغاء هذه الدعوة بحالتها الحالية."
_MSG_INVITATION_INVALID = "رابط الدعوة غير صالح أو منتهي الصلاحية."
_MSG_RATE_LIMITED = "عدد المحاولات تجاوز الحد المسموح. حاول لاحقًا."

# Rate limit for the public accept surface — per IP, separate from the
# centralised RATE_LIMITS table because we want to apply it inside the
# handler (the table-driven middleware doesn't yet wire the public
# router prefix). 10 attempts / 5 minutes per IP is generous for a
# legitimate parent following an emailed link but still kills brute
# enumeration of `token_hash` values.
_ACCEPT_RATE_MAX = 10
_ACCEPT_RATE_WINDOW = 300

_USER_PASSWORD_SENTINEL = "!invite-pending"
_INVALID_EMAIL_DOMAIN = "@invite.nassaq.invalid"


# -- Request / response models -------------------------------------------

class CreateInvitationRequest(BaseModel):
    parent_email: Optional[EmailStr] = None
    parent_phone: Optional[str] = Field(default=None, max_length=32)

    @field_validator("parent_phone")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s or None


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=10, max_length=4096)
    full_name: Optional[str] = Field(default=None, max_length=200)
    national_id: Optional[str] = Field(default=None, max_length=32)

    @field_validator("token", "full_name", "national_id")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s or None


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


_recent_mfa_403_dep = require_recent_mfa_403()


def _invitation_to_dict(row: ParentInvitation) -> Dict[str, Any]:
    """Project a ``ParentInvitation`` ORM row to the legacy dict shape used
    by the route's serialiser/audit/notify code paths.

    The route layer historically consumed ``gd_find_one`` dicts; keeping the
    same shape avoids a sweeping rewrite of every ``row.get(...)`` callsite.
    """
    return {
        "id": row.id,
        "workspace_school_id": row.workspace_school_id,
        "student_id": row.student_id,
        "parent_email": row.parent_email,
        "parent_phone": row.parent_phone,
        "token_hash": row.token_hash,
        "sent_at": row.sent_at,
        "accepted_at": row.accepted_at,
        "expires_at": row.expires_at,
        "status": row.status,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def _find_invitation(**filters) -> Optional[ParentInvitation]:
    stmt = select(ParentInvitation)
    for key, value in filters.items():
        stmt = stmt.where(getattr(ParentInvitation, key) == value)
    stmt = stmt.limit(1)
    result = await db.session.execute(stmt)
    return result.scalars().first()


async def _load_workspace_student(student_id: str, school_id: str) -> Dict[str, Any]:
    """Tenant-pinned student lookup. Cross-tenant → 404 (§8 inv. 3)."""
    student = await gd_find_one(
        db.session, "students",
        {"id": student_id, "school_id": school_id},
    )
    if not student:
        raise HTTPException(status_code=404, detail=_MSG_STUDENT_NOT_FOUND)
    return student


# -- Endpoint: POST create invitation -------------------------------------

@router.post("/independent-teacher/students/{student_id}/invite-parent-invitation")
async def create_parent_invitation(
    student_id: str,
    payload: CreateInvitationRequest,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
):
    """Create (or return the existing pending) parent invitation."""
    if not (payload.parent_email or payload.parent_phone):
        raise HTTPException(status_code=422, detail=_MSG_NEED_IDENTIFIER)

    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    student = await _load_workspace_student(student_id, school_id)
    if student.get("parent_id"):
        raise HTTPException(status_code=409, detail=_MSG_ALREADY_LINKED)

    # Idempotency: if a pending invitation already exists for this
    # (workspace, student) pair, return it verbatim. Token is NOT
    # rotated — the original recipient may still hold the link.
    existing = await _find_invitation(
        workspace_school_id=workspace_id,
        student_id=student_id,
        status="pending",
    )
    if existing:
        existing_d = _invitation_to_dict(existing)
        return _serialise_invitation(existing_d, channels=_channels(existing_d), reused=True)

    raw_token, t_hash, expires_at = mint_invitation_token(workspace_id, student_id)
    now = _utcnow()
    invitation_id = str(uuid.uuid4())
    row = {
        "id": invitation_id,
        "workspace_school_id": workspace_id,
        "student_id": student_id,
        "parent_email": payload.parent_email,
        "parent_phone": payload.parent_phone,
        "token_hash": t_hash,
        "sent_at": now,
        "accepted_at": None,
        "expires_at": expires_at,
        "status": "pending",
        "created_by": current_user["id"],
        "created_at": now,
        "updated_at": now,
    }
    try:
        async with db.session.begin_nested():
            db.session.add(ParentInvitation(**row))
            await db.session.flush()
            await audit_engine.log(
                action=AUDIT_INVITATION_CREATED,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="parent_invitation",
                entity_id=invitation_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "student_id": student_id,
                    "user_id": current_user["id"],
                    "parent_email": payload.parent_email,
                    "parent_phone": payload.parent_phone,
                    "expires_at": expires_at.isoformat(),
                },
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                actor_email=current_user.get("email"),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "create_parent_invitation failed for student=%s user=%s: %s",
            student_id, current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    fresh_row = await _find_invitation(id=invitation_id)
    fresh = _invitation_to_dict(fresh_row) if fresh_row else None
    payload_out = _serialise_invitation(fresh or row, channels=_channels(row), reused=False)
    # The raw token is returned ONCE so the calling adapter (Phase-2
    # email/SMS sender) can hand it to the user. Never logged.
    payload_out["token"] = raw_token
    return payload_out


def _channels(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "email": bool(row.get("parent_email")),
        "sms": bool(row.get("parent_phone")),
    }


def _serialise_invitation(
    row: Dict[str, Any],
    *,
    channels: Dict[str, Any],
    reused: bool,
) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "expires_at": _iso(row.get("expires_at")),
        "sent_at": _iso(row.get("sent_at")),
        "accepted_at": _iso(row.get("accepted_at")),
        "parent_email": row.get("parent_email"),
        "parent_phone": row.get("parent_phone"),
        "student_id": row.get("student_id"),
        "channels": channels,
        "reused": reused,
    }


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


# -- Endpoint: GET latest invitation by student id ------------------------
#
# Tiny read surface added in #206 (IT-P2 §6.2c) so the IT student-detail
# UI can render the chip (pending / accepted / expired / cancelled)
# without bolting onto the create-idempotency path. Returns the most
# recent row for the (workspace, student) pair, regardless of status,
# or 204 when no invitation exists. Cross-workspace student ids 404
# per §8 inv. 3 (the workspace pin on `parent_invitations` enforces it).

@router.get("/independent-teacher/students/{student_id}/parent-invitation")
async def get_latest_parent_invitation(
    student_id: str,
    current_user: dict = Depends(_require_independent_teacher),
):
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    # 404 the cross-tenant case before reading invitations.
    await _load_workspace_student(student_id, school_id)

    stmt = (
        select(ParentInvitation)
        .where(ParentInvitation.workspace_school_id == workspace_id)
        .where(ParentInvitation.student_id == student_id)
        .order_by(ParentInvitation.created_at.desc())
        .limit(1)
    )
    result = await db.session.execute(stmt)
    inv_row = result.scalars().first()
    if not inv_row:
        return {"invitation": None}
    row = _invitation_to_dict(inv_row)
    # Surface the derived "expired" view to the FE without touching the
    # stored status (cancellation/acceptance always win over expiry).
    derived_status = row.get("status")
    if derived_status == "pending":
        try:
            exp = row.get("expires_at")
            if isinstance(exp, str):
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            else:
                exp_dt = exp
            if exp_dt and exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt and exp_dt < _utcnow():
                derived_status = "expired"
        except (ValueError, TypeError):
            pass
    out = _serialise_invitation(row, channels=_channels(row), reused=False)
    out["status"] = derived_status
    # When the invitation is accepted, surface the linked parent's name
    # so the FE chip tooltip can read like "Linked to <parent name>".
    # Falls back silently when the linked parent_id is missing.
    if derived_status == "accepted":
        try:
            student_row = await gd_find_one(
                db.session, "students",
                {"id": student_id, "school_id": school_id},
            )
            parent_id = (student_row or {}).get("parent_id")
            if parent_id:
                parent_row = await gd_find_one(
                    db.session, "parents",
                    {"id": parent_id, "school_id": workspace_id},
                )
                if parent_row and parent_row.get("full_name"):
                    out["parent_name"] = parent_row.get("full_name")
        except Exception:  # noqa: BLE001
            logger.debug("get_latest_parent_invitation: parent name lookup failed")
    return {"invitation": out}


# -- Endpoint: POST cancel ------------------------------------------------

@router.post("/independent-teacher/parent-invitations/{invitation_id}/cancel")
async def cancel_parent_invitation(
    invitation_id: str,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
):
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    # Tenant-pin the lookup so cross-workspace ids 404 (§8 inv. 3).
    inv_row = await _find_invitation(
        id=invitation_id, workspace_school_id=workspace_id,
    )
    if not inv_row:
        raise HTTPException(status_code=404, detail=_MSG_INVITATION_NOT_FOUND)

    if inv_row.status != "pending":
        raise HTTPException(status_code=409, detail=_MSG_INVITATION_BAD_STATE)
    inv = _invitation_to_dict(inv_row)

    try:
        async with db.session.begin_nested():
            inv_row.status = "cancelled"
            inv_row.updated_at = _utcnow()
            await db.session.flush()
            await audit_engine.log(
                action=AUDIT_INVITATION_CANCELLED,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="parent_invitation",
                entity_id=invitation_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "student_id": inv.get("student_id"),
                    "user_id": current_user["id"],
                    "previous_status": "pending",
                },
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                actor_email=current_user.get("email"),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "cancel_parent_invitation failed id=%s user=%s: %s",
            invitation_id, current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    fresh_row = await _find_invitation(id=invitation_id)
    fresh = _invitation_to_dict(fresh_row) if fresh_row else inv
    return _serialise_invitation(fresh, channels=_channels(fresh), reused=False)


# -- Dedupe (parents) -- mirrors §5.6 -------------------------------------

async def _dedupe_parent(
    *, national_id: Optional[str], phone: Optional[str], email: Optional[str],
    workspace_id: str,
) -> tuple[Optional[Dict[str, Any]], str]:
    """Four-step dedupe scoped to ``workspace_id``.

    All lookups are constrained by ``school_id == workspace_id`` so that a
    phone/email/national_id shared by a parent in a different IT workspace
    never causes a cross-tenant family merge (mirrors the §5.6 fix).
    """
    scope = {"school_id": workspace_id}
    if national_id:
        row = await gd_find_one(db.session, "parents", {"national_id": national_id, **scope})
        if row:
            return row, "national_id"
    if phone and email:
        row = await gd_find_one(db.session, "parents", {"phone": phone, "email": email, **scope})
        if row:
            return row, "phone_email"
    if phone and not email:
        row = await gd_find_one(db.session, "parents", {"phone": phone, **scope})
        if row:
            return row, "phone"
    if email and not phone:
        row = await gd_find_one(db.session, "parents", {"email": email, **scope})
        if row:
            return row, "email"
    return None, "new"


def _conservative_fill(
    existing: Dict[str, Any],
    *,
    full_name: Optional[str],
    phone: Optional[str],
    email: Optional[str],
    national_id: Optional[str],
) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if not existing.get("full_name") and full_name:
        updates["full_name"] = full_name
    if not existing.get("phone") and phone:
        updates["phone"] = phone
    if not existing.get("email") and email:
        updates["email"] = email
    if not existing.get("national_id") and national_id:
        updates["national_id"] = national_id
    if updates:
        updates["updated_at"] = _utcnow_iso()
    return updates


# -- Endpoint: POST public accept -----------------------------------------

@router.post("/public/parent-invitations/accept")
async def accept_parent_invitation(
    payload: AcceptInvitationRequest,
    request: Request,
):
    """Token-protected public accept endpoint.

    Unauthenticated. IP rate-limited via the existing ``rate_store``.
    See module docstring for the atomic transaction contract.
    """
    client_ip = extract_client_ip(request)
    limited, _, retry_after = await rate_store.is_rate_limited(
        f"{client_ip}:invitation_accept",
        _ACCEPT_RATE_MAX,
        _ACCEPT_RATE_WINDOW,
    )
    if limited:
        raise HTTPException(
            status_code=429,
            detail=_MSG_RATE_LIMITED,
            headers={"Retry-After": str(retry_after)},
        )

    raw_token = payload.token
    t_hash = _token_hash(raw_token)
    inv_row = await _find_invitation(token_hash=t_hash)
    if not inv_row or inv_row.status != "pending":
        raise HTTPException(status_code=400, detail=_MSG_INVITATION_INVALID)
    inv = _invitation_to_dict(inv_row)

    workspace_id = inv["workspace_school_id"]
    student_id = inv["student_id"]
    invitation_id = inv["id"]

    if not verify_invitation_token(
        raw_token, t_hash,
        workspace_school_id=workspace_id,
        student_id=student_id,
    ):
        raise HTTPException(status_code=400, detail=_MSG_INVITATION_INVALID)

    expires_at = inv.get("expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except ValueError:
            expires_at = None
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < _utcnow():
            raise HTTPException(status_code=400, detail=_MSG_INVITATION_INVALID)

    student = await gd_find_one(db.session, "students", {
        "id": student_id, "school_id": workspace_id,
    })
    if not student:
        # Workspace was torn down or student moved. Treat as invalid
        # so the public surface never confirms cross-tenant existence.
        raise HTTPException(status_code=400, detail=_MSG_INVITATION_INVALID)

    if student.get("parent_id"):
        raise HTTPException(status_code=409, detail=_MSG_ALREADY_LINKED)

    parent_email = inv.get("parent_email")
    parent_phone = inv.get("parent_phone")

    try:
        async with db.session.begin_nested():
            # Task #356 / race-condition hardening: re-acquire BOTH the
            # invitation row and the student row under SELECT ... FOR UPDATE
            # before any write so that two concurrent requests using the same
            # one-time token serialise here. Only the first request to acquire
            # the lock proceeds; subsequent requests observe status != "pending"
            # (or parent_id already set) and get 400/409 respectively.
            # This prevents duplicate parent onboarding from a single invitation.

            locked_inv_result = await db.session.execute(
                select(ParentInvitation)
                .where(ParentInvitation.id == invitation_id)
                .limit(1)
                .with_for_update()
            )
            inv_locked = locked_inv_result.scalars().first()
            if not inv_locked or inv_locked.status != "pending":
                raise HTTPException(status_code=400, detail=_MSG_INVITATION_INVALID)

            locked_stu_result = await db.session.execute(
                select(Student)
                .where(
                    Student.id == student_id,
                    Student.school_id == workspace_id,
                )
                .limit(1)
                .with_for_update()
            )
            stu_locked = locked_stu_result.scalars().first()
            if not stu_locked:
                raise HTTPException(status_code=400, detail=_MSG_INVITATION_INVALID)
            if stu_locked.parent_id:
                raise HTTPException(status_code=409, detail=_MSG_ALREADY_LINKED)

            existing_parent, matched_by = await _dedupe_parent(
                national_id=payload.national_id,
                phone=parent_phone,
                email=parent_email,
                workspace_id=workspace_id,
            )

            if existing_parent:
                parent_id = existing_parent["id"]
                fill = _conservative_fill(
                    existing_parent,
                    full_name=payload.full_name,
                    phone=parent_phone,
                    email=parent_email,
                    national_id=payload.national_id,
                )
                if fill:
                    await gd_update_one(
                        db.session, "parents", {"id": parent_id}, fill,
                    )
            else:
                parent_id = str(uuid.uuid4())
                now = _utcnow_iso()
                await gd_insert(db.session, "parents", {
                    "id": parent_id,
                    "full_name": payload.full_name or "ولي الأمر",
                    "phone": parent_phone,
                    "email": parent_email,
                    "national_id": payload.national_id,
                    "school_id": workspace_id,
                    "is_active": True,
                    "student_ids": [student_id],
                    "created_at": now,
                    "updated_at": now,
                })

            # Materialise workspace `users` row. Closes the Task #203
            # carryover for the dedupe paths: a separate-transaction
            # acceptance can safely fall back to the .invalid placeholder
            # when the real email already belongs to a global users row.
            user_email = None
            if parent_email:
                collision = await gd_find_one(
                    db.session, "users", {"email": parent_email},
                )
                if not collision:
                    user_email = parent_email
            if user_email is None:
                user_email = f"invite+{parent_id}{_INVALID_EMAIL_DOMAIN}"

            parent_user_id = str(uuid.uuid4())
            now_iso = _utcnow_iso()
            await gd_insert(db.session, "users", {
                "id": parent_user_id,
                "role": "parent",
                "tenant_id": workspace_id,
                "email": user_email,
                "phone": parent_phone,
                "full_name": payload.full_name or (
                    existing_parent.get("full_name") if existing_parent else "ولي الأمر"
                ),
                "password_hash": _USER_PASSWORD_SENTINEL,
                "must_change_password": True,
                "is_active": True,
                "preferred_language": "ar",
                "preferred_theme": "light",
                "created_at": now_iso,
                "updated_at": now_iso,
            })

            existing_primary = await gd_count(
                db.session, "guardian_links",
                {
                    "tenant_id": workspace_id,
                    "student_id": student_id,
                    "is_primary": True,
                    "is_active": True,
                },
            )
            link_id = str(uuid.uuid4())
            await gd_insert(db.session, "guardian_links", {
                "id": link_id,
                "tenant_id": workspace_id,
                "student_id": student_id,
                "student_name": student.get("full_name"),
                "parent_id": parent_id,
                "parent_ref": parent_user_id,
                "parent_name": payload.full_name or (
                    existing_parent.get("full_name") if existing_parent else None
                ),
                "relationship": "guardian",
                "is_primary": existing_primary == 0,
                "is_active": True,
                "permissions": {
                    "can_pickup": True,
                    "can_view_grades": True,
                    "can_view_attendance": True,
                    "can_communicate": True,
                },
                "linked_by": parent_user_id,
                "linked_at": now_iso,
                "updated_at": now_iso,
            })

            updated = await gd_update_one(
                db.session, "students",
                {"id": student_id, "school_id": workspace_id},
                {"parent_id": parent_id, "updated_at": _utcnow_iso()},
            )
            if not updated:
                raise HTTPException(status_code=400, detail=_MSG_INVITATION_INVALID)

            now_dt = _utcnow()
            inv_locked.status = "accepted"
            inv_locked.accepted_at = now_dt
            inv_locked.updated_at = now_dt
            await db.session.flush()

            await audit_engine.log(
                action=AUDIT_INVITATION_ACCEPTED,
                performed_by=parent_user_id,
                tenant_id=workspace_id,
                entity_type="parent_invitation",
                entity_id=invitation_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "student_id": student_id,
                    "parent_id": parent_id,
                    "parent_user_id": parent_user_id,
                    "matched_by": matched_by,
                    "email_collision_fallback": user_email != parent_email
                        and parent_email is not None,
                },
                actor_role="parent",
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "accept_parent_invitation failed id=%s: %s",
            invitation_id, exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL_ACCEPT)

    # Task #249 — surface the accepted invitation in the IT inbox so
    # the host teacher sees real-time progress on outstanding invites.
    try:
        from routes.notification_routes_mod import create_notification_internal
        from routes.independent_teacher_notifications_routes import should_send_channel
        host_user_id = inv.get("created_by")
        if host_user_id:
            host_user = await gd_find_one(db.session, "users", {"id": host_user_id})
            if host_user and await should_send_channel(host_user, "parent_accept", "in_app"):
                parent_label = (payload.full_name or "ولي الأمر").strip() or "ولي الأمر"
                student_label = (student.get("full_name") or "").strip() or "الطالب"
                await create_notification_internal(
                    title="تم قبول دعوة ولي الأمر",
                    message=f"قَبِل {parent_label} الدعوة لربط الحساب بالطالب {student_label}.",
                    title_en="Parent invitation accepted",
                    message_en=f"{parent_label} accepted the invitation linking the parent account to {student_label}.",
                    recipient_id=host_user_id,
                    notification_type="parent_invitation_accepted",
                    priority="medium",
                    related_entity="parent_invitation",
                    related_entity_id=invitation_id,
                    school_id=workspace_id,
                    category="parent_accept",
                    cta_url=f"/teacher/students?student_id={student_id}",
                    extra_data={
                        "student_id": student_id,
                        "parent_id": parent_id,
                        "parent_user_id": parent_user_id,
                    },
                )
    except Exception as exc:  # noqa: BLE001
        logger.debug("parent invite accept inbox notify failed: %s", exc)

    bearer = create_access_token({
        "sub": parent_user_id,
        "role": "parent",
        "tenant_id": workspace_id,
    })

    # Task #277 — surface the inviting teacher's display name + the
    # workspace name so the parent-side accept landing can render a
    # branded welcome card ("تمت إضافتك من قِبل الأستاذ/ة …"). Both
    # fields are best-effort and fall back to None silently so a
    # missing schools/users row never breaks the accept flow itself.
    inviter_teacher_name = None
    workspace_name = None
    try:
        host_user_id = inv.get("created_by")
        if host_user_id:
            host_row = await gd_find_one(db.session, "users", {"id": host_user_id})
            if host_row:
                inviter_teacher_name = (host_row.get("full_name") or "").strip() or None
        ws_row = await gd_find_one(db.session, "schools", {"id": workspace_id})
        if ws_row:
            workspace_name = (ws_row.get("name") or "").strip() or None
    except Exception:  # noqa: BLE001
        logger.debug("accept invitation: inviter/workspace name lookup failed")

    student_name = (student.get("full_name") or "").strip() or None

    return {
        "ok": True,
        "invitation_id": invitation_id,
        "workspace_school_id": workspace_id,
        "student_id": student_id,
        "student_name": student_name,
        "parent_id": parent_id,
        "parent_user_id": parent_user_id,
        "matched_by": matched_by,
        "inviter_teacher_name": inviter_teacher_name,
        "workspace_name": workspace_name,
        "access_token": bearer,
        "token_type": "bearer",
    }
