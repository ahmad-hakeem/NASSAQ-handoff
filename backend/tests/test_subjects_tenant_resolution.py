"""Regression coverage for the GET /subjects tenant-resolution order.

The subject dropdown silently broke once because the route resolved the
caller's scope from a raw `tenant_id` before consulting the synthetic
Independent-Teacher workspace id. An IT access token can carry a truthy
`tenant_id` that is NOT the workspace id (`itw_{user_id}`); if that value
wins, the IT caller queries the wrong tenant and the dropdown comes back
empty even though workspace-scoped subjects exist.

These tests pin the resolution order so a regression is caught
immediately:

  * an IT token whose `tenant_id` differs from `itw_{user_id}` still
    receives ONLY workspace-scoped subjects and never the rows that live
    under the literal `tenant_id`;
  * a regular school teacher token is unaffected and keeps receiving its
    own `tenant_id`-scoped subjects.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.core.guards.tenant_guard import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _headers(uid: str, role: str, tenant_id) -> dict:
    token = create_access_token({
        "sub": uid,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(uid: str, role: str, tenant_id) -> None:
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": role,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": f"{role}-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


async def _mk_subject(school_id: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid,
        "school_id": school_id,
        "name": name,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return sid


@pytest.mark.asyncio
async def test_it_token_with_tenant_id_gets_workspace_scoped_subjects(client):
    """An IT token carrying a truthy (decoy) tenant_id must still resolve
    to its `itw_{user_id}` workspace, not the literal tenant_id."""
    uid = str(uuid.uuid4())
    it_user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
    }
    wsid = independent_workspace_id(it_user)
    # A real tenant id that is deliberately different from the workspace
    # id. If the resolution order regresses, the route would query this id
    # and leak `decoy` while hiding the real workspace subject.
    decoy_tenant_id = str(uuid.uuid4())
    assert decoy_tenant_id != wsid

    await _mk_school(wsid)
    await _mk_school(decoy_tenant_id)
    await _mk_user(uid, UserRole.INDEPENDENT_TEACHER.value, decoy_tenant_id)
    workspace_subject_id = await _mk_subject(wsid, "مادة-الورشة")
    decoy_subject_id = await _mk_subject(decoy_tenant_id, "مادة-الدخيل")

    resp = await client.get(
        "/subjects",
        headers=_headers(uid, UserRole.INDEPENDENT_TEACHER.value, decoy_tenant_id),
    )
    assert resp.status_code == 200, resp.text
    returned_ids = {s["id"] for s in resp.json()}
    assert workspace_subject_id in returned_ids
    assert decoy_subject_id not in returned_ids


@pytest.mark.asyncio
async def test_regular_teacher_token_gets_tenant_scoped_subjects(client):
    """A non-IT school teacher is unaffected: it keeps receiving subjects
    scoped to its own tenant_id and never another tenant's rows."""
    uid = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())

    await _mk_school(tenant_id)
    await _mk_school(other_tenant_id)
    await _mk_user(uid, UserRole.TEACHER.value, tenant_id)
    own_subject_id = await _mk_subject(tenant_id, "مادة-المدرسة")
    other_subject_id = await _mk_subject(other_tenant_id, "مادة-مدرسة-أخرى")

    resp = await client.get(
        "/subjects",
        headers=_headers(uid, UserRole.TEACHER.value, tenant_id),
    )
    assert resp.status_code == 200, resp.text
    returned_ids = {s["id"] for s in resp.json()}
    assert own_subject_id in returned_ids
    assert other_subject_id not in returned_ids
