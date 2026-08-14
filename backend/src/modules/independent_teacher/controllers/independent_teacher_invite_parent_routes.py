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
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator

_security = HTTPBearer(auto_error=False)

from src.core.guards.tenant_guard import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import db, get_current_user, require_recent_mfa
from engines.sql_utils import gd_find_one, gd_update_one
from src.common.utils.it_parent_link import link_workspace_parent_to_student


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


# -- Endpoint: POST invite-parent -----------------------------------------

def _parent_invitations_enabled() -> bool:
    """Phase-2 §6.2 feature flag.

    Default OFF in dev/test so every existing §5.6 test stays green and
    the v1 "credentials out-of-band" contract is preserved until the
    §6.2c FE lands. When ON, this route delegates to the §6.2b create
    endpoint instead of performing the immediate Pending → Linked
    transition. Read at request time so tests can flip the env var
    without re-importing.
    """
    return os.getenv("IT_PARENT_INVITATIONS_ENABLED", "0").lower() in {
        "1", "true", "yes", "on",
    }


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

    # Phase-2 §6.2 — when the invitation envelope is enabled, route the
    # legacy v1 endpoint through the §6.2b create surface. The same
    # IT-role + Tier-A MFA gates already cleared above are sufficient
    # for the create call (we are inlining, not re-dispatching).
    if _parent_invitations_enabled():
        if not (payload.phone or payload.email):
            # The invitation envelope requires a deliverable channel.
            raise HTTPException(status_code=422, detail=_MSG_NEED_IDENTIFIER)
        from src.modules.independent_teacher.controllers.independent_teacher_invitation_routes import (
            CreateInvitationRequest, create_parent_invitation,
        )
        # Delegate; create_parent_invitation re-runs the workspace
        # student lookup so cross-tenant ids still 404.
        return await create_parent_invitation(
            student_id=student_id,
            payload=CreateInvitationRequest(
                parent_email=payload.email,
                parent_phone=payload.phone,
            ),
            current_user=current_user,
            _mfa=current_user,
        )

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
            result = await link_workspace_parent_to_student(
                db.session,
                student=student,
                workspace_id=workspace_id,
                school_id=school_id,
                full_name=payload.full_name,
                phone=payload.phone,
                email=payload.email,
                national_id=payload.national_id,
                relationship=payload.relationship,
                actor=current_user,
            )

        return {
            "parent": result["parent"],
            "link": result["link"],
            "matched_by": result["matched_by"],
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
