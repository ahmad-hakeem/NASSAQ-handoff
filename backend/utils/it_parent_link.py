"""Independent-Teacher canonical parent-link writer (shared helper).

This module holds the ONE backend implementation that flips
``students.parent_id`` from NULL → non-NULL for an Independent-Teacher
workspace. It is the extracted core of the §5.6 invite-parent writer and
is reused by:

  * ``routes/independent_teacher_invite_parent_routes.py`` — the explicit
    Pending → Linked transition (POST .../invite-parent).
  * ``routes/academics_student_routes.py`` — the IT create-student wizard,
    so a student created WITH usable parent contact info is born Linked
    instead of Pending (Task #817).

There is intentionally NO second writer: both callers funnel through
``link_workspace_parent_to_student`` so the frozen dedupe order,
conservative fill, ``guardian_links.tenant_id == workspace_id`` tagging,
portal-user materialisation, and ``INDEPENDENT_TEACHER_PARENT_LINK`` audit
stay identical across surfaces.

Dedupe order is FROZEN (spec §5.6, first match wins, no fuzzy):

  1. ``national_id`` if provided.
  2. ``(phone, email)`` exact pair.
  3. ``phone`` alone (when email absent).
  4. ``email`` alone (when phone absent).

All dedupe lookups are scoped to ``school_id == workspace_id`` so a
phone/email/national_id shared by a parent in a different IT workspace
never causes a cross-tenant family merge. On a match, ``parents`` updates
are conservative — only NULL columns are filled; established values are
never overwritten. ``parents.school_id`` is set on first creation only.

The caller MUST own the transaction. Wrap the call in a SAVEPOINT, e.g.::

    async with db.session.begin_nested():
        result = await link_workspace_parent_to_student(...)

so any inner failure rolls back ALL writes (parents / users /
guardian_links / students.parent_id / audit) as one unit.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

from dependencies import audit_engine
from engines.sql_utils import gd_count, gd_find_one, gd_insert, gd_update_one


_AUDIT_ACTION = "INDEPENDENT_TEACHER_PARENT_LINK"
_USER_PASSWORD_SENTINEL = "!invite-pending"
_INVALID_EMAIL_DOMAIN = "@invite.nassaq.invalid"
_DEFAULT_PARENT_NAME = "ولي الأمر"
_MSG_STUDENT_NOT_FOUND = "الطالب غير موجود"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def dedupe_workspace_parent(
    session,
    *,
    national_id: Optional[str],
    phone: Optional[str],
    email: Optional[str],
    workspace_id: str,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Apply the frozen four-step dedupe, scoped to ``workspace_id``.

    Returns ``(parent_or_None, matched_by)`` where ``matched_by`` ∈
    {"national_id", "phone_email", "phone", "email", "new"}.
    First match wins; no fuzzy matching.
    """
    scope = {"school_id": workspace_id}

    # Step 1 — national_id.
    if national_id:
        row = await gd_find_one(
            session, "parents", {"national_id": national_id, **scope},
        )
        if row:
            return row, "national_id"

    # Step 2 — (phone, email) exact pair.
    if phone and email:
        row = await gd_find_one(
            session, "parents", {"phone": phone, "email": email, **scope},
        )
        if row:
            return row, "phone_email"

    # Step 3 — phone alone (when email absent).
    if phone and not email:
        row = await gd_find_one(session, "parents", {"phone": phone, **scope})
        if row:
            return row, "phone"

    # Step 4 — email alone (when phone absent).
    if email and not phone:
        row = await gd_find_one(session, "parents", {"email": email, **scope})
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
    """Build a partial update that ONLY fills NULL columns on the matched
    parent row. Established values are NEVER overwritten. Returns an empty
    dict when nothing needs to change.
    """
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


async def link_workspace_parent_to_student(
    session,
    *,
    student: Dict[str, Any],
    workspace_id: str,
    school_id: str,
    full_name: Optional[str],
    phone: Optional[str],
    email: Optional[str],
    national_id: Optional[str],
    relationship: Optional[str],
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    """Canonical IT Pending → Linked writer.

    MUST be invoked inside a caller-owned SAVEPOINT/transaction so a
    failure rolls back every write as one unit. The ``student`` row must
    already exist in the DB (this performs a ``gd_update_one`` to flip
    ``parent_id``); the ``students_clear_pending_parent_on_link_trg``
    trigger then clears the ``pending_parent_*`` columns.

    Returns a dict with ``parent`` (row), ``link`` (row), ``matched_by``,
    ``parent_id``, ``parent_user_id``, and ``parent_user_materialised``.
    """
    student_id = student["id"]
    pending_name = student.get("pending_parent_name")

    existing_parent, matched_by = await dedupe_workspace_parent(
        session,
        national_id=national_id,
        phone=phone,
        email=email,
        workspace_id=workspace_id,
    )

    if existing_parent:
        parent_id = existing_parent["id"]
        conservative = _conservative_fill(
            existing_parent,
            full_name=full_name,
            phone=phone,
            email=email,
            national_id=national_id,
        )
        if conservative:
            await gd_update_one(
                session, "parents", {"id": parent_id}, conservative,
            )
    else:
        parent_id = str(uuid.uuid4())
        now = _utcnow_iso()
        await gd_insert(session, "parents", {
            "id": parent_id,
            "full_name": full_name or pending_name or _DEFAULT_PARENT_NAME,
            "phone": phone,
            "email": email,
            "national_id": national_id,
            # First-creation only — never rewritten on cross-tenant link.
            "school_id": workspace_id,
            "is_active": True,
            "student_ids": [student_id],
            "created_at": now,
            "updated_at": now,
        })

    # guardian_links — tenant_id MUST be the workspace id (spec §8 inv. 8).
    # is_primary defaults true when no other primary link for this student
    # exists.
    existing_primary = await gd_count(
        session, "guardian_links",
        {
            "tenant_id": workspace_id,
            "student_id": student_id,
            "is_primary": True,
            "is_active": True,
        },
    )

    # On EVERY new-parent path, materialise a workspace-scoped `users` row
    # so the cohort resolver in `/notifications/bulk` can find the
    # recipient. Dedupe paths (existing parent reused) keep the legacy
    # parent_ref=parent_id behaviour.
    #
    # `users.email` is NOT NULL + globally UNIQUE. When the payload has no
    # email, OR a global users row already owns that email (cross-workspace
    # collision), synthesise a deterministic non-deliverable placeholder
    # keyed off the freshly minted parent_id. The `.invalid` TLD is
    # reserved (RFC 6761). The sentinel password_hash blocks any login.
    parent_user_id_for_ref = parent_id  # legacy fallback (dedupe paths)
    parent_user_materialised = False
    if not existing_parent:
        user_email_for_insert: Optional[str] = None
        if email:
            email_collision = await gd_find_one(
                session, "users", {"email": email},
            )
            if not email_collision:
                user_email_for_insert = email
        if user_email_for_insert is None:
            user_email_for_insert = f"invite+{parent_id}{_INVALID_EMAIL_DOMAIN}"

        parent_user_id_for_ref = str(uuid.uuid4())
        now_iso = _utcnow_iso()
        await gd_insert(session, "users", {
            "id": parent_user_id_for_ref,
            "role": "parent",
            "tenant_id": workspace_id,
            "email": user_email_for_insert,
            "phone": phone,
            "full_name": full_name or pending_name or _DEFAULT_PARENT_NAME,
            "password_hash": _USER_PASSWORD_SENTINEL,
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
    await gd_insert(session, "guardian_links", {
        "id": link_id,
        "tenant_id": workspace_id,
        "student_id": student_id,
        "student_name": student.get("full_name"),
        "parent_id": parent_id,
        "parent_ref": parent_user_id_for_ref,
        "parent_name": full_name or (existing_parent or {}).get("full_name"),
        "relationship": relationship or "guardian",
        "is_primary": existing_primary == 0,
        "is_active": True,
        "permissions": {
            "can_pickup": True,
            "can_view_grades": True,
            "can_view_attendance": True,
            "can_communicate": True,
        },
        "linked_by": actor["id"],
        "linked_at": now,
        "updated_at": now,
    })

    # Flip parent_id NULL → non-NULL. The
    # students_clear_pending_parent_on_link_trg trigger wipes
    # pending_parent_* atomically.
    updated = await gd_update_one(
        session, "students",
        {"id": student_id, "school_id": school_id},
        {"parent_id": parent_id, "updated_at": _utcnow_iso()},
    )
    if not updated:
        # The student vanished mid-transaction — bail out so the SAVEPOINT
        # rolls back the parent / link writes.
        raise HTTPException(status_code=404, detail=_MSG_STUDENT_NOT_FOUND)

    # Audit row — same transaction.
    await audit_engine.log(
        action=_AUDIT_ACTION,
        performed_by=actor["id"],
        tenant_id=workspace_id,
        entity_type="student",
        entity_id=student_id,
        details={
            "school_id": school_id,
            "tenant_id": workspace_id,
            "user_id": actor["id"],
            "student_id": student_id,
            "parent_id": parent_id,
            "matched_by": matched_by,
            "parent_user_materialised": parent_user_materialised,
            "parent_user_id": parent_user_id_for_ref,
        },
        actor_name=actor.get("full_name"),
        actor_role=actor.get("role"),
        actor_email=actor.get("email"),
    )

    parent_row = await gd_find_one(session, "parents", {"id": parent_id})
    link_row = await gd_find_one(session, "guardian_links", {"id": link_id})
    return {
        "parent": parent_row,
        "link": link_row,
        "matched_by": matched_by,
        "parent_id": parent_id,
        "parent_user_id": parent_user_id_for_ref,
        "parent_user_materialised": parent_user_materialised,
    }
