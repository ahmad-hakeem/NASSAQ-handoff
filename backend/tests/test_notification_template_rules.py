"""Pinning tests for the Communication-Center template → recipient
cohort guard added in `routes/notification_routes_mod.py`.

Spec: the FE Teacher Communication Center sends a `template_id` with
each `POST /notifications`. Templates listed in
`TEMPLATE_RECIPIENT_RULES` are restrictive; the backend MUST fail-closed
when the recipient cohort does not match, even if the FE filter is
bypassed (curl / tampered client). Templates not listed remain
unrestricted so existing flows are unaffected.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _headers(user: dict) -> dict:
    token = create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(role: UserRole, tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": f"{role.value}-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


@pytest_asyncio.fixture
async def teacher_user(tenant_a):
    return await _mk_user(UserRole.TEACHER, tenant_a)


@pytest_asyncio.fixture
async def parent_user(tenant_a):
    return await _mk_user(UserRole.PARENT, tenant_a)


@pytest_asyncio.fixture
async def vp_user(tenant_a):
    # vice principal maps to school_sub_admin under the FE role map.
    return await _mk_user(UserRole.SCHOOL_SUB_ADMIN, tenant_a)


def _payload(template_id: str, **overrides) -> dict:
    body = {
        "title": "T",
        "message": "M",
        "notification_type": "communication",
        "priority": "medium",
        "template_id": template_id,
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_homework_template_allows_parent_recipient_id(
    client, teacher_user, parent_user
):
    """Homework Reminder + a parent user → 200 (allowed cohort)."""
    res = await client.post(
        "/notifications",
        json=_payload("homework", recipient_id=parent_user["id"]),
        headers=_headers(teacher_user),
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_homework_template_rejects_role_broadcast(
    client, teacher_user
):
    """Homework Reminder + role broadcast (admin/staff) → 403, never a
    silent send. The FE filter hides these cards; the backend is the
    fail-closed boundary."""
    res = await client.post(
        "/notifications",
        json=_payload("homework", recipient_role="school_sub_admin"),
        headers=_headers(teacher_user),
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_homework_template_rejects_non_parent_recipient_id(
    client, teacher_user, vp_user
):
    """Homework Reminder + a non-parent user id (e.g. a vice principal)
    is rejected — recipient role is resolved server-side."""
    res = await client.post(
        "/notifications",
        json=_payload("homework", recipient_id=vp_user["id"]),
        headers=_headers(teacher_user),
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_unrestricted_template_allows_role_broadcast(
    client, teacher_user, vp_user
):
    """A template not listed in `TEMPLATE_RECIPIENT_RULES` (e.g.
    `meeting`) preserves the legacy "all cohorts allowed" behaviour, so
    role-broadcast still works for non-IT senders."""
    res = await client.post(
        "/notifications",
        json=_payload("meeting", recipient_role="school_sub_admin"),
        headers=_headers(teacher_user),
    )
    # The role-broadcast path requires at least one matching user;
    # `vp_user` was seeded above into tenant_a as school_sub_admin, so
    # the send must succeed.
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_homework_template_rejects_non_parent_user_even_if_in_students_parent_id(
    client, teacher_user, vp_user, tenant_a
):
    """Regression for the cohort-bypass the architect flagged: a
    non-parent user id (e.g. a vice principal) that happens to appear in
    `students.parent_id` MUST still be rejected. The template guard
    resolves the recipient through `users.role`, never through a
    permissive student fallback."""
    # Seed a parents row keyed to the VP's user id so the FK on
    # students.parent_id is satisfied. This is the worst-case shape the
    # earlier permissive fallback would have admitted.
    await gd_insert(db.session, "parents", {
        "id": vp_user["id"],
        "full_name": "edge-parent",
        "email": f"edge-{vp_user['id']}@t.test",
        "school_id": tenant_a,
        "is_active": True,
    })
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": tenant_a,
        "full_name": f"ST-{sid[:6]}",
        "parent_id": vp_user["id"],
        "is_active": True,
    })
    res = await client.post(
        "/notifications",
        json=_payload("homework", recipient_id=vp_user["id"]),
        headers=_headers(teacher_user),
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_homework_template_rejects_dual_field_role_and_non_parent_id(
    client, teacher_user, vp_user
):
    """Architect regression: a tampered request that supplies an
    *allowed* `recipient_role` together with a *non-allowed*
    `recipient_id` must NOT slip through. The route would otherwise
    deliver to `recipient_id` (single-recipient branch), so the guard
    must validate every supplied selector independently."""
    res = await client.post(
        "/notifications",
        json=_payload(
            "homework",
            recipient_role="parent",
            recipient_id=vp_user["id"],
        ),
        headers=_headers(teacher_user),
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_teacher_role_broadcast_with_student_tag_is_rejected(
    client, teacher_user
):
    """Safety net for the removed 'Student Counselor under Management'
    sub-flow. The only wire shape that variant produced was a teacher
    role-broadcast carrying `related_entity='student'`. With the FE
    sub-option gone, a teacher request that still carries this combo
    must be a tampered/legacy client — reject 403."""
    res = await client.post(
        "/notifications",
        json={
            "title": "T",
            "message": "M",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "school_sub_admin",
            "related_entity": "student",
            "related_entity_id": "any-id",
        },
        headers=_headers(teacher_user),
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_teacher_general_admin_broadcast_still_allowed(
    client, teacher_user, tenant_a
):
    """The Management → General Admin Notice path (recipient_role
    'school_principal' with no related_entity) must still succeed —
    that is the surviving canonical Management variant."""
    # Seed a principal so the role-broadcast resolution finds at least one user.
    await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    res = await client.post(
        "/notifications",
        json={
            "title": "T",
            "message": "M",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_role": "school_principal",
        },
        headers=_headers(teacher_user),
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_homework_template_resolves_parent_via_guardian_links(
    client, teacher_user, tenant_a
):
    """Task #463 — FE sends `related_entity='student' +
    related_entity_id=<student.id>` and the backend resolves the parent
    users.id via active guardian_links (canonical path). The resulting
    notification row must be addressed to that parent user."""
    # Parent user (only, no parents row needed for the canonical path).
    parent_user = await _mk_user(UserRole.PARENT, tenant_a)
    # Student with NO `parent_id` so we exercise the guardian_links
    # path exclusively — no legacy fallback can mask a missing canonical
    # row.
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": tenant_a,
        "full_name": f"ST-{sid[:6]}",
        "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "parent_ref": parent_user["id"],
        "student_id": sid,
        "relationship": "guardian",
        "tenant_id": tenant_a,
        "is_active": True,
    })
    res = await client.post(
        "/notifications",
        json=_payload(
            "homework",
            related_entity="student",
            related_entity_id=sid,
        ),
        headers=_headers(teacher_user),
    )
    assert res.status_code == 200, res.text
    # Notification row must be delivered to the resolved parent user.
    from engines.sql_utils import gd_find_one as _find
    row = await _find(db.session, "notifications", {"user_id": parent_user["id"]})
    assert row is not None, "no notification persisted for resolved parent"


@pytest.mark.asyncio
async def test_homework_template_student_with_no_linked_parent_returns_safe_404(
    client, teacher_user, tenant_a
):
    """No active guardian_links AND no canonical `students.parent_id →
    users.id` mapping → safe Arabic 404, not the generic FE error."""
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": tenant_a,
        "full_name": f"ST-{sid[:6]}",
        "is_active": True,
    })
    res = await client.post(
        "/notifications",
        json=_payload(
            "homework",
            related_entity="student",
            related_entity_id=sid,
        ),
        headers=_headers(teacher_user),
    )
    assert res.status_code == 404, res.text
    body = res.json()
    # API wraps HTTPException in {error: {message}}; tolerate either shape.
    detail = body.get("detail") or (body.get("error") or {}).get("message") or ""
    assert "ولي أمر" in detail, body


@pytest.mark.asyncio
async def test_homework_template_cross_tenant_student_returns_404(
    client, teacher_user, tenant_a, tenant_b
):
    """A student in another tenant must NOT leak: the resolver is
    tenant-scoped, so a cross-tenant student id returns the safe 404
    (no 403, no cross-tenant disclosure)."""
    other_parent = await _mk_user(UserRole.PARENT, tenant_b)
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": tenant_b,
        "full_name": f"ST-{sid[:6]}",
        "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "parent_ref": other_parent["id"],
        "student_id": sid,
        "relationship": "guardian",
        "tenant_id": tenant_b,
        "is_active": True,
    })
    res = await client.post(
        "/notifications",
        json=_payload(
            "homework",
            related_entity="student",
            related_entity_id=sid,
        ),
        headers=_headers(teacher_user),
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_no_template_id_preserves_legacy_behaviour(
    client, teacher_user, vp_user
):
    """Callers that omit `template_id` (every legacy/non-FE caller) skip
    the guard entirely — no regression for engines that pre-date the
    Communication Center."""
    res = await client.post(
        "/notifications",
        json={
            "title": "T",
            "message": "M",
            "notification_type": "communication",
            "priority": "medium",
            "recipient_id": vp_user["id"],
        },
        headers=_headers(teacher_user),
    )
    assert res.status_code == 200, res.text
