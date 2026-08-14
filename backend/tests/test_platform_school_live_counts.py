"""Task #825 — platform schools list reports LIVE student/teacher counts.

The platform "إدارة المدارس" list used to report the stale denormalized
``current_students`` / ``current_teachers`` columns on the ``schools`` row,
which drift away from the real row count over time. It now computes live
counts via ``_live_entity_counts_by_tenant`` using the SAME predicates the
in-school ``GET /students`` / ``GET /teachers`` endpoints apply.

These tests prove parity at the predicate level, including the NULL /
soft-delete edge cases the code reviewer flagged:

  * Students: ``is_active != False`` — excludes both FALSE and NULL rows
    (matches gd_find's ``$ne`` rendering).
  * Teachers (default active view): keeps everything EXCEPT soft-deleted rows
    (``is_active is False AND deleted_at`` set), so ``is_active`` NULL and
    ``is_active`` False-without-deleted_at rows are still counted.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as _sa_text

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert
from src.modules.schools.controllers.school_routes_mod import _live_entity_counts_by_tenant


def _headers(user: dict) -> dict:
    token = create_access_token(
        {"sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"]}
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


async def _mk_student(school_id: str, is_active) -> None:
    """Insert a student. ``is_active=None`` forces a true SQL NULL (the ORM
    default would otherwise coerce it to True), so the NULL edge case is real."""
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": "ST",
        "is_active": True if is_active is None else is_active,
    })
    if is_active is None:
        await db.session.execute(
            _sa_text("UPDATE students SET is_active = NULL WHERE id = :id"),
            {"id": sid},
        )


async def _mk_teacher(school_id: str, is_active, deleted_at=None) -> None:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": sid,
        "school_id": school_id,
        "full_name": "T",
        "is_active": True if is_active is None else is_active,
        "deleted_at": deleted_at,
    })
    if is_active is None:
        await db.session.execute(
            _sa_text("UPDATE teachers SET is_active = NULL WHERE id = :id"),
            {"id": sid},
        )


@pytest.mark.asyncio
async def test_live_counts_match_inschool_endpoints(client):
    """Helper counts equal what the in-school /students & /teachers lists return."""
    school_a = str(uuid.uuid4())
    school_b = str(uuid.uuid4())
    await _mk_school(school_a)
    await _mk_school(school_b)

    # Tenant A students: 3 active, 1 inactive (False), 1 NULL is_active.
    # GET /students filters is_active != False -> counts ONLY the 3 active
    # (FALSE and NULL are both excluded).
    for _ in range(3):
        await _mk_student(school_a, True)
    await _mk_student(school_a, False)
    await _mk_student(school_a, None)

    # Tenant A teachers: 2 active, 1 soft-deleted (False + deleted_at),
    # 1 inactive-without-deleted_at (False, None), 1 NULL is_active.
    # GET /teachers default view drops ONLY the soft-deleted one -> counts 4
    # (2 active + 1 inactive-no-delete + 1 NULL).
    for _ in range(2):
        await _mk_teacher(school_a, True)
    await _mk_teacher(school_a, False, deleted_at="2026-01-01T00:00:00+00:00")
    await _mk_teacher(school_a, False, deleted_at=None)
    await _mk_teacher(school_a, None)

    # Tenant B noise to prove per-tenant grouping isolates correctly.
    await _mk_student(school_b, True)
    await _mk_teacher(school_b, True)

    await db.session.flush()

    student_counts, teacher_counts = await _live_entity_counts_by_tenant()
    assert student_counts.get(school_a) == 3
    assert teacher_counts.get(school_a) == 4
    assert student_counts.get(school_b) == 1
    assert teacher_counts.get(school_b) == 1


@pytest.mark.asyncio
async def test_live_counts_match_inschool_endpoint_responses(client):
    """Helper counts equal the actual /students and /teachers list lengths.

    Uses only ``is_active`` states the endpoints can serialize (TRUE / FALSE);
    a NULL ``is_active`` teacher makes the endpoint's own ``TeacherResponse``
    500, so that pathological row is covered by the predicate-level test above
    rather than the live-endpoint comparison here.
    """
    school_a = str(uuid.uuid4())
    await _mk_school(school_a)

    # 3 active + 1 inactive students -> /students returns 3.
    for _ in range(3):
        await _mk_student(school_a, True)
    await _mk_student(school_a, False)

    # 2 active + 1 soft-deleted + 1 inactive-no-delete teachers
    # -> /teachers default view returns 3 (drops only the soft-deleted).
    for _ in range(2):
        await _mk_teacher(school_a, True)
    await _mk_teacher(school_a, False, deleted_at="2026-01-01T00:00:00+00:00")
    await _mk_teacher(school_a, False, deleted_at=None)

    admin = {
        "id": str(uuid.uuid4()),
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": school_a,
        "email": f"{uuid.uuid4()}@t.test",
        "full_name": "admin",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", admin)
    await db.session.flush()
    headers = _headers(admin)

    student_counts, teacher_counts = await _live_entity_counts_by_tenant()

    students_resp = await client.get("/students", headers=headers)
    teachers_resp = await client.get("/teachers", headers=headers)
    assert students_resp.status_code == 200
    assert teachers_resp.status_code == 200
    assert len(students_resp.json()) == student_counts.get(school_a) == 3
    assert len(teachers_resp.json()) == teacher_counts.get(school_a) == 3


@pytest.mark.asyncio
async def test_live_counts_ignore_stale_denormalized_columns(client):
    """A school whose stored columns drift still reports the real row count."""
    school = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": school,
        "name": "Drifted",
        "code": f"S{school[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        # Stale/over-stated denormalized aggregates.
        "current_students": 99,
        "current_teachers": 99,
    })
    await _mk_student(school, True)
    await _mk_student(school, True)
    await _mk_teacher(school, True)
    await db.session.flush()

    student_counts, teacher_counts = await _live_entity_counts_by_tenant()
    assert student_counts.get(school) == 2
    assert teacher_counts.get(school) == 1
