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
from engines.sql_utils import gd_find, gd_insert
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
