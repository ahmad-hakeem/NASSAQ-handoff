"""IT communication recipients + send hardening (Task #198 §5.6).

Covers the seven cases in the IT-P1-8 plan:
  (a) /auth/me/permissions exposes notifications.send for IT
  (b) my_students cohort returns exactly the IT's students
  (c) my_parents cohort returns parents linked via guardian_links
  (d) cross-IT isolation — IT-A never sees IT-B's recipients
  (e) IT POST /notifications/bulk with recipient_role → 403
  (f) IT POST /notifications/bulk with cross-tenant recipient → 403
  (g) IT POST /notifications/bulk with in-scope recipient → success +
      tenant_id tagged with itw_{user_id}
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_count, gd_find, gd_find_one, gd_insert


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_workspace(*, with_parent: bool = True, with_class: bool = True) -> dict:
    """Bootstrap a complete IT workspace: schools, teachers, classes,
    students, student-user, optional parent-user + guardian_links.
    Returns a dict of all the ids the tests need.
    """
    uid = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "teacher_id": teacher_id,
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
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
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": wsid,
        "user_id": uid,
        "full_name": user["full_name"],
        "email": user["email"],
        "is_active": True,
    })
    class_id = None
    if with_class:
        class_id = str(uuid.uuid4())
        await gd_insert(db.session, "classes", {
            "id": class_id,
            "name": "فصل أ",
            "school_id": wsid,
            "homeroom_teacher_id": teacher_id,
            "is_active": True,
        })
    student_user_id = str(uuid.uuid4())
    student_email = f"stud-{student_user_id}@t.test"
    await gd_insert(db.session, "users", {
        "id": student_user_id,
        "role": UserRole.STUDENT.value,
        "tenant_id": wsid,
        "email": student_email,
        "full_name": "طالب التجربة",
        "is_active": True,
        "password_hash": "x",
    })
    student_id = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": student_id,
        "school_id": wsid,
        "class_id": class_id,
        "full_name": "طالب التجربة",
        "email": student_email,
        "is_active": True,
    })

    parent_user_id = None
    parent_id = None
    if with_parent:
        parent_user_id = str(uuid.uuid4())
        await gd_insert(db.session, "users", {
            "id": parent_user_id,
            "role": UserRole.PARENT.value,
            "tenant_id": wsid,
            "email": f"par-{parent_user_id}@t.test",
            "full_name": "ولي أمر التجربة",
            "is_active": True,
            "password_hash": "x",
        })
        parent_id = str(uuid.uuid4())
        await gd_insert(db.session, "parents", {
            "id": parent_id,
            "school_id": wsid,
            "full_name": "ولي أمر التجربة",
            "email": f"par-{parent_user_id}@t.test",
            "user_id": parent_user_id,
            "is_active": True,
        })
        await gd_insert(db.session, "guardian_links", {
            "id": str(uuid.uuid4()),
            "parent_ref": parent_user_id,
            "parent_id": parent_id,
            "student_id": student_id,
            "relationship": "guardian",
            "tenant_id": wsid,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "user": user, "uid": uid, "wsid": wsid,
        "teacher_id": teacher_id, "class_id": class_id,
        "student_id": student_id, "student_user_id": student_user_id,
        "parent_user_id": parent_user_id, "parent_id": parent_id,
    }


# (a) ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_it_permissions_includes_notifications_send(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.get("/auth/me/permissions", headers=h)
    assert resp.status_code == 200, resp.text
    assert "notifications.send" in (resp.json().get("permissions") or [])


# (b) ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_it_my_students_cohort_returns_workspace_students(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.get(
        "/independent-teacher/communication/recipients?cohort=my_students",
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items") or []
    user_ids = {i["user_id"] for i in items}
    assert ws["student_user_id"] in user_ids


# (c) ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_it_my_parents_cohort_returns_linked_parents(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.get(
        "/independent-teacher/communication/recipients?cohort=my_parents",
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items") or []
    user_ids = {i["user_id"] for i in items}
    assert ws["parent_user_id"] in user_ids


# (d) ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_it_cohort_lookup_does_not_leak_other_workspace(client):
    ws_a = await _mk_workspace()
    ws_b = await _mk_workspace()
    h_a = _headers(ws_a["uid"], ws_a["user"]["role"], ws_a["wsid"])
    for cohort, expected_uid in (
        ("my_students", ws_a["student_user_id"]),
        ("my_parents", ws_a["parent_user_id"]),
    ):
        resp = await client.get(
            f"/independent-teacher/communication/recipients?cohort={cohort}",
            headers=h_a,
        )
        assert resp.status_code == 200, resp.text
        user_ids = {i["user_id"] for i in resp.json().get("items") or []}
        assert expected_uid in user_ids
        # Workspace B's accounts must NOT leak.
        assert ws_b["student_user_id"] not in user_ids
        assert ws_b["parent_user_id"] not in user_ids


# (e) ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_it_bulk_send_rejects_recipient_role(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.post(
        "/notifications/bulk",
        headers=h,
        json={
            "title": "x",
            "message": "y",
            "recipient_ids": [],
            "recipient_role": "parent",
        },
    )
    assert resp.status_code == 403, resp.text
    assert "البث حسب الدور" in (resp.json().get("error", {}) or {}).get("message", "")


# (f) ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_it_bulk_send_rejects_cross_tenant_recipient(client):
    ws_a = await _mk_workspace()
    ws_b = await _mk_workspace()
    h = _headers(ws_a["uid"], ws_a["user"]["role"], ws_a["wsid"])
    resp = await client.post(
        "/notifications/bulk",
        headers=h,
        json={
            "title": "x",
            "message": "y",
            "recipient_ids": [ws_b["student_user_id"]],
        },
    )
    assert resp.status_code == 403, resp.text
    assert "مساحتك" in (resp.json().get("error", {}) or {}).get("message", "")


# (g) ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_it_bulk_send_succeeds_for_in_scope_recipient(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    before = await gd_count(db.session, "notifications", {"user_id": ws["student_user_id"]})
    resp = await client.post(
        "/notifications/bulk",
        headers=h,
        json={
            "title": "اختبار",
            "message": "محتوى",
            "recipient_ids": [ws["student_user_id"]],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("created_count", 0) >= 1
    after = await gd_count(db.session, "notifications", {"user_id": ws["student_user_id"]})
    assert after == before + 1
    persisted = await gd_find_one(
        db.session, "notifications",
        {"user_id": ws["student_user_id"], "title": "اختبار"},
    )
    assert persisted is not None
    assert persisted.get("tenant_id") == ws["wsid"]


# (h) ----------------------------------------------------------------
# Spec §5.6 response shape: my_students MUST include student_id.
@pytest.mark.asyncio
async def test_it_my_students_response_includes_student_id(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.get(
        "/independent-teacher/communication/recipients?cohort=my_students",
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items") or []
    assert items, items
    by_uid = {i["user_id"]: i for i in items}
    row = by_uid.get(ws["student_user_id"])
    assert row is not None, by_uid
    assert row.get("student_id") == ws["student_id"]
    assert "full_name" in row


# (i) ----------------------------------------------------------------
# Spec §5.6 response shape: my_parents MUST include student_id + parent_id.
@pytest.mark.asyncio
async def test_it_my_parents_response_includes_parent_and_student_ids(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.get(
        "/independent-teacher/communication/recipients?cohort=my_parents",
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items") or []
    assert items, items
    row = next((i for i in items if i["user_id"] == ws["parent_user_id"]), None)
    assert row is not None, items
    assert row.get("student_id") == ws["student_id"]
    assert row.get("parent_id") == ws["parent_id"]


# (j) ----------------------------------------------------------------
# Spec §5.6: a workspace student that is NOT in any of the IT's classes
# must NOT appear in my_students (the IT teacher has no classes here).
@pytest.mark.asyncio
async def test_it_my_students_excludes_students_outside_teacher_classes(client):
    ws = await _mk_workspace(with_class=False, with_parent=False)
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.get(
        "/independent-teacher/communication/recipients?cohort=my_students",
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items") or []
    user_ids = {i["user_id"] for i in items}
    assert ws["student_user_id"] not in user_ids


# (k) ----------------------------------------------------------------
# Spec §5.6: the same out-of-class student must be rejected (403) by the
# send-side validator — the picker and the send path must agree.
@pytest.mark.asyncio
async def test_it_bulk_send_rejects_recipient_outside_teacher_classes(client):
    ws = await _mk_workspace(with_class=False, with_parent=False)
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.post(
        "/notifications/bulk",
        headers=h,
        json={
            "title": "x",
            "message": "y",
            "recipient_ids": [ws["student_user_id"]],
        },
    )
    assert resp.status_code == 403, resp.text


# (l) ----------------------------------------------------------------
# Spec §5.6: single POST /notifications must also pin tenant_id to the
# IT workspace id (not a stale users.tenant_id).
@pytest.mark.asyncio
async def test_it_single_send_pins_tenant_id_to_workspace(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.post(
        "/notifications",
        headers=h,
        json={
            "title": "single-it",
            "message": "single-body",
            "recipient_id": ws["student_user_id"],
            "notification_type": "communication",
            "priority": "medium",
        },
    )
    assert resp.status_code == 200, resp.text
    persisted = await gd_find_one(
        db.session, "notifications",
        {"user_id": ws["student_user_id"], "title": "single-it"},
    )
    assert persisted is not None
    assert persisted.get("tenant_id") == ws["wsid"]
