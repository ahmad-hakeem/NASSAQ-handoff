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

from src.core.guards.tenant_guard import independent_workspace_id
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


# (m) ----------------------------------------------------------------
# Task #1046: the IT end-of-lesson parent summary
# (recipient_role='parent', no recipient_id, with scope_class_id) is a
# legitimate per-class delivery that must NOT be rejected by the §5.6
# recipient_role guard — it delivers to exactly the workspace parents.
@pytest.mark.asyncio
async def test_it_class_scoped_parent_summary_delivers(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    title = f"ملخص الحصة — {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/notifications",
        headers=h,
        json={
            "title": title,
            "message": "اكتملت الحصة.",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "parent",
            "related_entity": "session",
            "related_entity_id": str(uuid.uuid4()),
            "scope_class_id": ws["class_id"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("created_count") == 1
    persisted = await gd_find_one(
        db.session, "notifications",
        {"user_id": ws["parent_user_id"], "title": title},
    )
    assert persisted is not None
    assert persisted.get("tenant_id") == ws["wsid"]
    assert persisted.get("student_id") == ws["student_id"]


# (n) ----------------------------------------------------------------
# Task #1046: a true role broadcast (recipient_role with NO scope_class_id)
# from an IT is still rejected — the §5.6 guard stays intact.
@pytest.mark.asyncio
async def test_it_parent_role_without_class_scope_still_rejected(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.post(
        "/notifications",
        headers=h,
        json={
            "title": "بث عام",
            "message": "y",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "parent",
        },
    )
    assert resp.status_code == 403, resp.text
    assert "البث حسب الدور" in (resp.json().get("error", {}) or {}).get("message", "")


# (o) ----------------------------------------------------------------
# Task #1046: an empty class (no students/parents) ends as a success
# no-op (created_count 0) so the summary screen shows no error popup.
@pytest.mark.asyncio
async def test_it_class_scoped_parent_summary_empty_roster_is_noop(client):
    ws = await _mk_workspace(with_parent=False)
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    empty_class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": empty_class_id,
        "name": "فصل فارغ",
        "school_id": ws["wsid"],
        "homeroom_teacher_id": ws["teacher_id"],
        "is_active": True,
    })
    resp = await client.post(
        "/notifications",
        headers=h,
        json={
            "title": "ملخص الحصة الفارغة",
            "message": "x",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "parent",
            "related_entity": "session",
            "scope_class_id": empty_class_id,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("created_count") == 0


async def _mk_session(ws: dict) -> str:
    """Insert a class_sessions row for ws and return its id."""
    session_id = str(uuid.uuid4())
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "class_id": ws["class_id"],
        "school_id": ws["wsid"],
        "teacher_id": ws["teacher_id"],
        "status": "completed",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return session_id


# (p) ----------------------------------------------------------------
# Task #1048: an IT end-session summary that carries the session id but
# NO scope_class_id (the FE-drops-the-class-scope bug) must NOT 403 —
# the backend resolves the class from the session and delivers to the
# teacher's own linked parents.
@pytest.mark.asyncio
async def test_it_session_summary_without_class_scope_delivers(client):
    ws = await _mk_workspace()
    session_id = await _mk_session(ws)
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    title = f"ملخص الحصة — {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/notifications",
        headers=h,
        json={
            "title": title,
            "message": "اكتملت الحصة.",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "parent",
            "related_entity": "session",
            "related_entity_id": session_id,
            # NOTE: no scope_class_id — this is the reported failure case.
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("created_count") == 1, body
    persisted = await gd_find_one(
        db.session, "notifications",
        {"user_id": ws["parent_user_id"], "title": title},
    )
    assert persisted is not None
    assert persisted.get("tenant_id") == ws["wsid"]
    assert persisted.get("student_id") == ws["student_id"]


# (q) ----------------------------------------------------------------
# Task #1048: cross-workspace isolation — IT-A's end-session summary can
# only reach IT-A's linked parents, never IT-B's.
@pytest.mark.asyncio
async def test_it_session_summary_no_cross_workspace_leak(client):
    ws_a = await _mk_workspace()
    ws_b = await _mk_workspace()
    session_id = await _mk_session(ws_a)
    h_a = _headers(ws_a["uid"], ws_a["user"]["role"], ws_a["wsid"])
    title = f"ملخص الحصة — {uuid.uuid4().hex[:6]}"
    before_b = await gd_count(
        db.session, "notifications", {"user_id": ws_b["parent_user_id"]},
    )
    resp = await client.post(
        "/notifications",
        headers=h_a,
        json={
            "title": title,
            "message": "اكتملت الحصة.",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "parent",
            "related_entity": "session",
            "related_entity_id": session_id,
        },
    )
    assert resp.status_code == 200, resp.text
    # IT-A's parent received it.
    got_a = await gd_find_one(
        db.session, "notifications",
        {"user_id": ws_a["parent_user_id"], "title": title},
    )
    assert got_a is not None
    # IT-B's parent received nothing new.
    after_b = await gd_count(
        db.session, "notifications", {"user_id": ws_b["parent_user_id"]},
    )
    assert after_b == before_b


# (r) ----------------------------------------------------------------
# Task #1048: when the teacher's own students have no real linked parent
# recipients, the summary returns a success-shaped, zero-delivery result
# with a safe Arabic message — never a 403 broadcast error.
@pytest.mark.asyncio
async def test_it_session_summary_empty_recipients_safe_result(client):
    ws = await _mk_workspace(with_parent=False)
    session_id = await _mk_session(ws)
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.post(
        "/notifications",
        headers=h,
        json={
            "title": "ملخص بلا أولياء",
            "message": "x",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "parent",
            "related_entity": "session",
            "related_entity_id": session_id,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("created_count") == 0, body
    # Precise, safe Arabic message — not the broadcast-block message.
    assert "أولياء أمور" in (body.get("message") or "")
    assert "البث حسب الدور" not in (body.get("message") or "")


# (s) ----------------------------------------------------------------
# Task #1048: a true IT role broadcast (session shape but no session id
# AND no class scope) is still rejected — the §5.6 guard stays intact.
@pytest.mark.asyncio
async def test_it_session_summary_without_any_scope_still_rejected(client):
    ws = await _mk_workspace()
    h = _headers(ws["uid"], ws["user"]["role"], ws["wsid"])
    resp = await client.post(
        "/notifications",
        headers=h,
        json={
            "title": "بث عام",
            "message": "y",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "parent",
            "related_entity": "session",
            # no related_entity_id, no scope_class_id → genuine broadcast.
        },
    )
    assert resp.status_code == 403, resp.text
    assert "البث حسب الدور" in (resp.json().get("error", {}) or {}).get("message", "")


# (t) ----------------------------------------------------------------
# Task #1048: school-teacher lesson-end delivery is unchanged. A
# `teacher`-role class-scoped parent summary still delivers via the
# existing Task #1038 branch and is NOT routed through the IT path.
@pytest.mark.asyncio
async def test_school_teacher_class_scoped_summary_unchanged(client):
    ws = await _mk_workspace()
    # Same tenant data, but caller is a plain school teacher.
    h = _headers(ws["uid"], UserRole.TEACHER.value, ws["wsid"])
    title = f"ملخص مدرسي — {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/notifications",
        headers=h,
        json={
            "title": title,
            "message": "اكتملت الحصة.",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "parent",
            "related_entity": "session",
            "related_entity_id": str(uuid.uuid4()),
            "scope_class_id": ws["class_id"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("created_count") == 1, body
    persisted = await gd_find_one(
        db.session, "notifications",
        {"user_id": ws["parent_user_id"], "title": title},
    )
    assert persisted is not None
    assert persisted.get("student_id") == ws["student_id"]
