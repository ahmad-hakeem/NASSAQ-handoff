"""
Independent-Teacher — Invite Parent (atomic Pending → Linked).

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §5.6, §5.7.
Task: #199 (IT-P1-9).

CANONICAL SINGLE WRITER — this module is the ONLY backend path that
flips ``students.parent_id`` from NULL → non-NULL for an Independent-
Teacher account. No other route may perform that transition.

Endpoints (IT-only, Tier-A MFA step-up):

  * ``POST   /independent-teacher/students/{student_id}/invite-parent``
      Atomically dedupes / creates the ``parents`` row, inserts a
      ``guardian_links`` row tagged ``tenant_id == itw_{user_id}``,
      sets ``students.parent_id`` (the
      ``students_clear_pending_parent_on_link_trg`` trigger from
      Alembic ``z1a2b3c4d5e6`` then clears ``pending_parent_*``),
      and writes one ``audit_logs`` row of action
      ``INDEPENDENT_TEACHER_PARENT_LINK``. All-or-nothing.

  * ``PATCH  /independent-teacher/students/{student_id}/pending-parent``
      Editor for the inline pending contact while the student is
      still in the Pending state. Returns 409 with the verbatim
      §5.6 message if the row has already been linked, since the
      Pending → Linked transition (above) is the only writer that
      may flip ``parent_id``.

Dedupe order is FROZEN (spec §5.6, first match wins, no fuzzy):

  1. ``national_id`` if provided.
  2. ``(phone, email)`` exact pair.
  3. ``phone`` alone (when email absent).
  4. ``email`` alone (when phone absent).

On a match, ``parents`` row updates are conservative — only NULL
fields are filled; established parent data is never overwritten.
``parents.school_id`` is set on first creation only; cross-tenant
links never rewrite it. Tenant scoping ALWAYS flows through
``guardian_links.tenant_id``.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator

_security = HTTPBearer(auto_error=False)

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import audit_engine, db, get_current_user, require_recent_mfa
from engines.sql_utils import gd_count, gd_find_one, gd_insert, gd_update_one


logger = logging.getLogger("nassaq.it_invite_parent")

router = APIRouter()


# -- Safe Arabic copy -----------------------------------------------------

_MSG_INTERNAL = "تعذّر ربط ولي الأمر — حاول لاحقًا."
_MSG_STUDENT_NOT_FOUND = "الطالب غير موجود"
_MSG_NEED_IDENTIFIER = "يلزم إدخال رقم الجوال أو البريد الإلكتروني أو رقم الهوية"
_MSG_ALREADY_LINKED_EDIT = (
    "بيانات ولي الأمر مرتبطة بحساب — عدّلها من ملف ولي الأمر."
)
_MSG_ALREADY_LINKED_INVITE = (
    "هذا الطالب مرتبط بولي أمر بالفعل."
)

_AUDIT_ACTION = "INDEPENDENT_TEACHER_PARENT_LINK"


# -- Request models -------------------------------------------------------

class InviteParentRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[EmailStr] = None
    national_id: Optional[str] = Field(default=None, max_length=32)
    relationship: Optional[str] = Field(default="guardian", max_length=32)

    @field_validator("full_name", "phone", "national_id", "relationship")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s or None


class PendingParentPatch(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=32)
    email: Optional[EmailStr] = None

    @field_validator("full_name", "phone")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
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


# Per Task #199 "Done looks like" + Step 6: this surface returns
# **403** (not 401) when fresh MFA is missing, so the existing
# sensitive-action step-up modal pattern (AccountSettingsPage UX)
# can drive a Tier-A re-auth. The canonical step-up payload (``code``
# / ``challenge_endpoint`` / ``max_age_seconds``) is preserved
# verbatim from the underlying ``require_recent_mfa`` dependency.
_BASE_RECENT_MFA_DEP = require_recent_mfa()


async def _require_recent_mfa_403(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    current_user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await _BASE_RECENT_MFA_DEP(
            credentials=credentials, current_user=current_user,
        )
    except HTTPException as exc:
        if exc.status_code == 401 and isinstance(exc.detail, dict) and (
            exc.detail.get("code") in {
                "MFA_STEPUP_REQUIRED",
                "MFA_PASSKEY_REQUIRED",
                "MFA_RESTORE_REQUIRED",
            }
        ):
            raise HTTPException(status_code=403, detail=exc.detail) from exc
        raise


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _load_workspace_student(student_id: str, school_id: str) -> Dict[str, Any]:
    """Fetch the student row scoped to the IT workspace.

    Cross-tenant lookups MUST 404 (never 403) so the route never
    confirms the existence of a student in another tenant
    (spec §8 inv. 3).
    """
    student = await gd_find_one(
        db.session, "students",
        {"id": student_id, "school_id": school_id},
    )
    if not student:
        raise HTTPException(status_code=404, detail=_MSG_STUDENT_NOT_FOUND)
    return student


async def _dedupe_parent(payload: InviteParentRequest) -> tuple[Optional[Dict[str, Any]], str]:
    """Apply the frozen four-step dedupe. Returns ``(parent_or_None, matched_by)``.

    ``matched_by`` ∈ {"national_id", "phone_email", "phone", "email", "new"}.
    First match wins; no fuzzy matching.
    """
    # Step 1 — national_id.
    if payload.national_id:
        row = await gd_find_one(
            db.session, "parents", {"national_id": payload.national_id},
        )
        if row:
            return row, "national_id"

    # Step 2 — (phone, email) exact pair.
    if payload.phone and payload.email:
        row = await gd_find_one(
            db.session, "parents",
            {"phone": payload.phone, "email": payload.email},
        )
        if row:
            return row, "phone_email"

    # Step 3 — phone alone (when email absent).
    if payload.phone and not payload.email:
        row = await gd_find_one(
            db.session, "parents", {"phone": payload.phone},
        )
        if row:
            return row, "phone"

    # Step 4 — email alone (when phone absent).
    if payload.email and not payload.phone:
        row = await gd_find_one(
            db.session, "parents", {"email": payload.email},
        )
        if row:
            return row, "email"

    return None, "new"


def _conservative_fill(existing: Dict[str, Any], payload: InviteParentRequest) -> Dict[str, Any]:
    """Build a partial update that ONLY fills NULL columns on the
    matched parent row. Established values are NEVER overwritten.
    Returns an empty dict when nothing needs to change.
    """
    updates: Dict[str, Any] = {}
    if not existing.get("full_name") and payload.full_name:
        updates["full_name"] = payload.full_name
    if not existing.get("phone") and payload.phone:
        updates["phone"] = payload.phone
    if not existing.get("email") and payload.email:
        updates["email"] = payload.email
    if not existing.get("national_id") and payload.national_id:
        updates["national_id"] = payload.national_id
    if updates:
        updates["updated_at"] = _utcnow_iso()
    return updates


# -- Endpoint: POST invite-parent -----------------------------------------

@router.post("/independent-teacher/students/{student_id}/invite-parent")
async def invite_parent(
    student_id: str,
    payload: InviteParentRequest,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_require_recent_mfa_403),
):
    """Atomic Pending → Linked transition. See module docstring."""
    # Require at least one identifier (spec: 422 with safe Arabic).
    if not (payload.phone or payload.email or payload.national_id):
        raise HTTPException(status_code=422, detail=_MSG_NEED_IDENTIFIER)

    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    student = await _load_workspace_student(student_id, school_id)

    # If already linked, refuse — this endpoint is only for the
    # Pending → Linked transition (single-writer invariant).
    if student.get("parent_id"):
        raise HTTPException(status_code=409, detail=_MSG_ALREADY_LINKED_INVITE)

    # Begin atomic block. Any inner failure rolls everything back.
    try:
        async with db.session.begin_nested():
            existing_parent, matched_by = await _dedupe_parent(payload)

            if existing_parent:
                parent_id = existing_parent["id"]
                conservative = _conservative_fill(existing_parent, payload)
                if conservative:
                    await gd_update_one(
                        db.session, "parents",
                        {"id": parent_id},
                        conservative,
                    )
            else:
                parent_id = str(uuid.uuid4())
                now = _utcnow_iso()
                await gd_insert(db.session, "parents", {
                    "id": parent_id,
                    "full_name": payload.full_name or (
                        student.get("pending_parent_name")
                        or "ولي الأمر"
                    ),
                    "phone": payload.phone,
                    "email": payload.email,
                    "national_id": payload.national_id,
                    # First-creation only — never rewritten on cross-tenant link.
                    "school_id": workspace_id,
                    "is_active": True,
                    "student_ids": [student_id],
                    "created_at": now,
                    "updated_at": now,
                })

            # guardian_links — tenant_id MUST be the workspace id
            # (spec §8 inv. 8). is_primary defaults true when no other
            # primary link for this student exists.
            existing_primary = await gd_count(
                db.session, "guardian_links",
                {
                    "tenant_id": workspace_id,
                    "student_id": student_id,
                    "is_primary": True,
                    "is_active": True,
                },
            )
            # Task #203 (§5.9 #7): on EVERY new-parent path, materialise
            # a workspace-scoped `users` row so the cohort resolver in
            # `/notifications/bulk` can find the recipient. Dedupe paths
            # (existing parent reused) keep the legacy parent_ref=parent_id
            # behaviour and will gain portal accounts via Phase-2 onboarding.
            #
            # `users.email` is NOT NULL + globally UNIQUE. To honour both:
            #   - When the payload has no email, OR a global users row
            #     already owns that email (cross-workspace collision),
            #     synthesise a deterministic non-deliverable placeholder
            #     keyed off the freshly minted parent_id (uuid4 → unique).
            #     The `.invalid` TLD is reserved (RFC 6761) so this can
            #     never collide with a real address. The sentinel
            #     password_hash also blocks any login attempt.
            parent_user_id_for_ref = parent_id  # legacy fallback (dedupe paths)
            parent_user_materialised = False
            user_email_for_insert: Optional[str] = None
            if not existing_parent:
                if payload.email:
                    email_collision = await gd_find_one(
                        db.session, "users", {"email": payload.email}
                    )
                    if not email_collision:
                        user_email_for_insert = payload.email
                if user_email_for_insert is None:
                    user_email_for_insert = (
                        f"invite+{parent_id}@invite.nassaq.invalid"
                    )
                parent_user_id_for_ref = str(uuid.uuid4())
                now_iso = _utcnow_iso()
                # `users.password_hash` is NOT NULL. The parent has no
                # portal credentials at invite time — Phase-2 will issue
                # them via a proper onboarding flow. Use a non-bcrypt
                # sentinel that can never verify so the row exists for
                # cohort resolution but cannot authenticate.
                await gd_insert(db.session, "users", {
                    "id": parent_user_id_for_ref,
                    "role": "parent",
                    "tenant_id": workspace_id,
                    "email": user_email_for_insert,
                    "phone": payload.phone,
                    "full_name": payload.full_name
                        or student.get("pending_parent_name")
                        or "ولي الأمر",
                    "password_hash": "!invite-pending",
                    "must_change_password": True,
                    "is_active": True,
                    "preferred_language": "ar",
                    "preferred_theme": "light",
                    "created_at": now_iso,
                    "updated_at": now_iso,
                })
                parent_user_materialised = True

            link_id = str(uuid.uuid4())
            now = _utcnow_iso()
            await gd_insert(db.session, "guardian_links", {
                "id": link_id,
                "tenant_id": workspace_id,
                "student_id": student_id,
                "student_name": student.get("full_name"),
                "parent_id": parent_id,
                "parent_ref": parent_user_id_for_ref,
                "parent_name": (
                    payload.full_name
                    or (existing_parent or {}).get("full_name")
                ),
                "relationship": payload.relationship or "guardian",
                "is_primary": existing_primary == 0,
                "is_active": True,
                "permissions": {
                    "can_pickup": True,
                    "can_view_grades": True,
                    "can_view_attendance": True,
                    "can_communicate": True,
                },
                "linked_by": current_user["id"],
                "linked_at": now,
                "updated_at": now,
            })

            # Flip parent_id NULL → non-NULL. The
            # students_clear_pending_parent_on_link_trg trigger from
            # migration z1a2b3c4d5e6 wipes pending_parent_* atomically.
            updated = await gd_update_one(
                db.session, "students",
                {"id": student_id, "school_id": school_id},
                {
                    "parent_id": parent_id,
                    "updated_at": _utcnow_iso(),
                },
            )
            if not updated:
                # The student vanished mid-transaction — bail out so
                # the SAVEPOINT rolls back the parent / link writes.
                raise HTTPException(status_code=404, detail=_MSG_STUDENT_NOT_FOUND)

            # Audit row — same transaction.
            await audit_engine.log(
                action=_AUDIT_ACTION,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="student",
                entity_id=student_id,
                details={
                    "school_id": school_id,
                    "tenant_id": workspace_id,
                    "user_id": current_user["id"],
                    "student_id": student_id,
                    "parent_id": parent_id,
                    "matched_by": matched_by,
                    "parent_user_materialised": parent_user_materialised,
                    "parent_user_id": parent_user_id_for_ref,
                },
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                actor_email=current_user.get("email"),
            )

        # Re-read the freshly linked parent for the response payload.
        parent_row = await gd_find_one(db.session, "parents", {"id": parent_id})
        link_row = await gd_find_one(db.session, "guardian_links", {"id": link_id})
        return {
            "parent": parent_row,
            "link": link_row,
            "matched_by": matched_by,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — last-line safety net.
        # Atomicity contract: the ``async with db.session.begin_nested()``
        # SAVEPOINT context unwinds and rolls back ALL writes in this
        # block (parents/guardian_links/students/audit) before this
        # handler runs. We deliberately do NOT call
        # ``db.session.rollback()`` here — that would discard the
        # outer request transaction and any unrelated state owned by
        # upstream middleware. The forced-rollback test
        # ``test_invite_parent_rolls_back_on_audit_failure`` validates
        # that no half-linked row survives.
        logger.warning(
            "invite_parent failed for student=%s user=%s: %s",
            student_id, current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)


# -- Endpoint: PATCH pending-parent ---------------------------------------

@router.patch("/independent-teacher/students/{student_id}/pending-parent")
async def patch_pending_parent(
    student_id: str,
    payload: PendingParentPatch,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_require_recent_mfa_403),
):
    """Edit ``students.pending_parent_*`` while the student is still
    in the Pending state. Refuses with 409 + the verbatim §5.6
    message if the row has already transitioned to Linked
    (``parent_id IS NOT NULL``) — only ``invite_parent`` may flip
    that bit.
    """
    school_id = require_request_school_id(current_user)
    student = await _load_workspace_student(student_id, school_id)

    # 409 edit-conflict guard — see module docstring.
    if student.get("parent_id"):
        raise HTTPException(status_code=409, detail=_MSG_ALREADY_LINKED_EDIT)

    updates: Dict[str, Any] = {}
    if payload.full_name is not None:
        updates["pending_parent_name"] = payload.full_name
    if payload.phone is not None:
        updates["pending_parent_phone"] = payload.phone
    if payload.email is not None:
        updates["pending_parent_email"] = payload.email

    if not updates:
        return {"ok": True, "updated_fields": []}

    updates["updated_at"] = _utcnow_iso()
    await gd_update_one(
        db.session, "students",
        {"id": student_id, "school_id": school_id},
        updates,
    )
    return {
        "ok": True,
        "updated_fields": [k for k in updates.keys() if k != "updated_at"],
    }
