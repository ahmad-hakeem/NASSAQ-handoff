"""
Task #862 — regression tests for persisting live-session student groups.

Groups created during an active session must survive a full refresh because
they live on the durable ``class_sessions`` record (like ``seating_order``),
not just in client memory. These tests cover:

- Saving groups to an active session via ``POST /session/{id}/groups``.
- Rehydrating them via ``GET /session/{id}/groups`` (the reload read path).
- Cross-tenant / non-owner group reads and writes are blocked.
- Groups from one session do not leak into a sibling session of the same class.
"""
import uuid

import pytest
import pytest_asyncio

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one


def _headers(user: dict) -> dict:
    token = create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_teacher(tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.TEACHER.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": "Teacher",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_session(tenant_id: str, teacher_id: str, class_id: str = None) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "class_sessions", {
        "id": sid,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "teacher_id": teacher_id,
        "class_id": class_id or str(uuid.uuid4()),
        "subject_id": str(uuid.uuid4()),
        "status": "teaching_in_progress",
    })
    return sid


_GROUPS = [
    {"id": "g1", "name": "المتقدمون", "color": "bg-green-600", "students": ["s1", "s2"]},
    {"id": "g2", "name": "المتوسطون", "color": "bg-blue-600", "students": ["s3"]},
]


@pytest.mark.asyncio
async def test_save_and_rehydrate_groups(client, tenant_a):
    teacher = await _mk_teacher(tenant_a)
    sid = await _mk_session(tenant_a, teacher["id"])
    headers = _headers(teacher)

    # Initially no groups -> empty list (drives the empty-state on the FE).
    res = await client.get(f"/session/{sid}/groups", headers=headers)
    assert res.status_code == 200
    assert res.json()["groups"] == []

    # Save groups.
    save = await client.post(f"/session/{sid}/groups", json={"groups": _GROUPS}, headers=headers)
    assert save.status_code == 200

    # They are persisted on the durable record (survives "refresh").
    res = await client.get(f"/session/{sid}/groups", headers=headers)
    assert res.status_code == 200
    assert res.json()["groups"] == _GROUPS

    # And are written to the class_sessions row itself.
    row = await gd_find_one(db.session, "class_sessions", {"id": sid})
    assert row.get("groups") == _GROUPS


@pytest.mark.asyncio
async def test_update_and_clear_groups(client, tenant_a):
    teacher = await _mk_teacher(tenant_a)
    sid = await _mk_session(tenant_a, teacher["id"])
    headers = _headers(teacher)

    await client.post(f"/session/{sid}/groups", json={"groups": _GROUPS}, headers=headers)

    # Update (rename + membership change).
    updated = [{"id": "g1", "name": "فريق أ", "color": "bg-green-600", "students": ["s1"]}]
    await client.post(f"/session/{sid}/groups", json={"groups": updated}, headers=headers)
    res = await client.get(f"/session/{sid}/groups", headers=headers)
    assert res.json()["groups"] == updated

    # Delete all (empty list) -> empty-state again.
    await client.post(f"/session/{sid}/groups", json={"groups": []}, headers=headers)
    res = await client.get(f"/session/{sid}/groups", headers=headers)
    assert res.json()["groups"] == []


@pytest.mark.asyncio
async def test_groups_do_not_leak_between_sessions(client, tenant_a):
    teacher = await _mk_teacher(tenant_a)
    class_id = str(uuid.uuid4())
    sid1 = await _mk_session(tenant_a, teacher["id"], class_id)
    headers = _headers(teacher)
    await client.post(f"/session/{sid1}/groups", json={"groups": _GROUPS}, headers=headers)

    # A freshly started session for the same class has no groups.
    sid2 = await _mk_session(tenant_a, teacher["id"], class_id)
    res = await client.get(f"/session/{sid2}/groups", headers=headers)
    assert res.status_code == 200
    assert res.json()["groups"] == []


@pytest.mark.asyncio
async def test_cross_tenant_group_access_blocked(client, tenant_a, tenant_b):
    owner = await _mk_teacher(tenant_a)
    sid = await _mk_session(tenant_a, owner["id"])
    await client.post(f"/session/{sid}/groups", json={"groups": _GROUPS}, headers=_headers(owner))

    # A teacher from another tenant cannot read or write these groups.
    intruder = await _mk_teacher(tenant_b)
    intruder_headers = _headers(intruder)

    read = await client.get(f"/session/{sid}/groups", headers=intruder_headers)
    assert read.status_code in (403, 404)

    write = await client.post(
        f"/session/{sid}/groups",
        json={"groups": []},
        headers=intruder_headers,
    )
    assert write.status_code in (403, 404)

    # The owner's groups are untouched after the blocked write attempt.
    row = await gd_find_one(db.session, "class_sessions", {"id": sid})
    assert row.get("groups") == _GROUPS


@pytest.mark.asyncio
async def test_other_same_tenant_teacher_blocked(client, tenant_a):
    owner = await _mk_teacher(tenant_a)
    sid = await _mk_session(tenant_a, owner["id"])
    await client.post(f"/session/{sid}/groups", json={"groups": _GROUPS}, headers=_headers(owner))

    # A different teacher in the SAME tenant is not the session owner.
    other = await _mk_teacher(tenant_a)
    res = await client.get(f"/session/{sid}/groups", headers=_headers(other))
    assert res.status_code == 403
