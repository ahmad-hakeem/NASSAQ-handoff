"""Task #826 — stored school counts stay accurate across the *alternate*
student/teacher write paths (bulk import helpers), not just the academics
create endpoints.

The reconcile-on-write fix is only complete if every mutation path recomputes
``schools.current_students`` / ``current_teachers`` from live rows. These tests
drive the bulk-import helpers and assert the stored columns end up matching
what ``_live_entity_counts_by_tenant`` reports (the canonical live truth).
"""
from __future__ import annotations

import uuid

import pandas as pd
import pytest

from dependencies import db
from engines.sql_utils import gd_insert, gd_find_one
from routes.bulk_import_export_routes import _import_students, _import_teachers
from routes.school_routes_mod import _live_entity_counts_by_tenant


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


def _digits10(seed: int) -> str:
    return str(1000000000 + seed)[:10]


@pytest.mark.asyncio
async def test_bulk_import_students_reconciles_stored_count(client):
    """Importing students via the bulk helper heals the stored column to the
    true live count rather than leaving it drifted."""
    school = str(uuid.uuid4())
    # Stored column starts wildly wrong.
    await _mk_school(school, current_students=99, current_teachers=0)

    df = pd.DataFrame([
        {"first_name": "Sami", "last_name": "Ali",
         "national_id": _digits10(1), "parent_phone": "0500000001"},
        {"first_name": "Lina", "last_name": "Omar",
         "national_id": _digits10(2), "parent_phone": "0500000002"},
        {"first_name": "Nora", "last_name": "Saad",
         "national_id": _digits10(3), "parent_phone": "0500000003"},
    ])

    errors: list = []
    warnings: list = []
    result = await _import_students(db, df, school, {"id": "tester"}, errors, warnings)
    await db.session.flush()

    assert result["imported"] == 3, (result, errors)

    student_counts, _ = await _live_entity_counts_by_tenant()
    row = await gd_find_one(db.session, "schools", {"id": school})
    assert student_counts.get(school) == 3
    assert row["current_students"] == 3
    assert row["current_teachers"] == 0


@pytest.mark.asyncio
async def test_bulk_import_teachers_reconciles_stored_count(client):
    """Importing teachers via the bulk helper heals the stored column to the
    true live count."""
    school = str(uuid.uuid4())
    await _mk_school(school, current_students=0, current_teachers=42)

    df = pd.DataFrame([
        {"full_name": "Mr A", "email": f"a-{school[:6]}@ex.com", "phone": "0510000001"},
        {"full_name": "Ms B", "email": f"b-{school[:6]}@ex.com", "phone": "0510000002"},
    ])

    errors: list = []
    warnings: list = []
    result = await _import_teachers(db, df, school, {"id": "tester"}, errors, warnings)
    await db.session.flush()

    assert result["imported"] == 2, (result, errors)

    _, teacher_counts = await _live_entity_counts_by_tenant()
    row = await gd_find_one(db.session, "schools", {"id": school})
    assert teacher_counts.get(school) == 2
    assert row["current_teachers"] == 2
    assert row["current_students"] == 0
