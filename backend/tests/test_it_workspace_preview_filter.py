"""
Tests that IT workspaces never surface in the platform-admin preview list
and that the hardened role-switch endpoint refuses itw_* school IDs.

Covers two regression surfaces:
  1. GET /user-roles/my-roles — platform-admin preview list must exclude
     schools whose id starts with ``itw_`` OR whose status is ``archived``
     or ``pending_hard_delete``.
  2. POST /role-switch/switch — must return 403 (not 404 / 200) when the
     caller explicitly supplies an ``itw_`` school id, even with a valid
     reason and fresh MFA.

Design note on the my-roles positive assertion
-----------------------------------------------
The route fetches at most 100 schools via ``gd_find(..., limit=100)``, and
the test DB already holds 100+ committed seed rows.  A newly inserted school
may land beyond the 100-row window because PostgreSQL heap-scans place new
pages after existing ones when there is no ORDER BY clause.

To prove that *real* schools appear while *IT workspaces* do not, the test:
  * checks that at least one preview entry is present (real schools returned)
  * checks that none of the preview entries have an ``itw_*`` id
  * inserts the IT workspace *within the same session* and confirms it is
    absent even though it is visible to the same transaction
This makes the negative assertion precise and the positive assertion robust
against the pre-existing data volume.
"""
from __future__ import annotations

import time
import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert
from utils.platform_admin_preview import MSG_ARCHIVED, MSG_INDEPENDENT_TEACHER_WORKSPACE


# ───────────────────────── helpers ──────────────────────────────────────────


async def _mk_platform_admin() -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
        "email": f"pa-{uid}@t.test",
        "full_name": "Platform Admin",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_real_school() -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"Real School {sid[:6]}",
        "code": f"RS{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return sid


async def _seed_principal(school_id: str) -> dict:
    """Seed an active school_principal user in *school_id*.

    Required because /role-switch/switch returns 422 if the target school
    has no active principal — the endpoint enforces this as a pre-condition
    before minting the impersonation token.
    """
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"principal-{uid}@t.test",
        "full_name": "Principal User",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_it_workspace(status: str = "archived") -> str:
    uid = str(uuid.uuid4())
    ws_id = f"itw_{uid}"
    await gd_insert(db.session, "schools", {
        "id": ws_id,
        "name": f"IT Workspace {uid[:6]}",
        "code": f"ITW{uid[:7]}",
        "status": status,
        "country": "SA",
        "language": "ar",
    })
    return ws_id


def _admin_headers(user: dict, *, fresh_mfa: bool = False) -> dict:
    data: dict = {
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user.get("tenant_id"),
    }
    if fresh_mfa:
        data["mfa_recent_at"] = int(time.time())
    token = create_access_token(data)
    return {"Authorization": f"Bearer {token}"}


# ───────────────────── my-roles preview list ────────────────────────────────


@pytest.mark.asyncio
async def test_my_roles_no_itw_prefix_schools_leak_into_preview(client):
    """Core regression guard: none of the preview entries returned for a
    platform admin must have a tenant_id that starts with ``itw_``.

    Two IT workspaces (one archived, one with status=active) are inserted
    within the test transaction.  We confirm neither appears in the preview
    list, and that at least one non-itw_ preview entry IS present (proving
    real schools are not accidentally excluded by the filter).
    """
    admin = await _mk_platform_admin()
    headers = _admin_headers(admin)

    itw_archived = await _mk_it_workspace(status="archived")
    itw_active = await _mk_it_workspace(status="active")

    res = await client.get("/user-roles/my-roles", headers=headers)
    assert res.status_code == 200, res.text

    preview_roles = [
        r for r in res.json().get("available_roles", []) if r.get("is_preview")
    ]
    preview_tenant_ids = {r["tenant_id"] for r in preview_roles}

    # Negative: itw_* ids must be absent regardless of their status
    assert itw_archived not in preview_tenant_ids, (
        "itw_* workspace (archived) must NOT appear in the platform-admin preview list"
    )
    assert itw_active not in preview_tenant_ids, (
        "itw_* workspace (active) must NOT appear even when status is 'active'"
    )

    # Broad sweep: no preview entry in the response may have an itw_* id,
    # catching any itw_ rows that might have been committed to the DB.
    leaked = [tid for tid in preview_tenant_ids if (tid or "").startswith("itw_")]
    assert leaked == [], f"itw_* ids leaked into the preview list: {leaked}"

    # Positive: real (non-itw_) schools must still appear — confirms the
    # filter is selective, not a blanket drop of all entries.
    non_itw_entries = [
        tid for tid in preview_tenant_ids if not (tid or "").startswith("itw_")
    ]
    assert len(non_itw_entries) > 0, (
        "Expected at least one non-itw_ school in the preview list; got none. "
        "The filter may be too broad."
    )


@pytest.mark.asyncio
async def test_my_roles_excludes_archived_school(client):
    """Schools with status=``archived`` must not appear in the preview list."""
    admin = await _mk_platform_admin()
    headers = _admin_headers(admin)

    archived_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": archived_id,
        "name": "Archived School",
        "code": f"AR{archived_id[:8]}",
        "status": "archived",
        "country": "SA",
        "language": "ar",
    })

    res = await client.get("/user-roles/my-roles", headers=headers)
    assert res.status_code == 200, res.text

    preview_tenant_ids = {
        r["tenant_id"]
        for r in res.json().get("available_roles", [])
        if r.get("is_preview")
    }

    assert archived_id not in preview_tenant_ids, (
        "archived school must NOT appear in the platform-admin preview list"
    )


@pytest.mark.asyncio
async def test_my_roles_excludes_pending_hard_delete_school(client):
    """Schools with status=``pending_hard_delete`` must not appear in the
    preview list."""
    admin = await _mk_platform_admin()
    headers = _admin_headers(admin)

    phd_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": phd_id,
        "name": "Pending Delete School",
        "code": f"PD{phd_id[:8]}",
        "status": "pending_hard_delete",
        "country": "SA",
        "language": "ar",
    })

    res = await client.get("/user-roles/my-roles", headers=headers)
    assert res.status_code == 200, res.text

    preview_tenant_ids = {
        r["tenant_id"]
        for r in res.json().get("available_roles", [])
        if r.get("is_preview")
    }

    assert phd_id not in preview_tenant_ids, (
        "pending_hard_delete school must NOT appear in the platform-admin preview list"
    )


# ───────────────────── role-switch/switch 403 ────────────────────────────────


@pytest.mark.asyncio
async def test_role_switch_returns_403_for_itw_school_id(client, monkeypatch):
    """Platform admin targeting an itw_* school id via /role-switch/switch
    must receive 403, regardless of the school's status."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")

    admin = await _mk_platform_admin()
    headers = _admin_headers(admin, fresh_mfa=True)

    itw_id = await _mk_it_workspace(status="archived")

    res = await client.post(
        "/role-switch/switch",
        json={
            "target_role": "school_principal",
            "school_id": itw_id,
            "reason": "QA verification of IT workspace guard",
        },
        headers=headers,
    )
    assert res.status_code == 403, (
        f"Expected 403 when switching to itw_* school, got {res.status_code}: {res.text}"
    )
    assert MSG_INDEPENDENT_TEACHER_WORKSPACE in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_role_switch_returns_403_for_archived_status_school(client, monkeypatch):
    """Platform admin targeting a school with status=archived via
    /role-switch/switch must receive 403."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")

    admin = await _mk_platform_admin()
    headers = _admin_headers(admin, fresh_mfa=True)

    archived_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": archived_id,
        "name": "Archived Non-IT School",
        "code": f"AR{archived_id[:8]}",
        "status": "archived",
        "country": "SA",
        "language": "ar",
    })

    res = await client.post(
        "/role-switch/switch",
        json={
            "target_role": "school_principal",
            "school_id": archived_id,
            "reason": "QA verification of archived school guard",
        },
        headers=headers,
    )
    assert res.status_code == 403, (
        f"Expected 403 when switching to archived school, got {res.status_code}: {res.text}"
    )
    assert MSG_ARCHIVED in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_role_switch_returns_403_for_pending_hard_delete_school(client, monkeypatch):
    """Platform admin targeting a school with status=pending_hard_delete via
    /role-switch/switch must receive 403."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")

    admin = await _mk_platform_admin()
    headers = _admin_headers(admin, fresh_mfa=True)

    phd_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": phd_id,
        "name": "Pending Hard Delete School",
        "code": f"PD{phd_id[:8]}",
        "status": "pending_hard_delete",
        "country": "SA",
        "language": "ar",
    })

    res = await client.post(
        "/role-switch/switch",
        json={
            "target_role": "school_principal",
            "school_id": phd_id,
            "reason": "QA verification of pending_hard_delete school guard",
        },
        headers=headers,
    )
    assert res.status_code == 403, (
        f"Expected 403 when switching to pending_hard_delete school, got {res.status_code}: {res.text}"
    )


@pytest.mark.asyncio
async def test_role_switch_succeeds_for_real_active_school(client, monkeypatch):
    """Sanity check: the guard must not block switches to legitimate active
    schools.  A real school with an active principal must succeed (200).

    The route requires at least one active ``school_principal`` user to exist
    in the target school before minting the impersonation token; this test
    seeds one to satisfy that pre-condition.
    """
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")

    admin = await _mk_platform_admin()
    headers = _admin_headers(admin, fresh_mfa=True)

    real_id = await _mk_real_school()
    await _seed_principal(real_id)

    res = await client.post(
        "/role-switch/switch",
        json={
            "target_role": "school_principal",
            "school_id": real_id,
            "reason": "QA sanity check for real school",
        },
        headers=headers,
    )
    assert res.status_code == 200, (
        f"Expected 200 when switching to a real active school with a principal, "
        f"got {res.status_code}: {res.text}"
    )
