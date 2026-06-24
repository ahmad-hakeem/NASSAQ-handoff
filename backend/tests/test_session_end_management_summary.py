"""
Task #486 — regression tests for the end-of-session summary delivery to
school management (school_principal + school_sub_admin) via
``SessionEngine._send_management_session_summary`` and the canonical
recipient resolver ``_resolve_management_recipient_ids``, plus the
``POST /notifications`` ``recipient_role='admin'`` alias.
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_insert
from engines.session_engine import TeacherSessionEngine as SessionEngine


def _headers(user_id: str, role: str, tenant_id):
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(role: str, tenant_id, *, active: bool = True) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": role,
        "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test",
        "full_name": f"{role}-{uid[:6]}",
        "is_active": active,
        "password_hash": "x",
    })
    return uid


def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session
    return SessionEngine(_DBShim())


@pytest.mark.asyncio
async def test_resolve_management_principal_priority(tenant_a):
    principal_id = await _mk_user("school_principal", tenant_a)
    sub_id = await _mk_user("school_sub_admin", tenant_a)

    ids = await _engine()._resolve_management_recipient_ids(tenant_a)

    assert principal_id in ids
    assert sub_id in ids
    # Principal must come first (canonical priority).
    assert ids.index(principal_id) < ids.index(sub_id)


@pytest.mark.asyncio
async def test_resolve_management_sub_admin_only(tenant_a):
    sub_id = await _mk_user("school_sub_admin", tenant_a)

    ids = await _engine()._resolve_management_recipient_ids(tenant_a)

    assert ids == [sub_id]


@pytest.mark.asyncio
async def test_resolve_management_school_admin_only(tenant_a):
    # Task #490 — many real-world tenants provision the principal /
    # vice-principal under role ``school_admin`` (the original cohort
    # omitted this and silently delivered nothing). Verify it resolves.
    admin_id = await _mk_user("school_admin", tenant_a)

    ids = await _engine()._resolve_management_recipient_ids(tenant_a)

    assert ids == [admin_id]


@pytest.mark.asyncio
async def test_resolve_management_full_cohort_priority(tenant_a):
    # All three management role strings present in the same tenant.
    # Principal-tier (school_principal + school_admin) must come before
    # school_sub_admin; the two principal-tier roles are equal-rank.
    principal_id = await _mk_user("school_principal", tenant_a)
    admin_id = await _mk_user("school_admin", tenant_a)
    sub_id = await _mk_user("school_sub_admin", tenant_a)

    ids = await _engine()._resolve_management_recipient_ids(tenant_a)

    assert set(ids) == {principal_id, admin_id, sub_id}
    assert ids.index(sub_id) > ids.index(principal_id)
    assert ids.index(sub_id) > ids.index(admin_id)


@pytest.mark.asyncio
async def test_send_management_summary_persists_to_school_admin(tenant_a):
    # Task #490 regression: end-of-session summary must reach the head
    # of school when their role is stored as ``school_admin``.
    admin_id = await _mk_user("school_admin", tenant_a)

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    sent = await _engine()._send_management_session_summary(
        session_id=session_id,
        tenant_id=tenant_a,
        subject_id=None,
        class_id=None,
        duration_minutes=30,
        present=10,
        absent=0,
        total=10,
        attendance_rate=100.0,
        questions_count=3,
        correct=3,
        engagement_rate=80.0,
        now=now,
    )

    assert sent == 1
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a,
        "entity_type": "session",
        "entity_id": session_id,
    }, limit=10)
    assert {r.get("user_id") for r in rows} == {admin_id}


@pytest.mark.asyncio
async def test_resolve_management_no_users_returns_empty(tenant_a):
    # Teacher and parent exist, but no management roles.
    await _mk_user("teacher", tenant_a)
    await _mk_user("parent", tenant_a)

    ids = await _engine()._resolve_management_recipient_ids(tenant_a)

    assert ids == []


@pytest.mark.asyncio
async def test_resolve_management_cross_tenant_isolation(tenant_a, tenant_b):
    a_principal = await _mk_user("school_principal", tenant_a)
    b_principal = await _mk_user("school_principal", tenant_b)

    ids_a = await _engine()._resolve_management_recipient_ids(tenant_a)
    ids_b = await _engine()._resolve_management_recipient_ids(tenant_b)

    assert ids_a == [a_principal]
    assert ids_b == [b_principal]
    assert a_principal not in ids_b
    assert b_principal not in ids_a


@pytest.mark.asyncio
async def test_resolve_management_skips_inactive(tenant_a):
    active_id = await _mk_user("school_principal", tenant_a, active=True)
    await _mk_user("school_principal", tenant_a, active=False)

    ids = await _engine()._resolve_management_recipient_ids(tenant_a)

    assert ids == [active_id]


@pytest.mark.asyncio
async def test_resolve_management_independent_teacher_is_empty():
    itw_tenant = f"itw_{uuid.uuid4().hex}"
    # IT workspaces have no management recipient by design — the
    # resolver short-circuits on the ``itw_`` prefix regardless of
    # what the users table looks like.
    ids = await _engine()._resolve_management_recipient_ids(itw_tenant)

    assert ids == []


@pytest.mark.asyncio
async def test_send_management_summary_persists_per_recipient(tenant_a):
    principal_id = await _mk_user("school_principal", tenant_a)
    sub_id = await _mk_user("school_sub_admin", tenant_a)

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    sent = await _engine()._send_management_session_summary(
        session_id=session_id,
        tenant_id=tenant_a,
        subject_id=None,
        class_id=None,
        duration_minutes=42,
        present=18,
        absent=2,
        total=20,
        attendance_rate=90.0,
        questions_count=5,
        correct=4,
        engagement_rate=75.0,
        now=now,
    )

    assert sent == 2
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a,
        "entity_type": "session",
        "entity_id": session_id,
    }, limit=10)
    user_ids = {r.get("user_id") for r in rows}
    assert principal_id in user_ids
    assert sub_id in user_ids
    for r in rows:
        # Tenant-scoping invariant: persisted tenant_id must equal the
        # session's tenant, never widened.
        assert r.get("tenant_id") == tenant_a


@pytest.mark.asyncio
async def test_send_management_summary_no_recipients_is_noop(tenant_a):
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    sent = await _engine()._send_management_session_summary(
        session_id=session_id,
        tenant_id=tenant_a,
        subject_id=None,
        class_id=None,
        duration_minutes=10,
        present=1,
        absent=0,
        total=1,
        attendance_rate=100.0,
        questions_count=0,
        correct=0,
        engagement_rate=0.0,
        now=now,
    )

    assert sent == 0
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a,
        "entity_type": "session",
        "entity_id": session_id,
    }, limit=10)
    assert rows == []


@pytest.mark.asyncio
async def test_send_management_summary_independent_teacher_is_noop():
    itw_tenant = f"itw_{uuid.uuid4().hex}"
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    sent = await _engine()._send_management_session_summary(
        session_id=session_id,
        tenant_id=itw_tenant,
        subject_id=None,
        class_id=None,
        duration_minutes=30,
        present=5,
        absent=0,
        total=5,
        attendance_rate=100.0,
        questions_count=3,
        correct=3,
        engagement_rate=80.0,
        now=now,
    )

    assert sent == 0
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": itw_tenant,
        "entity_type": "session",
        "entity_id": session_id,
    }, limit=10)
    assert rows == []


# ---------- POST /notifications recipient_role='admin' alias ----------

@pytest.mark.asyncio
async def test_post_notifications_admin_alias_targets_management(client, tenant_a):
    principal_id = await _mk_user("school_principal", tenant_a)
    sub_id = await _mk_user("school_sub_admin", tenant_a)
    teacher_id = await _mk_user("teacher", tenant_a)

    resp = await client.post(
        "/notifications",
        json={
            "title": "Session Summary — Test",
            "message": "End of session report.",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "admin",
            "related_entity": "session",
            "related_entity_id": str(uuid.uuid4()),
        },
        headers=_headers(teacher_id, "teacher", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("created_count") == 2

    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a,
        "title": "Session Summary — Test",
    }, limit=10)
    user_ids = {r.get("user_id") for r in rows}
    assert user_ids == {principal_id, sub_id}


@pytest.mark.asyncio
async def test_post_notifications_admin_alias_includes_school_admin(client, tenant_a):
    # Task #490 — the ``admin`` alias must also resolve ``school_admin``
    # users (most common provisioned role for the head of school).
    admin_id = await _mk_user("school_admin", tenant_a)
    teacher_id = await _mk_user("teacher", tenant_a)

    resp = await client.post(
        "/notifications",
        json={
            "title": "Session Summary — Admin",
            "message": "End of session report.",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "admin",
            "related_entity": "session",
            "related_entity_id": str(uuid.uuid4()),
        },
        headers=_headers(teacher_id, "teacher", tenant_a),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("created_count") == 1

    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a,
        "title": "Session Summary — Admin",
    }, limit=10)
    assert {r.get("user_id") for r in rows} == {admin_id}


@pytest.mark.asyncio
async def test_post_notifications_admin_alias_safe_404_when_empty(client, tenant_a):
    teacher_id = await _mk_user("teacher", tenant_a)
    # No principal / sub-admin in this tenant.

    resp = await client.post(
        "/notifications",
        json={
            "title": "x",
            "message": "y",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "admin",
        },
        headers=_headers(teacher_id, "teacher", tenant_a),
    )
    assert resp.status_code == 404
    # Safe Arabic message — never raw exception strings. Error envelope
    # is wrapped by the global exception handler.
    body = resp.json()
    detail = body.get("detail") or body.get("error", {}).get("message", "")
    assert "بهذا الدور" in detail


# ---------- end_session integration: management delivery + truthful response ----------

async def _seed_minimal_session(tenant_id: str) -> tuple:
    """Insert the minimum rows the end_session pipeline needs and return
    (session_id, teacher_id, student_id)."""
    teacher_id = str(uuid.uuid4())
    class_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())

    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": tenant_id, "tenant_id": tenant_id,
        "name": "Math", "name_ar": "رياضيات", "name_en": "Math",
    })
    await gd_insert(db.session, "students", {
        "id": student_id, "school_id": tenant_id, "tenant_id": tenant_id,
        "full_name": "S1", "class_id": class_id, "is_active": True,
    })
    start_iso = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "tenant_id": tenant_id,
        "school_id": tenant_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "date": start_iso[:10],
        "start_time": start_iso,
        "status": "in_progress",
        "attendance_approved": True,
    })
    await gd_insert(db.session, "session_attendance", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "status": "present",
    })
    return session_id, teacher_id, student_id


@pytest.mark.asyncio
async def test_end_session_persists_management_summary_and_reports_count(tenant_a):
    principal_id = await _mk_user("school_principal", tenant_a)
    session_id, teacher_id, _ = await _seed_minimal_session(tenant_a)

    summary = await _engine().end_session(session_id=session_id, teacher_id=teacher_id)

    assert summary.management_notifications_sent == 1
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "entity_type": "session", "entity_id": session_id,
    }, limit=10)
    assert any(r.get("user_id") == principal_id for r in rows)


@pytest.mark.asyncio
async def test_end_session_no_management_reports_zero_and_does_not_raise(tenant_a):
    # No principal / sub-admin in this tenant — the toast must fall
    # back to parents-only on the FE, driven by this field being 0.
    session_id, teacher_id, _ = await _seed_minimal_session(tenant_a)

    summary = await _engine().end_session(session_id=session_id, teacher_id=teacher_id)

    assert summary.management_notifications_sent == 0
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "entity_type": "session", "entity_id": session_id,
    }, limit=10)
    assert rows == []


@pytest.mark.asyncio
async def test_end_session_does_not_resolve_cross_tenant_principal(tenant_a, tenant_b):
    # Principal exists only in tenant_b. The session is in tenant_a.
    # Cross-tenant delivery must be impossible.
    await _mk_user("school_principal", tenant_b)
    session_id, teacher_id, _ = await _seed_minimal_session(tenant_a)

    summary = await _engine().end_session(session_id=session_id, teacher_id=teacher_id)

    assert summary.management_notifications_sent == 0
    rows = await gd_find(db.session, "notifications", {
        "entity_type": "session", "entity_id": session_id,
    }, limit=10)
    assert rows == []


# ---------- teacher name embedded in the management summary ----------
# The principal's "ملخص الحصة" card must name the teacher who conducted the
# session (visible content), not just subject/class/stats.

@pytest.mark.asyncio
async def test_send_management_summary_includes_teacher_name(tenant_a):
    admin_id = await _mk_user("school_admin", tenant_a)
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": tenant_a, "full_name": "أ. محمد الفارابي",
    })

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    sent = await _engine()._send_management_session_summary(
        session_id=session_id, tenant_id=tenant_a, subject_id=None, class_id=None,
        duration_minutes=30, present=10, absent=0, total=10, attendance_rate=100.0,
        questions_count=3, correct=3, engagement_rate=80.0, now=now,
        teacher_id=teacher_id,
    )

    assert sent == 1
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "entity_type": "session", "entity_id": session_id,
    }, limit=10)
    assert len(rows) == 1
    row = rows[0]
    # Visible content (both locales) names the teacher.
    assert "أ. محمد الفارابي" in (row.get("message") or "")
    assert "أ. محمد الفارابي" in (row.get("message_en") or "")
    # Stable structured value for the FE / future use.
    data = row.get("data") or {}
    assert data.get("teacher_name") == "أ. محمد الفارابي"
    assert data.get("teacher_id") == teacher_id


@pytest.mark.asyncio
async def test_send_management_summary_resolves_teacher_via_users_fallback(tenant_a):
    # No authoritative ``teachers`` row — only a ``users`` row carrying the
    # ``teacher_id`` (the canonical fallback path used by start_session).
    await _mk_user("school_admin", tenant_a)
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": str(uuid.uuid4()), "role": "teacher", "tenant_id": tenant_a,
        "email": f"t-{teacher_id[:8]}@t.test", "full_name": "Mr Fallback Resolved",
        "teacher_id": teacher_id, "is_active": True, "password_hash": "x",
    })

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    sent = await _engine()._send_management_session_summary(
        session_id=session_id, tenant_id=tenant_a, subject_id=None, class_id=None,
        duration_minutes=20, present=5, absent=0, total=5, attendance_rate=100.0,
        questions_count=1, correct=1, engagement_rate=50.0, now=now,
        teacher_id=teacher_id,
    )

    assert sent == 1
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "entity_type": "session", "entity_id": session_id,
    }, limit=10)
    assert "Mr Fallback Resolved" in (rows[0].get("message") or "")


@pytest.mark.asyncio
async def test_send_management_summary_omits_teacher_when_unresolved(tenant_a):
    # Teacher cannot be resolved (no teachers/users row) — degrade gracefully:
    # no crash, no dangling "مع المعلم" with an empty name, no teacher in data.
    await _mk_user("school_admin", tenant_a)

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    sent = await _engine()._send_management_session_summary(
        session_id=session_id, tenant_id=tenant_a, subject_id=None, class_id=None,
        duration_minutes=10, present=1, absent=0, total=1, attendance_rate=100.0,
        questions_count=0, correct=0, engagement_rate=0.0, now=now,
        teacher_id=str(uuid.uuid4()),
    )

    assert sent == 1
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "entity_type": "session", "entity_id": session_id,
    }, limit=10)
    msg = rows[0].get("message") or ""
    assert "مع المعلم" not in msg
    assert (rows[0].get("data") or {}).get("teacher_name") is None


@pytest.mark.asyncio
async def test_end_session_summary_message_names_teacher(tenant_a):
    # Full integration: end_session must pass the conducting teacher through
    # so the persisted management notification names them.
    principal_id = await _mk_user("school_principal", tenant_a)
    session_id, teacher_id, _ = await _seed_minimal_session(tenant_a)
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": tenant_a, "full_name": "أ. سارة المعلمة",
    })

    summary = await _engine().end_session(session_id=session_id, teacher_id=teacher_id)

    assert summary.management_notifications_sent == 1
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "entity_type": "session", "entity_id": session_id,
    }, limit=10)
    prow = next(r for r in rows if r.get("user_id") == principal_id)
    assert "أ. سارة المعلمة" in (prow.get("message") or "")


@pytest.mark.asyncio
async def test_end_session_names_teacher_when_actor_is_users_id(tenant_a):
    # Route-realistic: the end-session route passes ``current_user["id"]`` (a
    # ``users.id``), which differs from the session's canonical ``teachers.id``.
    # The summary must still name the conducting teacher (resolved from the
    # session owner), not the actor's login name and not a blank.
    principal_id = await _mk_user("school_principal", tenant_a)
    teacher_rec_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_rec_id, "school_id": tenant_a, "full_name": "أ. خالد القائد",
    })
    await gd_insert(db.session, "users", {
        "id": user_id, "role": "teacher", "tenant_id": tenant_a,
        "email": f"t-{user_id[:8]}@t.test", "full_name": "Login Name Ignored",
        "teacher_id": teacher_rec_id, "is_active": True, "password_hash": "x",
    })

    class_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": tenant_a, "tenant_id": tenant_a, "name": "2B",
    })
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": tenant_a, "tenant_id": tenant_a,
        "name": "Science", "name_ar": "علوم", "name_en": "Science",
    })
    await gd_insert(db.session, "students", {
        "id": student_id, "school_id": tenant_a, "tenant_id": tenant_a,
        "full_name": "S2", "class_id": class_id, "is_active": True,
    })
    start_iso = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id, "tenant_id": tenant_a, "school_id": tenant_a,
        "class_id": class_id, "subject_id": subject_id, "teacher_id": teacher_rec_id,
        "date": start_iso[:10], "start_time": start_iso, "status": "in_progress",
        "attendance_approved": True,
    })
    await gd_insert(db.session, "session_attendance", {
        "id": str(uuid.uuid4()), "session_id": session_id,
        "student_id": student_id, "status": "present",
    })

    summary = await _engine().end_session(session_id=session_id, teacher_id=user_id)

    assert summary.management_notifications_sent == 1
    rows = await gd_find(db.session, "notifications", {
        "tenant_id": tenant_a, "entity_type": "session", "entity_id": session_id,
    }, limit=10)
    prow = next(r for r in rows if r.get("user_id") == principal_id)
    msg = prow.get("message") or ""
    assert "أ. خالد القائد" in msg
    assert "Login Name Ignored" not in msg
    assert (prow.get("data") or {}).get("teacher_name") == "أ. خالد القائد"


@pytest.mark.asyncio
async def test_end_session_with_closing_note_when_actor_is_users_id(tenant_a):
    # Regression: ending a session WITH a closing note must not raise a
    # foreign-key violation. The route passes ``current_user["id"]`` (a
    # ``users.id``), but ``session_notes.teacher_id`` references
    # ``teachers.id``. The closing-note row must be attributed to the
    # session's canonical ``teachers.id``, never the actor's ``users.id``.
    teacher_rec_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_rec_id, "school_id": tenant_a, "full_name": "أ. منى",
    })
    await gd_insert(db.session, "users", {
        "id": user_id, "role": "teacher", "tenant_id": tenant_a,
        "email": f"t-{user_id[:8]}@t.test", "full_name": "Login Name",
        "teacher_id": teacher_rec_id, "is_active": True, "password_hash": "x",
    })

    class_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": tenant_a, "tenant_id": tenant_a, "name": "3C",
    })
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": tenant_a, "tenant_id": tenant_a,
        "name": "Arabic", "name_ar": "عربي", "name_en": "Arabic",
    })
    await gd_insert(db.session, "students", {
        "id": student_id, "school_id": tenant_a, "tenant_id": tenant_a,
        "full_name": "S3", "class_id": class_id, "is_active": True,
    })
    start_iso = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id, "tenant_id": tenant_a, "school_id": tenant_a,
        "class_id": class_id, "subject_id": subject_id, "teacher_id": teacher_rec_id,
        "date": start_iso[:10], "start_time": start_iso, "status": "in_progress",
        "attendance_approved": True,
    })
    await gd_insert(db.session, "session_attendance", {
        "id": str(uuid.uuid4()), "session_id": session_id,
        "student_id": student_id, "status": "present",
    })

    # Must not raise (previously: ForeignKeyViolation -> INVALID_REFERENCE).
    summary = await _engine().end_session(
        session_id=session_id, teacher_id=user_id,
        closing_note="ملاحظة ختامية للحصة",
    )
    assert summary is not None

    # The closing-note row exists and is attributed to the canonical
    # teachers.id, never the actor's users.id.
    notes = await gd_find(db.session, "session_notes", {
        "session_id": session_id,
    }, limit=10)
    assert len(notes) == 1
    assert notes[0].get("teacher_id") == teacher_rec_id
    assert notes[0].get("teacher_id") != user_id
