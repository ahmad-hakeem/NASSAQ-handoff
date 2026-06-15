"""Attendance Engine API tests (ASGI harness).

Ported from a live-server `requests` script to the project's in-process
``AsyncClient`` harness (see ``tests/conftest.py``). Each test seeds its own
class + students in ``tenant_a`` and drives the real FastAPI app, so the suite
runs deterministically with no external server or pre-seeded data.

Covers:
- GET  /api/attendance/students-for-class/{class_id}
- POST /api/attendance/bulk
- GET  /api/attendance/report/daily/{class_id}
- GET  /api/attendance/report/summary
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_insert


TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _mk_class(school_id: str, name: str = "1A") -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": name,
        "capacity": 30,
        "is_active": True,
    })
    return cid


async def _mk_student(school_id: str, class_id: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "tenant_id": school_id,
        "class_id": class_id,
        "full_name": name,
        "is_active": True,
    })
    return sid


async def _seed_class_with_students(school_id: str, n: int = 4):
    class_id = await _mk_class(school_id)
    student_ids = [
        await _mk_student(school_id, class_id, f"طالب-{i}") for i in range(n)
    ]
    await db.session.flush()
    return class_id, student_ids


@pytest.mark.asyncio
async def test_get_students_for_class(client, school_principal_headers, tenant_a):
    class_id, student_ids = await _seed_class_with_students(tenant_a, 4)

    resp = await client.get(
        f"/attendance/students-for-class/{class_id}",
        params={"date": TODAY},
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["class_id"] == class_id
    assert "class_name" in data
    assert data["date"] == TODAY
    assert data["total_students"] == 4
    assert len(data["students"]) == 4
    # Nothing recorded yet.
    assert data["recorded_count"] == 0
    assert all(s["attendance_status"] is None for s in data["students"])


@pytest.mark.asyncio
async def test_bulk_attendance_create_mixed_statuses(client, school_principal_headers, tenant_a):
    class_id, student_ids = await _seed_class_with_students(tenant_a, 4)

    statuses = ["present", "absent", "late", "excused"]
    records = [
        {"student_id": sid, "status": statuses[i], "notes": f"test-{statuses[i]}"}
        for i, sid in enumerate(student_ids)
    ]

    resp = await client.post(
        "/attendance/bulk",
        json={
            "class_id": class_id,
            "subject_id": None,
            "time_slot_id": None,
            "date": TODAY,
            "records": records,
        },
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["created"] == 4
    assert data["updated"] == 0
    assert data["date"] == TODAY
    assert data["class_id"] == class_id


@pytest.mark.asyncio
async def test_bulk_attendance_upsert_updates_existing(client, school_principal_headers, tenant_a):
    class_id, student_ids = await _seed_class_with_students(tenant_a, 3)

    base = {
        "class_id": class_id,
        "subject_id": None,
        "time_slot_id": None,
        "date": TODAY,
    }
    # First write: all present (created).
    first = await client.post(
        "/attendance/bulk",
        json={**base, "records": [{"student_id": s, "status": "present"} for s in student_ids]},
        headers=school_principal_headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 3

    # Second write same day: flip to absent (updated, not created).
    second = await client.post(
        "/attendance/bulk",
        json={**base, "records": [{"student_id": s, "status": "absent"} for s in student_ids]},
        headers=school_principal_headers,
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["created"] == 0
    assert body["updated"] == 3


@pytest.mark.asyncio
async def test_daily_attendance_report(client, school_principal_headers, tenant_a):
    class_id, student_ids = await _seed_class_with_students(tenant_a, 4)

    statuses = ["present", "absent", "late", "excused"]
    records = [{"student_id": sid, "status": statuses[i]} for i, sid in enumerate(student_ids)]
    rec = await client.post(
        "/attendance/bulk",
        json={"class_id": class_id, "date": TODAY, "records": records},
        headers=school_principal_headers,
    )
    assert rec.status_code == 200, rec.text

    resp = await client.get(
        f"/attendance/report/daily/{class_id}",
        params={"date": TODAY},
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["class_id"] == class_id
    assert data["date"] == TODAY
    summary = data["summary"]
    assert summary["total_students"] == 4
    assert summary["present"] == 1
    assert summary["absent"] == 1
    assert summary["late"] == 1
    assert summary["excused"] == 1
    # (present + late) / total * 100 = 2/4*100 = 50.0
    assert summary["attendance_rate"] == 50.0
    assert len(data["records"]) == 4


@pytest.mark.asyncio
async def test_attendance_summary_report(client, school_principal_headers, tenant_a):
    class_id, student_ids = await _seed_class_with_students(tenant_a, 4)

    records = [{"student_id": sid, "status": "present"} for sid in student_ids]
    rec = await client.post(
        "/attendance/bulk",
        json={"class_id": class_id, "date": TODAY, "records": records},
        headers=school_principal_headers,
    )
    assert rec.status_code == 200, rec.text

    resp = await client.get(
        "/attendance/report/summary",
        params={"class_id": class_id},
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "overall" in data
    assert "daily" in data
    overall = data["overall"]
    assert overall["total_records"] == 4
    assert overall["present"] == 4
    assert overall["absent"] == 0
    assert overall["attendance_rate"] == 100.0


@pytest.mark.asyncio
async def test_mark_all_present_then_verify(client, school_principal_headers, tenant_a):
    class_id, student_ids = await _seed_class_with_students(tenant_a, 5)

    records = [{"student_id": sid, "status": "present", "notes": None} for sid in student_ids]
    rec = await client.post(
        "/attendance/bulk",
        json={"class_id": class_id, "date": TODAY, "records": records},
        headers=school_principal_headers,
    )
    assert rec.status_code == 200, rec.text

    verify = await client.get(
        f"/attendance/report/daily/{class_id}",
        params={"date": TODAY},
        headers=school_principal_headers,
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["summary"]["present"] == 5


@pytest.mark.asyncio
async def test_attendance_persistence_reflected_in_students_for_class(client, school_principal_headers, tenant_a):
    class_id, student_ids = await _seed_class_with_students(tenant_a, 3)

    records = [{"student_id": sid, "status": "present"} for sid in student_ids]
    rec = await client.post(
        "/attendance/bulk",
        json={"class_id": class_id, "date": TODAY, "records": records},
        headers=school_principal_headers,
    )
    assert rec.status_code == 200, rec.text

    resp = await client.get(
        f"/attendance/students-for-class/{class_id}",
        params={"date": TODAY},
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    students_with_status = [s for s in data["students"] if s.get("attendance_status")]
    assert data["recorded_count"] == len(students_with_status) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["present", "absent", "late", "excused"])
async def test_single_student_status_changes(client, school_principal_headers, tenant_a, status):
    class_id, student_ids = await _seed_class_with_students(tenant_a, 1)

    resp = await client.post(
        "/attendance/bulk",
        json={
            "class_id": class_id,
            "date": TODAY,
            "records": [{"student_id": student_ids[0], "status": status}],
        },
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 1


@pytest.mark.asyncio
async def test_parent_cannot_read_students_for_class(client, parent_headers, tenant_a):
    class_id, _ = await _seed_class_with_students(tenant_a, 2)
    resp = await client.get(
        f"/attendance/students-for-class/{class_id}",
        headers=parent_headers,
    )
    assert resp.status_code == 403, resp.text
