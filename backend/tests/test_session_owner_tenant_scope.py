"""Regression tests for the cross-tenant authorization hole in
`_verify_session_owner` (the chokepoint for every `/session/{id}` by-id route).

Pre-fix behaviour (the bug):
  * The session was fetched globally by id with NO tenant filter.
  * Any caller whose `role` was in `ADMIN_ROLES` (which includes the
    school-scoped `school_admin`) skipped every check -> cross-tenant
    read+write IDOR on every session-by-id route.
  * A non-owner foreign caller got 403, confirming the foreign session
    exists (IT spec §8 invariant 3 requires 404, never 403/200).

Post-fix guarantees verified here:
  * Owner -> 200.
  * Same-tenant school_admin (monitoring) -> 200 (flow preserved).
  * Cross-tenant teacher -> 404 (not 403).
  * Cross-tenant school_admin -> 404 (IDOR closed, not 200).
  * Cross-tenant WRITE (PUT attendance) -> 404 before any engine work.
  * Independent-Teacher cross-workspace -> 404.
"""
from __future__ import annotations

import uuid

import pytest
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _tok(*, user_id: str, role: str, tenant_id: str) -> dict:
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


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


async def _mk_teacher_user(school_id: str) -> tuple[dict, str]:
    """Teacher user + its linked `teachers` row. current_user.teacher_id
    auto-links to teachers.id (by user_id), which is what start_session pins
    on class_sessions.teacher_id."""
    user = await _mk_user(UserRole.TEACHER, school_id)
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": school_id,
        "user_id": user["id"],
        "full_name": f"T-{teacher_id[:6]}",
        "email": user["email"],
        "preferences": {},
        "constraints": {},
    })
    return user, teacher_id


async def _mk_session(school_id: str, teacher_id: str) -> str:
    sid = str(uuid.uuid4())
    cls = str(uuid.uuid4())
    subj = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cls, "school_id": school_id, "tenant_id": school_id, "name": "1A",
    })
    await gd_insert(db.session, "class_sessions", {
        "id": sid,
        "teacher_id": teacher_id,
        "class_id": cls,
        "subject_id": subj,
        "school_id": school_id,
        "date": "2026-06-22",
        "status": "attendance_in_progress",
        "attendance_approved": False,
    })
    return sid


@pytest.mark.asyncio
async def test_owner_can_read_own_session(client):
    school = str(uuid.uuid4())
    await _mk_school(school)
    teacher, teacher_id = await _mk_teacher_user(school)
    sid = await _mk_session(school, teacher_id)

    res = await client.get(
        f"/session/{sid}",
        headers=_tok(user_id=teacher["id"], role=teacher["role"], tenant_id=school),
    )
    assert res.status_code == 200, res.text
    assert res.json()["id"] == sid


@pytest.mark.asyncio
async def test_same_tenant_school_admin_can_monitor(client):
    """Monitoring flow preserved: a same-tenant school_admin keeps read access
    to a teacher's session."""
    school = str(uuid.uuid4())
    await _mk_school(school)
    _teacher, teacher_id = await _mk_teacher_user(school)
    sid = await _mk_session(school, teacher_id)

    admin = await _mk_user(UserRole.SCHOOL_ADMIN, school)
    res = await client.get(
        f"/session/{sid}",
        headers=_tok(user_id=admin["id"], role=admin["role"], tenant_id=school),
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_cross_tenant_teacher_gets_404_not_403(client):
    """A teacher from another school must get 404 (never 403, which would
    confirm the foreign session exists)."""
    school_a = str(uuid.uuid4())
    school_b = str(uuid.uuid4())
    await _mk_school(school_a)
    await _mk_school(school_b)
    _teacher_a, teacher_a_id = await _mk_teacher_user(school_a)
    sid = await _mk_session(school_a, teacher_a_id)

    teacher_b, _ = await _mk_teacher_user(school_b)
    res = await client.get(
        f"/session/{sid}",
        headers=_tok(user_id=teacher_b["id"], role=teacher_b["role"], tenant_id=school_b),
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_cross_tenant_school_admin_idor_closed(client):
    """The core bug: a school_admin from school B could read school A's session
    because the ADMIN_ROLES bypass skipped all tenant checks. Must be 404 now."""
    school_a = str(uuid.uuid4())
    school_b = str(uuid.uuid4())
    await _mk_school(school_a)
    await _mk_school(school_b)
    _teacher_a, teacher_a_id = await _mk_teacher_user(school_a)
    sid = await _mk_session(school_a, teacher_a_id)

    admin_b = await _mk_user(UserRole.SCHOOL_ADMIN, school_b)
    res = await client.get(
        f"/session/{sid}",
        headers=_tok(user_id=admin_b["id"], role=admin_b["role"], tenant_id=school_b),
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_cross_tenant_write_blocked_with_404(client):
    """The write IDOR is the scariest: a cross-tenant school_admin must not be
    able to mutate attendance. The guard 404s before any engine work."""
    school_a = str(uuid.uuid4())
    school_b = str(uuid.uuid4())
    await _mk_school(school_a)
    await _mk_school(school_b)
    _teacher_a, teacher_a_id = await _mk_teacher_user(school_a)
    sid = await _mk_session(school_a, teacher_a_id)

    admin_b = await _mk_user(UserRole.SCHOOL_ADMIN, school_b)
    res = await client.put(
        f"/session/{sid}/attendance/{uuid.uuid4()}",
        json={"status": "absent"},
        headers=_tok(user_id=admin_b["id"], role=admin_b["role"], tenant_id=school_b),
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_unresolvable_tenant_session_fails_closed_for_foreign_admin(client):
    """Fail-closed: a legacy session with NO resolvable tenant (school_id and
    tenant_id both absent) must NOT grant a foreign school_admin access. The
    guard 404s rather than falling through to the admin allow."""
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "class_sessions", {
        "id": sid,
        "teacher_id": str(uuid.uuid4()),
        "class_id": str(uuid.uuid4()),
        "subject_id": str(uuid.uuid4()),
        # Intentionally no school_id / tenant_id.
        "date": "2026-06-22",
        "status": "attendance_in_progress",
    })
    admin_school = str(uuid.uuid4())
    await _mk_school(admin_school)
    admin = await _mk_user(UserRole.SCHOOL_ADMIN, admin_school)
    res = await client.get(
        f"/session/{sid}",
        headers=_tok(user_id=admin["id"], role=admin["role"], tenant_id=admin["tenant_id"]),
    )
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_independent_teacher_cross_workspace_404(client):
    """Two IT workspaces are fully isolated. A materialised IT caller
    (tenant_id == itw_{user_id}) requesting another workspace's session by id
    must get 404, never 403/200."""
    owner = await _mk_user(UserRole.INDEPENDENT_TEACHER, None)  # pre-materialise
    owner_ws = f"itw_{owner['id']}"
    # The owning IT session is keyed by the user id (IT sessions pin
    # teacher_id == the IT user) and school_id == the synthetic workspace.
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "class_sessions", {
        "id": sid,
        "teacher_id": owner["id"],
        "class_id": str(uuid.uuid4()),
        "subject_id": str(uuid.uuid4()),
        "school_id": owner_ws,
        "date": "2026-06-22",
        "status": "attendance_in_progress",
    })

    other = await _mk_user(UserRole.INDEPENDENT_TEACHER, None)
    other_ws = f"itw_{other['id']}"
    res = await client.get(
        f"/session/{sid}",
        headers=_tok(user_id=other["id"], role=other["role"], tenant_id=other_ws),
    )
    assert res.status_code == 404, res.text

    # And the owner still reads their own session.
    res_owner = await client.get(
        f"/session/{sid}",
        headers=_tok(user_id=owner["id"], role=owner["role"], tenant_id=owner_ws),
    )
    assert res_owner.status_code == 200, res_owner.text
