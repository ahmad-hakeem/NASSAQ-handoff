"""Task #834 — routine check that flags drifting class & school counts.

Tasks #826 (school counters) and #829 (class counters) made the denormalized
``schools.current_students`` / ``schools.current_teachers`` and
``classes.current_students`` columns *self-healing* by reconciling them from
the live rows on every write instead of nudging by ``±1``. There was, however,
no test proving the stored columns stay in sync with the canonical live count
across the real student create / delete / transfer HTTP paths, and no sweep to
flag any future code path that nudges a counter without reconciling.

This module closes both gaps:

* ``test_lifecycle_stored_counters_match_live`` drives create → transfer →
  delete through the real routers and, after every step, asserts the stored
  class counters equal ``reconcile_class_counts``'s live count and the stored
  school counters equal ``reconcile_school_counts``'s live count.
* ``test_sweep_*`` cover the lightweight ``sweep_count_divergences`` audit:
  a clean inventory reports nothing, an artificially drifted counter is
  flagged, and ``fix=True`` heals it.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as _sa_text

from dependencies import db
from engines.sql_utils import gd_insert, gd_find_one
from engines.entity_counts import (
    reconcile_class_counts,
    reconcile_school_counts,
    sweep_count_divergences,
)


async def _stored_class_count(class_id: str) -> int:
    row = await gd_find_one(db.session, "classes", {"id": class_id})
    return int((row or {}).get("current_students") or 0)


async def _stored_school_counts(school_id: str):
    row = await gd_find_one(db.session, "schools", {"id": school_id})
    return (
        int((row or {}).get("current_students") or 0),
        int((row or {}).get("current_teachers") or 0),
    )


async def _assert_class_in_sync(class_id: str, school_id: str):
    """Stored class counter must equal the canonical live count.

    ``reconcile_class_counts`` returns the live truth (and re-persists it), so
    comparing the stored column to its return value proves they agree.
    """
    stored = await _stored_class_count(class_id)
    live = await reconcile_class_counts(db.session, class_id, school_id)
    assert stored == live, f"class {class_id}: stored={stored} live={live}"


async def _assert_school_in_sync(school_id: str):
    stored_students, stored_teachers = await _stored_school_counts(school_id)
    live_students, live_teachers = await reconcile_school_counts(db.session, school_id)
    assert stored_students == live_students, (
        f"school {school_id}: stored_students={stored_students} live={live_students}"
    )
    assert stored_teachers == live_teachers, (
        f"school {school_id}: stored_teachers={stored_teachers} live={live_teachers}"
    )


@pytest.mark.asyncio
async def test_lifecycle_stored_counters_match_live(
    client, school_principal_headers, tenant_a
):
    """Create / transfer / delete through the real routers never drifts the
    stored class or school counters away from the live truth."""
    class_a = str(uuid.uuid4())
    class_b = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_a, "school_id": tenant_a, "name": "1A", "current_students": 0,
    })
    await gd_insert(db.session, "classes", {
        "id": class_b, "school_id": tenant_a, "name": "1B", "current_students": 0,
    })
    await db.session.flush()

    # --- CREATE: two students into class A ---
    created = []
    for i in range(2):
        r = await client.post(
            "/students",
            json={"full_name": f"Pupil {i}", "class_id": class_a},
            headers=school_principal_headers,
        )
        assert r.status_code == 200, r.text
        created.append(r.json()["id"])

    await _assert_class_in_sync(class_a, tenant_a)
    await _assert_class_in_sync(class_b, tenant_a)
    await _assert_school_in_sync(tenant_a)
    assert await _stored_class_count(class_a) == 2
    assert (await _stored_school_counts(tenant_a))[0] == 2

    # --- TRANSFER: move one student A -> B ---
    r = await client.post(
        "/students/transfer-class",
        json={"student_id": created[0], "target_class_id": class_b},
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text

    await _assert_class_in_sync(class_a, tenant_a)
    await _assert_class_in_sync(class_b, tenant_a)
    await _assert_school_in_sync(tenant_a)
    assert await _stored_class_count(class_a) == 1
    assert await _stored_class_count(class_b) == 1
    # School total unchanged by a transfer.
    assert (await _stored_school_counts(tenant_a))[0] == 2

    # --- DELETE: soft-delete the student now in class B ---
    r = await client.delete(
        f"/students/{created[0]}", headers=school_principal_headers
    )
    assert r.status_code == 200, r.text

    await _assert_class_in_sync(class_a, tenant_a)
    await _assert_class_in_sync(class_b, tenant_a)
    await _assert_school_in_sync(tenant_a)
    assert await _stored_class_count(class_b) == 0
    assert (await _stored_school_counts(tenant_a))[0] == 1


@pytest.mark.asyncio
async def test_sweep_reports_no_divergence_when_in_sync(client, tenant_a):
    """A freshly reconciled inventory has no drift to flag."""
    cls = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cls, "school_id": tenant_a, "name": "2A", "current_students": 0,
    })
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_a, "full_name": "InSync",
        "class_id": cls, "is_active": True,
    })
    await db.session.flush()
    await reconcile_class_counts(db.session, cls, tenant_a)
    await reconcile_school_counts(db.session, tenant_a)

    report = await sweep_count_divergences(db.session)
    assert all(d["school_id"] != tenant_a for d in report["schools"])
    assert all(d["class_id"] != cls for d in report["classes"])


@pytest.mark.asyncio
async def test_sweep_flags_artificially_drifted_counters(client, tenant_a):
    """A counter nudged out of sync (simulating a bad future write path) is
    surfaced by the sweep with the stored-vs-live mismatch."""
    cls = str(uuid.uuid4())
    # Stored columns are deliberately wrong: class says 9, school says 7/3.
    await gd_insert(db.session, "classes", {
        "id": cls, "school_id": tenant_a, "name": "3A", "current_students": 9,
    })
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_a, "full_name": "Real",
        "class_id": cls, "is_active": True,
    })
    await db.session.execute(
        _sa_text(
            "UPDATE schools SET current_students = 7, current_teachers = 3 "
            "WHERE id = :id"
        ),
        {"id": tenant_a},
    )
    await db.session.flush()

    report = await sweep_count_divergences(db.session)

    school_hit = next(d for d in report["schools"] if d["school_id"] == tenant_a)
    assert school_hit["stored_students"] == 7
    assert school_hit["live_students"] == 1
    assert school_hit["stored_teachers"] == 3
    assert school_hit["live_teachers"] == 0

    class_hit = next(d for d in report["classes"] if d["class_id"] == cls)
    assert class_hit["stored_students"] == 9
    assert class_hit["live_students"] == 1

    # Read-only by default: nothing was healed.
    assert await _stored_class_count(cls) == 9
    assert (await _stored_school_counts(tenant_a)) == (7, 3)


@pytest.mark.asyncio
async def test_sweep_fix_heals_drifted_counters(client, tenant_a):
    """``fix=True`` overwrites the drifted columns with the live truth."""
    cls = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cls, "school_id": tenant_a, "name": "4A", "current_students": 42,
    })
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_a, "full_name": "Heal",
        "class_id": cls, "is_active": True,
    })
    await db.session.execute(
        _sa_text(
            "UPDATE schools SET current_students = 99, current_teachers = 5 "
            "WHERE id = :id"
        ),
        {"id": tenant_a},
    )
    await db.session.flush()

    await sweep_count_divergences(db.session, fix=True)

    assert await _stored_class_count(cls) == 1
    assert (await _stored_school_counts(tenant_a)) == (1, 0)

    # A second sweep now finds this tenant clean.
    report = await sweep_count_divergences(db.session)
    assert all(d["school_id"] != tenant_a for d in report["schools"])
    assert all(d["class_id"] != cls for d in report["classes"])
