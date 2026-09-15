"""Shared real-school parent account provisioning + guardian linking.

Single canonical implementation of the manual student-creation wizard's
parent logic, extracted so BOTH the create flow
(``routes/student_creation_routes.py``) and the existing-student guardian
edit flow (``routes/academics_student_routes.py`` -> ``update_student``)
provision and link parent accounts identically. This is the real-school
counterpart to ``utils/it_parent_link.link_workspace_parent_to_student``
(which stays the SOLE writer for Independent-Teacher workspaces; do not
route IT callers through here).

Tenant rules (must hold on every path):
  * ``parents`` rows are ALWAYS scoped to the student's ``school_id``; a
    parents row owned by another tenant is never reused.
  * ``users`` rows are global (``users.email`` is unique). An existing
    parent user is reused by email; binding an email that belongs to a
    NON-parent account is refused with 409.
  * ``guardian_links`` is the canonical store for the guardian
    RELATIONSHIP and is tagged with ``tenant_id == school_id``. The
    ``students``/``parents`` tables have no relationship column, so the
    relationship lives here and nowhere else.

The CALLER owns the transaction. Wrap calls in a SAVEPOINT
(``async with session.begin_nested()``) so any inner failure rolls back
the ``parents`` / ``users`` / ``guardian_links`` / ``students`` writes as
one unit (the request-level middleware commits non-GET responses even on
4xx, so writes must be grouped under a savepoint that rolls back on raise).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException

from engines.sql_utils import (
    gd_find,
    gd_find_one,
    gd_insert,
    gd_update_one,
    _gd_addtoset,
)

_PARENT_ROLE = "parent"
_PLACEHOLDER_EMAIL_DOMAIN = "@nassaq.local"
_DEFAULT_RELATIONSHIP = "guardian"
_DEFAULT_PARENT_NAME = "ولي الأمر"

_MSG_EMAIL_TAKEN = "البريد الإلكتروني مستخدم مسبقاً لحساب آخر"
_MSG_EMAIL_CONFLICT = "رقم الهاتف والبريد الإلكتروني يخصان حسابين مختلفين"
_MSG_NAME_REQUIRED = "اسم ولي الأمر مطلوب لإنشاء حساب ولي الأمر"
_MSG_GUARDIAN_REQUIRED = "أدخل اسم ولي الأمر ورقم هاتفه"
_MSG_PARENT_UNAVAILABLE = "حساب ولي الأمر مغلق أو غير نشط ولا يمكن ربط طالب جديد به"
_BLOCKED_PARENT_STATUSES = frozenset({"closed", "inactive", "suspended"})


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return value


def _parent_record_is_unavailable(parent: Optional[dict]) -> bool:
    """Return whether an existing parent must not be reused.

    ``parents`` has no persisted lifecycle ``status`` column.  Its
    ``is_active`` flag is the supported account-state signal, and this check is
    deliberately read-only: linking a student must never silently reopen an
    inactive account.
    """
    if not parent:
        return False
    return parent.get("is_active") is False


def _assert_parent_record_available(parent: Optional[dict]) -> None:
    if _parent_record_is_unavailable(parent):
        raise HTTPException(status_code=409, detail=_MSG_PARENT_UNAVAILABLE)


def _assert_parent_user_available(user: Optional[dict]) -> None:
    """Reject a closed/inactive login account instead of reusing it."""
    if not user:
        return
    status = _clean(user.get("status"))
    if (
        (status and str(status).lower() in _BLOCKED_PARENT_STATUSES)
        or user.get("is_active") is False
    ):
        raise HTTPException(status_code=409, detail=_MSG_PARENT_UNAVAILABLE)


async def find_or_create_parent(
    session,
    parent_data: dict,
    school_id: str,
    created_by: Optional[str],
    *,
    hash_password: Callable[[str], str],
    generate_secure_password: Callable[[], str],
    parent_role_value: str = _PARENT_ROLE,
) -> Dict[str, Any]:
    """Find an existing per-school parent or create a new parent + user.

    Dedupe order (per-school, first match wins): ``national_id`` ->
    ``phone`` -> ``email``. All lookups are scoped to ``school_id`` so a
    shared identifier in another tenant never causes a cross-tenant merge.
    An existing parent row is returned untouched (the caller decides
    whether to conservatively fill missing columns). When no parents row
    exists, a global parent ``users`` row is reused by email (409 if that
    email belongs to a non-parent), otherwise a fresh parent account +
    per-school ``parents`` row is minted.

    Returns ``{"parent", "is_new", "is_new_user", "linked_students",
    "temp_password"}``. ``is_new`` describes the per-school parent row;
    ``is_new_user`` is independently true only when this call minted the
    global users row. A per-school parent may legitimately reuse a global
    parent account.
    """
    existing_parent = None

    if parent_data.get("national_id"):
        existing_parent = await gd_find_one(session, "parents", {
            "national_id": parent_data["national_id"],
            "school_id": school_id,
        })
    if not existing_parent and parent_data.get("phone"):
        existing_parent = await gd_find_one(session, "parents", {
            "phone": parent_data["phone"],
            "school_id": school_id,
        })
    if not existing_parent and parent_data.get("email"):
        existing_parent = await gd_find_one(session, "parents", {
            "email": parent_data["email"],
            "school_id": school_id,
        })

    if existing_parent:
        _assert_parent_record_available(existing_parent)

        # Re-derive the parent's user id by email when the parents row does
        # not carry one (parents has no user_id column; it is in-memory only).
        matched_user_id = existing_parent.get("user_id")
        if not matched_user_id and existing_parent.get("email"):
            linked_user = await gd_find_one(session, "users", {
                "email": existing_parent["email"],
                "role": parent_role_value,
            })
            if linked_user:
                _assert_parent_user_available(linked_user)
                matched_user_id = linked_user.get("id")
                existing_parent["user_id"] = matched_user_id
        elif matched_user_id:
            linked_user = await gd_find_one(
                session, "users", {"id": matched_user_id, "role": parent_role_value}
            )
            _assert_parent_user_available(linked_user)

        # Email-consistency guard: the parent was matched by national_id or
        # phone. If the caller ALSO supplied an email that belongs to a
        # DIFFERENT account (another parent, or any non-parent), refuse with
        # 409 rather than mis-binding two identities. Without this, the
        # downstream conservative-fill + user-resolution could attach this
        # student's guardian_link to a foreign parent user while parent_id
        # points at the phone-matched row — a broken-access-control leak.
        submitted_email = parent_data.get("email")
        if submitted_email and submitted_email != existing_parent.get("email"):
            other_user = await gd_find_one(session, "users", {"email": submitted_email})
            if other_user and other_user.get("id") != matched_user_id:
                raise HTTPException(status_code=409, detail=_MSG_EMAIL_CONFLICT)

        linked_students = []
        student_ids = existing_parent.get("student_ids") or []
        if student_ids:
            linked_students = await gd_find(
                session, "students",
                {"id": {"$in": student_ids}, "school_id": school_id},
                limit=20,
            )
        return {
            "parent": existing_parent,
            "is_new": False,
            "is_new_user": False,
            "linked_students": linked_students,
            "temp_password": None,
        }

    # No per-school parents row — reuse a global parent users row by email
    # when present, else mint a new account.
    existing_user = None
    if parent_data.get("email"):
        existing_user = await gd_find_one(session, "users", {"email": parent_data["email"]})
        if existing_user and existing_user.get("role") != parent_role_value:
            raise HTTPException(status_code=409, detail=_MSG_EMAIL_TAKEN)
        _assert_parent_user_available(existing_user)

    full_name = parent_data.get("full_name") or (
        existing_user.get("full_name") if existing_user else None
    )
    if not full_name:
        # parents.full_name is NOT NULL — refuse to mint an anonymous row.
        raise HTTPException(status_code=422, detail=_MSG_NAME_REQUIRED)

    parent_id = str(uuid.uuid4())
    now = _utcnow_iso()
    temp_password: Optional[str] = None

    if existing_user:
        user_id = existing_user.get("id")
        parent_email = existing_user.get("email")
    else:
        temp_password = generate_secure_password()
        user_id = str(uuid.uuid4())
        parent_email = parent_data.get("email") or f"parent_{parent_id[:8]}{_PLACEHOLDER_EMAIL_DOMAIN}"
        await gd_insert(session, "users", {
            "id": user_id,
            "email": parent_email,
            "password_hash": hash_password(temp_password),
            "full_name": full_name,
            "role": parent_role_value,
            "phone": parent_data.get("phone"),
            "is_active": True,
            "must_change_password": True,
            "tenant_id": school_id,
            "created_at": now,
            "created_by": created_by,
        })

    parent_doc = {
        "id": parent_id,
        "user_id": user_id,
        "full_name": full_name,
        "national_id": parent_data.get("national_id"),
        "phone": parent_data.get("phone"),
        "email": parent_email,
        "relationship": parent_data.get("relationship", _DEFAULT_RELATIONSHIP),
        "address": parent_data.get("address"),
        "student_ids": [],
        "school_id": school_id,
        "is_active": True,
        "created_at": now,
        "created_by": created_by,
    }
    await gd_insert(session, "parents", parent_doc)
    return {
        "parent": parent_doc,
        "is_new": True,
        "is_new_user": existing_user is None,
        "linked_students": [],
        "temp_password": temp_password,
    }


async def ensure_parent_user_account(
    session,
    parent: dict,
    school_id: str,
    created_by: Optional[str],
    *,
    hash_password: Callable[[str], str],
    generate_secure_password: Callable[[], str],
    parent_role_value: str = _PARENT_ROLE,
) -> str:
    """Return a parent ``users.id`` for ``parent``, minting it if absent.

    Used when an existing per-school ``parents`` row has no linked parent
    user yet, so ``guardian_links`` can carry a ``parent_ref``. Mirrors the
    user-mint logic of :func:`find_or_create_parent`. Refuses to bind an
    email owned by a non-parent account (409).
    """
    _assert_parent_record_available(parent)

    if parent.get("user_id"):
        linked_user = await gd_find_one(session, "users", {"id": parent["user_id"]})
        _assert_parent_user_available(linked_user)
        return parent["user_id"]

    email = parent.get("email")
    if email:
        existing_user = await gd_find_one(session, "users", {"email": email})
        if existing_user:
            if existing_user.get("role") != parent_role_value:
                raise HTTPException(status_code=409, detail=_MSG_EMAIL_TAKEN)
            _assert_parent_user_available(existing_user)
            return existing_user.get("id")

    user_id = str(uuid.uuid4())
    parent_email = email or f"parent_{str(parent.get('id') or uuid.uuid4().hex)[:8]}{_PLACEHOLDER_EMAIL_DOMAIN}"
    await gd_insert(session, "users", {
        "id": user_id,
        "email": parent_email,
        "password_hash": hash_password(generate_secure_password()),
        "full_name": parent.get("full_name") or _DEFAULT_PARENT_NAME,
        "role": parent_role_value,
        "phone": parent.get("phone"),
        "is_active": True,
        "must_change_password": True,
        "tenant_id": school_id,
        "created_at": _utcnow_iso(),
        "created_by": created_by,
    })
    return user_id


async def link_or_update_real_school_guardian(
    session,
    student: dict,
    school_id: str,
    created_by: Optional[str],
    *,
    parent_name: Optional[str] = None,
    parent_phone: Optional[str] = None,
    parent_email: Optional[str] = None,
    parent_relationship: Optional[str] = None,
    hash_password: Callable[[str], str],
    generate_secure_password: Callable[[], str],
    parent_role_value: str = _PARENT_ROLE,
) -> Dict[str, Any]:
    """Provision/link a real-school parent account for an EXISTING student
    and persist the guardian relationship canonically.

    Merges the supplied guardian fields over whatever the student row
    already carries (so dedupe can match on an existing phone/email even
    when the principal edits only one field), runs the shared dedupe,
    conservatively fills NULL parent columns on an existing match, ensures
    a parent ``users`` account exists, links the student into the parent's
    ``student_ids``, and upserts the canonical ``guardian_links`` row
    (creating it or refreshing its ``relationship``).

    Returns the denormalised ``students`` mirror fields the caller should
    merge into its own students-row update so that write stays atomic::

        {"parent_id", "parent_name", "parent_phone", "parent_email",
         "parent_relationship", "is_new", "is_new_user", "parent_user_id"}

    The CALLER owns the transaction; wrap in ``begin_nested()``.
    """
    student_id = student.get("id")

    merged_name = _clean(parent_name) if parent_name is not None else _clean(student.get("parent_name"))
    merged_phone = _clean(parent_phone) if parent_phone is not None else _clean(student.get("parent_phone"))
    merged_email = parent_email if parent_email is not None else student.get("parent_email")
    merged_email = _clean(merged_email)
    relationship = _clean(parent_relationship) or _DEFAULT_RELATIONSHIP

    parent_data = {
        "full_name": merged_name,
        "phone": merged_phone,
        "email": merged_email,
        "national_id": None,
        "relationship": relationship,
    }

    has_identity = bool(merged_name or merged_phone or merged_email)
    already_linked = bool(student.get("parent_id"))
    if not has_identity and not already_linked:
        # A relationship with no identity and no existing parent has nowhere
        # canonical to live — refuse rather than silently drop it.
        raise HTTPException(status_code=422, detail=_MSG_GUARDIAN_REQUIRED)

    # 1. Check if the student already has a linked parent in this school.
    existing_parent_id = student.get("parent_id")
    if not existing_parent_id and student_id:
        existing_link = await gd_find_one(session, "guardian_links", {
            "student_id": student_id,
            "tenant_id": school_id,
            "is_active": True,
        })
        if existing_link and existing_link.get("parent_id"):
            existing_parent_id = existing_link["parent_id"]

    current_parent = None
    if existing_parent_id:
        current_parent = await gd_find_one(session, "parents", {
            "id": existing_parent_id,
            "school_id": school_id,
        })

    # 2. If the student ALREADY has a parent record in this school, update in-place
    #    unless the phone/email explicitly matches a DIFFERENT existing parent in the school.
    if current_parent:
        _assert_parent_record_available(current_parent)
        target_parent = current_parent

        # Check if the updated phone belongs to another existing parent in this school (sibling merge)
        if merged_phone and merged_phone != current_parent.get("phone"):
            other_parent = await gd_find_one(session, "parents", {
                "phone": merged_phone,
                "school_id": school_id,
            })
            if other_parent and other_parent.get("id") != current_parent["id"]:
                _assert_parent_record_available(other_parent)
                target_parent = other_parent
                # Remove student from old parent student_ids
                old_sids = [sid for sid in (current_parent.get("student_ids") or []) if sid != student_id]
                await gd_update_one(
                    session, "parents",
                    {"id": current_parent["id"], "school_id": school_id},
                    {"student_ids": old_sids, "updated_at": _utcnow_iso()},
                )

        # Update target parent record in `parents` table
        p_update: Dict[str, Any] = {}
        if merged_name and merged_name != target_parent.get("full_name"):
            p_update["full_name"] = merged_name
        if merged_phone is not None and merged_phone != target_parent.get("phone"):
            p_update["phone"] = merged_phone
        if merged_email is not None and merged_email != target_parent.get("email"):
            p_update["email"] = merged_email
        if relationship and relationship != target_parent.get("relationship"):
            p_update["relationship"] = relationship
        if p_update:
            p_update["updated_at"] = _utcnow_iso()
            await gd_update_one(
                session, "parents",
                {"id": target_parent["id"], "school_id": school_id},
                p_update,
            )
            target_parent.update(p_update)

        # Ensure parent user account exists and update it. Track ownership
        # separately from the parent-row identity: an existing per-school
        # parent may need a user lookup but must never make that user appear
        # newly created to a rollback manifest.
        user_already_exists = bool(target_parent.get("user_id"))
        if not user_already_exists and target_parent.get("email"):
            user_already_exists = bool(await gd_find_one(
                session,
                "users",
                {"email": target_parent["email"], "role": parent_role_value},
            ))
        parent_user_id = await ensure_parent_user_account(
            session, target_parent, school_id, created_by,
            hash_password=hash_password,
            generate_secure_password=generate_secure_password,
            parent_role_value=parent_role_value,
        )
        u_update: Dict[str, Any] = {}
        if merged_name:
            u_update["full_name"] = merged_name
        if merged_phone is not None:
            u_update["phone"] = merged_phone
        if merged_email is not None and not str(merged_email).endswith(_PLACEHOLDER_EMAIL_DOMAIN):
            existing_email_user = await gd_find_one(session, "users", {"email": merged_email})
            if existing_email_user and existing_email_user.get("id") != parent_user_id:
                raise HTTPException(status_code=409, detail=_MSG_EMAIL_CONFLICT)
            u_update["email"] = merged_email
        if u_update:
            u_update["updated_at"] = _utcnow_iso()
            await gd_update_one(session, "users", {"id": parent_user_id}, u_update)

        # Link student into target parent's student_ids
        await _gd_addtoset(
            session, "parents",
            {"id": target_parent["id"], "school_id": school_id},
            {"student_ids": student_id},
        )

        # Canonical guardian_links row — upsert
        existing_link = await gd_find_one(session, "guardian_links", {
            "parent_ref": parent_user_id,
            "student_id": student_id,
        })
        if existing_link:
            await gd_update_one(
                session, "guardian_links",
                {"id": existing_link["id"]},
                {
                    "relationship": relationship,
                    "is_active": True,
                    "tenant_id": school_id,
                    "parent_id": target_parent["id"],
                    "updated_at": _utcnow_iso(),
                },
            )
        else:
            await gd_insert(session, "guardian_links", {
                "id": str(uuid.uuid4()),
                "parent_ref": parent_user_id,
                "parent_id": target_parent["id"],
                "student_id": student_id,
                "relationship": relationship,
                "tenant_id": school_id,
                "is_active": True,
                "created_at": _utcnow_iso(),
                "created_by": created_by,
            })

        mirror_email = merged_email if (merged_email and not str(merged_email).endswith(_PLACEHOLDER_EMAIL_DOMAIN)) else None
        return {
            "parent_id": target_parent.get("id"),
            "parent_name": target_parent.get("full_name") or merged_name,
            "parent_phone": target_parent.get("phone") or merged_phone,
            "parent_email": mirror_email,
            "parent_relationship": relationship,
            "is_new": False,
            "is_new_user": not user_already_exists,
            "parent_user_id": parent_user_id,
        }

    # 3. Student did NOT have a linked parent: find or create
    result = await find_or_create_parent(
        session, parent_data, school_id, created_by,
        hash_password=hash_password,
        generate_secure_password=generate_secure_password,
        parent_role_value=parent_role_value,
    )
    parent = result["parent"]
    is_new = result["is_new"]
    is_new_user = bool(result.get("is_new_user"))
    if not is_new:
        user_already_exists = bool(parent.get("user_id"))
        if not user_already_exists and parent.get("email"):
            user_already_exists = bool(await gd_find_one(
                session,
                "users",
                {"email": parent["email"], "role": parent_role_value},
            ))
        is_new_user = not user_already_exists

    # Fill / update parent record on an existing match
    if not is_new:
        fill: Dict[str, Any] = {}
        for col, val in (
            ("full_name", merged_name),
            ("phone", merged_phone),
            ("email", merged_email),
        ):
            if val and not parent.get(col):
                fill[col] = val
        if fill:
            await gd_update_one(
                session, "parents",
                {"id": parent["id"], "school_id": school_id},
                fill,
            )
            parent.update(fill)

    # Ensure a parent user account exists so guardian_links carries a ref.
    parent_user_id = await ensure_parent_user_account(
        session, parent, school_id, created_by,
        hash_password=hash_password,
        generate_secure_password=generate_secure_password,
        parent_role_value=parent_role_value,
    )

    # Link the student into the parent's roster (scoped to tenant).
    await _gd_addtoset(
        session, "parents",
        {"id": parent["id"], "school_id": school_id},
        {"student_ids": student_id},
    )

    # Canonical guardian_links row — insert or refresh the relationship.
    existing_link = await gd_find_one(session, "guardian_links", {
        "parent_ref": parent_user_id,
        "student_id": student_id,
    })
    if existing_link:
        await gd_update_one(
            session, "guardian_links",
            {"id": existing_link["id"]},
            {
                "relationship": relationship,
                "is_active": True,
                "tenant_id": school_id,
                "parent_id": parent["id"],
                "updated_at": _utcnow_iso(),
            },
        )
    else:
        await gd_insert(session, "guardian_links", {
            "id": str(uuid.uuid4()),
            "parent_ref": parent_user_id,
            "parent_id": parent["id"],
            "student_id": student_id,
            "relationship": relationship,
            "tenant_id": school_id,
            "is_active": True,
            "created_at": _utcnow_iso(),
            "created_by": created_by,
        })

    # Mirror only the REAL (non-placeholder) contact values onto the
    # students row. Never mirror a synthetic parent_*@nassaq.local email.
    mirror_email = merged_email if (merged_email and not str(merged_email).endswith(_PLACEHOLDER_EMAIL_DOMAIN)) else None
    return {
        "parent_id": parent.get("id"),
        "parent_name": parent.get("full_name") or merged_name,
        "parent_phone": parent.get("phone") or merged_phone,
        "parent_email": mirror_email,
        "parent_relationship": relationship,
        "is_new": is_new,
        "is_new_user": is_new_user,
        "parent_user_id": parent_user_id,
    }


async def enrich_student_guardian_fields(session, student: dict) -> dict:
    """Backfill ``parent_relationship`` (and missing contact mirror) on a
    single student dict from the canonical ``guardian_links`` / ``parents``.

    The ``students`` table has no ``parent_relationship`` column, so a raw
    read always shows a blank relationship. This fills it (and any missing
    parent_id/name/phone/email) from the canonical store, scoped to the
    student's own ``school_id`` so a foreign-tenant link is never read.
    Mutates and returns ``student``. Intended for the single-student GET
    only — the class roster stays unenriched to avoid N+1 lookups.
    """
    student_id = student.get("id")
    school_id = student.get("school_id")
    if not student_id:
        return student

    link_filter = {"student_id": student_id, "is_active": True}
    if school_id:
        link_filter["tenant_id"] = school_id
    link = await gd_find_one(session, "guardian_links", link_filter)
    if not link and not student.get("parent_id"):
        return student

    if link:
        if link.get("relationship"):
            student["parent_relationship"] = link.get("relationship")
        if not student.get("parent_id") and link.get("parent_id"):
            student["parent_id"] = link.get("parent_id")

    pid = student.get("parent_id") or (link.get("parent_id") if link else None)
    parent_obj = None
    if pid:
        parent_filter = {"id": pid}
        if school_id:
            parent_filter["school_id"] = school_id
        prow = await gd_find_one(session, "parents", parent_filter)
        if prow:
            relationship = (link.get("relationship") if link else None) or prow.get("relationship") or student.get("parent_relationship") or "guardian"
            email = prow.get("email")
            if not email or str(email).endswith(_PLACEHOLDER_EMAIL_DOMAIN):
                if prow.get("user_id"):
                    u = await gd_find_one(session, "users", {"id": prow["user_id"]})
                    if u and u.get("email") and not str(u.get("email")).endswith(_PLACEHOLDER_EMAIL_DOMAIN):
                        email = u.get("email")
                    else:
                        email = None
            else:
                email = str(email)

            parent_name = prow.get("full_name") or student.get("parent_name")
            parent_phone = prow.get("phone") or student.get("parent_phone")
            parent_id_val = prow.get("id") or pid

            student["parent_id"] = parent_id_val
            student["parent_name"] = parent_name
            student["parent_phone"] = parent_phone
            student["parent_email"] = email
            student["parent_relationship"] = relationship

            parent_obj = {
                "id": parent_id_val,
                "user_id": prow.get("user_id"),
                "full_name": parent_name,
                "full_name_en": prow.get("full_name_en"),
                "phone": parent_phone,
                "email": email,
                "national_id": prow.get("national_id"),
                "relationship": relationship,
                "address": prow.get("address"),
                "job_title": prow.get("job_title"),
                "is_active": prow.get("is_active", True),
            }

    student["parent"] = parent_obj
    return student
