"""Parent portal attendance-rate regression tests.

Root cause addressed:
  Some UI paths (e.g. "mark all present") only write DB rows for present
  students; absent students never get a row. This made the denominator equal
  the present count → always 100%. The fix uses the number of distinct
  calendar dates ANY student in the class had attendance recorded as the
  denominator, scoped by school_id.

Scenarios covered (detail endpoint + legacy dashboard endpoint):
  1. No attendance at all → null rate (placeholder, not fake 0%/100%).
  2. Teacher took attendance on 2 days, student present on 1 → 50.0%.
  3. Teacher took attendance on 2 days, student present on both → 100.0%.
  4. Cross-tenant attendance rows must not bleed into the rate calculation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert  # used for classes, parents, users
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parent_token(user_id: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "name": f"CL-{cid[:6]}",
        "capacity": 30,
        "is_active": True,
    })
    return cid


async def _seed_parent_with_child(tenant_id: str, class_id: str | None = None):
    """Seed a parent user + parents row + student linked via students.parent_id."""
    parent_record_id = str(uuid.uuid4())
    parent_user_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": parent_record_id,
        "full_name": "ولي أمر تجريبي",
        "email": f"p-{parent_record_id}@t.test",
        "school_id": tenant_id,
        "is_active": True,
        "student_ids": [],
    })
    await gd_insert(db.session, "users", {
        "id": parent_user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
        "parent_id": parent_record_id,
        "email": f"p-{parent_record_id}@t.test",
        "full_name": "ولي أمر تجريبي",
        "is_active": True,
        "password_hash": "x",
    })
    student_id = str(uuid.uuid4())
    # Use raw SQL to avoid optional ORM column issues (talents, is_gifted, …)
    await db.session.execute(
        text(
            "INSERT INTO students (id, school_id, full_name, parent_id, class_id, is_active)"
            " VALUES (:id, :school_id, :full_name, :parent_id, :class_id, true)"
        ),
        {
            "id": student_id,
            "school_id": tenant_id,
            "full_name": f"ST-{student_id[:6]}",
            "parent_id": parent_record_id,
            "class_id": class_id,
        },
    )
    return {
        "user_id": parent_user_id,
        "parent_record_id": parent_record_id,
        "student_id": student_id,
    }


async def _add_att(school_id: str, student_id: str, class_id: str,
                   date_str: str, status: str) -> None:
    """Insert a single attendance row directly into the DB.

    recorded_by is nullable (ON DELETE SET NULL) so we omit it to avoid
    seeding a users row just for the FK.
    """
    await db.session.execute(
        text(
            "INSERT INTO attendance"
            " (id, school_id, class_id, student_id, date, status,"
            "  created_at, updated_at)"
            " VALUES (:id, :school_id, :class_id, :student_id, :date, :status,"
            "  now(), now())"
        ),
        {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "class_id": class_id,
            "student_id": student_id,
            "date": datetime.fromisoformat(f"{date_str}T08:00:00+00:00"),
            "status": status,
        },
    )


# ---------------------------------------------------------------------------
# Tests — detail endpoint: GET /parent/child/{id}/attendance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_attendance_rate_null_when_no_records(client, tenant_a):
    """No attendance rows at all → statistics.attendance_rate is null."""
    class_id = await _mk_class(tenant_a)
    seeded = await _seed_parent_with_child(tenant_a, class_id)
    await db.session.flush()

    res = await client.get(
        f"/parent-portal/child/{seeded['student_id']}/attendance",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    stats = res.json()["statistics"]
    assert stats["attendance_rate"] is None
    assert stats["total_days"] == 0


@pytest.mark.asyncio
async def test_attendance_rate_50_when_only_present_rows_exist(client, tenant_a):
    """Core regression: teacher marked only one student present on 2 days;
    the absent student has NO DB row. Rate must be 50%, not 100%."""
    class_id = await _mk_class(tenant_a)
    seeded = await _seed_parent_with_child(tenant_a, class_id)

    # Seed a second student in the same class (the one who WAS present on both days).
    peer_id = str(uuid.uuid4())
    await db.session.execute(
        text(
            "INSERT INTO students (id, school_id, full_name, is_active, class_id)"
            " VALUES (:id, :school_id, 'peer', true, :class_id)"
        ),
        {"id": peer_id, "school_id": tenant_a, "class_id": class_id},
    )

    our_student = seeded["student_id"]

    # Day 1: our student IS present.
    await _add_att(tenant_a, our_student, class_id, "2026-05-01", "present")
    await _add_att(tenant_a, peer_id, class_id, "2026-05-01", "present")

    # Day 2: peer present; our student absent → NO row written for our_student
    # (simulates a UI that only records "present" clicks).
    await _add_att(tenant_a, peer_id, class_id, "2026-05-02", "present")

    await db.session.flush()

    res = await client.get(
        f"/parent-portal/child/{our_student}/attendance",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    stats = res.json()["statistics"]
    # Class has 2 distinct session dates; student present on 1 → 50%
    assert stats["total_days"] == 2
    assert stats["present"] == 1
    assert stats["attendance_rate"] == 50.0


@pytest.mark.asyncio
async def test_attendance_rate_100_when_always_present(client, tenant_a):
    """Student present on every day the class had attendance → 100%."""
    class_id = await _mk_class(tenant_a)
    seeded = await _seed_parent_with_child(tenant_a, class_id)
    our_student = seeded["student_id"]

    for day in ("2026-05-01", "2026-05-02"):
        await _add_att(tenant_a, our_student, class_id, day, "present")
    await db.session.flush()

    res = await client.get(
        f"/parent-portal/child/{our_student}/attendance",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    stats = res.json()["statistics"]
    assert stats["total_days"] == 2
    assert stats["present"] == 2
    assert stats["attendance_rate"] == 100.0


@pytest.mark.asyncio
async def test_attendance_rate_ignores_cross_tenant_rows(client, tenant_a, tenant_b):
    """Attendance rows from tenant_b must not inflate the denominator or
    the present count for a tenant_a student (school_id scope fix)."""
    class_id_a = await _mk_class(tenant_a)
    class_id_b = await _mk_class(tenant_b)
    seeded = await _seed_parent_with_child(tenant_a, class_id_a)
    our_student = seeded["student_id"]

    # Tenant A: 1 present row on 1 day
    await _add_att(tenant_a, our_student, class_id_a, "2026-05-01", "present")

    # Tenant B: forge rows using the same student_id (IDOR probe)
    await _add_att(tenant_b, our_student, class_id_b, "2026-05-02", "present")
    await _add_att(tenant_b, our_student, class_id_b, "2026-05-03", "present")
    await db.session.flush()

    res = await client.get(
        f"/parent-portal/child/{our_student}/attendance",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    stats = res.json()["statistics"]
    # Only tenant_a rows count: 1 class session date, 1 present
    assert stats["total_days"] == 1
    assert stats["present"] == 1
    assert stats["attendance_rate"] == 100.0


# ---------------------------------------------------------------------------
# Tests — legacy dashboard endpoint: GET /parent-portal/dashboard
# (attendance_rate on each child card — previously used raw gd_count with no
#  school_id filter; now uses gd_distinct class-dates denominator like the
#  newer dashboard path and the detail endpoint)
# ---------------------------------------------------------------------------

def _child_att_rate(dashboard_json: dict, student_id: str) -> float | None:
    """Extract attendance_rate for the given student from dashboard children."""
    for child in dashboard_json.get("children", []):
        if child.get("id") == student_id:
            return child.get("attendance_rate")
    raise KeyError(f"student {student_id} not in dashboard response")


@pytest.mark.asyncio
async def test_dashboard_attendance_rate_null_when_no_records(client, tenant_a):
    """Dashboard child card: no attendance rows → attendance_rate is null."""
    class_id = await _mk_class(tenant_a)
    seeded = await _seed_parent_with_child(tenant_a, class_id)
    await db.session.flush()

    res = await client.get(
        "/parent-portal/dashboard",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    rate = _child_att_rate(res.json(), seeded["student_id"])
    assert rate is None


@pytest.mark.asyncio
async def test_dashboard_attendance_rate_50_when_absent_has_no_row(client, tenant_a):
    """Core regression on dashboard: peer present on 2 days, our student only
    on 1 (and has no row on day 2). attendance_rate must be 50%, not 100%."""
    class_id = await _mk_class(tenant_a)
    seeded = await _seed_parent_with_child(tenant_a, class_id)

    peer_id = str(uuid.uuid4())
    await db.session.execute(
        text(
            "INSERT INTO students (id, school_id, full_name, is_active, class_id)"
            " VALUES (:id, :school_id, 'peer', true, :class_id)"
        ),
        {"id": peer_id, "school_id": tenant_a, "class_id": class_id},
    )

    our_student = seeded["student_id"]

    # Day 1: both present
    await _add_att(tenant_a, our_student, class_id, "2026-06-01", "present")
    await _add_att(tenant_a, peer_id, class_id, "2026-06-01", "present")

    # Day 2: only peer present; our student absent → no row written
    await _add_att(tenant_a, peer_id, class_id, "2026-06-02", "present")

    await db.session.flush()

    res = await client.get(
        "/parent-portal/dashboard",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    rate = _child_att_rate(res.json(), our_student)
    assert rate == 50.0


@pytest.mark.asyncio
async def test_dashboard_attendance_rate_100_when_always_present(client, tenant_a):
    """Dashboard child card: student present on every class session → 100%."""
    class_id = await _mk_class(tenant_a)
    seeded = await _seed_parent_with_child(tenant_a, class_id)
    our_student = seeded["student_id"]

    for day in ("2026-06-01", "2026-06-02"):
        await _add_att(tenant_a, our_student, class_id, day, "present")
    await db.session.flush()

    res = await client.get(
        "/parent-portal/dashboard",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    rate = _child_att_rate(res.json(), our_student)
    assert rate == 100.0


@pytest.mark.asyncio
async def test_dashboard_attendance_rate_ignores_cross_tenant_rows(
    client, tenant_a, tenant_b
):
    """Dashboard: forged attendance rows from tenant_b must not inflate the
    denominator or present count for a tenant_a student."""
    class_id_a = await _mk_class(tenant_a)
    class_id_b = await _mk_class(tenant_b)
    seeded = await _seed_parent_with_child(tenant_a, class_id_a)
    our_student = seeded["student_id"]

    # Tenant A: 1 present on 1 day → rate should be 100% (1/1)
    await _add_att(tenant_a, our_student, class_id_a, "2026-06-01", "present")

    # Tenant B: two extra rows with the same student_id (IDOR probe)
    await _add_att(tenant_b, our_student, class_id_b, "2026-06-02", "present")
    await _add_att(tenant_b, our_student, class_id_b, "2026-06-03", "present")
    await db.session.flush()

    res = await client.get(
        "/parent-portal/dashboard",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    rate = _child_att_rate(res.json(), our_student)
    # Only tenant_a class dates count (1 day, 1 present) → 100%
    assert rate == 100.0
