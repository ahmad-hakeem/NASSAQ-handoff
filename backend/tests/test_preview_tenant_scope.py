"""Regression tests for Task #508/#509.

Task #508 closed an `X-School-Context` preview-mode leak in four list
endpoints (`/students`, `/teachers`, `/classes`, `/parents`) that were
silently returning cross-tenant data to plain Platform Admin tokens.

These tests pin down the four behaviours the fix established, for each
endpoint, so a future refactor of `resolve_school_id` or any of the
routes cannot re-open the same leak undetected:

    1. Plain Platform Admin token + X-School-Context  → 403
    2. Impersonation token + matching X-School-Context → only that school's rows
    3. Impersonation token + mismatched X-School-Context → 403
    4. School Principal token + foreign X-School-Context → 403
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
    """Plain (non-impersonating) Platform Admin access token.

    `tenant_id` on the token is irrelevant — `resolve_school_id` keys the
    impersonation check off `is_impersonating`, which is absent here.
    """
    uid = await _seed_platform_admin_user()
    return create_access_token({
        "sub": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
    })


async def _impersonation_token(target_tenant_id: str) -> str:
    """Platform Admin token minted as if by `/role-switch/switch`:
    carries `is_impersonating=True` and pins `tenant_id` to the target."""
    uid = await _seed_platform_admin_user()
    return create_access_token({
        "sub": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": target_tenant_id,
        "is_impersonating": True,
        "original_role": UserRole.PLATFORM_ADMIN.value,
        "original_user_id": uid,
    })


async def _seed_principal_user(tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": "Principal Test",
        "is_active": True,
        "password_hash": "x",
    })
    return create_access_token({
        "sub": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": tenant_id,
    })


async def _seed_class(school_id: str, name: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": name,
        "is_active": True,
    })
    return cid


async def _seed_student(school_id: str, class_id: str | None = None) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": f"Student-{sid[:6]}",
        "class_id": class_id,
        "is_active": True,
    })
    return sid


async def _seed_teacher(school_id: str) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "school_id": school_id,
        "full_name": f"Teacher-{tid[:6]}",
        "email": f"t-{tid}@t.test",
        "is_active": True,
    })
    return tid


async def _seed_parent(school_id: str) -> str:
    pid = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": pid,
        "school_id": school_id,
        "full_name": f"Parent-{pid[:6]}",
        "email": f"p-{pid}@t.test",
        "is_active": True,
    })
    return pid


# --- fixtures --------------------------------------------------------------


@pytest_asyncio.fixture
async def two_school_directory(tenant_a, tenant_b):
    """Seed one of each entity in BOTH schools so we can verify both
    isolation (school B rows returned, school A rows excluded) and
    non-emptiness (school B rows are actually present)."""
    cls_a = await _seed_class(tenant_a, "A-Class")
    cls_b = await _seed_class(tenant_b, "B-Class")
    return {
        "school_a": tenant_a,
        "school_b": tenant_b,
        "class_a": cls_a,
        "class_b": cls_b,
        "student_a": await _seed_student(tenant_a, cls_a),
        "student_b": await _seed_student(tenant_b, cls_b),
        "teacher_a": await _seed_teacher(tenant_a),
        "teacher_b": await _seed_teacher(tenant_b),
        "parent_a": await _seed_parent(tenant_a),
        "parent_b": await _seed_parent(tenant_b),
    }


# Each endpoint advertises (a) its URL and (b) the dict key under
# `two_school_directory` that names the seeded row id in school B and A.
ENDPOINTS = [
    ("/students", "student_b", "student_a"),
    ("/teachers", "teacher_b", "teacher_a"),
    ("/classes",  "class_b",   "class_a"),
    ("/parents",  "parent_b",  "parent_a"),
]


def _extract_rows(payload):
    """`/parents` returns ``{"parents": [...]}``; the others return a list."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("parents", "students", "teachers", "classes", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def _row_ids(rows):
    out = set()
    for r in rows:
        if isinstance(r, dict):
            v = r.get("id") or r.get("teacher_id") or r.get("student_id")
            if v:
                out.add(v)
    return out


# --- tests -----------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("url,b_key,a_key", ENDPOINTS)
async def test_plain_platform_admin_with_preview_header_denied(
    client, two_school_directory, url, b_key, a_key,
):
    """1) Plain Platform Admin token + X-School-Context → 403 (no silent widen)."""
    resp = await client.get(
        url,
        headers={
            **_bearer(await _plain_platform_admin_token()),
            "X-School-Context": two_school_directory["school_b"],
        },
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("url,b_key,a_key", ENDPOINTS)
async def test_impersonation_matching_header_returns_only_target_tenant(
    client, two_school_directory, url, b_key, a_key,
):
    """2) Impersonation token with matching header returns only that school's rows."""
    school_b = two_school_directory["school_b"]
    resp = await client.get(
        url,
        headers={
            **_bearer(await _impersonation_token(school_b)),
            "X-School-Context": school_b,
        },
    )
    assert resp.status_code == 200, resp.text
    ids = _row_ids(_extract_rows(resp.json()))
    assert two_school_directory[b_key] in ids, (
        f"{url}: expected school B row {two_school_directory[b_key]} in {ids}"
    )
    assert two_school_directory[a_key] not in ids, (
        f"{url}: school A row {two_school_directory[a_key]} leaked into impersonation "
        f"of school B: {ids}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("url,b_key,a_key", ENDPOINTS)
async def test_impersonation_mismatched_header_denied(
    client, two_school_directory, url, b_key, a_key,
):
    """3) Impersonation pinned to school B + header pointing at school A → 403."""
    resp = await client.get(
        url,
        headers={
            **_bearer(await _impersonation_token(two_school_directory["school_b"])),
            "X-School-Context": two_school_directory["school_a"],
        },
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("url,b_key,a_key", ENDPOINTS)
async def test_school_principal_with_foreign_header_denied(
    client, two_school_directory, url, b_key, a_key,
):
    """4) School Principal of school A + X-School-Context=school B → 403."""
    principal_token = await _seed_principal_user(two_school_directory["school_a"])
    resp = await client.get(
        url,
        headers={
            **_bearer(principal_token),
            "X-School-Context": two_school_directory["school_b"],
        },
    )
    assert resp.status_code == 403, resp.text
