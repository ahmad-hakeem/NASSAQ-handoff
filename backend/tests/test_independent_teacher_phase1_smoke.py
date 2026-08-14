"""Phase 1 reuse smoke pass for the Independent-Teacher account.

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §5.5 + §7
Ticket: Task #194.

Each test exercises a real backend route via the FastAPI test client
with an IT-issued JWT and a fully bootstrapped synthetic workspace.
All 11 rows are required to pass.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.core.guards.tenant_guard import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one, gd_find

from tests._it_fixtures import seed_active_passkey, now_ts as _now_ts


def _it_headers_mfa(user: dict) -> dict:
    """Headers minted with a recent webauthn MFA assertion. Used by the
    §5.7 step-up-protected smoke rows added in Task #201; the caller
    must also have a real passkey factor seeded via
    `seed_active_passkey(user['id'])`."""
    token = create_access_token(
        {
            "sub": user["id"],
            "role": user["role"],
            "tenant_id": independent_workspace_id(user),
        },
        mfa_recent_at=_now_ts(),
        mfa_kind="webauthn",
    )
    return {"Authorization": f"Bearer {token}"}


def _it_headers(user: dict) -> dict:
    token = create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": independent_workspace_id(user),
    })
    return {"Authorization": f"Bearer {token}"}


async def _bootstrap_it_workspace() -> dict:
    uid = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "teacher_id": teacher_id,
        "email": f"smoke-it-{uid}@t.test",
        "full_name": f"IT-Smoke-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    wsid = independent_workspace_id(user)
    # Post-bootstrap state: the schools row exists FIRST (FK) and the user is
    # tenant-bound to the workspace — routes that resolve the tenant from the
    # DB row (e.g. session start) fail closed when tenant_id is NULL.
    user["tenant_id"] = wsid

    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher_workspace",
    })
    await gd_insert(db.session, "users", user)

    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": wsid,
        "user_id": uid,
        "full_name": user["full_name"],
        "email": user["email"],
        "is_active": True,
    })

    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id,
        "name": "فصل أ",
        "school_id": wsid,
        "tenant_id": wsid,
        "capacity": 10,
        "current_students": 1,
        "is_active": True,
    })

    student_id = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": student_id,
        "school_id": wsid,
        "tenant_id": wsid,
        "class_id": class_id,
        "full_name": "طالب التجربة",
        "is_active": True,
    })

    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "name": "Math",
        "name_ar": "رياضيات",
        "school_id": wsid,
        "is_active": True,
    })

    # Active teacher→class assignment: attendance write/read routes gate
    # teacher/IT callers via can_view_class(), which requires a
    # teacher_assignments (or class_sessions) link — same-tenant membership
    # alone is not sufficient.
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "teacher_id": teacher_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "is_active": True,
    })

    assessment_id = str(uuid.uuid4())
    await gd_insert(db.session, "assessments", {
        "id": assessment_id,
        "school_id": wsid,
        "tenant_id": wsid,
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "name": "اختبار قصير",
        "type": "quiz",
        "max_score": 10,
        "weight": 1.0,
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "user": user,
        "uid": uid,
        "wsid": wsid,
        "teacher_id": teacher_id,
        "class_id": class_id,
        "student_id": student_id,
        "subject_id": subject_id,
        "assessment_id": assessment_id,
        "headers": _it_headers(user),
    }


# Row 1 — Attendance recording (§7 row 11).
@pytest.mark.asyncio
async def test_smoke_row01_attendance_recording(client):
    ctx = await _bootstrap_it_workspace()
    payload = {
        "student_id": ctx["student_id"],
        "class_id": ctx["class_id"],
        "status": "present",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    resp = await client.post("/attendance", headers=ctx["headers"], json=payload)
    assert resp.status_code in (200, 201), resp.text


# Row 2 — Attendance reports / cross-tenant scoping (§7 row 12).
@pytest.mark.asyncio
async def test_smoke_row02_attendance_class_listing_is_workspace_scoped(client):
    ctx = await _bootstrap_it_workspace()
    rec_id = str(uuid.uuid4())
    await gd_insert(db.session, "attendance", {
        "id": rec_id,
        "school_id": ctx["wsid"],
        "tenant_id": ctx["wsid"],
        "class_id": ctx["class_id"],
        "student_id": ctx["student_id"],
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "present",
        "recorded_by": ctx["user"]["id"],
    })
    resp = await client.get(
        f"/attendance/class/{ctx['class_id']}", headers=ctx["headers"],
    )
    assert resp.status_code == 200, resp.text
    items = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
    assert any(it.get("id") == rec_id for it in items), items


# Row 3 — Assessments — create (§7 row 13).
@pytest.mark.asyncio
async def test_smoke_row03_assessments_create(client):
    ctx = await _bootstrap_it_workspace()
    payload = {
        "class_id": ctx["class_id"],
        "subject_id": ctx["subject_id"],
        "title": "اختبار جديد",
        "assessment_type": "quiz",
        "max_score": 20,
        "weight": 1.0,
        "date": datetime.now(timezone.utc).isoformat(),
        "is_published": False,
    }
    resp = await client.post("/assessments", headers=ctx["headers"], json=payload)
    assert resp.status_code in (200, 201), resp.text
    rows = await gd_find(db.session, "assessments", {"class_id": ctx["class_id"]}, limit=10)
    assert len(rows) >= 2, rows


# Row 4 — Assessments — edit. THE Task #194 grant regression — MUST pass.
@pytest.mark.asyncio
async def test_smoke_row04_assessments_edit(client):
    ctx = await _bootstrap_it_workspace()
    payload = {"description": "وصف محدث للتقييم", "max_score": 75.0}
    resp = await client.put(
        f"/assessments/{ctx['assessment_id']}",
        headers=ctx["headers"], json=payload,
    )
    assert resp.status_code == 200, resp.text
    row = await gd_find_one(db.session, "assessments", {"id": ctx["assessment_id"]})
    assert row.get("description") == "وصف محدث للتقييم", row
    assert float(row.get("max_score")) == 75.0, row


# Row 5 — Assessments — grade.
@pytest.mark.asyncio
async def test_smoke_row05_assessments_grade(client):
    ctx = await _bootstrap_it_workspace()
    payload = {
        "assessment_id": ctx["assessment_id"],
        "grades": [{"student_id": ctx["student_id"], "score": 8, "notes": "ممتاز"}],
    }
    resp = await client.post("/grades/bulk", headers=ctx["headers"], json=payload)
    assert resp.status_code in (200, 201), resp.text


# Row 6 — Behaviour records (§7 row 14).
@pytest.mark.asyncio
async def test_smoke_row06_behaviour_record(client):
    ctx = await _bootstrap_it_workspace()
    bt_id = str(uuid.uuid4())
    await gd_insert(db.session, "behaviour_types", {
        "id": bt_id, "tenant_id": ctx["wsid"], "name_ar": "إيجابي",
        "name_en": "Positive", "category": "positive",
        "default_severity": "minor", "default_points": 1,
    })
    payload = {
        "student_id": ctx["student_id"], "class_id": ctx["class_id"],
        "behaviour_type_id": bt_id, "title": "مشاركة ممتازة",
        "description": "شارك بفعالية",
        "incident_date": datetime.now(timezone.utc).isoformat(),
    }
    resp = await client.post(
        f"/behaviour-records?school_id={ctx['wsid']}",
        headers=ctx["headers"], json=payload,
    )
    assert resp.status_code in (200, 201), resp.text


# Row 1b — Bulk attendance for IT (regression for reviewer's blocking
# finding: `POST /attendance/bulk` allowed IT but used `tenant_id`
# directly without the IT workspace fallback, so the engine's
# `Class.school_id == tenant_id` check rejected the request).
@pytest.mark.asyncio
async def test_smoke_row01b_bulk_attendance_for_it(client):
    ctx = await _bootstrap_it_workspace()
    payload = {
        "class_id": ctx["class_id"],
        "subject_id": ctx["subject_id"],
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "records": [{"student_id": ctx["student_id"], "status": "present"}],
    }
    resp = await client.post("/attendance/bulk", headers=ctx["headers"], json=payload)
    assert resp.status_code in (200, 201), resp.text

    rows = await gd_find(
        db.session, "attendance",
        {"class_id": ctx["class_id"], "student_id": ctx["student_id"]},
        limit=10,
    )
    assert any(r.get("school_id") == ctx["wsid"] for r in rows), rows


# Row 7 — Portfolio (§7 row 15) — read + add CV item + verify save.
@pytest.mark.asyncio
async def test_smoke_row07_portfolio_add_cv_item(client):
    ctx = await _bootstrap_it_workspace()
    resp = await client.get("/teacher/portfolio", headers=ctx["headers"])
    assert resp.status_code == 200, resp.text

    add = await client.post(
        "/teacher/portfolio/cv-item",
        headers=ctx["headers"],
        json={"kind": "training_attended", "title": "ورشة تطوير مهني",
              "organization": "نَسَّق", "hours": 4,
              "description": "ورشة قصيرة عن تقييم الطلاب."},
    )
    assert add.status_code == 200, add.text
    body = add.json()
    assert body.get("success") is True, body
    item_id = body.get("item", {}).get("id")
    assert item_id, body

    saved = await gd_find_one(
        db.session, "teacher_portfolio_meta", {"teacher_id": ctx["uid"]},
    )
    assert saved is not None, "teacher_portfolio_meta row missing"
    items = saved.get("cv_items") or []
    assert any(it.get("id") == item_id for it in items), items


# Row 8 — AI Insights (§7 row 16). PASS = 200/503 envelope.
@pytest.mark.asyncio
async def test_smoke_row08_ai_insights_overview(client):
    ctx = await _bootstrap_it_workspace()
    resp = await client.get("/ai/insights/overview", headers=ctx["headers"])
    assert resp.status_code in (200, 503), (
        f"ai overview returned {resp.status_code}: {resp.text}"
    )


# Row 9 — Session start / teach lifecycle (§7 row 18).
@pytest.mark.asyncio
async def test_smoke_row09_session_start_and_current(client):
    ctx = await _bootstrap_it_workspace()
    # GET /classes — IT workspace classes are reachable.
    classes = await client.get("/classes", headers=ctx["headers"])
    assert classes.status_code == 200, classes.text
    items = classes.json() if isinstance(classes.json(), list) else classes.json().get("items", [])
    assert any(c.get("id") == ctx["class_id"] for c in items), items

    # Seed a schedule_session for the IT teacher and start a class session.
    sched_id = str(uuid.uuid4())
    schedule_id = str(uuid.uuid4())
    await gd_insert(db.session, "schedule_sessions", {
        "id": sched_id,
        "school_id": ctx["wsid"],
        "schedule_id": schedule_id,
        "teacher_id": ctx["teacher_id"],
        "class_id": ctx["class_id"],
        "subject_id": ctx["subject_id"],
        "day_of_week": "sunday",
        "start_time": "08:00",
        "end_time": "08:45",
        "status": "scheduled",
    })

    start = await client.post(
        "/session/start",
        headers=ctx["headers"],
        json={
            "schedule_session_id": sched_id,
            "teacher_id": ctx["teacher_id"],
            "class_id": ctx["class_id"],
            "subject_id": ctx["subject_id"],
        },
    )
    assert start.status_code == 200, start.text
    session_record_id = start.json().get("session_record_id")
    assert session_record_id, start.json()

    # GET /session/current — the just-started session is the active one.
    current = await client.get(
        f"/session/current?schedule_session_id={sched_id}",
        headers=ctx["headers"],
    )
    assert current.status_code == 200, current.text
    assert current.json().get("session_id") == session_record_id, current.json()


# Row 10 — Notifications — receive (§7 row 19).
@pytest.mark.asyncio
async def test_smoke_row10_notifications_receive(client):
    ctx = await _bootstrap_it_workspace()
    notif_id = str(uuid.uuid4())
    await gd_insert(db.session, "notifications", {
        "id": notif_id, "user_id": ctx["user"]["id"], "tenant_id": ctx["wsid"],
        "type": "system", "title": "اختبار", "message": "رسالة اختبار",
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    resp = await client.get("/notifications", headers=ctx["headers"])
    assert resp.status_code == 200, resp.text
    items = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
    assert any(n.get("id") == notif_id for n in items), items


# Row 11 — Personal-scope reports / exports (§7 row 25) — XLSX export.
@pytest.mark.asyncio
async def test_smoke_row11_personal_scope_attendance_export_xlsx(client):
    ctx = await _bootstrap_it_workspace()
    # Teachers/ITs must scope attendance reports to an assigned class —
    # school-wide reports (no class_id) are admin-only.
    resp = await client.get(
        f"/reports/school/attendance?class_id={ctx['class_id']}",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200, resp.text

    # `/export/report/...` is protected by the §5.7 IT MFA step-up
    # gate (Task #201). Mint a passkey-backed header for the export
    # call; the un-stepped header still drives `/reports/...` above so
    # the no-MFA path remains exercised.
    await seed_active_passkey(ctx["user"]["id"])
    # School-wide exports (school_*) are admin-only (Task #423); teachers/ITs
    # export class-scoped data via the class_report path with an assigned
    # class_id — that IS the §7 row 25 "personal scope".
    xlsx = await client.get(
        f"/export/report/class_report?format=xlsx&class_id={ctx['class_id']}",
        headers=_it_headers_mfa(ctx["user"]),
    )
    assert xlsx.status_code == 200, xlsx.text
    assert xlsx.headers.get("content-type", "").startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ), xlsx.headers
    assert xlsx.content[:2] == b"PK", xlsx.content[:8]
