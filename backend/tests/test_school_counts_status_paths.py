"""Task #826 — stored school counts stay accurate on status / cross-school
mutation paths.

* Suspending a STUDENT flips ``is_active`` -> False, which the canonical
  student predicate (``is_active != False``) excludes, so the live count drops
  and the stored ``schools.current_students`` must be reconciled down.
* The teacher predicate only excludes *soft-deleted* rows
  (``is_active = False AND deleted_at IS NOT NULL``), so a plain suspend does
  NOT change the teacher count. The path that DOES change teacher counts is the
  cross-school mismatch resolver, which soft-deletes the foreign record and
  provisions one in the intended school; both schools' stored counts must be
  reconciled.

These tests drive the real handlers and assert the stored columns end up equal
to ``_live_entity_counts_by_tenant`` (the live truth).
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_insert, gd_find_one
from src.modules.schools.controllers.school_routes_mod import _live_entity_counts_by_tenant
from src.modules.teacher_management.controllers.principal_management_routes import (
    UpdateAccountStatusRequest,
    update_student_account_status,
)
from src.modules.users.controllers.user_routes_mod import _do_resolve_teacher_mismatch


async def _mk_actor(school_id: str) -> dict:
    """audit_logs.performed_by / teachers.deleted_by need a real users row."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "email": f"actor-{uid[:8]}@ex.com",
        "full_name": "Actor",
        "role": "platform_admin",
        "tenant_id": school_id,
        "password_hash": "x",
        "is_active": True,
    })
    return {"id": uid, "role": "platform_admin", "tenant_id": school_id,
            "email": f"actor-{uid[:8]}@ex.com", "full_name": "Actor"}


async def _mk_school(school_id: str, current_students=0, current_teachers=0) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "current_students": current_students,
        "current_teachers": current_teachers,
    })


async def _mk_student(school_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "tenant_id": school_id,
        "full_name": "ST",
        "is_active": True,
        "status": "active",
    })
    return sid


@pytest.mark.asyncio
async def test_student_status_change_reconciles_stored_count(client):
    """Suspending a student (is_active -> False) heals the stored column."""
    school = str(uuid.uuid4())
    await _mk_school(school, current_students=99, current_teachers=0)
    keep = await _mk_student(school)  # noqa: F841 - stays active
    drop = await _mk_student(school)
    actor = await _mk_actor(school)
    await db.session.flush()

    await update_student_account_status(
        drop, UpdateAccountStatusRequest(status="suspended", reason="t"), actor
    )
    await db.session.flush()

    student_counts, _ = await _live_entity_counts_by_tenant()
    row = await gd_find_one(db.session, "schools", {"id": school})
    assert student_counts.get(school) == 1
    assert row["current_students"] == 1


@pytest.mark.asyncio
async def test_teacher_mismatch_resolution_reconciles_both_schools(client):
    """Resolving a cross-school mismatch soft-deletes the foreign teacher record
    and provisions one in the intended school; both stored counts heal."""
    school_a = str(uuid.uuid4())  # stuck/foreign school
    school_b = str(uuid.uuid4())  # intended school
    await _mk_school(school_a, current_teachers=50)
    await _mk_school(school_b, current_teachers=30)
    actor = await _mk_actor(school_b)

    # Teacher user whose intended tenant is school_b ...
    teacher_uid = str(uuid.uuid4())
    teacher_email = f"t-{teacher_uid[:8]}@ex.com"
    await gd_insert(db.session, "users", {
        "id": teacher_uid,
        "email": teacher_email,
        "full_name": "Teacher One",
        "role": "teacher",
        "tenant_id": school_b,
        "password_hash": "x",
        "is_active": True,
    })
    # ... but the live academic record is stuck in school_a.
    await gd_insert(db.session, "teachers", {
        "id": str(uuid.uuid4()),
        "user_id": teacher_uid,
        "school_id": school_a,
        "tenant_id": school_a,
        "email": teacher_email,
        "full_name": "Teacher One",
        "is_active": True,
    })
    await db.session.flush()

    await _do_resolve_teacher_mismatch(teacher_uid, actor)
    await db.session.flush()

    _, teacher_counts = await _live_entity_counts_by_tenant()
    row_a = await gd_find_one(db.session, "schools", {"id": school_a})
    row_b = await gd_find_one(db.session, "schools", {"id": school_b})

    # Foreign record retired -> 0 live in A; new record provisioned -> 1 in B.
    assert teacher_counts.get(school_a, 0) == 0
    assert teacher_counts.get(school_b) == 1
    assert row_a["current_teachers"] == 0
    assert row_b["current_teachers"] == 1
