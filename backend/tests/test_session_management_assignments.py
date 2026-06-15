"""Smart-scheduling session management + student assignments API tests.

Ported from a live-server `requests` script to the project's in-process
``AsyncClient`` harness (see ``tests/conftest.py``). Each test seeds its own
draft timetable + sessions in ``tenant_a`` and drives the real FastAPI app, so
the suite runs deterministically with no external server or pre-seeded data.

Covers:
- PUT    /api/smart-scheduling/session/{id}
- DELETE /api/smart-scheduling/session/{id}
- POST   /api/smart-scheduling/sessions/swap
- GET    /api/student-portal/assignments  (role gating)
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_insert, gd_find_one


async def _mk_timetable(school_id: str, status: str = "draft") -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": tid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": "Timetable A",
        "academic_year": "2026-2027",
        "semester": 1,
        "status": status,
        "version": 1,
        "total_sessions": 0,
    })
    return tid


async def _mk_session(school_id: str, timetable_id: str, *, day: str, period: int,
                      class_id: str = None, teacher_id: str = None) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "timetable_sessions", {
        "id": sid,
        "timetable_id": timetable_id,
        "school_id": school_id,
        "tenant_id": school_id,
        "class_id": class_id or str(uuid.uuid4()),
        "teacher_id": teacher_id,
        "day_of_week": day,
        "period_number": period,
    })
    return sid


async def _mk_teacher(school_id: str) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "school_id": school_id,
        "tenant_id": school_id,
        "full_name": f"معلم-{tid[:6]}",
        "is_active": True,
    })
    return tid


# ===================== PUT /smart-scheduling/session/{id} =====================

@pytest.mark.asyncio
async def test_update_session_change_teacher(client, school_principal_headers, tenant_a):
    tt = await _mk_timetable(tenant_a)
    class_id = str(uuid.uuid4())
    session_id = await _mk_session(tenant_a, tt, day="sunday", period=1, class_id=class_id)
    new_teacher = await _mk_teacher(tenant_a)
    await db.session.flush()

    resp = await client.put(
        f"/smart-scheduling/session/{session_id}",
        json={"teacher_id": new_teacher},
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True

    row = await gd_find_one(db.session, "timetable_sessions", {"id": session_id})
    assert row["teacher_id"] == new_teacher


@pytest.mark.asyncio
async def test_update_session_invalid_id(client, school_principal_headers, tenant_a):
    resp = await client.put(
        f"/smart-scheduling/session/{uuid.uuid4()}",
        json={"teacher_id": str(uuid.uuid4())},
        headers=school_principal_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_update_session_empty_body(client, school_principal_headers, tenant_a):
    tt = await _mk_timetable(tenant_a)
    session_id = await _mk_session(tenant_a, tt, day="monday", period=2)
    await db.session.flush()

    resp = await client.put(
        f"/smart-scheduling/session/{session_id}",
        json={},
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True


# =================== DELETE /smart-scheduling/session/{id} ===================

@pytest.mark.asyncio
async def test_delete_session(client, school_principal_headers, tenant_a):
    tt = await _mk_timetable(tenant_a)
    session_id = await _mk_session(tenant_a, tt, day="tuesday", period=3)
    await db.session.flush()

    resp = await client.delete(
        f"/smart-scheduling/session/{session_id}",
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert "message_ar" in data

    assert await gd_find_one(db.session, "timetable_sessions", {"id": session_id}) is None


@pytest.mark.asyncio
async def test_delete_session_invalid_id(client, school_principal_headers, tenant_a):
    resp = await client.delete(
        f"/smart-scheduling/session/{uuid.uuid4()}",
        headers=school_principal_headers,
    )
    assert resp.status_code == 404, resp.text


# ================== POST /smart-scheduling/sessions/swap ==================

@pytest.mark.asyncio
async def test_swap_sessions(client, school_principal_headers, tenant_a):
    tt = await _mk_timetable(tenant_a)
    # Two sessions for different classes/teachers in distinct slots so no
    # conflict is raised by the swap pre-checks.
    s1 = await _mk_session(tenant_a, tt, day="sunday", period=1,
                           class_id=str(uuid.uuid4()), teacher_id=str(uuid.uuid4()))
    s2 = await _mk_session(tenant_a, tt, day="monday", period=2,
                           class_id=str(uuid.uuid4()), teacher_id=str(uuid.uuid4()))
    await db.session.flush()

    resp = await client.post(
        "/smart-scheduling/sessions/swap",
        json={"session_id_1": s1, "session_id_2": s2},
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert "message_ar" in data

    r1 = await gd_find_one(db.session, "timetable_sessions", {"id": s1})
    r2 = await gd_find_one(db.session, "timetable_sessions", {"id": s2})
    assert r1["day_of_week"] == "monday" and r1["period_number"] == 2
    assert r2["day_of_week"] == "sunday" and r2["period_number"] == 1


@pytest.mark.asyncio
async def test_swap_sessions_invalid_ids(client, school_principal_headers, tenant_a):
    resp = await client.post(
        "/smart-scheduling/sessions/swap",
        json={"session_id_1": str(uuid.uuid4()), "session_id_2": str(uuid.uuid4())},
        headers=school_principal_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_swap_sessions_same_session(client, school_principal_headers, tenant_a):
    tt = await _mk_timetable(tenant_a)
    session_id = await _mk_session(tenant_a, tt, day="wednesday", period=4)
    await db.session.flush()

    resp = await client.post(
        "/smart-scheduling/sessions/swap",
        json={"session_id_1": session_id, "session_id_2": session_id},
        headers=school_principal_headers,
    )
    # Swapping a session with itself is a degenerate request: the engine may
    # no-op (200), reject it (400), or flag a self-overlap conflict (409). It
    # must not 404/500.
    assert resp.status_code in (200, 400, 409), resp.text


@pytest.mark.asyncio
async def test_published_timetable_session_is_immutable(client, school_principal_headers, tenant_a):
    tt = await _mk_timetable(tenant_a, status="published")
    session_id = await _mk_session(tenant_a, tt, day="thursday", period=5)
    await db.session.flush()

    resp = await client.delete(
        f"/smart-scheduling/session/{session_id}",
        headers=school_principal_headers,
    )
    assert resp.status_code == 400, resp.text


# ===================== GET /student-portal/assignments =====================

@pytest.mark.asyncio
async def test_student_token_rejected_while_student_login_disabled(client, student_headers, tenant_a):
    # Student login is currently disabled platform-wide
    # (``dependencies.STUDENT_LOGIN_DISABLED``), so a student bearer token is
    # rejected at the auth boundary regardless of the route. Assert that gate
    # holds rather than the (currently unreachable) student-success path.
    from dependencies import STUDENT_LOGIN_DISABLED
    assert STUDENT_LOGIN_DISABLED is True

    resp = await client.get("/student-portal/assignments", headers=student_headers)
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_assignments_requires_student_role(client, school_principal_headers, tenant_a):
    resp = await client.get("/student-portal/assignments", headers=school_principal_headers)
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_student_dashboard_requires_student_role(client, school_principal_headers, tenant_a):
    resp = await client.get("/student-portal/dashboard", headers=school_principal_headers)
    assert resp.status_code in (401, 403), resp.text


# ===================== Endpoint existence (no 405) =====================

@pytest.mark.asyncio
async def test_session_endpoints_exist(client, school_principal_headers, tenant_a):
    fake = str(uuid.uuid4())
    put = await client.put(
        f"/smart-scheduling/session/{fake}", json={}, headers=school_principal_headers
    )
    assert put.status_code != 405
    delete = await client.delete(
        f"/smart-scheduling/session/{fake}", headers=school_principal_headers
    )
    assert delete.status_code != 405
    swap = await client.post(
        "/smart-scheduling/sessions/swap",
        json={"session_id_1": fake, "session_id_2": fake},
        headers=school_principal_headers,
    )
    assert swap.status_code != 405
    assignments = await client.get(
        "/student-portal/assignments", headers=school_principal_headers
    )
    assert assignments.status_code != 405
