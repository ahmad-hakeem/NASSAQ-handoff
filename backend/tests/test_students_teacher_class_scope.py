"""Regression tests for the dropdown-audit LOW-3 least-privilege fix on
GET /students.

A regular TEACHER token must only list students in classes actually
assigned to them (teacher_assignments / teacher_class_assignments /
class_sessions union) — same-tenant membership alone is NOT sufficient.
School-admin roles keep the full tenant roster; a teacher with no
assignments gets an empty list.
"""
from __future__ import annotations

import uuid

import pytest
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _tok(user: dict) -> dict:
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


async def _mk_school() -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"School-{sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
    })
    return sid


async def _mk_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": f"Class-{cid[:6]}",
    })
    return cid


async def _mk_student(school_id: str, class_id: str | None = None) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": f"ST-{sid[:6]}",
        "is_active": True,
        "class_id": class_id,
    })
    return sid


async def _mk_teacher(school_id: str) -> tuple[dict, str]:
    """Create a teacher user plus its linked `teachers` row. Returns
    (user, teachers.id) — assignments are keyed by teachers.id (FK)."""
    user = await _mk_user(UserRole.TEACHER, school_id)
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": school_id,
        "user_id": user["id"],
        "full_name": f"T-{teacher_id[:6]}",
        "preferences": {},
        "constraints": {},
    })
    return user, teacher_id


async def _assign(school_id: str, teacher_id: str, class_id: str,
                  is_active: bool = True) -> None:
    # teacher_assignments is the authoritative visibility source consumed by
    # get_teacher_allowed_class_ids(); teacher_class_assignments is
    # intentionally excluded (auto-populated convenience table).
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "school_id": school_id,
        "name": f"Subj-{subject_id[:6]}",
        "is_active": True,
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "teacher_id": teacher_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "is_active": is_active,
    })


@pytest.mark.asyncio
async def test_teacher_students_scoped_to_assigned_classes(client):
    """Teacher assigned to class A sees only class A's students, never the
    same-tenant class B roster."""
    school = await _mk_school()
    class_a = await _mk_class(school)
    class_b = await _mk_class(school)
    sid_a = await _mk_student(school, class_id=class_a)
    sid_b = await _mk_student(school, class_id=class_b)

    teacher, teacher_id = await _mk_teacher(school)
    # Auto-linking resolves current_user.teacher_id to teachers.id; key the
    # assignment by that id (FK target).
    await _assign(school, teacher_id, class_a)

    res = await client.get("/students", headers=_tok(teacher))
    assert res.status_code == 200, res.text
    ids = {s["id"] for s in res.json()}
    assert sid_a in ids
    assert sid_b not in ids


@pytest.mark.asyncio
async def test_teacher_with_no_assignments_sees_empty(client):
    """A teacher with zero class assignments must receive an empty list,
    not the full same-tenant roster."""
    school = await _mk_school()
    class_a = await _mk_class(school)
    await _mk_student(school, class_id=class_a)

    teacher = await _mk_user(UserRole.TEACHER, school)
    res = await client.get("/students", headers=_tok(teacher))
    assert res.status_code == 200, res.text
    assert res.json() == []


@pytest.mark.asyncio
async def test_school_admin_still_sees_full_roster(client):
    """The least-privilege scoping is teacher-only — a school_admin keeps
    the full tenant roster across all classes."""
    school = await _mk_school()
    class_a = await _mk_class(school)
    class_b = await _mk_class(school)
    sid_a = await _mk_student(school, class_id=class_a)
    sid_b = await _mk_student(school, class_id=class_b)

    admin = await _mk_user(UserRole.SCHOOL_ADMIN, school)
    res = await client.get("/students", headers=_tok(admin))
    assert res.status_code == 200, res.text
    ids = {s["id"] for s in res.json()}
    assert sid_a in ids
    assert sid_b in ids


@pytest.mark.asyncio
async def test_inactive_assignment_does_not_grant_access(client):
    """A soft-revoked (is_active=False) assignment must NOT keep disclosing
    that class's roster."""
    school = await _mk_school()
    class_a = await _mk_class(school)
    sid_a = await _mk_student(school, class_id=class_a)

    teacher, teacher_id = await _mk_teacher(school)
    await _assign(school, teacher_id, class_a, is_active=False)

    res = await client.get("/students", headers=_tok(teacher))
    assert res.status_code == 200, res.text
    ids = {s["id"] for s in res.json()}
    assert sid_a not in ids
    assert res.json() == []


@pytest.mark.asyncio
async def test_class_id_outside_teacher_scope_returns_empty(client):
    """An explicit class_id the teacher is not assigned to must return []
    (no fall-through to the broader allowed set)."""
    school = await _mk_school()
    class_a = await _mk_class(school)
    class_b = await _mk_class(school)
    await _mk_student(school, class_id=class_a)
    await _mk_student(school, class_id=class_b)

    teacher, teacher_id = await _mk_teacher(school)
    await _assign(school, teacher_id, class_a)

    res = await client.get(
        "/students", params={"class_id": class_b}, headers=_tok(teacher)
    )
    assert res.status_code == 200, res.text
    assert res.json() == []
