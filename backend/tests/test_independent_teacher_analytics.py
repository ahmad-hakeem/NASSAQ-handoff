"""IT Phase 2 §6.x — Workspace analytics dashboard (Task #273).

Coverage:
  (a) non-IT role on the endpoint → 403
  (b) workspace-pinned: rows belonging to a sibling IT workspace are
      invisible (no cross-workspace bleed)
  (c) class_id filter narrows the attendance series; cross-workspace
      class_id → 404 (spec §8 inv. 3)
  (d) date-range filter excludes rows outside [from, to)
  (e) empty workspace returns the zero-state envelope (every collection
      is an empty list, never null)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _headers(uid: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({"sub": uid, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_it_workspace() -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-WS-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher_workspace",
    })
    user["tenant_id"] = wsid
    return user


async def _mk_class(wsid: str, name: str = "C1") -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": wsid,
        "name": name,
        "grade_level": "1",
    })
    return cid


async def _mk_student(wsid: str, full_name: str = "طالب") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": wsid,
        "full_name": full_name,
        "gender": "male",
    })
    return sid


async def _mk_attendance(wsid: str, sid: str, cid: str, day: datetime, status: str) -> None:
    await gd_insert(db.session, "attendance", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "class_id": cid,
        "student_id": sid,
        "date": day,
        "status": status,
        "is_excused": status == "excused",
    })


async def _mk_behaviour(
    wsid: str, sid: str, cid: str, when: datetime,
    btype: str = "negative", category: str = "talking",
) -> None:
    await gd_insert(db.session, "behaviour_records", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "student_id": sid,
        "class_id": cid,
        "type": btype,
        "category": category,
        "created_at": when,
    })


async def _mk_lesson_plan(wsid: str, uid: str, when: datetime) -> None:
    await gd_insert(db.session, "lesson_plans", {
        "id": str(uuid.uuid4()),
        "workspace_school_id": wsid,
        "created_by": uid,
        "topic": "t",
        "language": "ar",
        "plan": {"title": "t"},
        "is_saved": False,
        "created_at": when,
        "updated_at": when,
    })


# ----------------------------------------------------------------------
# (a) Non-IT role → 403
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analytics_non_it_role_is_forbidden(client):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": "S", "code": "S1", "status": "active",
        "country": "SA", "language": "ar",
    })
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": sid, "email": f"p-{uid}@t.test",
        "full_name": "P", "is_active": True, "password_hash": "x",
    })
    h = _headers(uid, UserRole.SCHOOL_PRINCIPAL.value, sid)
    r = await client.get("/independent-teacher/analytics", headers=h)
    assert r.status_code == 403, r.text


# ----------------------------------------------------------------------
# (b) Workspace pinning: sibling workspace's rows are invisible
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analytics_does_not_leak_sibling_workspace(client):
    a = await _mk_it_workspace()
    b = await _mk_it_workspace()
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    cid_b = await _mk_class(b["tenant_id"])
    s_b = await _mk_student(b["tenant_id"])
    # Plant rows ONLY in workspace B.
    await _mk_attendance(b["tenant_id"], s_b, cid_b, yesterday, "absent")
    await _mk_behaviour(b["tenant_id"], s_b, cid_b, yesterday)
    await _mk_lesson_plan(b["tenant_id"], b["id"], yesterday)

    h = _headers(a["id"], a["role"], a["tenant_id"])
    r = await client.get("/independent-teacher/analytics", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attendance"] == []
    assert body["behavior"] == []
    assert body["lesson_plans"] == []
    assert body["top_students_absence"] == []
    assert body["top_students_behavior"] == []
    assert body["top_classes_attendance"] == []


# ----------------------------------------------------------------------
# (c) class_id filter + cross-workspace 404
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analytics_class_filter_and_cross_workspace_404(client):
    a = await _mk_it_workspace()
    b = await _mk_it_workspace()
    c1 = await _mk_class(a["tenant_id"], "C1")
    c2 = await _mk_class(a["tenant_id"], "C2")
    cb = await _mk_class(b["tenant_id"], "Cb")
    s1 = await _mk_student(a["tenant_id"], "Alpha")
    s2 = await _mk_student(a["tenant_id"], "Beta")
    now = datetime.now(timezone.utc)
    # Each student needs ≥ 3 attendance rows (the min-sample guard)
    # before the absence-rate top can rank them. Plant 3 absent rows
    # for s1 in c1 and 3 absent rows for s2 in c2 across distinct days.
    for i in range(1, 4):
        await _mk_attendance(a["tenant_id"], s1, c1, now - timedelta(days=i), "absent")
        await _mk_attendance(a["tenant_id"], s2, c2, now - timedelta(days=i), "absent")

    h = _headers(a["id"], a["role"], a["tenant_id"])

    # Unfiltered: both classes' rows show up
    r = await client.get("/independent-teacher/analytics", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert sum(d["absent"] for d in body["attendance"]) == 6
    assert len(body["top_students_absence"]) == 2
    # absence_rate must be present and == 1.0 (3/3) for both students
    for row in body["top_students_absence"]:
        assert row["absent_count"] == 3
        assert row["total_count"] == 3
        assert row["absence_rate"] == 1.0

    # class_id filter restricts to one class
    r = await client.get(
        "/independent-teacher/analytics",
        headers=h, params={"class_id": c1},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert sum(d["absent"] for d in body["attendance"]) == 3
    names = {row["name"] for row in body["top_students_absence"]}
    assert names == {"Alpha"}

    # Cross-workspace class_id → 404 (spec §8 inv. 3)
    r = await client.get(
        "/independent-teacher/analytics",
        headers=h, params={"class_id": cb},
    )
    assert r.status_code == 404, r.text


# ----------------------------------------------------------------------
# (d) Date-range filter excludes rows outside [from, to)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analytics_date_range_excludes_outside_rows(client):
    a = await _mk_it_workspace()
    cid = await _mk_class(a["tenant_id"])
    s = await _mk_student(a["tenant_id"])
    now = datetime.now(timezone.utc)
    inside = now - timedelta(days=2)
    outside = now - timedelta(days=120)
    await _mk_attendance(a["tenant_id"], s, cid, inside, "absent")
    await _mk_attendance(a["tenant_id"], s, cid, outside, "absent")

    h = _headers(a["id"], a["role"], a["tenant_id"])
    r = await client.get(
        "/independent-teacher/analytics",
        headers=h,
        params={
            "from": (now - timedelta(days=7)).isoformat(),
            "to": now.isoformat(),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert sum(d["absent"] for d in body["attendance"]) == 1


# ----------------------------------------------------------------------
# (e) Empty workspace → zero-state envelope
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analytics_empty_workspace_returns_zero_state(client):
    a = await _mk_it_workspace()
    h = _headers(a["id"], a["role"], a["tenant_id"])
    r = await client.get("/independent-teacher/analytics", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    for k in (
        "attendance", "behavior", "lesson_plans",
        "top_students_absence", "top_students_behavior",
        "top_classes_attendance",
    ):
        assert body[k] == [], f"{k} must be empty list, got {body[k]!r}"
    assert "range" in body and "from" in body["range"] and "to" in body["range"]


# ----------------------------------------------------------------------
# (g) Task #283 — CSV / PDF exports mirror the workspace pinning + 404
#     invariants of the JSON endpoint and stream a usable file.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analytics_export_csv_and_pdf(client):
    a = await _mk_it_workspace()
    cid = await _mk_class(a["tenant_id"], "C1")
    s = await _mk_student(a["tenant_id"], "Alpha")
    now = datetime.now(timezone.utc)
    for i in range(1, 4):
        await _mk_attendance(a["tenant_id"], s, cid, now - timedelta(days=i), "absent")

    h = _headers(a["id"], a["role"], a["tenant_id"])

    # CSV
    r = await client.get("/independent-teacher/analytics/export.csv", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    cd_csv = r.headers["content-disposition"]
    assert "attachment" in cd_csv
    assert ".csv" in cd_csv
    # Filename must carry the Hijri stamp suffix so a teacher can sort
    # exported snapshots chronologically against the calendar they use.
    assert "H.csv" in cd_csv, cd_csv
    body = r.content.decode("utf-8-sig")
    assert "NASSAQ Workspace Analytics" in body
    assert "attendance" in body
    assert "Alpha" in body  # top_students_absence row

    # PDF
    r = await client.get("/independent-teacher/analytics/export.pdf", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    cd_pdf = r.headers["content-disposition"]
    assert ".pdf" in cd_pdf
    assert "H.pdf" in cd_pdf, cd_pdf
    # The chart-builder helpers must return a Drawing for non-empty
    # series so the PDF carries the visual snapshot the spec asks for
    # (not just a tabular dump).
    from routes.independent_teacher_analytics_routes import (
        _aggregate_all, _build_attendance_chart,
        _build_behavior_chart, _build_lesson_plan_chart,
        _workspace_id as _ws_id_helper,
    )
    payload = await _aggregate_all(
        a["tenant_id"],
        now - timedelta(days=30), now, None,
    )
    assert _build_attendance_chart(payload["attendance"]) is not None
    # behavior + lesson_plan helpers return None when the series is
    # empty (planted only attendance rows), exercising the empty-state
    # branch — that's the contract the PDF body relies on.
    assert _build_behavior_chart([]) is None
    assert _build_lesson_plan_chart([]) is None
    assert _ws_id_helper({"id": "u1", "role": "independent_teacher"}) == "itw_u1"


@pytest.mark.asyncio
async def test_analytics_export_cross_workspace_class_id_404(client):
    a = await _mk_it_workspace()
    b = await _mk_it_workspace()
    cb = await _mk_class(b["tenant_id"], "Cb")
    h = _headers(a["id"], a["role"], a["tenant_id"])
    for path in (
        "/independent-teacher/analytics/export.csv",
        "/independent-teacher/analytics/export.pdf",
    ):
        r = await client.get(path, headers=h, params={"class_id": cb})
        assert r.status_code == 404, (path, r.text)


@pytest.mark.asyncio
async def test_analytics_export_non_it_role_is_forbidden(client):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": "S", "code": f"S{sid[:6]}", "status": "active",
        "country": "SA", "language": "ar",
    })
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": sid, "email": f"p-{uid}@t.test",
        "full_name": "P", "is_active": True, "password_hash": "x",
    })
    h = _headers(uid, UserRole.SCHOOL_PRINCIPAL.value, sid)
    for path in (
        "/independent-teacher/analytics/export.csv",
        "/independent-teacher/analytics/export.pdf",
    ):
        r = await client.get(path, headers=h)
        assert r.status_code == 403, (path, r.text)


# ----------------------------------------------------------------------
# (f) Behavior series buckets positive vs negative; lesson plans
#     return both `generated` and `saved` per day.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analytics_behavior_split_and_lesson_plans_saves(client):
    a = await _mk_it_workspace()
    cid = await _mk_class(a["tenant_id"])
    s = await _mk_student(a["tenant_id"])
    now = datetime.now(timezone.utc)
    inside = now - timedelta(days=2)
    # 2 positive + 1 negative this week
    await _mk_behaviour(a["tenant_id"], s, cid, inside, btype="positive")
    await _mk_behaviour(a["tenant_id"], s, cid, inside, btype="positive")
    await _mk_behaviour(a["tenant_id"], s, cid, inside, btype="negative")
    # 2 lesson plans generated; 1 of them is_saved=True
    pid_saved = str(uuid.uuid4())
    await gd_insert(db.session, "lesson_plans", {
        "id": pid_saved, "workspace_school_id": a["tenant_id"],
        "created_by": a["id"], "topic": "t", "language": "ar",
        "plan": {"title": "t"}, "is_saved": True,
        "created_at": inside, "updated_at": inside,
    })
    await _mk_lesson_plan(a["tenant_id"], a["id"], inside)

    h = _headers(a["id"], a["role"], a["tenant_id"])
    r = await client.get("/independent-teacher/analytics", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()

    # Behavior: a single weekly bucket with both columns split
    assert len(body["behavior"]) == 1
    bweek = body["behavior"][0]
    assert bweek["positive"] == 2
    assert bweek["negative"] == 1

    # Lesson plans: a single daily point with generated & saved counts
    assert len(body["lesson_plans"]) == 1
    lp = body["lesson_plans"][0]
    assert lp["generated"] == 2
    assert lp["saved"] == 1


# ----------------------------------------------------------------------
# (g) Render back-pressure must reach the caller.
#
#     The PDF/XLSX handlers wrap their render in a broad `except Exception
#     -> 500`. CpuOffloadBusy/CpuOffloadTimeout are plain Exceptions, so
#     without an explicit re-raise that catch swallows them and the client
#     gets an opaque 500 with no retry signal instead of the central
#     503 RENDER_BUSY / 504 RENDER_TIMEOUT envelope.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/independent-teacher/analytics/export.pdf",
    "/independent-teacher/analytics/export.xlsx",
])
@pytest.mark.parametrize("exc_name,status,code", [
    ("CpuOffloadBusy", 503, "RENDER_BUSY"),
    ("CpuOffloadTimeout", 504, "RENDER_TIMEOUT"),
])
async def test_analytics_export_surfaces_render_backpressure(
    client, monkeypatch, path, exc_name, status, code,
):
    import services.cpu_offload as cpu_offload
    from routes import independent_teacher_analytics_routes as mod

    exc_cls = getattr(cpu_offload, exc_name)

    async def _boom(*_a, **_kw):
        raise exc_cls()

    monkeypatch.setattr(mod, "run_cpu_bound", _boom)

    a = await _mk_it_workspace()
    h = _headers(a["id"], a["role"], a["tenant_id"])
    r = await client.get(path, headers=h)

    assert r.status_code == status, (path, exc_name, r.status_code, r.text)
    body = r.json()
    assert body["success"] is False, body
    assert body["error"]["code"] == code, body
    # Arabic message for the user, English for the operator.
    assert body["error"]["message"], body
    assert body["error"]["message_en"], body
    if status == 503:
        assert r.headers.get("Retry-After") == "30", dict(r.headers)
