"""Regression coverage for GET /parents children aggregation.

Background — Task #335 (Users-and-Classes Management page reportedly
shows 0 students / 0 parents in production). Backend reads were
verified correct in dev; the FE silent-error swallow was hardened.
This test locks in the deterministic children aggregation in
`backend/routes/academics_student_routes.py::get_parents` so that the
per-parent `children_count` cannot silently collapse to 0 when only
one of the two link sources is populated:

  * canonical legacy path A — `parents.student_ids` array
  * canonical legacy path B — `students.parent_id` back-reference

Both must contribute, deduped by student id, scoped by tenant.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


async def _admin_headers(tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": "school admin",
        "is_active": True,
        "password_hash": "x",
    })
    token = create_access_token({
        "sub": uid,
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _raw_insert_student(*, student_id: str, school_id: str,
                              parent_id: str | None = None,
                              full_name: str = "طالب") -> None:
    await db.session.execute(
        text(
            """
            INSERT INTO students (id, school_id, full_name, parent_id, is_active)
            VALUES (:id, :school_id, :full_name, :parent_id, true)
            """
        ),
        {
            "id": student_id,
            "school_id": school_id,
            "full_name": full_name,
            "parent_id": parent_id,
        },
    )


async def _insert_parent(*, parent_id: str, school_id: str,
                         student_ids: list[str] | None = None) -> None:
    await gd_insert(db.session, "parents", {
        "id": parent_id,
        "full_name": "ولي أمر",
        "email": f"p-{parent_id}@t.test",
        "school_id": school_id,
        "is_active": True,
        "student_ids": list(student_ids or []),
    })


@pytest.mark.asyncio
async def test_parents_endpoint_uses_back_reference_when_student_ids_empty(
    client, tenant_a
):
    """Parent row has empty `student_ids` but a real student row points
    at it via `students.parent_id` — children must still surface."""
    parent_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())
    await _insert_parent(parent_id=parent_id, school_id=tenant_a, student_ids=[])
    await _raw_insert_student(
        student_id=student_id, school_id=tenant_a, parent_id=parent_id
    )

    res = await client.get("/parents", headers=await _admin_headers(tenant_a))
    assert res.status_code == 200, res.text
    parents = res.json()
    target = next((p for p in parents if p["id"] == parent_id), None)
    assert target is not None
    assert target["children_count"] == 1
    assert {c["id"] for c in target["children"]} == {student_id}


@pytest.mark.asyncio
async def test_parents_endpoint_dedupes_when_both_sources_populated(
    client, tenant_a
):
    """When BOTH `parents.student_ids` and `students.parent_id` reference
    the same child, the response must include the child exactly once."""
    parent_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())
    await _insert_parent(
        parent_id=parent_id, school_id=tenant_a, student_ids=[student_id]
    )
    await _raw_insert_student(
        student_id=student_id, school_id=tenant_a, parent_id=parent_id
    )

    res = await client.get("/parents", headers=await _admin_headers(tenant_a))
    assert res.status_code == 200, res.text
    target = next((p for p in res.json() if p["id"] == parent_id), None)
    assert target is not None
    assert target["children_count"] == 1
    assert [c["id"] for c in target["children"]] == [student_id]


@pytest.mark.asyncio
async def test_parents_endpoint_back_reference_is_tenant_scoped(
    client, tenant_a, tenant_b
):
    """A foreign-tenant student row that happens to point at our
    parent_id must NEVER appear in our parents listing — the back-ref
    lookup must be scoped by school_id (tenant safety invariant)."""
    parent_id = str(uuid.uuid4())
    own_student_id = str(uuid.uuid4())
    foreign_student_id = str(uuid.uuid4())
    await _insert_parent(parent_id=parent_id, school_id=tenant_a, student_ids=[])
    await _raw_insert_student(
        student_id=own_student_id, school_id=tenant_a, parent_id=parent_id
    )
    await _raw_insert_student(
        student_id=foreign_student_id, school_id=tenant_b, parent_id=parent_id,
        full_name="طالب من مدرسة أخرى",
    )

    res = await client.get("/parents", headers=await _admin_headers(tenant_a))
    assert res.status_code == 200, res.text
    target = next((p for p in res.json() if p["id"] == parent_id), None)
    assert target is not None
    ids = {c["id"] for c in target["children"]}
    assert own_student_id in ids
    assert foreign_student_id not in ids
