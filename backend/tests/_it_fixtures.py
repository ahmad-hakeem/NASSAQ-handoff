"""Shared Independent-Teacher test helpers.

Promoted from the duplicate inline copies in
`test_independent_teacher_phase1_exit.py`,
`test_independent_teacher_communication.py`,
`test_independent_teacher_invite_parent.py`,
`test_independent_teacher_phase1_smoke.py`,
and `test_it_mfa_stepup_backfill.py`.

These helpers exist so the §5.9 exit-criteria suite can drive real
backend routes without dragging the per-feature test files into a
monolithic file. They are intentionally minimal: token mint, MFA
factor seed, and a complete workspace bootstrap that returns every id
a downstream test needs to chain real API calls.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


STEP_UP_CODES = {
    "MFA_STEPUP_REQUIRED",
    "MFA_PASSKEY_REQUIRED",
    "MFA_RESTORE_REQUIRED",
}


def now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def headers(
    user_id: str,
    role: str,
    tenant_id=None,
    *,
    mfa_recent_at: int | None = None,
) -> dict:
    """Mint an Authorization header for a synthetic caller."""
    token = create_access_token(
        {"sub": user_id, "role": role, "tenant_id": tenant_id},
        mfa_recent_at=mfa_recent_at,
        mfa_kind="webauthn" if mfa_recent_at else None,
    )
    return {"Authorization": f"Bearer {token}"}


async def seed_active_passkey(user_id: str) -> None:
    """Tier-A users need at least one active webauthn factor for
    require_recent_mfa to clear the passkey gate."""
    await gd_insert(db.session, "mfa_factors", {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "kind": "webauthn",
        "is_active": True,
        "is_primary": True,
        "webauthn_credential_id": uuid.uuid4().bytes,
        "webauthn_public_key": b"\x00",
        "webauthn_sign_count": 0,
    })


async def mk_it_workspace(
    *,
    with_class: bool = True,
    with_student: bool = True,
    with_parent: bool = True,
    with_passkey: bool = True,
) -> dict:
    """Bootstrap a complete Independent-Teacher workspace.

    Returns a dict carrying every id a downstream test may reference
    (uid, wsid, teacher_id, class_id, student_id, student_user_id,
    parent_user_id, parent_id) plus the user dict itself.

    The bootstrap is direct-insert (NOT the public /independent-teacher/
    bootstrap endpoint) because the §5.9 #4 idempotency test owns that
    endpoint's contract, and overlapping coverage would couple the
    two suites unnecessarily.
    """
    uid = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "teacher_id": teacher_id,
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    user["tenant_id"] = wsid

    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher_workspace",
    })
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": wsid,
        "user_id": uid,
        "full_name": user["full_name"],
        "email": user["email"],
        "is_active": True,
    })

    class_id = None
    if with_class:
        class_id = str(uuid.uuid4())
        await gd_insert(db.session, "classes", {
            "id": class_id,
            "name": "فصل أ",
            "school_id": wsid,
            "tenant_id": wsid,
            "homeroom_teacher_id": teacher_id,
            "capacity": 10,
            "current_students": 1,
            "is_active": True,
        })

    student_id = None
    student_user_id = None
    if with_student:
        student_user_id = str(uuid.uuid4())
        student_email = f"stud-{student_user_id}@t.test"
        await gd_insert(db.session, "users", {
            "id": student_user_id,
            "role": UserRole.STUDENT.value,
            "tenant_id": wsid,
            "email": student_email,
            "full_name": "طالب التجربة",
            "is_active": True,
            "password_hash": "x",
        })
        student_id = str(uuid.uuid4())
        await gd_insert(db.session, "students", {
            "id": student_id,
            "school_id": wsid,
            "tenant_id": wsid,
            "class_id": class_id,
            "full_name": "طالب التجربة",
            "email": student_email,
            "is_active": True,
        })

    parent_user_id = None
    parent_id = None
    if with_parent and with_student:
        parent_user_id = str(uuid.uuid4())
        await gd_insert(db.session, "users", {
            "id": parent_user_id,
            "role": UserRole.PARENT.value,
            "tenant_id": wsid,
            "email": f"par-{parent_user_id}@t.test",
            "full_name": "ولي أمر التجربة",
            "is_active": True,
            "password_hash": "x",
        })
        parent_id = str(uuid.uuid4())
        await gd_insert(db.session, "parents", {
            "id": parent_id,
            "school_id": wsid,
            "full_name": "ولي أمر التجربة",
            "email": f"par-{parent_user_id}@t.test",
            "user_id": parent_user_id,
            "is_active": True,
        })
        await gd_insert(db.session, "guardian_links", {
            "id": str(uuid.uuid4()),
            "parent_ref": parent_user_id,
            "parent_id": parent_id,
            "student_id": student_id,
            "relationship": "guardian",
            "tenant_id": wsid,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    if with_passkey:
        await seed_active_passkey(uid)

    return {
        "user": user, "uid": uid, "wsid": wsid,
        "teacher_id": teacher_id,
        "class_id": class_id,
        "student_id": student_id, "student_user_id": student_user_id,
        "parent_user_id": parent_user_id, "parent_id": parent_id,
    }


def it_headers(ctx: dict, *, with_mfa: bool = False) -> dict:
    return headers(
        ctx["uid"], ctx["user"]["role"], ctx["wsid"],
        mfa_recent_at=now_ts() if with_mfa else None,
    )
