"""Regression tests for the class deletion + student-unassign flow (Task #916).

Task #916 fixed two production defects in `DELETE /classes/{id}`
(`backend/routes/academics_class_routes.py::delete_class`):

  * empty classes that "deleted" then reappeared, and
  * classes with students that could not be deleted at all.

These tests lock in the resulting contract so a future change can't silently
regress it:

  * an EMPTY class deletes immediately (``success: true``, no
    ``requires_confirmation``) and disappears from ``GET /classes``;
  * a class with dependencies (teacher_assignments / class_subjects /
    timetable_sessions) and/or linked students returns the
    ``requires_confirmation`` envelope with a populated ``dependencies`` dict
    (including ``students``) and performs NO deletion;
  * ``force=true`` soft-deletes the class, unassigns active students
    (``class_id`` cleared, rows stay active), returns ``students_unassigned``,
    and the students survive and remain reassignable;
  * cross-workspace/IT by-id reads return 404 (spec §8 inv. 3); and
  * a student in another tenant is never touched.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one, gd_count
from auth_scope import independent_workspace_id


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_class(school_id: str, name: str = None, active: bool = True) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": name or f"C-{cid[:6]}",
        "capacity": 20,
        "current_students": 0,
        "is_active": active,
    })
    return cid


async def _mk_student(school_id: str, class_id, name: str = None, active: bool = True) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": name or f"ST-{sid[:6]}",
        "class_id": class_id,
        "is_active": active,
    })
    return sid


async def _mk_class_subject(school_id: str, class_id: str) -> str:
    csid = str(uuid.uuid4())
    await gd_insert(db.session, "class_subjects", {
        "id": csid,
        "class_id": class_id,
        "school_id": school_id,
        "subject_id": f"subj-{csid[:6]}",
        "subject_name": "مادة",
        "weekly_periods": 3,
        "is_active": True,
    })
    return csid


async def _mk_independent_teacher() -> dict:
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": now,
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return user


# ----------------------------------------------------------------------
# (1) Empty class deletes immediately and disappears from the listing
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_class_deletes_immediately_and_is_gone(
    client, school_principal_headers, tenant_a, _db_session
):
    cid = await _mk_class(tenant_a, name="Empty")
    await _db_session.flush()

    resp = await client.delete(f"/classes/{cid}", headers=school_principal_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    # No confirmation gate for an empty class.
    assert "requires_confirmation" not in body
    assert body.get("students_unassigned") == 0

    # Soft-deleted: gone from the default listing.
    listing = await client.get("/classes", headers=school_principal_headers)
    assert listing.status_code == 200, listing.text
    assert cid not in {c["id"] for c in listing.json()}

    # The row is soft-deleted, not hard-deleted.
    row = await gd_find_one(_db_session, "classes", {"id": cid})
    assert row is not None
    assert row.get("is_active") is False
    assert row.get("deleted_at") is not None


# ----------------------------------------------------------------------
# (2) Class with dependencies/students => requires_confirmation, no deletion
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_class_with_dependencies_requires_confirmation_no_deletion(
    client, school_principal_headers, tenant_a, _db_session
):
    cid = await _mk_class(tenant_a, name="Busy")
    await _mk_class_subject(tenant_a, cid)
    s1 = await _mk_student(tenant_a, cid)
    s2 = await _mk_student(tenant_a, cid)
    await _db_session.flush()

    resp = await client.delete(f"/classes/{cid}", headers=school_principal_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("requires_confirmation") is True
    assert body.get("warning") is True
    deps = body.get("dependencies")
    assert isinstance(deps, dict)
    assert deps.get("students") == 2
    assert deps.get("class_subjects") == 1
    # Keys are always present even when zero.
    assert "teacher_assignments" in deps
    assert "timetable_sessions" in deps

    # NO deletion occurred — class still active, students still assigned.
    row = await gd_find_one(_db_session, "classes", {"id": cid})
    assert row.get("is_active") is not False
    assert row.get("deleted_at") is None
    for sid in (s1, s2):
        st = await gd_find_one(_db_session, "students", {"id": sid})
        assert st.get("class_id") == cid
        assert st.get("is_active") is True

    # Still visible in the listing.
    listing = await client.get("/classes", headers=school_principal_headers)
    assert cid in {c["id"] for c in listing.json()}


# ----------------------------------------------------------------------
# (3) force=true soft-deletes, unassigns active students, they survive
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_force_delete_unassigns_students_who_survive_and_reassign(
    client, school_principal_headers, tenant_a, _db_session
):
    cid = await _mk_class(tenant_a, name="ToForce")
    await _mk_class_subject(tenant_a, cid)
    s1 = await _mk_student(tenant_a, cid)
    s2 = await _mk_student(tenant_a, cid)
    # An already-inactive student in the class must NOT be counted/unassigned.
    s_inactive = await _mk_student(tenant_a, cid, active=False)
    await _db_session.flush()

    resp = await client.delete(
        f"/classes/{cid}?force=true", headers=school_principal_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    assert body.get("students_unassigned") == 2

    # Class soft-deleted.
    row = await gd_find_one(_db_session, "classes", {"id": cid})
    assert row.get("is_active") is False
    assert row.get("deleted_at") is not None

    # Active students: unassigned (class_id cleared) but rows stay active.
    for sid in (s1, s2):
        st = await gd_find_one(_db_session, "students", {"id": sid})
        assert st.get("class_id") is None
        assert st.get("is_active") is True

    # The pre-existing inactive student is untouched (still pointing at class).
    st_inactive = await gd_find_one(_db_session, "students", {"id": s_inactive})
    assert st_inactive.get("class_id") == cid
    assert st_inactive.get("is_active") is False

    # Survivors are reassignable: move one into a fresh class via the real API.
    new_cid = await _mk_class(tenant_a, name="Fresh")
    await _db_session.flush()
    move = await client.post(
        "/students/transfer-class",
        json={"student_id": s1, "target_class_id": new_cid},
        headers=school_principal_headers,
    )
    assert move.status_code == 200, move.text
    assert move.json().get("success") is True
    moved = await gd_find_one(_db_session, "students", {"id": s1})
    assert moved.get("class_id") == new_cid


# ----------------------------------------------------------------------
# (4) IT cross-workspace by-id delete returns 404 (spec §8 inv. 3)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_force_delete_cross_workspace_returns_404_no_mutation(
    client, _db_session
):
    user_a = await _mk_independent_teacher()
    user_b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(user_a)
    wsid_b = independent_workspace_id(user_b)
    cid = await _mk_class(wsid_a, name="IT-A class")
    sid = await _mk_student(wsid_a, cid)
    await _db_session.flush()

    h_b = _headers(user_b["id"], user_b["role"], wsid_b)
    resp = await client.delete(f"/classes/{cid}?force=true", headers=h_b)
    assert resp.status_code == 404, resp.text
    msg = (resp.json().get("error") or {}).get("message") or resp.json().get("detail") or ""
    assert "غير موجود" in msg

    # Nothing in IT-A's workspace was mutated.
    row = await gd_find_one(_db_session, "classes", {"id": cid})
    assert row.get("is_active") is not False
    assert row.get("deleted_at") is None
    st = await gd_find_one(_db_session, "students", {"id": sid})
    assert st.get("class_id") == cid
    assert st.get("is_active") is True


# ----------------------------------------------------------------------
# (5) Tenancy: a student in another tenant is never unassigned
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_force_delete_never_touches_foreign_tenant_student(
    client, school_principal_headers, tenant_a, tenant_b, _db_session
):
    cid = await _mk_class(tenant_a, name="Owned")
    own_student = await _mk_student(tenant_a, cid)
    # A foreign-tenant student that happens to carry the SAME class_id must be
    # left alone — the unassign is pinned to the class's school_id.
    foreign_student = await _mk_student(tenant_b, cid)
    await _db_session.flush()

    resp = await client.delete(
        f"/classes/{cid}?force=true", headers=school_principal_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("students_unassigned") == 1

    own = await gd_find_one(_db_session, "students", {"id": own_student})
    assert own.get("class_id") is None

    foreign = await gd_find_one(_db_session, "students", {"id": foreign_student})
    assert foreign.get("class_id") == cid
    assert foreign.get("is_active") is True
