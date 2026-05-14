"""Regression coverage for the Parent Portal dashboard linkage path.

Background — production incident:
  The parent dashboard at /parent-portal/dashboard was returning 500 for
  every parent because `_get_linked_student_ids` queried the optional
  `guardian_links` join table unconditionally. In environments where the
  table was never installed (only the canonical `students.parent_id` and
  `parents.student_ids` legacy paths exist) SQLAlchemy raised, the route
  500'd, and the FE collapsed every non-2xx into the generic "check your
  internet" error — masking valid parents who had children linked via
  `students.parent_id`.

Coverage (per the implementation spec attached to the task):
  * canonical `students.parent_id` linkage → dashboard returns the child
  * parent with zero linked children → 200 with an empty children array
    (a truthful empty state, never a 500)
  * cross-tenant child rows must not leak into a parent's response
  * the dashboard route stays 2xx even when the optional `guardian_links`
    join-table lookup explodes — proves the regression is fixed and the
    fail-safe degradation in `_get_linked_student_ids` holds.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio

from sqlalchemy import text

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


async def _raw_insert_student(*, student_id: str, school_id: str, parent_id: str, full_name: str = "طالب تجريبي") -> None:
    """Insert a `students` row via raw SQL.

    The ORM model carries optional columns (`talents`, `character_traits`,
    `is_gifted`) that have not yet been migrated everywhere; using
    `gd_insert` injects defaults for those columns and explodes on DBs
    that haven't run the migration. This helper sticks to the canonical
    column subset the resolver actually reads.
    """
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


def _parent_headers(user_id: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _seed_parent_with_child(tenant_id: str, *, link_child: bool = True):
    """Mirrors the production data shape:
      - users row with role=parent and parent_id pointing at a parents row
      - parents row with empty student_ids array (legacy default)
      - optionally a students row with parent_id = parents.id (canonical
        legacy linkage path that the resolver MUST honour).
    """
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
    student_id = None
    if link_child:
        student_id = str(uuid.uuid4())
        await _raw_insert_student(
            student_id=student_id,
            school_id=tenant_id,
            parent_id=parent_record_id,
        )
    return {
        "user_id": parent_user_id,
        "parent_record_id": parent_record_id,
        "student_id": student_id,
    }


@pytest.mark.asyncio
async def test_dashboard_resolves_child_via_canonical_parent_id_linkage(client, tenant_a):
    """Canonical legacy linkage (students.parent_id → parents.id) must
    surface the child on the dashboard. This is the path the failing
    production parent (إبراهيم الجهني) was on."""
    seeded = await _seed_parent_with_child(tenant_a, link_child=True)
    res = await client.get(
        "/parent-portal/dashboard",
        headers=_parent_headers(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["children_count"] >= 1
    ids = {c["id"] for c in body["children"]}
    assert seeded["student_id"] in ids


@pytest.mark.asyncio
async def test_dashboard_returns_empty_state_for_unlinked_parent(client, tenant_a):
    """No linked children → 200 with empty array (truthful empty state).
    The FE renders the "no children enrolled" empty card; it must NEVER
    see a 500 in this case (the previous bug)."""
    seeded = await _seed_parent_with_child(tenant_a, link_child=False)
    res = await client.get(
        "/parent-portal/dashboard",
        headers=_parent_headers(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["children_count"] == 0
    assert body["children"] == []


@pytest.mark.asyncio
async def test_dashboard_does_not_leak_other_tenant_children(client, tenant_a, tenant_b):
    """Tenant scoping invariant: a parent in tenant A must never see a
    student row from tenant B even if the parent_id values happened to
    collide. The resolver scopes the students query by school_id."""
    seeded = await _seed_parent_with_child(tenant_a, link_child=True)
    # Forge a tenant-B student whose parent_id matches our tenant-A parent.
    foreign_student_id = str(uuid.uuid4())
    await _raw_insert_student(
        student_id=foreign_student_id,
        school_id=tenant_b,
        parent_id=seeded["parent_record_id"],
        full_name="طالب من مدرسة أخرى",
    )
    res = await client.get(
        "/parent-portal/dashboard",
        headers=_parent_headers(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    ids = {c["id"] for c in res.json()["children"]}
    assert seeded["student_id"] in ids
    assert foreign_student_id not in ids


@pytest.mark.asyncio
async def test_child_by_id_route_resolves_when_guardian_links_lookup_explodes(client, tenant_a):
    """By-id parent route (`_verify_parent_access`) regression.

    The same missing-table failure that broke the dashboard could 500 the
    by-id child detail/grades/attendance routes via fallback 1. The
    canonical `students.parent_id` lookup MUST still authorize the child
    even when the optional `guardian_links` join table is unreachable, and
    the §8 cross-tenant 404 invariant must still hold for foreign children.
    """
    seeded = await _seed_parent_with_child(tenant_a, link_child=True)

    from routes import parent_portal_routes as ppr
    real_gd_find_one = ppr.gd_find_one

    async def _explode_on_guardian_links(session, collection, *args, **kwargs):
        if collection == "guardian_links":
            from sqlalchemy.exc import ProgrammingError as _PE
            raise _PE(
                'SELECT', {}, Exception('relation "guardian_links" does not exist')
            )
        return await real_gd_find_one(session, collection, *args, **kwargs)

    with patch.object(ppr, "gd_find_one", side_effect=_explode_on_guardian_links):
        # Linked child resolves successfully (canonical path wins).
        ok = await client.get(
            f"/parent-portal/child/{seeded['student_id']}",
            headers=_parent_headers(seeded["user_id"], tenant_a),
        )
        assert ok.status_code == 200, ok.text

        # Unrelated child id MUST still be denied (the parent-portal
        # by-id route returns 403 on miss; the §8 IT invariant for 404 is
        # IT-only). The fail-safe must NOT widen access into a 200.
        bogus_child_id = str(uuid.uuid4())
        denied = await client.get(
            f"/parent-portal/child/{bogus_child_id}",
            headers=_parent_headers(seeded["user_id"], tenant_a),
        )
        assert denied.status_code in (403, 404), denied.text

        # Locks in the security property the architect flagged: even an
        # EXISTING student row that is NOT linked to this parent must be
        # denied while fallback-1 is exploding. A naive fail-open would
        # have widened access here.
        unrelated_parent_id = str(uuid.uuid4())
        unrelated_child_id = str(uuid.uuid4())
        await gd_insert(db.session, "parents", {
            "id": unrelated_parent_id,
            "full_name": "ولي أمر آخر",
            "email": f"p-{unrelated_parent_id}@t.test",
            "school_id": tenant_a,
            "is_active": True,
            "student_ids": [],
        })
        await _raw_insert_student(
            student_id=unrelated_child_id,
            school_id=tenant_a,
            parent_id=unrelated_parent_id,
            full_name="طالب غير مرتبط",
        )
        denied_existing = await client.get(
            f"/parent-portal/child/{unrelated_child_id}",
            headers=_parent_headers(seeded["user_id"], tenant_a),
        )
        assert denied_existing.status_code in (403, 404), denied_existing.text


@pytest.mark.asyncio
async def test_child_by_id_route_resolves_when_parents_lookup_explodes(client, tenant_a):
    """Companion regression for fallback 2 (`parents.student_ids`).

    The same hardening applies to the second legacy linkage path. A
    missing `parents` table / column must not 500 by-id parent routes,
    and the fail-safe must not widen access to unrelated children.
    """
    seeded = await _seed_parent_with_child(tenant_a, link_child=True)

    from routes import parent_portal_routes as ppr
    real_gd_find_one = ppr.gd_find_one

    async def _explode_on_parents(session, collection, *args, **kwargs):
        if collection == "parents":
            from sqlalchemy.exc import ProgrammingError as _PE
            raise _PE(
                'SELECT', {}, Exception('column parents.student_ids does not exist')
            )
        return await real_gd_find_one(session, collection, *args, **kwargs)

    with patch.object(ppr, "gd_find_one", side_effect=_explode_on_parents):
        ok = await client.get(
            f"/parent-portal/child/{seeded['student_id']}",
            headers=_parent_headers(seeded["user_id"], tenant_a),
        )
        assert ok.status_code == 200, ok.text

        bogus = await client.get(
            f"/parent-portal/child/{uuid.uuid4()}",
            headers=_parent_headers(seeded["user_id"], tenant_a),
        )
        assert bogus.status_code in (403, 404), bogus.text


@pytest.mark.asyncio
async def test_dashboard_still_2xx_when_guardian_links_lookup_explodes(client, tenant_a):
    """Regression for the production 500.

    Simulate the missing `guardian_links` table by patching the route's
    `gd_find` so that any call against that collection raises (mirrors the
    SQLAlchemy `ProgrammingError: relation "guardian_links" does not
    exist` we saw in prod). The dashboard MUST still return the canonical
    child via `students.parent_id` instead of 500ing the whole response."""
    seeded = await _seed_parent_with_child(tenant_a, link_child=True)

    from routes import parent_portal_routes as ppr
    real_gd_find = ppr.gd_find

    async def _explode_on_guardian_links(session, collection, *args, **kwargs):
        if collection == "guardian_links":
            from sqlalchemy.exc import ProgrammingError as _PE
            # Mirrors the production stack: asyncpg UndefinedTableError
            # surfaces as a SQLAlchemy ProgrammingError.
            raise _PE(
                'SELECT', {}, Exception('relation "guardian_links" does not exist')
            )
        return await real_gd_find(session, collection, *args, **kwargs)

    with patch.object(ppr, "gd_find", side_effect=_explode_on_guardian_links):
        res = await client.get(
            "/parent-portal/dashboard",
            headers=_parent_headers(seeded["user_id"], tenant_a),
        )

    assert res.status_code == 200, res.text
    ids = {c["id"] for c in res.json()["children"]}
    assert seeded["student_id"] in ids, (
        "canonical students.parent_id linkage must still resolve the child "
        "when the optional guardian_links join table is missing"
    )
