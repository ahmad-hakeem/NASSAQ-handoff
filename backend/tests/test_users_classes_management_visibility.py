"""Regression coverage for the principal "Users and Classes Management"
read paths (Task #335).

Verifies, for a school_admin / school_principal caller in tenant A:
  * GET /students returns own-tenant rows
  * GET /students never leaks tenant B rows
  * GET /students surfaces a freshly-inserted student immediately
    (Noor-import-style — INSERT then GET on the same connection)
  * GET /classes still aggregates per-class student counts
  * GET /teachers still scopes to the caller's tenant
  * The fail-closed scope guard rejects a token without tenant_id
    (school_admin role with no tenant) with HTTP 403 instead of an
    unscoped or empty 200.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


async def _mk_admin(tenant_id: str) -> str:
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
    return uid


def _headers_for(uid: str, tenant_id: str | None) -> dict:
    payload: dict = {
        "sub": uid,
        "role": UserRole.SCHOOL_ADMIN.value,
    }
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    token = create_access_token(payload)
    return {"Authorization": f"Bearer {token}"}


async def _raw_insert_student(*, student_id: str, school_id: str,
                              class_id: str | None = None,
                              full_name: str = "طالب",
                              is_active: bool = True) -> None:
    await db.session.execute(
        text(
            """
            INSERT INTO students (id, school_id, full_name, class_id, is_active)
            VALUES (:id, :school_id, :full_name, :class_id, :is_active)
            """
        ),
        {
            "id": student_id,
            "school_id": school_id,
            "full_name": full_name,
            "class_id": class_id,
            "is_active": is_active,
        },
    )


@pytest.mark.asyncio
async def test_students_endpoint_returns_own_tenant_rows(client, tenant_a):
    """Baseline: a school_admin in tenant A sees students inserted in
    tenant A — locks in the symptom inverse for Task #335 (page reportedly
    showed 0)."""
    uid = await _mk_admin(tenant_a)
    sid_a = str(uuid.uuid4())
    await _raw_insert_student(student_id=sid_a, school_id=tenant_a)

    res = await client.get("/students", headers=_headers_for(uid, tenant_a))
    assert res.status_code == 200, res.text
    ids = {s["id"] for s in res.json()}
    assert sid_a in ids
    assert len(ids) >= 1


@pytest.mark.asyncio
async def test_students_endpoint_does_not_leak_other_tenant(
    client, tenant_a, tenant_b
):
    """Tenant safety: students belonging to tenant B must NEVER appear
    for a tenant A admin (regression guard for the new fail-closed
    `require_request_school_id` resolver)."""
    uid_a = await _mk_admin(tenant_a)
    sid_a = str(uuid.uuid4())
    sid_b = str(uuid.uuid4())
    await _raw_insert_student(student_id=sid_a, school_id=tenant_a)
    await _raw_insert_student(
        student_id=sid_b, school_id=tenant_b, full_name="طالب أجنبي"
    )

    res = await client.get("/students", headers=_headers_for(uid_a, tenant_a))
    assert res.status_code == 200, res.text
    ids = {s["id"] for s in res.json()}
    assert sid_a in ids
    assert sid_b not in ids


@pytest.mark.asyncio
async def test_freshly_inserted_student_surfaces_immediately(client, tenant_a):
    """Noor-import shape: INSERT then GET on the same session must show
    the new row. Locks in the "newly Noor-imported students missing"
    symptom from Task #335 — if the read path ever silently filters by
    a stale flag, this test fails."""
    uid = await _mk_admin(tenant_a)
    sid = str(uuid.uuid4())
    await _raw_insert_student(
        student_id=sid, school_id=tenant_a, full_name="طالب جديد من نور"
    )

    res = await client.get("/students", headers=_headers_for(uid, tenant_a))
    assert res.status_code == 200, res.text
    ids = {s["id"] for s in res.json()}
    assert sid in ids


@pytest.mark.asyncio
async def test_students_endpoint_fails_closed_without_tenant(client):
    """A token with no tenant_id (e.g. corrupted or pre-bootstrap) must
    NOT receive an unscoped or empty 200 — it must 403 via the canonical
    `require_request_school_id` resolver."""
    uid = str(uuid.uuid4())
    # No DB user row — the route only needs the JWT to reach the
    # scope resolver. We're locking in the resolver's behaviour.
    res = await client.get("/students", headers=_headers_for(uid, None))
    assert res.status_code in (401, 403), res.text


@pytest.mark.asyncio
async def test_classes_endpoint_aggregates_per_class_student_counts(
    client, tenant_a
):
    """Per-class student counts (the cards on the management page) must
    reflect the actual roster — non-regression for the §6.1 server-side
    aggregation in `academics_class_routes.get_classes`."""
    uid = await _mk_admin(tenant_a)
    cls_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cls_id,
        "school_id": tenant_a,
        "name": "صف اختبار 335",
    })
    for _ in range(3):
        await _raw_insert_student(
            student_id=str(uuid.uuid4()), school_id=tenant_a, class_id=cls_id,
        )
    # Add an inactive student to confirm the count excludes is_active=false.
    await _raw_insert_student(
        student_id=str(uuid.uuid4()), school_id=tenant_a, class_id=cls_id,
        is_active=False,
    )

    res = await client.get("/classes", headers=_headers_for(uid, tenant_a))
    assert res.status_code == 200, res.text
    target = next((c for c in res.json() if c["id"] == cls_id), None)
    assert target is not None
    assert target.get("student_count") == 3


@pytest.mark.asyncio
async def test_teachers_endpoint_scoped_to_caller_tenant(
    client, tenant_a, tenant_b
):
    """Non-regression: /teachers must remain tenant-scoped. The Task #335
    diff did not touch this route; this test guards against accidental
    regressions while the parents/students paths were edited."""
    uid_a = await _mk_admin(tenant_a)
    tid_a = str(uuid.uuid4())
    tid_b = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid_a, "school_id": tenant_a,
        "full_name": "معلم أ", "email": f"{tid_a}@t.test",
    })
    await gd_insert(db.session, "teachers", {
        "id": tid_b, "school_id": tenant_b,
        "full_name": "معلم ب", "email": f"{tid_b}@t.test",
    })

    res = await client.get("/teachers", headers=_headers_for(uid_a, tenant_a))
    assert res.status_code == 200, res.text
    ids = {t.get("id") for t in res.json()}
    assert tid_a in ids
    assert tid_b not in ids
