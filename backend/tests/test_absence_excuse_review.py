"""Task #466 — Absence-excuse visibility for principals.

Regression contract:
  (a) Parent in school A submits an excuse → principal in school A sees it.
  (b) Principal in school B does not see it; by-id approve returns 404.
  (c) Teacher in school A only sees it when assigned to the student's class.
  (d) Approve flips the matching `attendance` row from `absent` to `excused`.
  (e) Reject persists `rejection_reason` and surfaces via the list/parent view.

These tests do not exercise the parent-portal POST directly — they seed the
`absence_excuses` row with the exact shape the parent-portal writer emits
(see `backend/routes/parent_portal_routes.py:2956-3003`), which is what
the staff endpoints must read.
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one


def _headers(user_id: str, role: str, tenant_id):
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(role: UserRole, tenant_id: str, *, prefix: str = "u") -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": role.value,
        "tenant_id": tenant_id,
        "email": f"{prefix}-{uid}@t.test",
        "full_name": f"{role.value}-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    return uid


async def _mk_student(school_id: str, class_id=None) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": f"ST-{sid[:6]}",
        "class_id": class_id,
        "is_active": True,
    })
    return sid


async def _mk_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "name": f"C-{cid[:4]}",
    })
    return cid


async def _seed_excuse(
    school_id: str, parent_id: str, child_id: str,
    *, absence_date: str = "2026-05-20", status: str = "pending",
) -> str:
    eid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "absence_excuses", {
        "id": eid,
        "parent_id": parent_id,
        "parent_name": "Parent Name",
        "child_id": child_id,
        "child_name": "Child Name",
        "school_id": school_id,
        "absence_date": absence_date,
        "reason": "مرض",
        "attachment_url": None,
        "attachment_name": None,
        "status": status,
        "created_at": now,
        "updated_at": now,
    })
    return eid


@pytest_asyncio.fixture
async def parent_a(tenant_a):
    return await _mk_user(UserRole.PARENT, tenant_a, prefix="parent")


@pytest_asyncio.fixture
async def principal_b(tenant_b):
    uid = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_b, prefix="prinB")
    return _headers(uid, UserRole.SCHOOL_PRINCIPAL.value, tenant_b)


# ---------------------------------------------------------------------------
# (a) Principal of the same school sees the pending excuse
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_principal_sees_pending_excuse_same_school(
    client, school_principal_headers, tenant_a, parent_a,
):
    child = await _mk_student(tenant_a)
    eid = await _seed_excuse(tenant_a, parent_a, child)

    r = await client.get("/attendance/excuses", headers=school_principal_headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list)
    ids = [row["id"] for row in rows]
    assert eid in ids, "principal should see the parent-submitted pending excuse"
    found = next(row for row in rows if row["id"] == eid)
    assert found["status"] == "pending"
    # canonical and staff-alias names both projected
    assert found["child_id"] == child
    assert found["student_id"] == child
    assert found["absence_date"] == "2026-05-20"
    assert found["date"] == "2026-05-20"


@pytest.mark.asyncio
async def test_pending_count_endpoint_reflects_open_excuses(
    client, school_principal_headers, tenant_a, parent_a,
):
    child = await _mk_student(tenant_a)
    await _seed_excuse(tenant_a, parent_a, child)
    await _seed_excuse(tenant_a, parent_a, child, status="approved")

    r = await client.get("/attendance/excuses/pending-count", headers=school_principal_headers)
    assert r.status_code == 200, r.text
    assert r.json().get("count") == 1


# ---------------------------------------------------------------------------
# (b) Cross-tenant principal must not see / cannot action
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_principal_cannot_see_excuse(
    client, tenant_a, parent_a, principal_b,
):
    child = await _mk_student(tenant_a)
    eid = await _seed_excuse(tenant_a, parent_a, child)

    r = await client.get("/attendance/excuses", headers=principal_b)
    assert r.status_code == 200
    assert all(row["id"] != eid for row in r.json())


@pytest.mark.asyncio
async def test_cross_tenant_approve_returns_404(
    client, tenant_a, parent_a, principal_b,
):
    child = await _mk_student(tenant_a)
    eid = await _seed_excuse(tenant_a, parent_a, child)

    r = await client.put(f"/attendance/excuse/{eid}/approve", headers=principal_b)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# (c) Teacher scope: only assigned-class students surface
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_teacher_only_sees_excuses_for_assigned_classes(
    client, tenant_a, parent_a,
):
    class_taught = await _mk_class(tenant_a)
    class_other = await _mk_class(tenant_a)
    my_student = await _mk_student(tenant_a, class_id=class_taught)
    other_student = await _mk_student(tenant_a, class_id=class_other)

    teacher_uid = await _mk_user(UserRole.TEACHER, tenant_a, prefix="t")
    await gd_insert(db.session, "teachers", {
        "id": teacher_uid, "school_id": tenant_a,
        "full_name": "T", "is_active": True,
    })
    subj_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subj_id, "school_id": tenant_a, "name": "Math",
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "teacher_id": teacher_uid,
        "class_id": class_taught,
        "subject_id": subj_id,
        "school_id": tenant_a,
        "is_active": True,
    })
    teacher_headers = _headers(teacher_uid, UserRole.TEACHER.value, tenant_a)

    mine = await _seed_excuse(tenant_a, parent_a, my_student)
    theirs = await _seed_excuse(tenant_a, parent_a, other_student)

    r = await client.get("/attendance/excuses", headers=teacher_headers)
    assert r.status_code == 200, r.text
    ids = {row["id"] for row in r.json()}
    assert mine in ids
    assert theirs not in ids


@pytest.mark.asyncio
async def test_teacher_cannot_approve(
    client, tenant_a, teacher_headers, parent_a,
):
    child = await _mk_student(tenant_a)
    eid = await _seed_excuse(tenant_a, parent_a, child)
    r = await client.put(f"/attendance/excuse/{eid}/approve", headers=teacher_headers)
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# (d) Approve cascades to attendance row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_flips_attendance_to_excused(
    client, school_principal_headers, tenant_a, parent_a,
):
    child = await _mk_student(tenant_a)
    eid = await _seed_excuse(tenant_a, parent_a, child, absence_date="2026-05-19")

    att_id = str(uuid.uuid4())
    await gd_insert(db.session, "attendance", {
        "id": att_id,
        "student_id": child,
        "date": "2026-05-19",
        "status": "absent",
        "school_id": tenant_a,
        "tenant_id": tenant_a,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })

    r = await client.put(f"/attendance/excuse/{eid}/approve", headers=school_principal_headers)
    assert r.status_code == 200, r.text

    row = await gd_find_one(db.session, "attendance", {"id": att_id})
    assert row and row.get("status") == "excused"
    assert row.get("is_excused") is True

    excuse_row = await gd_find_one(db.session, "absence_excuses", {"id": eid})
    assert excuse_row.get("status") == "approved"
    assert excuse_row.get("reviewed_at")


# ---------------------------------------------------------------------------
# (e) Reject stores rejection_reason
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reject_persists_rejection_reason(
    client, school_principal_headers, tenant_a, parent_a,
):
    child = await _mk_student(tenant_a)
    eid = await _seed_excuse(tenant_a, parent_a, child)

    r = await client.put(
        f"/attendance/excuse/{eid}/reject",
        json={"reason": "وثائق غير كافية"},
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text

    row = await gd_find_one(db.session, "absence_excuses", {"id": eid})
    assert row.get("status") == "rejected"
    assert row.get("rejection_reason") == "وثائق غير كافية"
