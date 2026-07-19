"""Parent portal — Independent-Teacher workspace child schedule (الجدول tab).

Root cause covered (audit 2026-07-19): ``GET /parent-portal/child/{id}/schedule``
and the today-live resolver read ONLY the modern engine (``timetables`` +
``timetable_sessions``). IT workspaces never create that parent — their grid
lives directly in ``schedule_sessions`` (status="scheduled", SHORT day codes
like "sun"/"sat", ``slot_number`` as the period, denormalised subject/teacher
names, EMPTY start/end times). Result: the parent's ملف الطالب → الجدول tab was
blank in both list and grid views for every IT child.

Pins:
1. IT child schedule returns the stored sessions with normalised Arabic days,
   slot-derived times, and denormalised names.
2. Saturday sessions are NOT dropped — السبت is appended to ``days`` only when
   used (real-school Sun–Thu day list unchanged).
3. Duplicate (day, slot) rows are deduped.
4. ``periods`` covers the workspace period clock so the grid view renders rows.
5. Cross-workspace access still fails closed (403).
6. The IT branch of the today-live resolver returns timed sessions.
"""
import uuid

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert


def _headers(user_id: str, role: str, tenant_id):
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_it_workspace() -> tuple:
    owner_uid = str(uuid.uuid4())
    tenant = f"itw_{owner_uid}"
    await gd_insert(db.session, "schools", {
        "id": tenant,
        "name": "مساحة معلم مستقل",
        "code": f"IT{owner_uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
        "tenant_type": "independent_teacher",
    })
    await gd_insert(db.session, "users", {
        "id": owner_uid, "role": "independent_teacher", "tenant_id": tenant,
        "email": f"it-{owner_uid}@t.test", "full_name": "المعلم المستقل",
        "is_active": True, "password_hash": "x",
    })
    # Authoritative teachers row (mirrors real IT bootstrap) — the
    # schedule_sessions.teacher_id FK points at teachers.id.
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": tenant, "user_id": owner_uid,
        "full_name": "المعلم المستقل", "is_active": True,
    })
    return tenant, teacher_id


async def _mk_parent_and_child(tenant):
    parent_uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": parent_uid, "role": "parent", "tenant_id": tenant,
        "email": f"p-{parent_uid}@t.test", "full_name": "ولي الأمر",
        "is_active": True, "password_hash": "x",
    })
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant, "tenant_id": tenant, "name": "مقرر تجريبي",
    })
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant, "tenant_id": tenant,
        "full_name": "طالب اختبار", "class_id": cid, "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()), "tenant_id": tenant,
        "student_id": sid, "parent_ref": parent_uid,
        "is_active": True,
    })
    return parent_uid, sid, cid


async def _mk_it_session(tenant, cid, owner_uid, day, slot, subject="رياضيات"):
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": tenant,
        "schedule_id": f"itw_schedule_{tenant}",
        "class_id": cid, "teacher_id": owner_uid,
        "day_of_week": day, "slot_number": slot, "status": "scheduled",
        "subject_name": subject, "teacher_name": "المعلم المستقل",
        "class_name": "مقرر تجريبي",
        "start_time": "", "end_time": "",
    })


@pytest.mark.asyncio
async def test_it_child_schedule_returns_sessions(client):
    tenant, owner_uid = await _mk_it_workspace()
    parent_uid, sid, cid = await _mk_parent_and_child(tenant)
    await _mk_it_session(tenant, cid, owner_uid, "sun", 1, subject="English")
    await _mk_it_session(tenant, cid, owner_uid, "mon", 3)
    # Duplicate (day, slot) — must be deduped, not doubled.
    await _mk_it_session(tenant, cid, owner_uid, "mon", 3)

    resp = await client.get(f"/parent-portal/child/{sid}/schedule",
                            headers=_headers(parent_uid, "parent", tenant))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    sun = body["schedule"].get("الأحد") or []
    mon = body["schedule"].get("الاثنين") or []
    assert len(sun) == 1 and len(mon) == 1, body["schedule"]
    assert sun[0]["subject"] == "English"
    assert sun[0]["teacher"] == "المعلم المستقل"
    assert sun[0]["period"] == 1
    # Slot times derived from the workspace period clock (default 07:00/45min).
    assert sun[0]["start_time"] and sun[0]["end_time"]
    assert mon[0]["period"] == 3

    # Grid rows: canonical period list must exist and cover the used slots.
    period_indexes = [p["period"] for p in body["periods"]]
    assert 1 in period_indexes and 3 in period_indexes

    # No weekend sessions → the default Sun–Thu day list is unchanged.
    assert body["days"] == ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]


@pytest.mark.asyncio
async def test_it_child_schedule_includes_saturday_when_used(client):
    tenant, owner_uid = await _mk_it_workspace()
    parent_uid, sid, cid = await _mk_parent_and_child(tenant)
    await _mk_it_session(tenant, cid, owner_uid, "sat", 2, subject="فيزياء")

    resp = await client.get(f"/parent-portal/child/{sid}/schedule",
                            headers=_headers(parent_uid, "parent", tenant))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "السبت" in body["days"]
    assert body["days"][-1] == "السبت"  # weekend appended at the end
    sat = body["schedule"].get("السبت") or []
    assert len(sat) == 1 and sat[0]["subject"] == "فيزياء"


@pytest.mark.asyncio
async def test_it_child_schedule_cross_workspace_forbidden(client):
    tenant_x, owner_x = await _mk_it_workspace()
    _, sid_x, cid_x = await _mk_parent_and_child(tenant_x)
    await _mk_it_session(tenant_x, cid_x, owner_x, "sun", 1)

    tenant_y, _ = await _mk_it_workspace()
    parent_y, _, _ = await _mk_parent_and_child(tenant_y)

    resp = await client.get(f"/parent-portal/child/{sid_x}/schedule",
                            headers=_headers(parent_y, "parent", tenant_y))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_it_today_resolver_returns_timed_sessions():
    from routes.parent_portal_routes import _resolve_class_today_sessions

    tenant, owner_uid = await _mk_it_workspace()
    _, sid, cid = await _mk_parent_and_child(tenant)
    await _mk_it_session(tenant, cid, owner_uid, "sun", 2, subject="علوم")
    await _mk_it_session(tenant, cid, owner_uid, "sat", 1, subject="فيزياء")

    resolved = await _resolve_class_today_sessions(db.session, tenant, cid, "sunday")
    assert len(resolved) == 1
    entry = resolved[0]
    assert entry["period"] == 2
    assert entry["subject_name"] == "علوم"
    assert entry["teacher_name"] == "المعلم المستقل"
    assert entry["start_time"] and entry["end_time"]

    # Saturday resolves too (IT teachers schedule weekends).
    resolved_sat = await _resolve_class_today_sessions(db.session, tenant, cid, "saturday")
    assert len(resolved_sat) == 1
    assert resolved_sat[0]["subject_name"] == "فيزياء"
