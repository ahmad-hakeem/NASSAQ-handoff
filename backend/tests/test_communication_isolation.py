"""
Regression tests for Task #177 — Communication cross-tenant leak fix
(Phase 0 hotfix B-3 from the Independent Teacher phased spec, §4.3).

Goal: prove the recipient cohort builders in
``backend/routes/communication_routes.py`` and
``backend/engines/school_notification_engine.py`` never include users
from another tenant. The headline scenario the spec calls out is
"Independent Teacher A broadcasts -> only A's own students/parents
receive, never another independent teacher's family".

These tests do NOT change who is allowed to send a message — that gate
moves with Phase 1 §5.6. They only assert the recipient resolution is
already tenant-scoped so the messaging power can be granted later
without leaking data.
"""
import uuid

import pytest
import pytest_asyncio

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_insert
from routes.communication_routes import _resolve_recipient_ids
from engines.school_notification_engine import (
    SchoolNotificationEngine,
    RecipientType,
)


def _headers(user_id: str, role: str, tenant_id):
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(role: UserRole, tenant_id, *, email_prefix: str = "u") -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": role.value,
        "tenant_id": tenant_id,
        "email": f"{email_prefix}-{uid}@t.test",
        "full_name": f"{role.value}-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    return uid


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"S-{school_id[:6]}",
        "code": f"C{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


async def _mk_independent_teacher_with_students(*, n_students: int = 1):
    """Seed an Independent Teacher with their workspace and `n_students`
    student users plus a parent user per student, all keyed to the same
    `itw_{user_id}` tenant. Returns the IT user id, workspace id, and the
    set of recipient user ids (students + parents) the IT should be able
    to reach.
    """
    it_uid = await _mk_user(UserRole.INDEPENDENT_TEACHER, None, email_prefix="it")
    workspace_id = f"itw_{it_uid}"
    await _mk_school(workspace_id)
    # Backfill the workspace tenant id on the IT's user row, mirroring the
    # post-bootstrap state that Phase 1 §5.1 will materialise.
    from sqlalchemy import update
    from pg_models import User
    await db.session.execute(
        update(User).where(User.id == it_uid).values(tenant_id=workspace_id)
    )

    expected_recipients = set()
    for _ in range(n_students):
        sid = await _mk_user(UserRole.STUDENT, workspace_id, email_prefix="s")
        pid = await _mk_user(UserRole.PARENT, workspace_id, email_prefix="p")
        expected_recipients.add(sid)
        expected_recipients.add(pid)
    return it_uid, workspace_id, expected_recipients


# ---------------------------------------------------------------------------
# (1) Helper-level isolation: `_resolve_recipient_ids` and
#     `SchoolNotificationEngine._resolve_recipients` must each scope by
#     tenant and never bleed across two co-existing IT workspaces.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_independent_teacher_recipient_resolution_is_tenant_scoped():
    """Two independent teachers each have a student + a parent in their
    own workspace. The recipient cohort returned for IT-A must be exactly
    A's own users; it must never include any user from IT-B's workspace.
    """
    a_uid, a_ws, a_expected = await _mk_independent_teacher_with_students()
    b_uid, b_ws, b_expected = await _mk_independent_teacher_with_students()

    # Helper used by `POST /communication`.
    students_for_a = await _resolve_recipient_ids(db, "students", a_ws, [])
    parents_for_a = await _resolve_recipient_ids(db, "parents", a_ws, [])
    students_for_b = await _resolve_recipient_ids(db, "students", b_ws, [])
    parents_for_b = await _resolve_recipient_ids(db, "parents", b_ws, [])

    # A reaches only A's family; same for B.
    a_reach = set(students_for_a) | set(parents_for_a)
    b_reach = set(students_for_b) | set(parents_for_b)
    assert a_reach == a_expected
    assert b_reach == b_expected
    assert a_reach.isdisjoint(b_reach)

    # Engine-level cohort builder used by `POST /notifications/send`.
    engine = SchoolNotificationEngine(db)
    a_students_eng = await engine._resolve_recipients(
        RecipientType.all_students, None, a_ws
    )
    a_parents_eng = await engine._resolve_recipients(
        RecipientType.all_parents, None, a_ws
    )
    a_eng_reach = {r["user_id"] for r in a_students_eng + a_parents_eng}
    assert a_eng_reach == a_expected
    assert a_eng_reach.isdisjoint(b_expected)


@pytest.mark.asyncio
async def test_recipient_resolution_fails_closed_without_tenant():
    """A non-platform caller whose tenant cannot be resolved (school_id is
    falsy) must get an empty cohort, not the unscoped global users list.
    Same guarantee at the engine layer.
    """
    # Seed *some* users so an unscoped query would clearly return >0.
    await _mk_independent_teacher_with_students()
    await _mk_independent_teacher_with_students()

    assert await _resolve_recipient_ids(db, "students", None, []) == []
    assert await _resolve_recipient_ids(db, "parents", None, []) == []
    assert await _resolve_recipient_ids(db, "teachers", None, []) == []
    assert await _resolve_recipient_ids(db, "all", None, []) == []
    assert await _resolve_recipient_ids(db, "custom", None, ["x", "y"]) == []

    # Platform admin opt-in path is still allowed to be cross-tenant.
    cross = await _resolve_recipient_ids(
        db, "students", None, [], allow_platform_wide=True,
    )
    assert len(cross) >= 4  # at minimum the 4 students seeded above

    engine = SchoolNotificationEngine(db)
    no_tenant = await engine._resolve_recipients(
        RecipientType.all_students, None, ""
    )
    assert no_tenant == []


# ---------------------------------------------------------------------------
# (2) Route-level isolation: `POST /communication` must fan-out per-user
#     `notifications` rows scoped to the sender's tenant. We exercise the
#     SCHOOL_PRINCIPAL path here because that role is allowed to send
#     today; once Phase 1 §5.6 grants `NOTIFICATIONS_SEND` to IT, the
#     same guarantee must continue to hold (covered by the helper-level
#     tests above which call the cohort builder directly).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_principal_broadcast_only_reaches_own_tenant(client, tenant_a, tenant_b):
    """A school principal in tenant A broadcasts to "students". Only
    tenant A's student users may receive the resulting notification rows
    — never tenant B's students. This guards the existing principal flow
    against regression from the B-3 hotfix.
    """
    principal_uid = await _mk_user(
        UserRole.SCHOOL_PRINCIPAL, tenant_a, email_prefix="prin"
    )
    a_student = await _mk_user(UserRole.STUDENT, tenant_a, email_prefix="sa")
    b_student = await _mk_user(UserRole.STUDENT, tenant_b, email_prefix="sb")

    headers = _headers(
        principal_uid, UserRole.SCHOOL_PRINCIPAL.value, tenant_a
    )
    res = await client.post(
        "/communication",
        json={
            "title": "hello",
            "content": "world",
            "audience": "students",
            "audience_ids": [],
            "channels": ["in_app"],
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text

    # Notifications fanned out to A's student only.
    a_rows = await gd_find(
        db.session, "notifications", {"user_id": a_student}, limit=10
    )
    b_rows = await gd_find(
        db.session, "notifications", {"user_id": b_student}, limit=10
    )
    assert len(a_rows) == 1, a_rows
    assert b_rows == [], b_rows
    # And every fanned-out row carries A's tenant id.
    assert a_rows[0].get("tenant_id") == tenant_a
