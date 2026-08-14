"""Coverage for the teacher / subject soft-delete + restore routes
(Task #645 hooks added under DELETE /teachers/{id},
POST /teachers/{id}/restore, DELETE /subjects/{id},
POST /subjects/{id}/restore, and the ``include_deleted`` filter on
the corresponding list endpoints).

Pinned invariants:
  * IT cross-workspace ids return 404 (spec §8 inv. 3) on delete,
    restore, and include_deleted permission filtering.
  * Restore only succeeds when both ``is_active=False`` AND
    ``deleted_at IS NOT NULL`` — a row that is merely inactive
    (never soft-deleted) returns 404 on /restore.
  * Dependent rows (teacher_assignments, schedule sessions, …)
    stay inactive after restore — the response surfaces the counts
    so the UI can re-link them deliberately.
  * ``include_deleted=true`` is honored only for admin roles
    (principal / school_admin / IT in their own workspace) and
    silently ignored for unprivileged callers (regular teacher).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.core.guards.tenant_guard import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find_one, gd_insert, gd_update_one


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _bearer(uid: str, role: str, tenant_id):
    token = create_access_token({"sub": uid, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(role: UserRole, tenant_id) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role.value,
        "tenant_id": tenant_id,
        "email": f"{role.value}-{uid}@t.test",
        "full_name": f"{role.value}-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_it_workspace() -> dict:
    """Create an Independent-Teacher workspace + linked teacher row."""
    uid = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "teacher_id": teacher_id,
    }
    wsid = independent_workspace_id(user)
    user["tenant_id"] = wsid
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-WS-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher_workspace",
    })
    await gd_insert(db.session, "users", user)
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": wsid,
        "user_id": uid,
        "full_name": user["full_name"],
        "email": user["email"],
        "is_active": True,
    })
    user["tenant_id"] = wsid
    return {"user": user, "uid": uid, "wsid": wsid, "teacher_id": teacher_id}


async def _mk_teacher(school_id: str) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "school_id": school_id,
        "full_name": f"T-{tid[:6]}",
        "email": f"t-{tid}@t.test",
        "is_active": True,
    })
    return tid


async def _mk_subject(school_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid,
        "school_id": school_id,
        "name": f"مادة-{sid[:6]}",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return sid


async def _mk_teacher_assignment(school_id: str, teacher_id: str, subject_id: str | None = None) -> str:
    aid = str(uuid.uuid4())
    if subject_id is None:
        subject_id = await _mk_subject(school_id)
    await gd_insert(db.session, "teacher_assignments", {
        "id": aid,
        "school_id": school_id,
        "tenant_id": school_id,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "is_active": True,
    })
    return aid


# ===========================================================================
# DELETE /teachers/{id}
# ===========================================================================

@pytest.mark.asyncio
async def test_delete_teacher_principal_soft_deletes_and_cascades(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    teacher_id = await _mk_teacher(tenant_a)
    assignment_id = await _mk_teacher_assignment(tenant_a, teacher_id)

    resp = await client.delete(
        f"/teachers/{teacher_id}",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    assert body.get("cleanup", {}).get("teacher_assignments") == 1

    row = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert row.get("is_active") is False
    assert row.get("deleted_at") is not None
    assert row.get("deleted_by") == principal["id"]

    assignment = await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id})
    assert assignment.get("is_active") is False


@pytest.mark.asyncio
async def test_delete_teacher_it_in_own_workspace(client):
    ctx = await _mk_it_workspace()
    target_teacher_id = await _mk_teacher(ctx["wsid"])

    resp = await client.delete(
        f"/teachers/{target_teacher_id}",
        headers=_bearer(ctx["uid"], UserRole.INDEPENDENT_TEACHER.value, ctx["wsid"]),
    )
    assert resp.status_code == 200, resp.text

    row = await gd_find_one(db.session, "teachers", {"id": target_teacher_id})
    assert row.get("is_active") is False
    assert row.get("deleted_at") is not None


@pytest.mark.asyncio
async def test_delete_teacher_it_cross_workspace_returns_404(client):
    owner = await _mk_it_workspace()
    intruder = await _mk_it_workspace()
    target_teacher_id = await _mk_teacher(owner["wsid"])

    resp = await client.delete(
        f"/teachers/{target_teacher_id}",
        headers=_bearer(intruder["uid"], UserRole.INDEPENDENT_TEACHER.value, intruder["wsid"]),
    )
    assert resp.status_code == 404, resp.text

    row = await gd_find_one(db.session, "teachers", {"id": target_teacher_id})
    assert row.get("is_active") is True
    assert row.get("deleted_at") in (None, "")


@pytest.mark.asyncio
async def test_delete_teacher_cross_tenant_principal_blocked(client, tenant_a, tenant_b):
    """A principal of tenant A may not soft-delete a teacher owned by tenant B."""
    intruder = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    foreign_teacher_id = await _mk_teacher(tenant_b)

    resp = await client.delete(
        f"/teachers/{foreign_teacher_id}",
        headers=_bearer(intruder["id"], intruder["role"], tenant_a),
    )
    assert resp.status_code in (403, 404), resp.text

    row = await gd_find_one(db.session, "teachers", {"id": foreign_teacher_id})
    assert row.get("is_active") is True
    assert row.get("deleted_at") in (None, "")


# ===========================================================================
# POST /teachers/{id}/restore
# ===========================================================================

@pytest.mark.asyncio
async def test_restore_teacher_happy_path(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    teacher_id = await _mk_teacher(tenant_a)
    assignment_id = await _mk_teacher_assignment(tenant_a, teacher_id)

    # Soft-delete first.
    del_resp = await client.delete(
        f"/teachers/{teacher_id}",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert del_resp.status_code == 200

    resp = await client.post(
        f"/teachers/{teacher_id}/restore",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    # Dependent rows were soft-deactivated by delete and stay inactive.
    assert body.get("inactive_dependents", {}).get("teacher_assignments") == 1

    row = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert row.get("is_active") is True
    assert row.get("deleted_at") is None
    assert row.get("deleted_by") is None

    # Dependent assignment is NOT auto-reactivated.
    assignment = await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id})
    assert assignment.get("is_active") is False


@pytest.mark.asyncio
async def test_restore_teacher_404_when_not_soft_deleted(client, tenant_a):
    """A row that is merely inactive (never soft-deleted) must not be
    restorable — both ``is_active=False`` AND ``deleted_at IS NOT NULL``
    are required."""
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    teacher_id = await _mk_teacher(tenant_a)
    # Mark inactive without setting deleted_at.
    await gd_update_one(db.session, "teachers", {"id": teacher_id}, {"is_active": False})

    resp = await client.post(
        f"/teachers/{teacher_id}/restore",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 404, resp.text

    row = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert row.get("is_active") is False
    assert row.get("deleted_at") in (None, "")


@pytest.mark.asyncio
async def test_restore_teacher_404_on_active_row(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    teacher_id = await _mk_teacher(tenant_a)

    resp = await client.post(
        f"/teachers/{teacher_id}/restore",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_restore_teacher_cross_tenant_principal_blocked(client, tenant_a, tenant_b):
    """A principal of tenant A may not restore a soft-deleted teacher
    owned by tenant B even when the target row IS in the restorable
    state (Task #670 — close the asymmetry with DELETE)."""
    owner = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_b)
    intruder = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    foreign_teacher_id = await _mk_teacher(tenant_b)

    # Owner soft-deletes their own teacher row so the target IS restorable.
    del_resp = await client.delete(
        f"/teachers/{foreign_teacher_id}",
        headers=_bearer(owner["id"], owner["role"], tenant_b),
    )
    assert del_resp.status_code == 200

    resp = await client.post(
        f"/teachers/{foreign_teacher_id}/restore",
        headers=_bearer(intruder["id"], intruder["role"], tenant_a),
    )
    assert resp.status_code in (403, 404), resp.text

    row = await gd_find_one(db.session, "teachers", {"id": foreign_teacher_id})
    assert row.get("is_active") is False
    assert row.get("deleted_at") is not None


@pytest.mark.asyncio
async def test_restore_teacher_it_cross_workspace_404(client):
    owner = await _mk_it_workspace()
    intruder = await _mk_it_workspace()
    target_teacher_id = await _mk_teacher(owner["wsid"])

    # Owner soft-deletes their own teacher row so the target IS in the
    # restorable state. Intruder must still get 404 on cross-workspace
    # restore (spec §8 inv. 3).
    del_resp = await client.delete(
        f"/teachers/{target_teacher_id}",
        headers=_bearer(owner["uid"], UserRole.INDEPENDENT_TEACHER.value, owner["wsid"]),
    )
    assert del_resp.status_code == 200

    resp = await client.post(
        f"/teachers/{target_teacher_id}/restore",
        headers=_bearer(intruder["uid"], UserRole.INDEPENDENT_TEACHER.value, intruder["wsid"]),
    )
    assert resp.status_code == 404, resp.text

    row = await gd_find_one(db.session, "teachers", {"id": target_teacher_id})
    assert row.get("is_active") is False
    assert row.get("deleted_at") is not None


# ===========================================================================
# DELETE /subjects/{id}
# ===========================================================================

@pytest.mark.asyncio
async def test_delete_subject_principal_no_deps_soft_deletes(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    subject_id = await _mk_subject(tenant_a)

    resp = await client.delete(
        f"/subjects/{subject_id}",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "warning" not in body

    row = await gd_find_one(db.session, "subjects", {"id": subject_id})
    assert row.get("is_active") is False
    assert row.get("deleted_at") is not None
    assert row.get("deleted_by") == principal["id"]


@pytest.mark.asyncio
async def test_delete_subject_it_cross_workspace_404(client):
    owner = await _mk_it_workspace()
    intruder = await _mk_it_workspace()
    subject_id = await _mk_subject(owner["wsid"])

    resp = await client.delete(
        f"/subjects/{subject_id}",
        headers=_bearer(intruder["uid"], UserRole.INDEPENDENT_TEACHER.value, intruder["wsid"]),
    )
    assert resp.status_code == 404, resp.text

    row = await gd_find_one(db.session, "subjects", {"id": subject_id})
    assert row.get("is_active") is True


@pytest.mark.asyncio
async def test_delete_subject_cross_tenant_principal_blocked(client, tenant_a, tenant_b):
    intruder = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    foreign_subject_id = await _mk_subject(tenant_b)

    resp = await client.delete(
        f"/subjects/{foreign_subject_id}",
        headers=_bearer(intruder["id"], intruder["role"], tenant_a),
    )
    assert resp.status_code in (403, 404), resp.text

    row = await gd_find_one(db.session, "subjects", {"id": foreign_subject_id})
    assert row.get("is_active") is True


# ===========================================================================
# POST /subjects/{id}/restore
# ===========================================================================

@pytest.mark.asyncio
async def test_restore_subject_happy_path(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    teacher_id = await _mk_teacher(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    # Reference row that depends on the subject — should stay inactive
    # after the subject is restored.
    assignment_id = await _mk_teacher_assignment(tenant_a, teacher_id, subject_id)
    # Mark the assignment inactive to simulate the dependency cleanup
    # the subject-delete force branch would have done.
    await gd_update_one(
        db.session, "teacher_assignments", {"id": assignment_id}, {"is_active": False}
    )
    # Soft-delete the subject.
    await client.delete(
        f"/subjects/{subject_id}?force=true",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )

    resp = await client.post(
        f"/subjects/{subject_id}/restore",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    assert body.get("inactive_dependents", {}).get("teacher_assignments") == 1

    row = await gd_find_one(db.session, "subjects", {"id": subject_id})
    assert row.get("is_active") is True
    assert row.get("deleted_at") is None
    assert row.get("deleted_by") is None

    assignment = await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id})
    assert assignment.get("is_active") is False


@pytest.mark.asyncio
async def test_restore_subject_404_when_not_soft_deleted(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    subject_id = await _mk_subject(tenant_a)
    # Inactive but NOT soft-deleted (no deleted_at).
    await gd_update_one(db.session, "subjects", {"id": subject_id}, {"is_active": False})

    resp = await client.post(
        f"/subjects/{subject_id}/restore",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 404, resp.text

    row = await gd_find_one(db.session, "subjects", {"id": subject_id})
    assert row.get("is_active") is False
    assert row.get("deleted_at") in (None, "")


@pytest.mark.asyncio
async def test_restore_subject_404_on_active_row(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    subject_id = await _mk_subject(tenant_a)

    resp = await client.post(
        f"/subjects/{subject_id}/restore",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_restore_subject_it_cross_workspace_404(client):
    owner = await _mk_it_workspace()
    intruder = await _mk_it_workspace()
    subject_id = await _mk_subject(owner["wsid"])

    del_resp = await client.delete(
        f"/subjects/{subject_id}?force=true",
        headers=_bearer(owner["uid"], UserRole.INDEPENDENT_TEACHER.value, owner["wsid"]),
    )
    assert del_resp.status_code == 200

    resp = await client.post(
        f"/subjects/{subject_id}/restore",
        headers=_bearer(intruder["uid"], UserRole.INDEPENDENT_TEACHER.value, intruder["wsid"]),
    )
    assert resp.status_code == 404, resp.text

    row = await gd_find_one(db.session, "subjects", {"id": subject_id})
    assert row.get("is_active") is False
    assert row.get("deleted_at") is not None


# ===========================================================================
# GET /teachers?include_deleted=true permission filtering
# ===========================================================================

@pytest.mark.asyncio
async def test_get_teachers_include_deleted_principal_sees_soft_deleted(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    active_id = await _mk_teacher(tenant_a)
    deleted_id = await _mk_teacher(tenant_a)
    await client.delete(
        f"/teachers/{deleted_id}",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )

    # Default — soft-deleted row hidden.
    default_resp = await client.get(
        "/teachers",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert default_resp.status_code == 200
    default_ids = {t["id"] for t in default_resp.json()}
    assert active_id in default_ids
    assert deleted_id not in default_ids

    # include_deleted=true — soft-deleted row exposed.
    resp = await client.get(
        "/teachers?include_deleted=true",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert active_id in ids
    assert deleted_id in ids


@pytest.mark.asyncio
async def test_get_teachers_include_deleted_silently_ignored_for_teacher(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    teacher_caller = await _mk_user(UserRole.TEACHER, tenant_a)
    active_id = await _mk_teacher(tenant_a)
    deleted_id = await _mk_teacher(tenant_a)
    await client.delete(
        f"/teachers/{deleted_id}",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )

    resp = await client.get(
        "/teachers?include_deleted=true",
        headers=_bearer(teacher_caller["id"], teacher_caller["role"], tenant_a),
    )
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert active_id in ids
    assert deleted_id not in ids


@pytest.mark.asyncio
async def test_get_teachers_include_deleted_it_scoped_to_own_workspace(client):
    owner = await _mk_it_workspace()
    intruder = await _mk_it_workspace()
    # Owner soft-deletes a teacher in their own workspace.
    owner_target = await _mk_teacher(owner["wsid"])
    await client.delete(
        f"/teachers/{owner_target}",
        headers=_bearer(owner["uid"], UserRole.INDEPENDENT_TEACHER.value, owner["wsid"]),
    )

    # Intruder must NEVER see the owner's soft-deleted teacher row,
    # even with include_deleted=true.
    resp = await client.get(
        "/teachers?include_deleted=true",
        headers=_bearer(intruder["uid"], UserRole.INDEPENDENT_TEACHER.value, intruder["wsid"]),
    )
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert owner_target not in ids


# ===========================================================================
# GET /subjects?include_deleted=true permission filtering
# ===========================================================================

@pytest.mark.asyncio
async def test_get_subjects_include_deleted_principal_sees_soft_deleted(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    active_id = await _mk_subject(tenant_a)
    deleted_id = await _mk_subject(tenant_a)
    await client.delete(
        f"/subjects/{deleted_id}",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )

    default_resp = await client.get(
        "/subjects",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert default_resp.status_code == 200
    default_ids = {s["id"] for s in default_resp.json()}
    assert active_id in default_ids
    assert deleted_id not in default_ids

    resp = await client.get(
        "/subjects?include_deleted=true",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()}
    assert active_id in ids
    assert deleted_id in ids


@pytest.mark.asyncio
async def test_get_subjects_include_deleted_silently_ignored_for_teacher(client, tenant_a):
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    teacher_caller = await _mk_user(UserRole.TEACHER, tenant_a)
    active_id = await _mk_subject(tenant_a)
    deleted_id = await _mk_subject(tenant_a)
    await client.delete(
        f"/subjects/{deleted_id}",
        headers=_bearer(principal["id"], principal["role"], tenant_a),
    )

    resp = await client.get(
        "/subjects?include_deleted=true",
        headers=_bearer(teacher_caller["id"], teacher_caller["role"], tenant_a),
    )
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()}
    assert active_id in ids
    assert deleted_id not in ids


@pytest.mark.asyncio
async def test_get_subjects_include_deleted_it_scoped_to_own_workspace(client):
    owner = await _mk_it_workspace()
    intruder = await _mk_it_workspace()
    owner_subject = await _mk_subject(owner["wsid"])
    await client.delete(
        f"/subjects/{owner_subject}?force=true",
        headers=_bearer(owner["uid"], UserRole.INDEPENDENT_TEACHER.value, owner["wsid"]),
    )

    resp = await client.get(
        "/subjects?include_deleted=true",
        headers=_bearer(intruder["uid"], UserRole.INDEPENDENT_TEACHER.value, intruder["wsid"]),
    )
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()}
    assert owner_subject not in ids
