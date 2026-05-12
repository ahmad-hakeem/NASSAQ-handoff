"""Tests for IT manual schedule editor (Task #193 — spec §5.4)."""
from __future__ import annotations

import uuid

import pytest

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
)
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert


GRID_PATH = "/independent-teacher/schedule/grid"
SLOT_PATH = "/independent-teacher/schedule/slot"


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_independent_teacher_with_workspace() -> dict:
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
        "name": f"IT-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
        "tenant_type": "independent_teacher",
    })
    await gd_insert(db.session, "school_settings", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "working_days": ["sun", "mon", "tue", "wed", "thu"],
        "periods_per_day": 7,
        "period_duration": 45,
        "language": "ar",
    })
    teacher_id = str(uuid.uuid4())
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
        "school_id": wsid,
        "name": "فصل أ",
        "is_active": True,
    })
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "school_id": wsid,
        "name": "الرياضيات",
        "is_active": True,
    })
    return {
        "user": user,
        "wsid": wsid,
        "teacher_id": teacher_id,
        "class_id": class_id,
        "subject_id": subject_id,
    }


async def _delete(client, url, **kwargs):
    return await client.request("DELETE", url, **kwargs)


@pytest.mark.asyncio
async def test_get_grid_returns_workspace_scoped_payload(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    resp = await client.get(GRID_PATH, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["workspace_id"] == ctx["wsid"]
    assert body["teacher_id"] == ctx["teacher_id"]
    assert body["periods_per_day"] == 7
    assert "sun" in body["working_days"]
    assert body["slots"] == []
    assert body["sessions"] == []
    assert any(c["id"] == ctx["class_id"] for c in body["classes"])
    assert any(s["id"] == ctx["subject_id"] for s in body["subjects"])


@pytest.mark.asyncio
async def test_put_with_foreign_workspace_class_returns_404(client):
    """Cross-tenant impossibility: a class_id from another workspace
    must never resolve, even if the caller is otherwise authenticated."""
    a = await _mk_independent_teacher_with_workspace()
    b = await _mk_independent_teacher_with_workspace()
    h_a = _headers(a["user"]["id"], a["user"]["role"], a["wsid"])
    resp = await client.put(SLOT_PATH, headers=h_a, json={
        "day_of_week": "sun", "slot_number": 1, "expected_version": 0,
        "class_id": b["class_id"], "subject_id": a["subject_id"],
    })
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_client_supplied_teacher_id_is_ignored(client):
    """The request body has no `teacher_id` field; any client-supplied
    value must be silently dropped by Pydantic and the server must
    resolve the teacher from the bearer (`users.id → teachers.user_id`)."""
    a = await _mk_independent_teacher_with_workspace()
    b = await _mk_independent_teacher_with_workspace()
    h_a = _headers(a["user"]["id"], a["user"]["role"], a["wsid"])
    resp = await client.put(SLOT_PATH, headers=h_a, json={
        "day_of_week": "sun", "slot_number": 1, "expected_version": 0,
        "class_id": a["class_id"], "subject_id": a["subject_id"],
        "teacher_id": b["teacher_id"],  # forged — must be ignored
    })
    assert resp.status_code == 200, resp.text
    row = await gd_find_one(
        db.session, "schedule_sessions", {"id": resp.json()["id"]},
    )
    assert row["teacher_id"] == a["teacher_id"]
    assert row["school_id"] == a["wsid"]


@pytest.mark.asyncio
async def test_export_pdf_returns_pdf_bytes(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    await client.put(SLOT_PATH, headers=h, json={
        "day_of_week": "sun", "slot_number": 1, "expected_version": 0,
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
    })
    resp = await client.get(
        "/independent-teacher/schedule/export.pdf", headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_put_inserts_new_slot_with_version_one(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    payload = {
        "day_of_week": "sun",
        "slot_number": 1,
        "expected_version": 0,
        "class_id": ctx["class_id"],
        "subject_id": ctx["subject_id"],
    }
    resp = await client.put(SLOT_PATH, headers=h, json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == 1
    assert body["class_id"] == ctx["class_id"]
    assert body["subject_id"] == ctx["subject_id"]
    assert body["day_of_week"] == "sun"
    assert body["slot_number"] == 1

    row = await gd_find_one(db.session, "schedule_sessions", {"id": body["id"]})
    assert row["school_id"] == ctx["wsid"]
    assert row["teacher_id"] == ctx["teacher_id"]
    assert int(row["version"]) == 1


@pytest.mark.asyncio
async def test_put_same_content_with_correct_version_bumps_no_audit(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    base = {
        "day_of_week": "mon",
        "slot_number": 2,
        "class_id": ctx["class_id"],
        "subject_id": ctx["subject_id"],
    }
    r1 = await client.put(SLOT_PATH, headers=h, json={**base, "expected_version": 0})
    assert r1.status_code == 200
    assert r1.json()["version"] == 1

    r2 = await client.put(SLOT_PATH, headers=h, json={**base, "expected_version": 1})
    assert r2.status_code == 200, r2.text
    assert r2.json()["version"] == 2

    overwrites = await gd_find(
        db.session, "audit_logs",
        {"action": "INDEPENDENT_TEACHER_SCHEDULE_OVERWRITE", "school_id": ctx["wsid"]},
        limit=10,
    )
    assert overwrites == []


@pytest.mark.asyncio
async def test_put_overwrite_with_different_content_emits_audit(client):
    ctx = await _mk_independent_teacher_with_workspace()
    other_class = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": other_class, "school_id": ctx["wsid"],
        "name": "فصل ب", "is_active": True,
    })

    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    r1 = await client.put(SLOT_PATH, headers=h, json={
        "day_of_week": "tue", "slot_number": 3, "expected_version": 0,
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
    })
    assert r1.status_code == 200

    r2 = await client.put(SLOT_PATH, headers=h, json={
        "day_of_week": "tue", "slot_number": 3, "expected_version": 1,
        "class_id": other_class, "subject_id": ctx["subject_id"],
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["class_id"] == other_class
    assert r2.json()["version"] == 2

    overwrites = await gd_find(
        db.session, "audit_logs",
        {"action": "INDEPENDENT_TEACHER_SCHEDULE_OVERWRITE", "school_id": ctx["wsid"]},
        limit=10,
    )
    assert len(overwrites) == 1
    details = overwrites[0].get("details") or {}
    assert details.get("old", {}).get("class_id") == ctx["class_id"]
    assert details.get("new", {}).get("class_id") == other_class


@pytest.mark.asyncio
async def test_put_wrong_expected_version_returns_409_with_current_row(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    r1 = await client.put(SLOT_PATH, headers=h, json={
        "day_of_week": "wed", "slot_number": 4, "expected_version": 0,
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
    })
    assert r1.status_code == 200

    r2 = await client.put(SLOT_PATH, headers=h, json={
        "day_of_week": "wed", "slot_number": 4, "expected_version": 99,
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
    })
    assert r2.status_code == 409, r2.text
    body = r2.json()
    detail = (body.get("error") or {}).get("message") or body.get("detail")
    if isinstance(detail, dict):
        assert detail.get("code") == "schedule_slot_conflict"
        assert "تم تعديل" in detail.get("message", "")
        assert detail.get("current_row", {}).get("version") == 1
    else:
        # tenant_isolation/error wrapping may flatten the dict to its message
        assert "تم تعديل" in str(detail)


@pytest.mark.asyncio
async def test_put_expected_version_zero_on_existing_row_returns_409(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    await client.put(SLOT_PATH, headers=h, json={
        "day_of_week": "thu", "slot_number": 5, "expected_version": 0,
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
    })

    r2 = await client.put(SLOT_PATH, headers=h, json={
        "day_of_week": "thu", "slot_number": 5, "expected_version": 0,
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
    })
    assert r2.status_code == 409, r2.text


@pytest.mark.asyncio
async def test_delete_clears_slot_with_correct_version(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    r1 = await client.put(SLOT_PATH, headers=h, json={
        "day_of_week": "sun", "slot_number": 6, "expected_version": 0,
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
    })
    sid = r1.json()["id"]

    r2 = await _delete(
        client, SLOT_PATH, headers=h,
        json={"day_of_week": "sun", "slot_number": 6, "expected_version": 1},
    )
    assert r2.status_code == 200, r2.text
    row = await gd_find_one(db.session, "schedule_sessions", {"id": sid})
    assert row is None


@pytest.mark.asyncio
async def test_cross_workspace_isolation_and_non_it_role_denied(client):
    a = await _mk_independent_teacher_with_workspace()
    b = await _mk_independent_teacher_with_workspace()

    # Seed a slot in workspace A.
    h_a = _headers(a["user"]["id"], a["user"]["role"], a["wsid"])
    await client.put(SLOT_PATH, headers=h_a, json={
        "day_of_week": "sun", "slot_number": 1, "expected_version": 0,
        "class_id": a["class_id"], "subject_id": a["subject_id"],
    })

    # IT-B's grid never sees A's session.
    h_b = _headers(b["user"]["id"], b["user"]["role"], b["wsid"])
    grid_b = await client.get(GRID_PATH, headers=h_b)
    assert grid_b.status_code == 200
    assert grid_b.json()["sessions"] == []

    # IT-B writing slot 1 lands on B's workspace, not A's.
    rb = await client.put(SLOT_PATH, headers=h_b, json={
        "day_of_week": "sun", "slot_number": 1, "expected_version": 0,
        "class_id": b["class_id"], "subject_id": b["subject_id"],
    })
    assert rb.status_code == 200
    a_sessions = await gd_find(
        db.session, "schedule_sessions", {"school_id": a["wsid"]}, limit=10,
    )
    assert len(a_sessions) == 1
    assert a_sessions[0]["class_id"] == a["class_id"]

    # Non-IT roles are denied with the safe Arabic message.
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": "S", "code": f"S{sid[:6]}",
        "status": "active", "country": "SA", "language": "ar",
    })
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": UserRole.TEACHER.value, "tenant_id": sid,
        "email": f"u-{uid}@t.test", "full_name": "U",
        "is_active": True, "password_hash": "x",
    })
    h_t = _headers(uid, UserRole.TEACHER.value, sid)
    resp = await client.get(GRID_PATH, headers=h_t)
    assert resp.status_code == 403
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert INDEPENDENT_TEACHER_DENIED_AR in msg
