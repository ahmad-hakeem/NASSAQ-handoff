"""Regression tests for tenant-scoped parent account binding in get_current_user().

Covers the fallback logic that resolves `users.parent_id` when it is NULL:
the lookup against `parents.email`, `parents.phone`, and `parents.national_id`
must be constrained to the user's own tenant_id so that a shared identifier
(phone/email/national_id) in a different workspace cannot hijack the binding.

Also verifies that the resolved `parent_id` is persisted back to the `users`
row so subsequent requests skip the fallback entirely.
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find_one, gd_insert
from tests._it_fixtures import headers, mk_it_workspace, now_ts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parent_headers(user_id: str, tenant_id: str) -> dict:
    """Mint a parent JWT without a pre-encoded parent_id (forces fallback)."""
    token = create_access_token(
        {"sub": user_id, "role": UserRole.PARENT.value, "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_parent_user(tenant_id: str, *, email: str) -> str:
    """Seed a parent users row without parent_id (simulates pre-link state)."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
        "email": email,
        "full_name": "ولي الأمر",
        "password_hash": "!test",
        "is_active": True,
        "preferred_language": "ar",
        "preferred_theme": "light",
    })
    return uid


async def _mk_parents_row(school_id: str, *, email: str) -> str:
    """Seed a parents record and return its id."""
    pid = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": pid,
        "full_name": "ولي الأمر",
        "email": email,
        "school_id": school_id,
        "is_active": True,
    })
    return pid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_user_binds_parent_to_same_tenant_record(client):
    """When two `parents` rows share the same email but belong to different
    workspaces, `get_current_user()` must bind the parent user to the row
    in their OWN workspace (tenant_id-scoped), not the cross-workspace one.
    """
    ctx_a = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    ctx_b = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)

    shared_email = f"shared-binding-{uuid.uuid4()}@example.com"

    # Parent record in workspace A (the correct target).
    parent_id_a = await _mk_parents_row(ctx_a["wsid"], email=shared_email)
    # Parent record in workspace B (must NOT be selected).
    parent_id_b = await _mk_parents_row(ctx_b["wsid"], email=shared_email)

    # Parent user belongs to workspace A.
    user_id = await _mk_parent_user(ctx_a["wsid"], email=shared_email)

    # A request with a JWT that carries no parent_id claim triggers the fallback.
    h = _parent_headers(user_id, ctx_a["wsid"])
    resp = await client.get("/parent-portal/dashboard", headers=h)
    # The dashboard may return 200 or an empty list; we only care that
    # it does NOT crash and that get_current_user() picked the right row.
    assert resp.status_code in {200, 404, 409}, resp.text

    # Verify the users row now has the workspace-A parent_id persisted.
    user_row = await gd_find_one(db.session, "users", {"id": user_id})
    assert user_row is not None
    assert user_row.get("parent_id") == parent_id_a, (
        "get_current_user() must persist the same-workspace parents.id, "
        f"not the cross-workspace one ({parent_id_b})"
    )


@pytest.mark.asyncio
async def test_get_current_user_does_not_bind_cross_tenant_parent_record(client):
    """When the only matching `parents` row is in a DIFFERENT workspace,
    `get_current_user()` must NOT set parent_id to that cross-tenant row.
    The binding should remain unresolved via email rather than cross the
    tenant boundary.
    """
    ctx_a = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    ctx_b = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)

    shared_email = f"cross-tenant-{uuid.uuid4()}@example.com"

    # Parent record only in workspace B — no matching record in workspace A.
    parent_id_b = await _mk_parents_row(ctx_b["wsid"], email=shared_email)

    # Parent user belongs to workspace A.
    user_id = await _mk_parent_user(ctx_a["wsid"], email=shared_email)

    h = _parent_headers(user_id, ctx_a["wsid"])
    resp = await client.get("/parent-portal/dashboard", headers=h)
    assert resp.status_code in {200, 404, 409}, resp.text

    # The cross-workspace parent_id must NOT have been written to this user.
    user_row = await gd_find_one(db.session, "users", {"id": user_id})
    assert user_row is not None
    resolved = user_row.get("parent_id")
    assert resolved != parent_id_b, (
        "get_current_user() must not persist a cross-tenant parents.id"
    )


@pytest.mark.asyncio
async def test_get_current_user_parent_id_persisted_on_resolution(client):
    """Once `get_current_user()` resolves the parent via email fallback,
    the resolved `parent_id` is written back to `users` so the next
    request skips the fallback query entirely.
    """
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    shared_email = f"persist-{uuid.uuid4()}@example.com"

    parent_id = await _mk_parents_row(ctx["wsid"], email=shared_email)
    user_id = await _mk_parent_user(ctx["wsid"], email=shared_email)

    # First request: parent_id not in JWT — fallback fires.
    h = _parent_headers(user_id, ctx["wsid"])
    resp1 = await client.get("/parent-portal/dashboard", headers=h)
    assert resp1.status_code in {200, 404, 409}, resp1.text

    # After first request, users.parent_id should be persisted.
    user_row = await gd_find_one(db.session, "users", {"id": user_id})
    assert user_row is not None
    assert user_row.get("parent_id") == parent_id, (
        "Resolved parent_id should be written back to users table after first resolution"
    )
