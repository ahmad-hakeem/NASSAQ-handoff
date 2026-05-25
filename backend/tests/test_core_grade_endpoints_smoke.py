"""Task #592 — Core grade-level endpoint smoke tests.

Guards against schema/model mismatches on:
  - GET  /api/grade-levels
  - POST /api/grade-levels
  - GET  /api/classes/options/grades

Covers:
  1. Legacy-row graceful handling — a `grade_levels` row with only `id`
     and `school_id` must NOT cause a 500; the list endpoint must return
     200 and include (or silently skip) the incomplete row.
  2. POST → GET round-trip — the created row appears in the list with the
     correct `name`, `name_ar`, and `school_id`; `created_at` must be
     absent from the response (regression for the original
     ValidationError).
  3. /classes/options/grades availability — returns 200 with a JSON array
     where every item has at least an `id` field.
  4. Unauthenticated access — both endpoints must refuse without a valid
     JWT (401 or 403).
"""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from server import app
from dependencies import db, UserRole
from engines.sql_utils import gd_insert
from tests.conftest import _mk_user, _mk_school, _headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_tenant() -> str:
    """Create a fresh school and return its id."""
    sid = str(uuid.uuid4())
    await _mk_school(sid)
    return sid


# ---------------------------------------------------------------------------
# Test 1 — Legacy / incomplete row must not cause 500
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_legacy_grade_row_no_500(client):
    """A grade_levels row with only id + school_id must not 500 the list endpoint.

    This is the direct regression guard for the production incident: Pydantic
    blew up with a ValidationError when `name` / `created_at` were required
    but absent from the ORM row.
    """
    tenant = await _seed_tenant()
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant)
    hdrs = _headers(principal)

    legacy_id = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": legacy_id,
        "school_id": tenant,
    })

    resp = await client.get("/grade-levels", headers=hdrs)
    assert resp.status_code == 200, (
        f"Expected 200 for tenant with a legacy grade row, got {resp.status_code}: {resp.text}"
    )
    rows = resp.json()
    assert isinstance(rows, list), f"Expected a list, got: {rows}"


# ---------------------------------------------------------------------------
# Test 2 — POST → GET round-trip with schema assertion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_then_get_grade_level_round_trip(client):
    """Create a grade level then verify it appears in the list.

    Asserts:
    - id is present
    - name equals the submitted Arabic name
    - name_ar equals the submitted Arabic name
    - school_id matches the tenant
    - created_at is NOT present in the response (regression: it was once a
      required field that the DB never populated, causing a Pydantic crash)
    """
    tenant = await _seed_tenant()
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant)
    hdrs = _headers(principal)

    create_resp = await client.post(
        "/grade-levels",
        headers=hdrs,
        json={
            "name": "الصف الأول",
            "name_en": "Grade 1",
            "order": 1,
            "is_active": True,
            "school_id": tenant,
        },
    )
    assert create_resp.status_code == 200, (
        f"POST /grade-levels failed: {create_resp.status_code} {create_resp.text}"
    )
    created = create_resp.json()
    assert created.get("id"), f"Created row has no id: {created}"
    assert created.get("name") == "الصف الأول", created
    assert created.get("name_ar") == "الصف الأول", created
    assert created.get("school_id") == tenant, created
    assert "created_at" not in created, (
        f"created_at must not appear in the response (regression guard): {created}"
    )

    list_resp = await client.get("/grade-levels", headers=hdrs)
    assert list_resp.status_code == 200, (
        f"GET /grade-levels failed after POST: {list_resp.status_code} {list_resp.text}"
    )
    rows = list_resp.json()
    match = next((r for r in rows if r.get("id") == created["id"]), None)
    assert match is not None, (
        f"Newly created grade level {created['id']} not found in list: {rows}"
    )
    assert match.get("name") == "الصف الأول", match
    assert match.get("name_ar") == "الصف الأول", match
    assert match.get("school_id") == tenant, match
    assert "created_at" not in match, (
        f"created_at must not appear in list items (regression guard): {match}"
    )


# ---------------------------------------------------------------------------
# Test 3 — /classes/options/grades availability
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classes_options_grades_availability(client):
    """GET /classes/options/grades returns 200 with a JSON array.

    Each item in the array must have at least an `id` field (basic schema
    guard). An empty array is acceptable if the school has no grade levels.
    """
    tenant = await _seed_tenant()
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant)
    hdrs = _headers(principal)

    grade_id = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": grade_id,
        "school_id": tenant,
        "name_ar": "الصف الثاني",
        "name_en": "Grade 2",
        "order": 2,
        "is_active": True,
    })

    resp = await client.get("/classes/options/grades", headers=hdrs)
    assert resp.status_code == 200, (
        f"GET /classes/options/grades failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    data = body if isinstance(body, list) else body.get("grades", body)
    assert isinstance(data, list), f"Expected a list (or dict with 'grades' key), got: {body}"

    for item in data:
        assert "id" in item, (
            f"Item in /classes/options/grades response is missing 'id' field: {item}"
        )


# ---------------------------------------------------------------------------
# Test 4 — Unauthenticated access returns 401 or 403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grade_levels_requires_authentication(client):
    """GET /api/grade-levels without a JWT must not return 200."""
    resp = await client.get("/grade-levels")
    assert resp.status_code in (401, 403), (
        f"Expected 401/403 for unauthenticated GET /grade-levels, got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_classes_options_grades_requires_authentication(client):
    """GET /api/classes/options/grades without a JWT must not return 200."""
    resp = await client.get("/classes/options/grades")
    assert resp.status_code in (401, 403), (
        f"Expected 401/403 for unauthenticated GET /classes/options/grades, got {resp.status_code}"
    )
