"""Task #826 — schools.current_students / current_teachers stop drifting.

The denormalized count columns used to be nudged by scattered ``±1``
increments and never recomputed, so they drifted from the real row counts.
They are now *reconciled* (recomputed from live rows) on every
student/teacher create/delete/restore via
``engines.entity_counts.reconcile_school_counts``, which uses the SAME
canonical predicates as the platform list / in-school pages.

These tests prove the reconcile helper:
  * overwrites drifted stored columns with the true live counts, and
  * uses the canonical predicates (FALSE / NULL students excluded; only
    soft-deleted teachers excluded) so the stored columns match what
    ``_live_entity_counts_by_tenant`` reports.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as _sa_text

from dependencies import db
from engines.sql_utils import gd_insert, gd_find_one
from engines.entity_counts import reconcile_school_counts
from src.modules.schools.controllers.school_routes_mod import _live_entity_counts_by_tenant


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


async def _mk_student(school_id: str, is_active) -> None:
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
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "school_id": school_id,
        "full_name": "T",
        "is_active": True if is_active is None else is_active,
        "deleted_at": deleted_at,
    })
    if is_active is None:
        await db.session.execute(
            _sa_text("UPDATE teachers SET is_active = NULL WHERE id = :id"),
            {"id": tid},
        )


@pytest.mark.asyncio
async def test_reconcile_overwrites_drifted_columns(client):
    """A school whose stored counts drifted is healed to the true live count."""
    school = str(uuid.uuid4())
    # Stored columns are wildly wrong (both over- and could be under-stated).
    await _mk_school(school, current_students=99, current_teachers=0)

    # Live truth: 2 active students; 2 active teachers.
    await _mk_student(school, True)
    await _mk_student(school, True)
    await _mk_teacher(school, True)
    await _mk_teacher(school, True)
    await db.session.flush()

    students, teachers = await reconcile_school_counts(db.session, school)
    assert (students, teachers) == (2, 2)

    row = await gd_find_one(db.session, "schools", {"id": school})
    assert row["current_students"] == 2
    assert row["current_teachers"] == 2


@pytest.mark.asyncio
async def test_reconcile_matches_canonical_predicates(client):
    """Reconciled columns equal what _live_entity_counts_by_tenant reports,
    including the FALSE/NULL/soft-delete edge cases."""
    school = str(uuid.uuid4())
    await _mk_school(school, current_students=5, current_teachers=5)

    # Students: 3 active, 1 FALSE, 1 NULL -> canonical count = 3.
    for _ in range(3):
        await _mk_student(school, True)
    await _mk_student(school, False)
    await _mk_student(school, None)

    # Teachers: 2 active, 1 soft-deleted (FALSE + deleted_at), 1 FALSE-no-delete
    # -> canonical count = 3 (only the soft-deleted one is dropped).
    for _ in range(2):
        await _mk_teacher(school, True)
    await _mk_teacher(school, False, deleted_at="2026-01-01T00:00:00+00:00")
    await _mk_teacher(school, False, deleted_at=None)
    await db.session.flush()

    students, teachers = await reconcile_school_counts(db.session, school)
    student_counts, teacher_counts = await _live_entity_counts_by_tenant()

    assert students == student_counts.get(school) == 3
    assert teachers == teacher_counts.get(school) == 3

    row = await gd_find_one(db.session, "schools", {"id": school})
    assert row["current_students"] == 3
    assert row["current_teachers"] == 3


@pytest.mark.asyncio
async def test_reconcile_noops_on_missing_school(client):
    """A falsy / unknown school_id is a safe no-op, not an error."""
    assert await reconcile_school_counts(db.session, "") == (0, 0)
    assert await reconcile_school_counts(db.session, str(uuid.uuid4())) == (0, 0)
