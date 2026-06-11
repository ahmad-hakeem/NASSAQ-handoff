"""Coverage for GET /teacher/my-subjects (Task #876).

The session-settings subject dropdown must show a school teacher only the
subjects assigned to them via `teacher_assignments` — never the full
tenant subject catalogue. Independent teachers own every subject in their
workspace, so the filtered list equals the full workspace list. Non-teacher
callers (principal/admin) are rejected with 403 and must keep using the
unfiltered /subjects route.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _headers(uid: str, role: str, tenant_id) -> dict:
    token = create_access_token({"sub": uid, "role": role, "tenant_id": tenant_id})
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


async def _mk_teacher_user(school_id: str) -> tuple[str, str]:
    """Create a (users, teachers) pair and return (user_id, teacher_id)."""
    uid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "full_name": f"T-{tid[:6]}",
        "school_id": school_id,
        "user_id": uid,
        "is_active": True,
    })
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.TEACHER.value,
        "tenant_id": school_id,
        "teacher_id": tid,
        "email": f"{uid}@t.test",
        "full_name": f"Teacher-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    return uid, tid


async def _mk_subject(school_id: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid,
        "school_id": school_id,
        "name": name,
        "is_active": True,
        "default_periods_per_week": 4,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return sid


async def _mk_assignment(school_id: str, teacher_id: str, subject_id: str) -> None:
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "is_active": True,
    })


@pytest.mark.asyncio
async def test_school_teacher_sees_only_assigned_subjects(client):
    """Teacher A sees only their assigned subjects, not Teacher B's and not
    the unassigned tenant subjects."""
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)

    uid_a, tid_a = await _mk_teacher_user(school_id)
    uid_b, tid_b = await _mk_teacher_user(school_id)

    subj_a = await _mk_subject(school_id, "مادة-أ")
    subj_b = await _mk_subject(school_id, "مادة-ب")
    subj_unassigned = await _mk_subject(school_id, "مادة-غير-معينة")

    # A teaches subj_a (twice, to prove dedupe); B teaches subj_b.
    await _mk_assignment(school_id, tid_a, subj_a)
    await _mk_assignment(school_id, tid_a, subj_a)
    await _mk_assignment(school_id, tid_b, subj_b)

    resp = await client.get(
        "/teacher/my-subjects",
        headers=_headers(uid_a, UserRole.TEACHER.value, school_id),
    )
    assert resp.status_code == 200, resp.text
    ids = [s["id"] for s in resp.json()]
    assert ids == [subj_a]  # exactly one, deduped
    assert subj_b not in ids
    assert subj_unassigned not in ids

    # Teacher B sees only their own.
    resp_b = await client.get(
        "/teacher/my-subjects",
        headers=_headers(uid_b, UserRole.TEACHER.value, school_id),
    )
    assert resp_b.status_code == 200, resp_b.text
    ids_b = {s["id"] for s in resp_b.json()}
    assert ids_b == {subj_b}


@pytest.mark.asyncio
async def test_teacher_with_no_assignments_gets_empty_list(client):
    """A teacher with zero assignments gets [] — never the full catalogue."""
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)
    uid, _tid = await _mk_teacher_user(school_id)
    # Tenant has subjects, but none assigned to this teacher.
    await _mk_subject(school_id, "مادة-١")
    await _mk_subject(school_id, "مادة-٢")

    resp = await client.get(
        "/teacher/my-subjects",
        headers=_headers(uid, UserRole.TEACHER.value, school_id),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_inactive_assigned_subject_is_excluded(client):
    """A soft-deleted subject is excluded even if still referenced by an
    active assignment."""
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)
    uid, tid = await _mk_teacher_user(school_id)
    active = await _mk_subject(school_id, "مادة-فعالة")
    deleted = await _mk_subject(school_id, "مادة-محذوفة")
    from engines.sql_utils import gd_update_one
    await gd_update_one(db.session, "subjects", {"id": deleted}, {"is_active": False})
    await _mk_assignment(school_id, tid, active)
    await _mk_assignment(school_id, tid, deleted)

    resp = await client.get(
        "/teacher/my-subjects",
        headers=_headers(uid, UserRole.TEACHER.value, school_id),
    )
    assert resp.status_code == 200, resp.text
    ids = {s["id"] for s in resp.json()}
    assert ids == {active}


@pytest.mark.asyncio
async def test_independent_teacher_gets_full_workspace_list(client):
    """An IT teacher receives every active subject in their workspace,
    regardless of teacher_assignments (they own all of them)."""
    uid = str(uuid.uuid4())
    it_user = {"id": uid, "role": UserRole.INDEPENDENT_TEACHER.value, "tenant_id": None}
    wsid = independent_workspace_id(it_user)
    await _mk_school(wsid)
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": wsid,
        "email": f"{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    s1 = await _mk_subject(wsid, "ورشة-١")
    s2 = await _mk_subject(wsid, "ورشة-٢")

    resp = await client.get(
        "/teacher/my-subjects",
        headers=_headers(uid, UserRole.INDEPENDENT_TEACHER.value, wsid),
    )
    assert resp.status_code == 200, resp.text
    ids = {s["id"] for s in resp.json()}
    assert ids == {s1, s2}


@pytest.mark.asyncio
async def test_non_teacher_caller_is_forbidden(client):
    """Principal/admin callers are rejected with 403 and must use /subjects."""
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"{uid}@t.test",
        "full_name": f"P-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    resp = await client.get(
        "/teacher/my-subjects",
        headers=_headers(uid, UserRole.SCHOOL_PRINCIPAL.value, school_id),
    )
    assert resp.status_code == 403, resp.text
