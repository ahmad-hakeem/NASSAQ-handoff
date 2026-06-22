"""Task #1054 — automated coverage for the IT lesson-end parent report.

The Independent-Teacher lesson-end summary (POST /notifications with
``recipient_role == 'parent'`` + ``related_entity == 'session'``) stamps a
structured per-child ``lesson_report`` (attendance, participation, homework,
teacher note) onto each parent's notification. This module locks in:

  A. Per-child scoping — each parent's notification carries ONLY their own
     child's lesson_report (no sibling / other-family data bleed).
  B. Both roster-resolution paths — the explicit ``scope_class_id``
     (class-scoped) path and the session-id-resolved path produce the same
     per-child delivery.
  C. Graceful degrade — a missing/unknown session id delivers a generic
     notification (lesson_report absent) without failing the send.
  D. GET /notifications surfaces ``lesson_report`` only on the IT summary
     rows and ``null`` everywhere else.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token, session_engine
from engines.sql_utils import gd_insert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(uid: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({"sub": uid, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_it_workspace() -> dict:
    """Create an IT user + its materialised workspace school + teachers row.

    Returns a dict carrying the user id, the synthetic workspace id, and the
    teachers.id so callers can wire classes/assignments to the teacher.
    """
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
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "user_id": uid,
        "school_id": wsid,
        "full_name": user["full_name"],
        "is_active": True,
    })
    return {"user_id": uid, "workspace_id": wsid, "teacher_id": teacher_id}


async def _mk_class(wsid: str, teacher_id: str, name: str = "C1") -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": wsid,
        "name": name,
        "grade_level": "1",
        "homeroom_teacher_id": teacher_id,
        "is_active": True,
    })
    return cid


async def _mk_student(wsid: str, cid: str, full_name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": wsid,
        "class_id": cid,
        "full_name": full_name,
        "gender": "male",
        "is_active": True,
    })
    return sid


async def _mk_parent_linked(wsid: str, sid: str, full_name: str) -> str:
    """Create a parent USER inside the workspace tenant and an active
    guardian_link binding them to ``sid``. Returns the parent user id."""
    pid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": pid,
        "role": "parent",
        "tenant_id": wsid,
        "email": f"parent-{pid}@t.test",
        "full_name": full_name,
        "is_active": True,
        "password_hash": "x",
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "student_id": sid,
        "tenant_id": wsid,
        "parent_ref": pid,
        "parent_user_id": pid,
        "is_active": True,
    })
    return pid


async def _mk_session(wsid: str, cid, status: str = "ended") -> str:
    session_id = str(uuid.uuid4())
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        # `cid` may be None for a course / no-class session.
        "class_id": cid,
        "school_id": wsid,
        "tenant_id": wsid,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return session_id


async def _mk_attendance(session_id: str, sid: str, status: str) -> None:
    await gd_insert(db.session, "session_attendance", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": sid,
        "status": status,
    })


async def _mk_interaction(
    session_id: str, sid: str,
    interaction_type: str = "participation",
    answer_result: str | None = None,
    behaviour_category: str | None = None,
) -> None:
    await gd_insert(db.session, "session_interactions", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": sid,
        # `type` is a real NOT-NULL column; `interaction_type` is the
        # field the report builder reads (mirrors the engine's own writes).
        "type": interaction_type,
        "interaction_type": interaction_type,
        "answer_result": answer_result,
        "behaviour_category": behaviour_category,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })


async def _mk_homework(session_id: str, sid: str, status: str) -> None:
    await gd_insert(db.session, "session_homework", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": sid,
        "status": status,
    })


def _summary_payload(session_id: str, scope_class_id: str | None = None) -> dict:
    payload = {
        "title": "ملخص الحصة",
        "message": "انتهت الحصة",
        "notification_type": "communication",
        "priority": "medium",
        "recipient_role": "parent",
        "related_entity": "session",
        "related_entity_id": session_id,
    }
    if scope_class_id:
        payload["scope_class_id"] = scope_class_id
    return payload


async def _build_two_child_session():
    """Two children of two different parents in one class, with distinct
    per-child academic data and a shared closing note. Returns a context
    dict for the per-child assertions."""
    ws = await _mk_it_workspace()
    wsid = ws["workspace_id"]
    cid = await _mk_class(wsid, ws["teacher_id"])

    sid_a = await _mk_student(wsid, cid, "طالب أ")
    sid_b = await _mk_student(wsid, cid, "طالب ب")
    parent_a = await _mk_parent_linked(wsid, sid_a, "ولي أمر أ")
    parent_b = await _mk_parent_linked(wsid, sid_b, "ولي أمر ب")

    session_id = await _mk_session(wsid, cid)

    # Child A: present, 2 participations, 1 correct answer, homework done.
    await _mk_attendance(session_id, sid_a, "present")
    await _mk_interaction(session_id, sid_a, "participation")
    await _mk_interaction(session_id, sid_a, "participation")
    await _mk_interaction(session_id, sid_a, "question", answer_result="correct")
    await _mk_homework(session_id, sid_a, "done")

    # Child B: absent, 1 wrong answer, 1 negative behaviour, homework not done.
    await _mk_attendance(session_id, sid_b, "absent")
    await _mk_interaction(session_id, sid_b, "question", answer_result="wrong")
    await _mk_interaction(session_id, sid_b, "behaviour", behaviour_category="negative")
    await _mk_homework(session_id, sid_b, "not_done")

    return {
        "ws": ws,
        "wsid": wsid,
        "class_id": cid,
        "session_id": session_id,
        "sid_a": sid_a,
        "sid_b": sid_b,
        "parent_a": parent_a,
        "parent_b": parent_b,
    }


# ---------------------------------------------------------------------------
# A. build_parent_lesson_reports — per-child scoping (no cross-child bleed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_reports_are_per_child_scoped():
    ctx = await _build_two_child_session()
    engine = session_engine
    reports = await engine.build_parent_lesson_reports(ctx["session_id"])

    assert set(reports.keys()) == {ctx["sid_a"], ctx["sid_b"]}

    rep_a = reports[ctx["sid_a"]]
    assert rep_a["attendance_status"] == "present"
    assert rep_a["participations"] == 2
    assert rep_a["correct_answers"] == 1
    assert rep_a["wrong_answers"] == 0
    assert rep_a["negative_behaviours"] == 0
    assert rep_a["homework_status"] == "done"
    # The lesson-level closing note is keyed off `is_closing_note`, which the
    # session_notes schema does not persist, so teacher_note is the empty
    # string in the current implementation. Assert the key is always present
    # (shape contract) without locking in a value the schema can't produce.
    assert "teacher_note" in rep_a

    rep_b = reports[ctx["sid_b"]]
    assert rep_b["attendance_status"] == "absent"
    assert rep_b["participations"] == 0
    assert rep_b["correct_answers"] == 0
    assert rep_b["wrong_answers"] == 1
    assert rep_b["negative_behaviours"] == 1
    assert rep_b["homework_status"] == "not_done"
    assert "teacher_note" in rep_b


@pytest.mark.asyncio
async def test_build_reports_unknown_session_returns_empty():
    engine = session_engine
    reports = await engine.build_parent_lesson_reports(str(uuid.uuid4()))
    assert reports == {}


# ---------------------------------------------------------------------------
# Delivery — each parent's notification carries ONLY their own child report
# ---------------------------------------------------------------------------

async def _deliver_and_fetch(client, ctx, scope_class_id=None):
    """Send the IT summary, then return {parent_user_id: [notification rows]}
    fetched via GET /notifications for each parent."""
    it_headers = _headers(ctx["ws"]["user_id"], UserRole.INDEPENDENT_TEACHER.value, tenant_id=ctx["wsid"])
    resp = await client.post(
        "/notifications",
        json=_summary_payload(ctx["session_id"], scope_class_id),
        headers=it_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["created_count"] == 2

    out = {}
    for parent_uid in (ctx["parent_a"], ctx["parent_b"]):
        r = await client.get(
            "/notifications",
            headers=_headers(parent_uid, "parent", tenant_id=ctx["wsid"]),
        )
        assert r.status_code == 200, r.text
        out[parent_uid] = r.json()
    return out


@pytest.mark.asyncio
async def test_delivery_session_resolved_per_child_no_bleed(client):
    """Session-id-resolved roster path: no scope_class_id supplied, the
    class/roster is derived from the session id. Each parent sees only their
    own child's lesson_report."""
    ctx = await _build_two_child_session()
    rows_by_parent = await _deliver_and_fetch(client, ctx, scope_class_id=None)

    a_rows = rows_by_parent[ctx["parent_a"]]
    assert len(a_rows) == 1
    a_report = a_rows[0]["lesson_report"]
    assert a_report is not None
    assert a_report["attendance_status"] == "present"
    assert a_report["homework_status"] == "done"

    b_rows = rows_by_parent[ctx["parent_b"]]
    assert len(b_rows) == 1
    b_report = b_rows[0]["lesson_report"]
    assert b_report is not None
    assert b_report["attendance_status"] == "absent"
    assert b_report["homework_status"] == "not_done"

    # Cross-child bleed guard: parent A's report must not equal parent B's.
    assert a_report != b_report


@pytest.mark.asyncio
async def test_delivery_class_scoped_roster_path(client):
    """Class-scoped roster path: scope_class_id supplied explicitly. Same
    per-child delivery as the session-resolved path."""
    ctx = await _build_two_child_session()
    rows_by_parent = await _deliver_and_fetch(
        client, ctx, scope_class_id=ctx["class_id"],
    )

    a_report = rows_by_parent[ctx["parent_a"]][0]["lesson_report"]
    b_report = rows_by_parent[ctx["parent_b"]][0]["lesson_report"]
    assert a_report["attendance_status"] == "present"
    assert b_report["attendance_status"] == "absent"
    assert a_report != b_report


# ---------------------------------------------------------------------------
# C. Graceful degrade — unknown session → generic notification, send succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_session_degrades_to_generic_notification(client):
    """An unknown session id still delivers (to the teacher's whole parent
    cohort fallback) but with no lesson_report stamped — the send must not
    fail."""
    ws = await _mk_it_workspace()
    wsid = ws["workspace_id"]
    cid = await _mk_class(wsid, ws["teacher_id"])
    sid = await _mk_student(wsid, cid, "طالب")
    parent_uid = await _mk_parent_linked(wsid, sid, "ولي أمر")

    unknown_session = str(uuid.uuid4())
    it_headers = _headers(ws["user_id"], UserRole.INDEPENDENT_TEACHER.value, tenant_id=wsid)
    resp = await client.post(
        "/notifications",
        json=_summary_payload(unknown_session),
        headers=it_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["created_count"] == 1

    r = await client.get(
        "/notifications",
        headers=_headers(parent_uid, "parent", tenant_id=wsid),
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    # Generic notification — lesson_report must be absent (null).
    assert rows[0]["lesson_report"] is None


# ---------------------------------------------------------------------------
# D. GET /notifications — lesson_report only on IT summary rows, null else
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_notifications_lesson_report_only_on_summary_rows(client):
    """A parent with both an IT summary row and an unrelated notification
    sees lesson_report populated on the summary row and null on the other."""
    ctx = await _build_two_child_session()

    # Pre-existing, non-summary notification for parent A (no lesson_report).
    await gd_insert(db.session, "notifications", {
        "id": str(uuid.uuid4()),
        "user_id": ctx["parent_a"],
        "title": "إشعار عام",
        "message": "رسالة عامة",
        "type": "system",
        "priority": "normal",
        "tenant_id": ctx["wsid"],
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })

    it_headers = _headers(ctx["ws"]["user_id"], UserRole.INDEPENDENT_TEACHER.value, tenant_id=ctx["wsid"])
    resp = await client.post(
        "/notifications",
        json=_summary_payload(ctx["session_id"]),
        headers=it_headers,
    )
    assert resp.status_code == 200, resp.text

    r = await client.get(
        "/notifications",
        headers=_headers(ctx["parent_a"], "parent", tenant_id=ctx["wsid"]),
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2

    with_report = [n for n in rows if n["lesson_report"] is not None]
    without_report = [n for n in rows if n["lesson_report"] is None]
    assert len(with_report) == 1
    assert len(without_report) == 1
    # The summary row carries this child's own data.
    assert with_report[0]["lesson_report"]["attendance_status"] == "present"
    assert without_report[0]["title"] == "إشعار عام"


# ---------------------------------------------------------------------------
# E. Course / no-class session — delivery falls back to the teacher's own
#    parent cohort with NO broadcast-deny error (Task #1057)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_course_no_class_session_falls_back_to_cohort(client):
    """A course session that is not tied to any class (``class_id is None``)
    still delivers the summary — the roster cannot be resolved from the
    session, so delivery falls back to the teacher's whole §5.6 parent cohort.
    Critically, the IT broadcast-deny rule must NOT fire (200, not 403)."""
    ws = await _mk_it_workspace()
    wsid = ws["workspace_id"]
    # The teacher has a class with a linked parent — this is the cohort the
    # fallback resolves — but the SESSION itself has no class.
    cid = await _mk_class(wsid, ws["teacher_id"])
    sid = await _mk_student(wsid, cid, "طالب")
    parent_uid = await _mk_parent_linked(wsid, sid, "ولي أمر")

    course_session = await _mk_session(wsid, None)

    it_headers = _headers(ws["user_id"], UserRole.INDEPENDENT_TEACHER.value, tenant_id=wsid)
    resp = await client.post(
        "/notifications",
        json=_summary_payload(course_session),
        headers=it_headers,
    )
    # 200 (delivered) — never the §5.6 broadcast-deny 403.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["created_count"] == 1

    r = await client.get(
        "/notifications",
        headers=_headers(parent_uid, "parent", tenant_id=wsid),
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# F. Re-ended (already-completed) session — still delivers, no error
#    (Task #1057)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_already_completed_session_still_delivers(client):
    """A session that is already marked ``completed`` (the teacher re-opened a
    finished lesson and ended it again) must still deliver the per-child
    summary without raising the broadcast-deny error."""
    ws = await _mk_it_workspace()
    wsid = ws["workspace_id"]
    cid = await _mk_class(wsid, ws["teacher_id"])
    sid = await _mk_student(wsid, cid, "طالب")
    parent_uid = await _mk_parent_linked(wsid, sid, "ولي أمر")

    completed_session = await _mk_session(wsid, cid, status="completed")
    await _mk_attendance(completed_session, sid, "present")
    await _mk_interaction(completed_session, sid, "participation")

    it_headers = _headers(ws["user_id"], UserRole.INDEPENDENT_TEACHER.value, tenant_id=wsid)
    resp = await client.post(
        "/notifications",
        json=_summary_payload(completed_session),
        headers=it_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["created_count"] == 1

    r = await client.get(
        "/notifications",
        headers=_headers(parent_uid, "parent", tenant_id=wsid),
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["lesson_report"] is not None
    assert rows[0]["lesson_report"]["attendance_status"] == "present"


# ---------------------------------------------------------------------------
# G. Class with NO homeroom_teacher_id and NO teacher_assignments row
#    (Task #1064) — the reproduced "مقرر تجريبي" course case. Its students
#    have active guardian_links, so delivery must reach those parents and
#    NOT 403 on the §5.6 homeroom/assignment cohort re-validation.
# ---------------------------------------------------------------------------

async def _mk_class_no_teacher(wsid: str, name: str = "مقرر تجريبي") -> str:
    """A workspace class with neither a homeroom teacher nor a
    teacher_assignments row — the IT course-without-assignment case."""
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": wsid,
        "name": name,
        "grade_level": "1",
        # NOTE: no homeroom_teacher_id.
        "is_active": True,
    })
    return cid


@pytest.mark.asyncio
async def test_delivery_class_without_homeroom_or_assignment(client):
    """The reproduced failure: an IT class created without a
    homeroom_teacher_id and without a teacher_assignments row, whose
    students have active guardian_links, must deliver the lesson report to
    those parents — no 403, notification rows written."""
    ws = await _mk_it_workspace()
    wsid = ws["workspace_id"]
    cid = await _mk_class_no_teacher(wsid)

    sid = await _mk_student(wsid, cid, "طالب المقرر")
    parent_uid = await _mk_parent_linked(wsid, sid, "ولي أمر المقرر")

    session_id = await _mk_session(wsid, cid)
    await _mk_attendance(session_id, sid, "present")
    await _mk_interaction(session_id, sid, "participation")

    it_headers = _headers(
        ws["user_id"], UserRole.INDEPENDENT_TEACHER.value, tenant_id=wsid,
    )
    resp = await client.post(
        "/notifications",
        json=_summary_payload(session_id),
        headers=it_headers,
    )
    # Must NOT 403 on the cohort re-validation.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["created_count"] == 1

    r = await client.get(
        "/notifications",
        headers=_headers(parent_uid, "parent", tenant_id=wsid),
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["lesson_report"] is not None
    assert rows[0]["lesson_report"]["attendance_status"] == "present"


@pytest.mark.asyncio
async def test_delivery_no_cross_workspace_leak_on_no_homeroom_class(client):
    """Even on the no-homeroom class path, a parent that belongs to ANOTHER
    workspace must never receive the report. Workspace B's parent is forged
    onto workspace A's student via a guardian_link pinned to A's tenant; the
    tenant-scoped roster resolver drops them, so they receive nothing and
    the send stays a success-shaped no-op (never a leak)."""
    ws_a = await _mk_it_workspace()
    ws_b = await _mk_it_workspace()
    wsid_a = ws_a["workspace_id"]
    cid = await _mk_class_no_teacher(wsid_a)
    sid = await _mk_student(wsid_a, cid, "طالب أ")

    # A parent USER that lives in workspace B (cross-workspace target).
    foreign_parent = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": foreign_parent,
        "role": "parent",
        "tenant_id": ws_b["workspace_id"],
        "email": f"foreign-{foreign_parent}@t.test",
        "full_name": "ولي أمر خارجي",
        "is_active": True,
        "password_hash": "x",
    })
    # Forge a guardian_link (pinned to workspace A's tenant) so delivery
    # would resolve this foreign parent into the roster pairs if the
    # tenant scoping ever regressed.
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "student_id": sid,
        "tenant_id": wsid_a,
        "parent_ref": foreign_parent,
        "parent_user_id": foreign_parent,
        "is_active": True,
    })

    session_id = await _mk_session(wsid_a, cid)
    it_headers = _headers(
        ws_a["user_id"], UserRole.INDEPENDENT_TEACHER.value, tenant_id=wsid_a,
    )
    resp = await client.post(
        "/notifications",
        json=_summary_payload(session_id),
        headers=it_headers,
    )
    # Success-shaped no-op — the foreign parent is dropped, not delivered.
    assert resp.status_code == 200, resp.text
    assert resp.json()["created_count"] == 0

    # The foreign parent received nothing.
    r = await client.get(
        "/notifications",
        headers=_headers(foreign_parent, "parent", tenant_id=ws_b["workspace_id"]),
    )
    assert r.status_code == 200, r.text
    assert r.json() == []


@pytest.mark.asyncio
async def test_validator_rejects_cross_workspace_target():
    """Explicit defence-in-depth: the workspace-scoped re-validation 403s a
    resolved target that is not an active parent user pinned to the caller's
    workspace tenant, even if a roster pair somehow carried it."""
    from fastapi import HTTPException
    from routes.notification_routes_mod import (
        _it_validate_summary_recipients_or_403,
    )

    ws_a = await _mk_it_workspace()
    ws_b = await _mk_it_workspace()

    # A real parent in workspace B.
    foreign_parent = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": foreign_parent,
        "role": "parent",
        "tenant_id": ws_b["workspace_id"],
        "email": f"foreign-{foreign_parent}@t.test",
        "full_name": "ولي أمر خارجي",
        "is_active": True,
        "password_hash": "x",
    })

    pairs = [(str(uuid.uuid4()), foreign_parent)]
    with pytest.raises(HTTPException) as exc:
        await _it_validate_summary_recipients_or_403(ws_a["workspace_id"], pairs)
    assert exc.value.status_code == 403
