"""Regression coverage for Platform Admin > User Management teacher-school linking.

Root cause being guarded: a school teacher lives in BOTH the `users` table
(login/role/tenant_id) AND the authoritative `teachers` table (keyed by
`school_id`, which drives the Teachers page and every academic flow). Editing
only `users.tenant_id` made the change "succeed" without the teacher ever
appearing under the new school.

Chosen resolution: create-if-missing — when linking a teacher to a school where
they have NO `teachers` record, auto-create one so they appear; BLOCK moving a
teacher who already has an academic record (a `teachers` row) in another school.
"""

import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one, gd_find, gd_count, gd_update_one

pytestmark = pytest.mark.asyncio


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def _platform_admin_headers(tenant_id: str) -> dict:
    """Platform admin is Tier A: needs a fresh mfa claim AND an active
    webauthn factor for require_recent_mfa() to clear the step-up gate."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": "PA",
        "is_active": True,
        "password_hash": "x",
    })
    await gd_insert(db.session, "mfa_factors", {
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "kind": "webauthn",
        "is_active": True,
        "is_primary": True,
        "webauthn_credential_id": uuid.uuid4().bytes,
        "webauthn_public_key": b"\x00",
        "webauthn_sign_count": 0,
    })
    token = create_access_token(
        {"sub": uid, "role": UserRole.PLATFORM_ADMIN.value, "tenant_id": tenant_id},
        mfa_recent_at=_now_ts(),
        mfa_kind="webauthn",
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_teacher_user(tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.TEACHER.value,
        "tenant_id": tenant_id,
        "email": f"teacher-{uid}@t.test",
        "full_name": "معلم تجريبي",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _insert_teacher_record(school_id: str, user: dict) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "teacher_id": tid,
        "user_id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "school_id": school_id,
        "is_active": True,
    })
    return tid


async def test_link_teacher_without_record_creates_one(client, tenant_a, tenant_b):
    """Editing a teacher's school when they have NO teachers row auto-creates
    one in the target school so they actually appear there."""
    headers = await _platform_admin_headers(tenant_a)
    teacher = await _mk_teacher_user(tenant_a)

    resp = await client.patch(
        f"/users/{teacher['id']}", json={"tenant_id": tenant_b}, headers=headers
    )
    assert resp.status_code == 200, resp.text

    # users row moved
    updated = await gd_find_one(db.session, "users", {"id": teacher["id"]})
    assert updated["tenant_id"] == tenant_b

    # teachers row now exists in the target school, linked to the user
    rows = await gd_find(db.session, "teachers", {"school_id": tenant_b, "email": teacher["email"]})
    assert len(rows) == 1, "expected exactly one teachers row created in target school"
    created = rows[0]
    assert created["user_id"] == teacher["id"]
    assert created["is_active"] is True
    # explicit linkage written back to the user
    assert updated.get("teacher_id") == created["id"]


async def test_move_teacher_with_existing_record_is_blocked(client, tenant_a, tenant_b):
    """A teacher who already has an academic record (teachers row) in another
    school cannot be moved — the change is blocked, not silently faked."""
    headers = await _platform_admin_headers(tenant_a)
    teacher = await _mk_teacher_user(tenant_a)
    await _insert_teacher_record(tenant_a, teacher)

    resp = await client.patch(
        f"/users/{teacher['id']}", json={"tenant_id": tenant_b}, headers=headers
    )
    assert resp.status_code == 400, resp.text

    # No teachers row leaked into the target school
    leaked = await gd_find(db.session, "teachers", {"school_id": tenant_b, "email": teacher["email"]})
    assert leaked == []

    # users row NOT moved (fail closed — no false success)
    unchanged = await gd_find_one(db.session, "users", {"id": teacher["id"]})
    assert unchanged["tenant_id"] == tenant_a


async def test_relink_same_school_is_idempotent(client, tenant_a):
    """Re-linking a teacher to the school where their record already lives does
    not create a duplicate teachers row."""
    headers = await _platform_admin_headers(tenant_a)
    teacher = await _mk_teacher_user(tenant_a)
    existing_id = await _insert_teacher_record(tenant_a, teacher)

    resp = await client.patch(
        f"/users/{teacher['id']}", json={"tenant_id": tenant_a}, headers=headers
    )
    assert resp.status_code == 200, resp.text

    count = await gd_count(db.session, "teachers", {"school_id": tenant_a, "email": teacher["email"]})
    assert count == 1
    updated = await gd_find_one(db.session, "users", {"id": teacher["id"]})
    assert updated.get("teacher_id") == existing_id


async def test_move_blocked_even_when_other_record_is_inactive(client, tenant_a, tenant_b):
    """A non-deleted but deactivated academic record in another school still
    blocks the move — academic history must not be silently forked."""
    headers = await _platform_admin_headers(tenant_a)
    teacher = await _mk_teacher_user(tenant_a)
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "teacher_id": tid,
        "user_id": teacher["id"],
        "full_name": teacher["full_name"],
        "email": teacher["email"],
        "school_id": tenant_a,
        "is_active": False,
    })

    resp = await client.patch(
        f"/users/{teacher['id']}", json={"tenant_id": tenant_b}, headers=headers
    )
    assert resp.status_code == 400, resp.text

    leaked = await gd_find(db.session, "teachers", {"school_id": tenant_b, "email": teacher["email"]})
    assert leaked == []
    unchanged = await gd_find_one(db.session, "users", {"id": teacher["id"]})
    assert unchanged["tenant_id"] == tenant_a


async def test_relink_reactivates_deactivated_same_school_record(client, tenant_a):
    """Re-linking to the school where a DEACTIVATED record lives reactivates it
    (so the teacher reappears) instead of creating a duplicate."""
    headers = await _platform_admin_headers(tenant_a)
    teacher = await _mk_teacher_user(tenant_a)
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "teacher_id": tid,
        "user_id": teacher["id"],
        "full_name": teacher["full_name"],
        "email": teacher["email"],
        "school_id": tenant_a,
        "is_active": False,
    })

    resp = await client.patch(
        f"/users/{teacher['id']}", json={"tenant_id": tenant_a}, headers=headers
    )
    assert resp.status_code == 200, resp.text

    count = await gd_count(db.session, "teachers", {"school_id": tenant_a, "email": teacher["email"]})
    assert count == 1
    reactivated = await gd_find_one(db.session, "teachers", {"id": tid})
    assert reactivated["is_active"] is True


async def test_link_teacher_adopts_existing_national_id_record(client, tenant_a, tenant_b):
    """Linking a teacher to a school that already holds a row for their
    national_id (under a different email/user_id) ADOPTS that row instead of
    crashing on uq_teachers_national_id_school. Mirrors the Task #794 backfill."""
    headers = await _platform_admin_headers(tenant_a)
    nid = uuid.uuid4().hex[:10]
    teacher = await _mk_teacher_user(tenant_a)
    await gd_update_one(db.session, "users", {"id": teacher["id"]}, {"national_id": nid})

    existing_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": existing_id,
        "teacher_id": existing_id,
        "full_name": "سجل قائم",
        "email": f"other-{uuid.uuid4().hex}@t.test",
        "national_id": nid,
        "school_id": tenant_b,
        "is_active": True,
    })

    resp = await client.patch(
        f"/users/{teacher['id']}", json={"tenant_id": tenant_b}, headers=headers
    )
    assert resp.status_code == 200, resp.text

    rows = await gd_find(db.session, "teachers", {"school_id": tenant_b, "national_id": nid})
    assert len(rows) == 1, "must adopt the existing national_id row, not duplicate"
    assert rows[0]["id"] == existing_id
    assert rows[0]["user_id"] == teacher["id"]

    updated = await gd_find_one(db.session, "users", {"id": teacher["id"]})
    assert updated["tenant_id"] == tenant_b
    assert updated.get("teacher_id") == existing_id


async def test_link_teacher_blocked_on_soft_deleted_national_id_record(client, tenant_a, tenant_b):
    """Linking to a school whose (national_id, school_id) slot is held by a
    SOFT-DELETED row must be blocked (not silently un-deleted, not crash on the
    full unique constraint) and surfaced for manual review."""
    headers = await _platform_admin_headers(tenant_a)
    nid = uuid.uuid4().hex[:10]
    teacher = await _mk_teacher_user(tenant_a)
    await gd_update_one(db.session, "users", {"id": teacher["id"]}, {"national_id": nid})

    existing_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": existing_id,
        "teacher_id": existing_id,
        "full_name": "سجل محذوف",
        "email": f"other-{uuid.uuid4().hex}@t.test",
        "national_id": nid,
        "school_id": tenant_b,
        "is_active": False,
        "deleted_at": datetime.now(timezone.utc),
    })

    resp = await client.patch(
        f"/users/{teacher['id']}", json={"tenant_id": tenant_b}, headers=headers
    )
    assert resp.status_code == 400, resp.text

    # user NOT moved (fail closed), soft-deleted row untouched, no duplicate
    unchanged = await gd_find_one(db.session, "users", {"id": teacher["id"]})
    assert unchanged["tenant_id"] == tenant_a
    rows = await gd_find(db.session, "teachers", {"school_id": tenant_b, "national_id": nid})
    assert len(rows) == 1
    assert rows[0]["deleted_at"] is not None


async def test_create_teacher_in_school_provisions_record(client, tenant_b):
    """Creating a teacher user under a school also provisions the authoritative
    teachers row so they appear immediately."""
    headers = await _platform_admin_headers(tenant_b)
    email = f"new-teacher-{uuid.uuid4().hex}@example.com"

    resp = await client.post(
        "/users/create",
        json={
            "email": email,
            "password": "Str0ng!Passw0rd",
            "full_name": "معلم جديد",
            "role": UserRole.TEACHER.value,
            "tenant_id": tenant_b,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    rows = await gd_find(db.session, "teachers", {"school_id": tenant_b, "email": email})
    assert len(rows) == 1
    assert rows[0]["is_active"] is True
