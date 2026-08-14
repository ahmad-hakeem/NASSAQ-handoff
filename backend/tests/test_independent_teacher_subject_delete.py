"""Automated coverage for the IT subject-delete dependency-warning
envelope (Task #289 / #309).

Asserts:
  * each of the three reference collections (`classes`,
    `teacher_assignments`, `schedule_sessions`) contributes its own
    non-zero count to `dependencies` and the warning fires when any
    of them is non-empty;
  * `?force=true` actually performs the soft-delete
    (`is_active=False`);
  * cross-workspace ids return 404 on both the warning and the
    force-delete branches (spec §8 invariant 3).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.core.guards.tenant_guard import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find_one, gd_insert


def _headers(uid: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_it_workspace() -> dict:
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
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-WS-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher_workspace",
    })
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


async def _mk_subject(wsid: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid,
        "school_id": wsid,
        "name": f"مادة-{sid[:6]}",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return sid


async def _ref_class(wsid: str, subject_id: str) -> None:
    await gd_insert(db.session, "classes", {
        "id": str(uuid.uuid4()),
        "name": "فصل أ",
        "school_id": wsid,
        "tenant_id": wsid,
        "subject_id": subject_id,
        "is_active": True,
    })


async def _ref_assignment(wsid: str, subject_id: str, teacher_id: str) -> None:
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "tenant_id": wsid,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "is_active": True,
    })


async def _ref_session(wsid: str, subject_id: str, teacher_id: str) -> None:
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "tenant_id": wsid,
        "schedule_id": str(uuid.uuid4()),
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "day_of_week": "1",
        "period_number": 1,
        "status": "scheduled",
    })


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ref_kind,dep_key",
    [
        ("classes", "classes"),
        ("teacher_assignments", "teacher_assignments"),
        ("schedule_sessions", "schedule_sessions"),
    ],
)
async def test_delete_subject_warns_per_reference_collection(client, ref_kind, dep_key):
    ctx = await _mk_it_workspace()
    wsid, teacher_id = ctx["wsid"], ctx["teacher_id"]
    subject_id = await _mk_subject(wsid)
    if ref_kind == "classes":
        await _ref_class(wsid, subject_id)
    elif ref_kind == "teacher_assignments":
        await _ref_assignment(wsid, subject_id, teacher_id)
    else:
        await _ref_session(wsid, subject_id, teacher_id)

    resp = await client.delete(
        f"/subjects/{subject_id}",
        headers=_headers(ctx["uid"], wsid),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("warning") is True
    assert body.get("requires_confirmation") is True
    deps = body.get("dependencies") or {}
    assert deps.get(dep_key) == 1
    other_keys = {"classes", "teacher_assignments", "schedule_sessions"} - {dep_key}
    for k in other_keys:
        assert deps.get(k) == 0

    persisted = await gd_find_one(db.session, "subjects", {"id": subject_id})
    assert persisted is not None
    assert persisted.get("is_active") is True


@pytest.mark.asyncio
async def test_delete_subject_force_soft_deletes(client):
    ctx = await _mk_it_workspace()
    wsid = ctx["wsid"]
    subject_id = await _mk_subject(wsid)
    await _ref_class(wsid, subject_id)
    await _ref_assignment(wsid, subject_id, ctx["teacher_id"])
    await _ref_session(wsid, subject_id, ctx["teacher_id"])

    resp = await client.delete(
        f"/subjects/{subject_id}?force=true",
        headers=_headers(ctx["uid"], wsid),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "warning" not in body
    assert body.get("message") == "تم حذف المادة"

    persisted = await gd_find_one(db.session, "subjects", {"id": subject_id})
    assert persisted is not None
    assert persisted.get("is_active") is False


@pytest.mark.asyncio
async def test_delete_subject_cross_workspace_404_warning_branch(client):
    owner = await _mk_it_workspace()
    intruder = await _mk_it_workspace()
    subject_id = await _mk_subject(owner["wsid"])
    await _ref_class(owner["wsid"], subject_id)

    resp = await client.delete(
        f"/subjects/{subject_id}",
        headers=_headers(intruder["uid"], intruder["wsid"]),
    )
    assert resp.status_code == 404, resp.text

    persisted = await gd_find_one(db.session, "subjects", {"id": subject_id})
    assert persisted is not None
    assert persisted.get("is_active") is True


@pytest.mark.asyncio
async def test_delete_subject_cross_workspace_404_force_branch(client):
    owner = await _mk_it_workspace()
    intruder = await _mk_it_workspace()
    subject_id = await _mk_subject(owner["wsid"])

    resp = await client.delete(
        f"/subjects/{subject_id}?force=true",
        headers=_headers(intruder["uid"], intruder["wsid"]),
    )
    assert resp.status_code == 404, resp.text

    persisted = await gd_find_one(db.session, "subjects", {"id": subject_id})
    assert persisted is not None
    assert persisted.get("is_active") is True
