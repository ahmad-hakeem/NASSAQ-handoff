"""Regression coverage for the Task #794 teacher-record backfill data migration.

Root cause: a school teacher lives in BOTH ``users`` (login / role / tenant_id)
AND the authoritative ``teachers`` table (keyed by ``school_id``, which drives the
principal's teacher list). Historically a teacher could have ``users.tenant_id``
set to a school WITHOUT a matching active ``teachers`` row there — correct profile,
invisible in the principal list.

The migration ``c9d5e3f7a2b1`` reconciles those stale rows using the SAME product
rules as ``user_routes_mod._ensure_school_teacher_record``:
  * create-if-missing,
  * reactivate a deactivated same-school record,
  * BLOCK / skip a teacher with a live record in a DIFFERENT school.

These tests exercise the migration's ``upgrade()`` directly against the test DB,
inside the per-test (rolled-back) transaction, so they assert the real backfill
behavior — not a reimplementation.
"""
import importlib.util
import os
import uuid

import pytest

from alembic.migration import MigrationContext
from alembic.operations import Operations

from dependencies import db, UserRole
from engines.sql_utils import gd_insert, gd_find, gd_find_one, gd_count

pytestmark = pytest.mark.asyncio

_MIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "alembic", "versions",
    "c9d5e3f7a2b1_backfill_teacher_records_for_reassigned.py",
)
_spec = importlib.util.spec_from_file_location("mig_794_backfill", _MIG_PATH)
_MIG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_MIG)


def _run_upgrade(sync_conn):
    ctx = MigrationContext.configure(sync_conn)
    with Operations.context(ctx):
        _MIG.upgrade()


async def _apply_backfill():
    """Run the migration upgrade() on the test session's own connection so it
    sees the uncommitted seeded rows."""
    await db.session.flush()
    conn = await db.session.connection()
    await conn.run_sync(_run_upgrade)


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


async def _insert_teacher_record(school_id: str, user: dict, is_active: bool = True) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "teacher_id": tid,
        "user_id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "school_id": school_id,
        "is_active": is_active,
    })
    return tid


async def test_backfill_creates_record_for_mismatched_teacher(tenant_a):
    """A teacher with the school set on users.tenant_id but NO teachers row gets
    an active record provisioned in that school and linked back to the user."""
    teacher = await _mk_teacher_user(tenant_a)

    await _apply_backfill()

    rows = await gd_find(db.session, "teachers", {"school_id": tenant_a, "email": teacher["email"]})
    assert len(rows) == 1, "expected exactly one teachers row created in the user's school"
    created = rows[0]
    assert created["user_id"] == teacher["id"]
    assert created["is_active"] is True
    assert created["id"].startswith("TCH-")

    updated = await gd_find_one(db.session, "users", {"id": teacher["id"]})
    assert updated.get("teacher_id") == created["id"]


async def test_backfill_skips_teacher_with_record_in_other_school(tenant_a, tenant_b):
    """A teacher whose live academic record lives in a DIFFERENT school is left
    untouched — never silently migrated (cross-school block preserved)."""
    teacher = await _mk_teacher_user(tenant_a)
    await _insert_teacher_record(tenant_b, teacher)  # live record in another school

    await _apply_backfill()

    leaked = await gd_find(db.session, "teachers", {"school_id": tenant_a, "email": teacher["email"]})
    assert leaked == [], "no teachers row should be created in the target school"

    # user link not pointed at any new target-school record
    updated = await gd_find_one(db.session, "users", {"id": teacher["id"]})
    other = await gd_find_one(db.session, "teachers", {"school_id": tenant_b, "email": teacher["email"]})
    assert updated.get("teacher_id") in (None, other["id"])


async def test_backfill_is_idempotent(tenant_a):
    """Re-running the backfill does not create duplicate teachers rows."""
    teacher = await _mk_teacher_user(tenant_a)

    await _apply_backfill()
    await _apply_backfill()

    count = await gd_count(db.session, "teachers", {"school_id": tenant_a, "email": teacher["email"]})
    assert count == 1


async def test_backfill_reactivates_deactivated_same_school_record(tenant_a):
    """A deactivated (non-soft-deleted) record in the SAME school is reactivated
    instead of duplicated, so the teacher reappears."""
    teacher = await _mk_teacher_user(tenant_a)
    tid = await _insert_teacher_record(tenant_a, teacher, is_active=False)

    await _apply_backfill()

    count = await gd_count(db.session, "teachers", {"school_id": tenant_a, "email": teacher["email"]})
    assert count == 1, "should reactivate, not duplicate"
    reactivated = await gd_find_one(db.session, "teachers", {"id": tid})
    assert reactivated["is_active"] is True
