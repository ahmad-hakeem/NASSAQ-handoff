"""Regression tests for Task #512.

Task #508/#509 fixed the `X-School-Context` preview-mode leak on the
four highest-traffic admin list endpoints (`/students`, `/teachers`,
`/classes`, `/parents`), and `backend/tests/test_preview_tenant_scope.py`
locked that behaviour in.

Task #512 audited every other backend list endpoint that reads
`X-School-Context` and confirmed they already route through
`utils.tenant_scope.resolve_school_id` for BOTH the Platform Admin and
non-Platform branches. These tests pin down the same 4-scenario
contract on the remaining admin list endpoints so a future refactor of
`resolve_school_id` or any of these routes cannot silently re-open the
leak:

    1. Plain Platform Admin token + X-School-Context  -> 403
    2. Impersonation token + matching X-School-Context -> only that school's rows
    3. Impersonation token + mismatched X-School-Context -> 403
    4. School Principal of school A + X-School-Context=school B -> 403

Endpoints covered (all under /api):
    GET /academic-years
    GET /terms
    GET /subjects
    GET /school/subjects
    GET /school/constraints
    GET /academic/subjects?include_global=false

`/grade-levels` reads the header through the same `resolve_school_id`
helper, but has a pre-existing ORM-vs-Postgres schema drift that
prevents the seed/round-trip pattern used here: `grade_levels` is
missing `name`/`created_at` on the ORM model (response Pydantic
validation fails). That is outside the scope of Task #512 — the
security contract is still enforced by the shared `resolve_school_id`
helper, which IS covered here through every other endpoint that calls
it.

Task #521 added `tenant_id` and `is_global` columns to
`educational_stages`, so `/academic/stages` is now exercised here too.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


# --- helpers ---------------------------------------------------------------


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_platform_admin_user() -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
        "email": f"{uid}@t.test",
        "full_name": "Platform Admin",
        "is_active": True,
        "password_hash": "x",
    })
    return uid


async def _plain_platform_admin_token() -> str:
    uid = await _seed_platform_admin_user()
    return create_access_token({
        "sub": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
    })


async def _impersonation_token(target_tenant_id: str) -> str:
    uid = await _seed_platform_admin_user()
    return create_access_token({
        "sub": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": target_tenant_id,
        "is_impersonating": True,
        "original_role": UserRole.PLATFORM_ADMIN.value,
        "original_user_id": uid,
    })


async def _seed_principal_token(tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": "Principal",
        "is_active": True,
        "password_hash": "x",
    })
    return create_access_token({
        "sub": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": tenant_id,
    })


# --- per-endpoint seeders --------------------------------------------------
#
# Each seeder inserts ONE row in the given school and returns its id so the
# "impersonation matches" scenario can assert both inclusion (school B row
# present) and isolation (school A row absent).


async def _seed_academic_year(school_id: str) -> str:
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "academic_years", {
        "id": rid,
        "school_id": school_id,
        "name": f"AY-{rid[:6]}",
        "start_date": "2025-09-01",
        "end_date": "2026-06-30",
        "is_current": False,
        "created_at": "2025-09-01T00:00:00",
    })
    return rid


async def _seed_term(school_id: str) -> str:
    ay = await _seed_academic_year(school_id)
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "terms", {
        "id": rid,
        "school_id": school_id,
        "academic_year_id": ay,
        "name": f"T-{rid[:6]}",
        "start_date": "2025-09-01",
        "end_date": "2025-12-31",
        "is_current": False,
        "created_at": "2025-09-01T00:00:00",
    })
    return rid


async def _seed_grade_level(school_id: str) -> str:
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": rid,
        "school_id": school_id,
        "name": f"G-{rid[:6]}",
        "order": 1,
        "is_active": True,
        "created_at": "2025-09-01T00:00:00",
    })
    return rid


async def _seed_subject_school_id(school_id: str) -> str:
    """For routes that query `subjects` by `school_id` (e.g. /subjects,
    /school/subjects)."""
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": rid,
        "school_id": school_id,
        "name": f"Subj-{rid[:6]}",
        "name_ar": f"Subj-{rid[:6]}",
        "is_active": True,
    })
    return rid


async def _seed_subject_tenant_id(school_id: str) -> str:
    """For routes that query `subjects` by `tenant_id` (e.g. /academic/subjects).
    `is_global` is explicitly False so the row is not picked up by the
    global-fallback branch."""
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": rid,
        "tenant_id": school_id,
        "school_id": school_id,
        "name": f"Subj-{rid[:6]}",
        "name_ar": f"Subj-{rid[:6]}",
        "is_active": True,
        "is_global": False,
    })
    return rid


async def _seed_constraint(school_id: str) -> str:
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "school_constraints", {
        "id": rid,
        "school_id": school_id,
        "name_ar": f"C-{rid[:6]}",
        "type": "hard",
        "priority": "high",
        "is_active": True,
    })
    return rid


async def _seed_stage(school_id: str) -> str:
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "educational_stages", {
        "id": rid,
        "tenant_id": school_id,
        "name_ar": f"Stage-{rid[:6]}",
        "code": f"S{rid[:6]}",
        "order": 1,
        "is_active": True,
        "is_global": False,
    })
    return rid


# --- response unpackers ----------------------------------------------------


def _extract_rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("stages", "subjects", "terms", "data", "items"):
            v = payload.get(key)
            if isinstance(v, list):
                return v
    return []


def _row_ids(rows):
    out = set()
    for r in rows:
        if isinstance(r, dict):
            v = r.get("id")
            if v:
                out.add(v)
    return out


# --- endpoint matrix --------------------------------------------------------
#
# (url, seeder)
# The seeder is invoked once per school so we always have a school-A row
# AND a school-B row in the relevant collection.

ENDPOINTS = [
    ("/academic-years",   _seed_academic_year),
    ("/terms",            _seed_term),
    ("/subjects",         _seed_subject_school_id),
    ("/school/subjects",  _seed_subject_school_id),
    ("/school/constraints", _seed_constraint),
    # `include_global=false` removes the global-row OR branch so the
    # "school A row absent" assertion isn't polluted by ambient globals.
    ("/academic/subjects?include_global=false", _seed_subject_tenant_id),
    # Task #521: educational_stages now has tenant_id + is_global columns.
    # `include_global=false` keeps the seeded global defaults out of the
    # response so the "school A row absent" assertion is clean.
    ("/academic/stages?include_global=false", _seed_stage),
]


@pytest_asyncio.fixture
async def two_school_rows(tenant_a, tenant_b, request):
    """Per-endpoint two-tenant seeding fixture parametrized via
    `request.param = (url, seeder)`."""
    _url, seeder = request.param
    row_a = await seeder(tenant_a)
    row_b = await seeder(tenant_b)
    return {
        "school_a": tenant_a,
        "school_b": tenant_b,
        "row_a": row_a,
        "row_b": row_b,
    }


# --- tests -----------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "two_school_rows,url",
    [((u, s), u) for (u, s) in ENDPOINTS],
    indirect=["two_school_rows"],
)
async def test_plain_platform_admin_with_preview_header_denied(
    client, two_school_rows, url,
):
    """1) Plain Platform Admin token + X-School-Context -> 403 (no silent widen)."""
    resp = await client.get(
        url,
        headers={
            **_bearer(await _plain_platform_admin_token()),
            "X-School-Context": two_school_rows["school_b"],
        },
    )
    assert resp.status_code == 403, f"{url}: {resp.status_code} {resp.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "two_school_rows,url",
    [((u, s), u) for (u, s) in ENDPOINTS],
    indirect=["two_school_rows"],
)
async def test_impersonation_matching_header_returns_only_target_tenant(
    client, two_school_rows, url,
):
    """2) Impersonation token with matching header returns only that school's rows."""
    school_b = two_school_rows["school_b"]
    resp = await client.get(
        url,
        headers={
            **_bearer(await _impersonation_token(school_b)),
            "X-School-Context": school_b,
        },
    )
    assert resp.status_code == 200, f"{url}: {resp.status_code} {resp.text}"
    ids = _row_ids(_extract_rows(resp.json()))
    assert two_school_rows["row_b"] in ids, (
        f"{url}: expected school B row {two_school_rows['row_b']} in {ids}"
    )
    assert two_school_rows["row_a"] not in ids, (
        f"{url}: school A row {two_school_rows['row_a']} leaked into "
        f"impersonation of school B: {ids}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "two_school_rows,url",
    [((u, s), u) for (u, s) in ENDPOINTS],
    indirect=["two_school_rows"],
)
async def test_impersonation_mismatched_header_denied(
    client, two_school_rows, url,
):
    """3) Impersonation pinned to school B + header pointing at school A -> 403."""
    resp = await client.get(
        url,
        headers={
            **_bearer(await _impersonation_token(two_school_rows["school_b"])),
            "X-School-Context": two_school_rows["school_a"],
        },
    )
    assert resp.status_code == 403, f"{url}: {resp.status_code} {resp.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "two_school_rows,url",
    [((u, s), u) for (u, s) in ENDPOINTS],
    indirect=["two_school_rows"],
)
async def test_school_principal_with_foreign_header_denied(
    client, two_school_rows, url,
):
    """4) School Principal of school A + X-School-Context=school B -> 403."""
    token = await _seed_principal_token(two_school_rows["school_a"])
    resp = await client.get(
        url,
        headers={
            **_bearer(token),
            "X-School-Context": two_school_rows["school_b"],
        },
    )
    assert resp.status_code == 403, f"{url}: {resp.status_code} {resp.text}"
