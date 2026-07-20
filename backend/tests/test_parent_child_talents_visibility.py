"""Parent portal — talents & skills visibility (المواهب والمهارات).

Root cause addressed:
  The School-Admin student profile stores talents on the students row
  (`students.talents` + `students.is_gifted`), but every parent-facing
  serializer in parent_portal_routes.py builds a reduced hand-picked dict
  that omitted both fields, so the Parent → Student Profile could never
  show them. There is no business rule hiding talents from parents — the
  fields were simply never exposed.

Contract enforced here:
  1. GET /parent-portal/children           → each child carries talents + is_gifted
  2. GET /parent-portal/child/{id}         → talents + is_gifted present
  3. GET /parent-portal/child/{id}/profile → talents + is_gifted present
  4. A student with no talents yields [] / False (clean empty state), never
     a missing key.
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert
from sqlalchemy import text


def _parent_headers(user_id: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_school() -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"School-{sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return sid


async def _seed_parent_with_child(tenant_id: str, talents: list[str] | None):
    """Parent user + parents row + student linked via students.parent_id."""
    parent_record_id = str(uuid.uuid4())
    parent_user_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": parent_record_id,
        "full_name": "ولي أمر تجريبي",
        "email": f"p-{parent_record_id}@t.test",
        "school_id": tenant_id,
        "is_active": True,
        "student_ids": [],
    })
    await gd_insert(db.session, "users", {
        "id": parent_user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
        "parent_id": parent_record_id,
        "email": f"p-{parent_record_id}@t.test",
        "full_name": "ولي أمر تجريبي",
        "is_active": True,
        "password_hash": "x",
    })
    student_id = str(uuid.uuid4())
    if talents is None:
        await db.session.execute(
            text(
                "INSERT INTO students (id, school_id, full_name, parent_id, is_active)"
                " VALUES (:id, :school_id, :full_name, :parent_id, true)"
            ),
            {
                "id": student_id,
                "school_id": tenant_id,
                "full_name": f"ST-{student_id[:6]}",
                "parent_id": parent_record_id,
            },
        )
    else:
        import json
        await db.session.execute(
            text(
                "INSERT INTO students (id, school_id, full_name, parent_id, is_active,"
                " talents, is_gifted)"
                " VALUES (:id, :school_id, :full_name, :parent_id, true,"
                " CAST(:talents AS jsonb), :is_gifted)"
            ),
            {
                "id": student_id,
                "school_id": tenant_id,
                "full_name": f"ST-{student_id[:6]}",
                "parent_id": parent_record_id,
                "talents": json.dumps(talents),
                "is_gifted": len(talents) > 0,
            },
        )
    return parent_user_id, student_id


TALENTS = ["academically_gifted", "artistic"]


@pytest.mark.asyncio
async def test_children_list_includes_talents(client):
    tenant = await _mk_school()
    parent_uid, student_id = await _seed_parent_with_child(tenant, TALENTS)
    r = await client.get("/parent-portal/children", headers=_parent_headers(parent_uid, tenant))
    assert r.status_code == 200, r.text
    kids = [c for c in r.json()["children"] if c["id"] == student_id]
    assert kids, "seeded child missing from children list"
    assert kids[0].get("talents") == TALENTS
    assert kids[0].get("is_gifted") is True


@pytest.mark.asyncio
async def test_child_details_includes_talents(client):
    tenant = await _mk_school()
    parent_uid, student_id = await _seed_parent_with_child(tenant, TALENTS)
    r = await client.get(f"/parent-portal/child/{student_id}",
                         headers=_parent_headers(parent_uid, tenant))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("talents") == TALENTS
    assert body.get("is_gifted") is True


@pytest.mark.asyncio
async def test_child_profile_includes_talents(client):
    tenant = await _mk_school()
    parent_uid, student_id = await _seed_parent_with_child(tenant, TALENTS)
    r = await client.get(f"/parent-portal/child/{student_id}/profile",
                         headers=_parent_headers(parent_uid, tenant))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("talents") == TALENTS
    assert body.get("is_gifted") is True


@pytest.mark.asyncio
async def test_child_without_talents_yields_clean_empty(client):
    tenant = await _mk_school()
    parent_uid, student_id = await _seed_parent_with_child(tenant, None)
    r = await client.get(f"/parent-portal/child/{student_id}",
                         headers=_parent_headers(parent_uid, tenant))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("talents") == []
    assert body.get("is_gifted") is False
