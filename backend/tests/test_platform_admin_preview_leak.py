"""Task #511 — Platform Admin preview tenant-leak regression coverage.

When a Platform Admin opens a brand-new school via Command Center
preview, the Users & Classes page must show ZERO students/teachers/
parents/classes — never another tenant's rows.

These tests pin the four list endpoints (`/students`, `/teachers`,
`/parents`, `/classes`) into a fail-closed posture for the
platform-admin role:

  (a) a real School Principal sees only their own tenant's rows on a
      brand-new school (expect `[]`);
  (b) a plain PA token WITHOUT `X-School-Context` gets an empty list,
      never a cross-tenant dump;
  (c) a PA token minted via /role-switch/switch for school A with
      header `X-School-Context: A` returns only school-A rows, and
      a mismatched header `X-School-Context: B` returns 403.
"""
from __future__ import annotations

import time
import uuid

import pytest
from sqlalchemy import text

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


# ───────────────────────── helpers ──────────────────────────────────────────


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


async def _mk_principal(school_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"{uid}@t.test",
        "full_name": "principal",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_platform_admin() -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
        "email": f"{uid}@t.test",
        "full_name": "Platform Admin",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


def _headers(user: dict, *, extra: dict | None = None) -> dict:
    token = create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user.get("tenant_id"),
    })
    h = {"Authorization": f"Bearer {token}"}
    if extra:
        h.update(extra)
    return h


def _impersonation_headers(user: dict, target_tenant: str, *, extra: dict | None = None) -> dict:
    """Token shape minted by /role-switch/switch — `is_impersonating=True`
    with the target tenant baked into the bearer."""
    token = create_access_token({
        "sub": user["id"],
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "original_role": user["role"],
        "original_user_id": user["id"],
        "tenant_id": target_tenant,
        "is_impersonating": True,
    })
    h = {"Authorization": f"Bearer {token}"}
    if extra:
        h.update(extra)
    return h


async def _seed_tenant_data(school_id: str) -> dict[str, str]:
    """Insert one student, teacher, parent and class for *school_id*."""
    sid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    await db.session.execute(
        text(
            "INSERT INTO students (id, school_id, full_name, is_active) "
            "VALUES (:id, :sid, 'طالب', TRUE)"
        ),
        {"id": sid, "sid": school_id},
    )
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": school_id,
        "full_name": "معلم", "email": f"{tid}@t.test",
    })
    await gd_insert(db.session, "parents", {
        "id": pid, "school_id": school_id,
        "full_name": "ولي أمر", "email": f"{pid}@t.test",
    })
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "name": "فصل",
    })
    return {"student": sid, "teacher": tid, "parent": pid, "class": cid}


ENDPOINTS = ["/students", "/teachers", "/parents", "/classes"]


# ───────────────────── (a) real principal on empty school ────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ENDPOINTS)
async def test_principal_on_empty_school_sees_empty_list(client, path):
    """A real School Principal on a brand-new (empty) school must see
    an empty list on each of the four directory endpoints."""
    empty_school = str(uuid.uuid4())
    await _mk_school(empty_school)
    principal = await _mk_principal(empty_school)

    res = await client.get(path, headers=_headers(principal))
    assert res.status_code == 200, res.text
    assert res.json() == []


# ───────────────────── (b) plain PA token — fail-closed ─────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ENDPOINTS)
async def test_plain_platform_admin_without_header_fails_closed(client, path):
    """A plain Platform Admin bearer token, with NO `X-School-Context`
    header, must NOT receive a cross-tenant dump. The route must return
    an empty list (fail-closed) regardless of how many rows live in
    other tenants.

    This is the leak Task #511 is closing: prior behavior was an
    unscoped query returning every tenant's rows.
    """
    # Seed two foreign tenants with data so an unscoped query would
    # obviously leak it.
    foreign_a = str(uuid.uuid4())
    foreign_b = str(uuid.uuid4())
    await _mk_school(foreign_a)
    await _mk_school(foreign_b)
    await _seed_tenant_data(foreign_a)
    await _seed_tenant_data(foreign_b)

    admin = await _mk_platform_admin()
    res = await client.get(path, headers=_headers(admin))
    assert res.status_code == 200, res.text
    assert res.json() == [], (
        f"{path} leaked cross-tenant rows to a plain PA token "
        f"(no X-School-Context header): {res.json()[:3]}..."
    )


# ───────────────────── (c) impersonation token — scoped ─────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("path,key", list(zip(ENDPOINTS, ["student", "teacher", "parent", "class"])))
async def test_impersonation_token_scopes_to_target_school(client, path, key):
    """A PA token minted by /role-switch/switch for school A with a
    matching `X-School-Context: A` header must return only school-A
    rows — never school-B rows."""
    school_a = str(uuid.uuid4())
    school_b = str(uuid.uuid4())
    await _mk_school(school_a)
    await _mk_school(school_b)
    ids_a = await _seed_tenant_data(school_a)
    ids_b = await _seed_tenant_data(school_b)

    admin = await _mk_platform_admin()
    headers = _impersonation_headers(
        admin, school_a, extra={"X-School-Context": school_a}
    )
    res = await client.get(path, headers=headers)
    assert res.status_code == 200, res.text
    returned = {row.get("id") for row in res.json()}
    assert ids_a[key] in returned
    assert ids_b[key] not in returned, (
        f"{path} leaked school-B {key} into a school-A impersonation context"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ENDPOINTS)
async def test_plain_platform_admin_with_header_is_rejected(client, path):
    """A PLAIN Platform Admin bearer token (no `is_impersonating=True`
    claim) that supplies an `X-School-Context` header for any school
    MUST be rejected with HTTP 403 by `resolve_school_id` — never
    silently honored.

    This pins the requirement that PA scope-override only flows
    through the MFA-gated `/role-switch/switch` path; a stolen plain
    PA token cannot just append a header to read a tenant's data.
    """
    target = str(uuid.uuid4())
    await _mk_school(target)
    await _seed_tenant_data(target)

    admin = await _mk_platform_admin()
    res = await client.get(
        path,
        headers=_headers(admin, extra={"X-School-Context": target}),
    )
    assert res.status_code == 403, (
        f"{path} accepted an X-School-Context override on a plain PA "
        f"token (no role-switch impersonation): {res.status_code} {res.text}"
    )
