"""
Task #1038 — every parent-reachable student-specific notification must
persist a trustworthy child reference (``notifications.student_id``) at
CREATION so the Parent Portal inbox can render the child chip and the
per-child filter before the notification is opened.

Covers the two production write paths that previously left parents with a
child-less (or undelivered) row:

1. ``POST /notifications`` with ``recipient_role='parent'`` +
   ``scope_class_id`` (the end-of-session "ملخص الحصة" summary fired from
   ``SessionTeachPage.sendParentNotifications``). It must deliver one row
   per (parent, child-in-class) pair, each stamped with that child's
   ``student_id`` on the indexed ``user_id`` column.
2. ``SessionEngine._send_smart_end_session_notifications`` (absence /
   repeated-negative / outstanding) which previously wrote the legacy,
   never-read ``recipient_id`` field with no ``student_id``.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert
from engines.session_engine import TeacherSessionEngine as SessionEngine


def _headers(user_id: str, role: str, tenant_id):
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session
    return SessionEngine(_DBShim())


async def _mk_user(role: str, tenant_id) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": f"{role}-{uid[:6]}",
        "is_active": True, "password_hash": "x",
    })
    return uid


async def _mk_class(tenant_id) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_student(tenant_id, class_id, *, parent_user_id=None, name="S") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "full_name": name, "class_id": class_id, "is_active": True,
    })
    if parent_user_id:
        await gd_insert(db.session, "guardian_links", {
            "id": str(uuid.uuid4()), "tenant_id": tenant_id,
            "student_id": sid, "parent_user_id": parent_user_id,
            "is_active": True,
        })
    return sid


# ---------- POST /notifications: class-scoped parent summary ----------

@pytest.mark.asyncio
async def test_class_scoped_parent_summary_tags_each_child(client, tenant_a):
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    parent1 = await _mk_user("parent", tenant_a)
    parent2 = await _mk_user("parent", tenant_a)
    s1 = await _mk_student(tenant_a, class_id, parent_user_id=parent1, name="A")
    s2 = await _mk_student(tenant_a, class_id, parent_user_id=parent2, name="B")

    title = f"ملخص الحصة — {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/notifications",
        json={
            "title": title,
            "message": "اكتملت الحصة.",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "parent",
            "related_entity": "session",
            "related_entity_id": str(uuid.uuid4()),
            "scope_class_id": class_id,
        },
        headers=_headers(teacher_id, "teacher", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("created_count") == 2

    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "title": title,
    }, limit=10)
    by_user = {r["user_id"]: r for r in rows}
    assert set(by_user) == {parent1, parent2}
    # Each parent's row carries THEIR child's student_id (the chip source).
    assert by_user[parent1].get("student_id") == s1
    assert by_user[parent2].get("student_id") == s2


@pytest.mark.asyncio
async def test_class_scoped_summary_excludes_other_class_parents(client, tenant_a):
    teacher_id = await _mk_user("teacher", tenant_a)
    target_class = await _mk_class(tenant_a)
    other_class = await _mk_class(tenant_a)
    in_parent = await _mk_user("parent", tenant_a)
    out_parent = await _mk_user("parent", tenant_a)
    await _mk_student(tenant_a, target_class, parent_user_id=in_parent, name="In")
    await _mk_student(tenant_a, other_class, parent_user_id=out_parent, name="Out")

    title = f"ملخص الحصة — {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/notifications",
        json={
            "title": title, "message": "x",
            "notification_type": "communication", "priority": "medium",
            "recipient_role": "parent", "related_entity": "session",
            "scope_class_id": target_class,
        },
        headers=_headers(teacher_id, "teacher", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("created_count") == 1
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "title": title,
    }, limit=10)
    assert {r["user_id"] for r in rows} == {in_parent}


@pytest.mark.asyncio
async def test_class_scoped_summary_cross_tenant_isolation(client, tenant_a, tenant_b):
    # Class lives in tenant_a; a same-id-less parent in tenant_b must never
    # be resolved, and the caller's tenant cannot reach tenant_b rows.
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    parent_a = await _mk_user("parent", tenant_a)
    await _mk_student(tenant_a, class_id, parent_user_id=parent_a, name="A")
    # A class with the same id-shape in tenant_b is unrelated.
    await _mk_user("parent", tenant_b)

    title = f"ملخص الحصة — {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/notifications",
        json={
            "title": title, "message": "x",
            "notification_type": "communication", "priority": "medium",
            "recipient_role": "parent", "related_entity": "session",
            "scope_class_id": class_id,
        },
        headers=_headers(teacher_id, "teacher", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    rows = await gd_find(db.session, "notifications", {"title": title}, limit=10)
    assert {r["user_id"] for r in rows} == {parent_a}
    for r in rows:
        assert r.get("tenant_id") == tenant_a


@pytest.mark.asyncio
async def test_parent_role_without_class_scope_uses_legacy_broadcast(client, tenant_a):
    # No scope_class_id → falls through to the generic role broadcast,
    # which delivers child-less to every parent in the tenant (unchanged
    # legacy behaviour, no student_id invented).
    teacher_id = await _mk_user("teacher", tenant_a)
    parent1 = await _mk_user("parent", tenant_a)

    title = f"إعلان عام — {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/notifications",
        json={
            "title": title, "message": "x",
            "notification_type": "communication", "priority": "medium",
            "recipient_role": "parent",
        },
        headers=_headers(teacher_id, "teacher", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "title": title,
    }, limit=10)
    assert parent1 in {r["user_id"] for r in rows}
    for r in rows:
        assert r.get("student_id") is None


# ---------- engine smart end-session notifications ----------

@pytest.mark.asyncio
async def test_smart_end_session_absence_tags_child_on_user_id(tenant_a):
    parent_id = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    # Canonical linkage via guardian_links (the resolver's primary path);
    # students has no parent_user_id column, which is why the legacy
    # student.get("parent_user_id") read always resolved to None.
    sid = await _mk_student(tenant_a, class_id, parent_user_id=parent_id, name="Absent One")

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await _engine()._send_smart_end_session_notifications(
        session_id=session_id,
        school_id=tenant_a,
        attendance=[{"student_id": sid, "status": "absent"}],
        neg_students={},
        student_interactions={},
        now=now,
    )

    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "user_id": parent_id, "entity_id": session_id,
    }, limit=10)
    assert len(rows) == 1
    assert rows[0].get("student_id") == sid


# ---------- Task #1042: end-lesson 500 crash regression ----------
#
# Ending a lesson runs parent/management notification side effects in the
# SAME transaction as the core lesson-completion. A failing notification
# insert used to poison that shared session, so the next (unguarded)
# activity-log write crashed with PendingRollbackError and the whole "end
# lesson" flow 500'd — rolling back the completion too. The fix isolates
# each notification side effect in its own SAVEPOINT and never attempts a
# NULL-recipient insert.


@pytest.mark.asyncio
async def test_smart_end_session_skips_null_recipient(tenant_a):
    # A repeated-negative-behaviour student with NO linked parent. The
    # management resolver is forced to yield falsy recipients alongside one
    # valid id — the falsy entries must be skipped, never written as a
    # NULL-user notification (which would violate NOT NULL and crash the end).
    class_id = await _mk_class(tenant_a)
    sid = await _mk_student(tenant_a, class_id, name="Neg One")
    mgmt_id = await _mk_user("school_principal", tenant_a)

    eng = _engine()

    async def _fake_mgmt(school_id):
        return [None, "", mgmt_id]

    eng._resolve_management_recipient_ids = _fake_mgmt

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    # Must NOT raise even though two of the three recipients are falsy.
    await eng._send_smart_end_session_notifications(
        session_id=session_id,
        school_id=tenant_a,
        attendance=[],
        neg_students={sid: 3},
        student_interactions={},
        now=now,
    )

    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "entity_id": session_id,
    }, limit=10)
    # Exactly one row — the valid recipient. No NULL-user row was inserted.
    assert len(rows) == 1
    assert rows[0]["user_id"] == mgmt_id
    assert rows[0]["student_id"] == sid
    assert all(r.get("user_id") for r in rows)


@pytest.mark.asyncio
async def test_smart_end_session_neg_behaviour_notifies_parent(tenant_a):
    # Happy path is unchanged: a linked parent still gets the repeated
    # negative-behaviour alert, stamped with the child's student_id.
    parent_id = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    sid = await _mk_student(tenant_a, class_id, parent_user_id=parent_id, name="Neg Two")

    eng = _engine()

    async def _no_mgmt(school_id):
        return []

    eng._resolve_management_recipient_ids = _no_mgmt

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await eng._send_smart_end_session_notifications(
        session_id=session_id,
        school_id=tenant_a,
        attendance=[],
        neg_students={sid: 3},
        student_interactions={},
        now=now,
    )

    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "entity_id": session_id, "user_id": parent_id,
    }, limit=10)
    assert len(rows) == 1
    assert rows[0]["student_id"] == sid
    assert rows[0]["category"] == "behaviour"


@pytest.mark.asyncio
async def test_end_session_completes_despite_notification_failure(tenant_a):
    # The core Task #1042 regression: a notification side effect that does a
    # poisoning failed flush must NOT abort the lesson completion. end_session
    # returns a summary, the session is marked COMPLETED, and the SESSION_ENDED
    # audit write (which used to crash with PendingRollbackError) succeeds.
    teacher = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = str(uuid.uuid4())
    start = datetime.now(timezone.utc)
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "teacher_id": teacher,
        "tenant_id": tenant_a,
        "school_id": tenant_a,
        "class_id": class_id,
        "subject_id": str(uuid.uuid4()),
        "status": "active",
        "attendance_approved": True,
        "start_time": start.isoformat(),
    })

    eng = _engine()

    # Isolate the test to the notification side effect: the other
    # post-completion side effects may make network/LLM calls.
    async def _noop(*a, **k):
        return None

    eng._update_student_profiles_after_session = _noop
    eng._trigger_session_analytics = _noop
    eng._generate_ai_session_insights = _noop

    # Simulate the original crash: a NULL-user_id notification insert that
    # poisons the shared session if it isn't isolated in a SAVEPOINT.
    async def _poison(*a, **k):
        await gd_insert(db.session, "notifications", {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_a,
            "user_id": None,
            "title": "x",
            "message": "y",
            "type": "alert",
            "category": "attendance",
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    eng._send_smart_end_session_notifications = _poison

    # Must NOT raise — the SAVEPOINT isolates the poisoning failure.
    result = await eng.end_session(session_id=session_id, teacher_id=teacher)
    assert result is not None

    # Core completion is durable.
    sess = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    assert sess["status"] == "completed"

    events = await gd_find(db.session, "session_event_log", {
        "session_id": session_id, "event_type": "session_ended",
    }, limit=10)
    assert len(events) == 1


@pytest.mark.asyncio
async def test_smart_end_session_absence_dedups_across_sessions_same_day(tenant_a):
    # Task #1040 — a student absent across several sessions on the same day
    # must yield AT MOST ONE absence alert per (parent, child, category) per
    # day, not one per period. (The absence branch fires once per session.)
    parent_id = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    sid = await _mk_student(tenant_a, class_id, parent_user_id=parent_id, name="Absent All Day")

    now = datetime.now(timezone.utc)
    engine = _engine()
    for _ in range(3):  # three separate sessions, same day
        await engine._send_smart_end_session_notifications(
            session_id=str(uuid.uuid4()),
            school_id=tenant_a,
            attendance=[{"student_id": sid, "status": "absent"}],
            neg_students={},
            student_interactions={},
            now=now,
        )

    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "user_id": parent_id, "category": "attendance",
    }, limit=20)
    assert len(rows) == 1
    assert rows[0].get("student_id") == sid


@pytest.mark.asyncio
async def test_smart_end_session_dedup_is_per_child(tenant_a):
    # Two different children each absent across two sessions: each parent
    # still gets exactly one alert for THEIR child (dedup is per-child, it
    # must not collapse distinct children into one).
    parent1 = await _mk_user("parent", tenant_a)
    parent2 = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    s1 = await _mk_student(tenant_a, class_id, parent_user_id=parent1, name="Child One")
    s2 = await _mk_student(tenant_a, class_id, parent_user_id=parent2, name="Child Two")

    now = datetime.now(timezone.utc)
    engine = _engine()
    for _ in range(2):
        await engine._send_smart_end_session_notifications(
            session_id=str(uuid.uuid4()),
            school_id=tenant_a,
            attendance=[
                {"student_id": s1, "status": "absent"},
                {"student_id": s2, "status": "absent"},
            ],
            neg_students={},
            student_interactions={},
            now=now,
        )

    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "category": "attendance",
    }, limit=20)
    by_user = {}
    for r in rows:
        by_user.setdefault(r["user_id"], []).append(r)
    assert len(by_user.get(parent1, [])) == 1
    assert len(by_user.get(parent2, [])) == 1
    assert by_user[parent1][0].get("student_id") == s1
    assert by_user[parent2][0].get("student_id") == s2


# ---------- student-targeted single send (Homework Reminder path) ----------
#
# The Teacher Communication Center "Homework Reminder" (Task #463 shape:
# `related_entity='student'` + `related_entity_id`, no recipient_id / no
# recipient_role) resolves the parent canonically but used to persist the
# row WITHOUT `student_id` — so the parent inbox could not render the child
# chip nor match the per-child filter for exactly these teacher-to-parent
# messages.


@pytest.mark.asyncio
async def test_student_targeted_send_stamps_student_id(client, tenant_a):
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    parent_id = await _mk_user("parent", tenant_a)
    sid = await _mk_student(tenant_a, class_id, parent_user_id=parent_id, name="ولد الواجب")

    title = f"تذكير بالواجب — {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/notifications",
        json={
            "title": title,
            "message": "نود تذكيركم بضرورة متابعة أداء الواجبات المنزلية لابنكم.",
            "notification_type": "communication",
            "priority": "medium",
            "related_entity": "student",
            "related_entity_id": sid,
            "template_id": "homework",
        },
        headers=_headers(teacher_id, "teacher", tenant_a),
    )
    assert resp.status_code == 200, resp.text

    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "title": title,
    }, limit=10)
    assert len(rows) == 1
    assert rows[0]["user_id"] == parent_id
    # The chip / per-child-filter source must be stamped at creation.
    assert rows[0].get("student_id") == sid


@pytest.mark.asyncio
async def test_student_targeted_send_get_returns_student_ref(client, tenant_a):
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    parent_id = await _mk_user("parent", tenant_a)
    sid = await _mk_student(tenant_a, class_id, parent_user_id=parent_id, name="بنت الواجب")

    title = f"تذكير بالواجب — {uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/notifications",
        json={
            "title": title,
            "message": "متابعة الواجبات.",
            "notification_type": "communication",
            "priority": "medium",
            "related_entity": "student",
            "related_entity_id": sid,
        },
        headers=_headers(teacher_id, "teacher", tenant_a),
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(
        "/notifications?limit=50",
        headers=_headers(parent_id, "parent", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    mine = [n for n in resp.json() if n["title"] == title]
    assert len(mine) == 1
    assert mine[0]["student"] is not None
    assert mine[0]["student"]["id"] == sid
    assert mine[0]["student"]["name_ar"] == "بنت الواجب"


@pytest.mark.asyncio
async def test_legacy_student_row_enriches_from_related_entity(client, tenant_a):
    # Rows written BEFORE the stamp fix have student_id=NULL but still carry
    # related_entity='student' + related_entity_id. The parent read path must
    # fall back to that pair so historical inboxes get the child chip too —
    # no backfill migration needed.
    class_id = await _mk_class(tenant_a)
    parent_id = await _mk_user("parent", tenant_a)
    sid = await _mk_student(tenant_a, class_id, parent_user_id=parent_id, name="طفل قديم")

    title = f"تذكير قديم — {uuid.uuid4().hex[:6]}"
    await gd_insert(db.session, "notifications", {
        "id": str(uuid.uuid4()),
        "user_id": parent_id,
        "title": title,
        "message": "رسالة قديمة بدون ختم الطالب.",
        "type": "communication",
        "priority": "medium",
        "related_entity": "student",
        "related_entity_id": sid,
        "tenant_id": tenant_a,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })

    resp = await client.get(
        "/notifications?limit=50",
        headers=_headers(parent_id, "parent", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    mine = [n for n in resp.json() if n["title"] == title]
    assert len(mine) == 1
    assert mine[0]["student"] is not None
    assert mine[0]["student"]["id"] == sid
    assert mine[0]["student"]["name_ar"] == "طفل قديم"


@pytest.mark.asyncio
async def test_non_student_related_entity_yields_no_student_ref(client, tenant_a):
    # A row whose related_entity is NOT 'student' (e.g. 'session') must never
    # be misread as a child reference by the read-path fallback.
    parent_id = await _mk_user("parent", tenant_a)

    title = f"ملخص — {uuid.uuid4().hex[:6]}"
    await gd_insert(db.session, "notifications", {
        "id": str(uuid.uuid4()),
        "user_id": parent_id,
        "title": title,
        "message": "x",
        "type": "communication",
        "priority": "medium",
        "related_entity": "session",
        "related_entity_id": str(uuid.uuid4()),
        "tenant_id": tenant_a,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })

    resp = await client.get(
        "/notifications?limit=50",
        headers=_headers(parent_id, "parent", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    mine = [n for n in resp.json() if n["title"] == title]
    assert len(mine) == 1
    assert mine[0]["student"] is None


@pytest.mark.asyncio
async def test_fallback_never_resolves_cross_tenant_student(client, tenant_a, tenant_b):
    # The read-path fallback consumes related_entity_id, which is
    # caller-writable at creation time. Even if a row points at a student
    # from ANOTHER tenant, the enrichment lookup must be scoped to the
    # parent's own school and return student=None — never the foreign
    # child's name (tenant-isolation invariant).
    class_b = await _mk_class(tenant_b)
    foreign_sid = await _mk_student(tenant_b, class_b, name="طالب مدرسة أخرى")

    parent_id = await _mk_user("parent", tenant_a)
    title = f"اختراق — {uuid.uuid4().hex[:6]}"
    await gd_insert(db.session, "notifications", {
        "id": str(uuid.uuid4()),
        "user_id": parent_id,
        "title": title,
        "message": "صف مزروع يشير إلى طالب خارج المدرسة.",
        "type": "communication",
        "priority": "medium",
        "related_entity": "student",
        "related_entity_id": foreign_sid,
        "tenant_id": tenant_a,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })

    resp = await client.get(
        "/notifications?limit=50",
        headers=_headers(parent_id, "parent", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    mine = [n for n in resp.json() if n["title"] == title]
    assert len(mine) == 1
    assert mine[0]["student"] is None
    assert "طالب مدرسة أخرى" not in resp.text
