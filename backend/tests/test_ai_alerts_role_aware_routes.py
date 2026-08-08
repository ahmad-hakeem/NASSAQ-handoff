"""
Task #1072 — regression tests for role-aware AI Insights "Smart Alerts" links.

The GET /ai/insights/alerts builder attaches a `route` to attendance and
behaviour alerts. Teachers / independent teachers must be sent to their own
self-scoping pages (/teacher/attendance, /teacher/behavior); the admin
attendance/behaviour pages would 403 their data call. Admins / principals
keep the canonical leadership pages (/principal/attendance; behaviour
alerts route to /principal/students because leadership has no dedicated
behaviour page — /admin/behaviour was never a registered route and
bounced to the homepage via the frontend catch-all).

These were two separate manual fixes with no automated guard. This test
fails if a future change silently re-hardcodes an admin route for the
teacher path (or vice versa).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


# -------------------------------------------------------------- helpers


def _headers(user_id: str, role: str, tenant_id, *, teacher_id=None):
    payload = {"sub": user_id, "role": role, "tenant_id": tenant_id}
    if teacher_id is not None:
        payload["teacher_id"] = teacher_id
    return {"Authorization": f"Bearer {create_access_token(payload)}"}


async def _seed_class(school_id: str, name: str = "1A") -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "name": name, "is_active": True,
    })
    return cid


async def _seed_student(school_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": school_id, "full_name": f"S-{sid[:6]}",
        "class_id": class_id, "is_active": True,
    })
    return sid


async def _seed_teacher_user(school_id: str, class_id: str):
    """Create a TEACHER user assigned to one class so the AI-insights scope
    resolver returns a populated teacher scope."""
    user_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": user_id, "role": UserRole.TEACHER.value,
        "tenant_id": school_id, "teacher_id": teacher_id,
        "email": f"t-{user_id}@t.test", "full_name": f"T-{user_id[:6]}",
        "is_active": True, "password_hash": "x",
    })
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": school_id, "user_id": user_id,
        "full_name": f"T-{user_id[:6]}",
    })
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": str(uuid.uuid4()), "teacher_id": teacher_id,
        "school_id": school_id, "class_id": class_id,
    })
    return user_id, teacher_id


async def _seed_chronic_absence(school_id: str, class_id: str, student_ids):
    """Each student absent on 3 distinct days within the past week → triggers
    the 'chronic absence' attendance alert."""
    today = datetime.now(timezone.utc)
    for sid in student_ids:
        for d in range(1, 4):
            day = (today - timedelta(days=d)).strftime("%Y-%m-%d")
            await gd_insert(db.session, "attendance", {
                "id": str(uuid.uuid4()), "school_id": school_id,
                "student_id": sid, "class_id": class_id,
                "date": day, "status": "absent",
            })


async def _seed_negative_behaviour(school_id: str, class_id: str,
                                   student_id: str, n: int = 6):
    """n negative behaviour records within the past week → triggers the
    behaviour alert (threshold is >= 5)."""
    today = datetime.now(timezone.utc)
    for _ in range(n):
        await gd_insert(db.session, "behaviour_records", {
            "id": str(uuid.uuid4()), "school_id": school_id,
            "student_id": student_id, "class_id": class_id, "type": "negative",
            "created_at": (today - timedelta(days=1)).isoformat(),
        })


def _routes_by_category(alerts, category):
    return [a.get("route") for a in alerts if a.get("category") == category]


# -------------------------------------------------------------- tests


@pytest.mark.asyncio
async def test_teacher_alerts_link_to_self_scoping_pages(client, tenant_a):
    """A teacher must get /teacher/attendance and /teacher/behavior routes on
    their attendance / behaviour alerts."""
    cls = await _seed_class(tenant_a, "T-cls")
    students = [await _seed_student(tenant_a, cls) for _ in range(3)]
    user_id, teacher_id = await _seed_teacher_user(tenant_a, cls)
    await _seed_chronic_absence(tenant_a, cls, students)
    await _seed_negative_behaviour(tenant_a, cls, students[0])

    headers = _headers(user_id, UserRole.TEACHER.value, tenant_a,
                       teacher_id=teacher_id)
    r = await client.get("/ai/insights/alerts", headers=headers)
    assert r.status_code == 200, r.text
    alerts = r.json()

    attendance_routes = _routes_by_category(alerts, "attendance")
    behaviour_routes = _routes_by_category(alerts, "behaviour")

    assert attendance_routes, f"no attendance alert produced: {alerts!r}"
    assert behaviour_routes, f"no behaviour alert produced: {alerts!r}"
    assert all(rt == "/teacher/attendance" for rt in attendance_routes), \
        attendance_routes
    assert all(rt == "/teacher/behavior" for rt in behaviour_routes), \
        behaviour_routes


@pytest.mark.asyncio
async def test_principal_alerts_link_to_admin_pages(
    client, tenant_a, school_principal_headers
):
    """A principal (non-teacher scope) must get the canonical leadership
    routes (/principal/attendance; /principal/students for behaviour)
    on the same data state."""
    cls = await _seed_class(tenant_a, "P-cls")
    students = [await _seed_student(tenant_a, cls) for _ in range(3)]
    await _seed_chronic_absence(tenant_a, cls, students)
    await _seed_negative_behaviour(tenant_a, cls, students[0])

    r = await client.get("/ai/insights/alerts",
                         headers=school_principal_headers)
    assert r.status_code == 200, r.text
    alerts = r.json()

    attendance_routes = _routes_by_category(alerts, "attendance")
    behaviour_routes = _routes_by_category(alerts, "behaviour")

    assert attendance_routes, f"no attendance alert produced: {alerts!r}"
    assert behaviour_routes, f"no behaviour alert produced: {alerts!r}"
    assert all(rt == "/principal/attendance" for rt in attendance_routes), \
        attendance_routes
    assert all(rt == "/principal/students" for rt in behaviour_routes), \
        behaviour_routes


@pytest.mark.asyncio
async def test_school_admin_alerts_link_to_admin_pages(
    client, tenant_a, school_admin_headers
):
    """A school admin must also land on the leadership attendance/behaviour
    destinations, never the teacher self-scoping pages."""
    cls = await _seed_class(tenant_a, "A-cls")
    students = [await _seed_student(tenant_a, cls) for _ in range(3)]
    await _seed_chronic_absence(tenant_a, cls, students)
    await _seed_negative_behaviour(tenant_a, cls, students[0])

    r = await client.get("/ai/insights/alerts", headers=school_admin_headers)
    assert r.status_code == 200, r.text
    alerts = r.json()

    for rt in _routes_by_category(alerts, "attendance"):
        assert rt == "/principal/attendance", rt
    for rt in _routes_by_category(alerts, "behaviour"):
        assert rt == "/principal/students", rt
