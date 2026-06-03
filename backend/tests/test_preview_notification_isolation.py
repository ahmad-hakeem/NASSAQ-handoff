"""Regression tests for Task #780 (follow-up to the Task #778 fix).

Task #778 closed a cross-tenant disclosure bug: a Platform Admin
previewing/impersonating a school saw their OWN native-context
notifications bleeding into the previewed school's inbox. The fix lives
in two places that must stay in lock-step:

  * ``notification_routes_mod._preview_tenant_scope`` — strictly scopes
    ``GET /notifications`` and ``GET /notifications/unread-count`` by the
    previewed ``tenant_id`` whenever the bearer carries
    ``is_impersonating``/``is_switched``.
  * ``communication_routes.get_communication_stats`` — applies the same
    preview-only tenant scoping to ``received_messages``.

These tests pin the four behaviours that fix established so a future
refactor cannot silently re-open the leak:

  1. A Platform Admin impersonation token (``is_impersonating=True`` with
     an overridden ``tenant_id``) gets an empty list + zero unread from
     ``GET /notifications`` / ``GET /notifications/unread-count`` and
     ``received_messages=0`` from ``GET /communication/stats`` when the
     previewed school holds none of the admin's notifications.
  2. A genuine school principal login (no impersonation) still sees their
     own notifications — including legacy rows written with a NULL
     ``tenant_id`` (the no-regression guard).
  3. Switching the preview between two schools never carries a row across
     either endpoint.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest

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


def _plain_token(uid: str) -> str:
    """Plain (non-impersonating) Platform Admin access token."""
    return create_access_token({
        "sub": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
    })


def _impersonation_token(uid: str, target_tenant_id: str) -> str:
    """Platform Admin token minted as if by ``/role-switch/switch``:
    carries ``is_impersonating=True`` and pins ``tenant_id`` to the
    previewed school."""
    return create_access_token({
        "sub": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
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
    return uid


def _principal_token(uid: str, tenant_id: str) -> str:
    return create_access_token({
        "sub": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": tenant_id,
    })


# Monotonic clock so notifications get distinct ordered created_at values.
_seq = 0


async def _seed_notification(
    user_id: str,
    tenant_id: str | None,
    *,
    is_read: bool = False,
) -> str:
    """Insert one notification addressed to ``user_id`` tagged with
    ``tenant_id`` (which may be NULL to mimic a legacy row)."""
    global _seq
    _seq += 1
    nid = str(uuid.uuid4())
    await gd_insert(db.session, "notifications", {
        "id": nid,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "title": f"N-{nid[:6]}",
        "message": "body",
        "type": "system",
        "priority": "medium",
        "is_read": is_read,
        "created_at": datetime.now(timezone.utc) + timedelta(seconds=_seq),
    })
    return nid


def _ids(payload) -> set:
    return {row.get("id") for row in payload if isinstance(row, dict)}


# --- (1) preview of an empty school: nothing leaks in ----------------------


@pytest.mark.asyncio
async def test_impersonation_empty_preview_hides_admin_own_notifications(
    client, tenant_a, tenant_b,
):
    """Admin has native-context notifications (NULL tenant_id) plus rows
    tagged to school A. While impersonating brand-new school B (no rows
    for the admin), all three read surfaces must come back empty."""
    admin = await _seed_platform_admin_user()
    # The admin's own notifications: a legacy NULL-tenant row and rows
    # tagged to a *different* school (A) they previously previewed.
    await _seed_notification(admin, None, is_read=False)
    await _seed_notification(admin, tenant_a, is_read=False)
    await _seed_notification(admin, tenant_a, is_read=True)

    headers = _bearer(_impersonation_token(admin, tenant_b))

    res = await client.get("/notifications", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == [], (
        f"impersonation preview of empty school B leaked admin rows: {res.json()[:3]}"
    )

    res = await client.get("/notifications/unread-count", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["unread_count"] == 0

    res = await client.get("/communication/stats", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["received_messages"] == 0, (
        f"communication stats leaked admin received messages into preview: {res.json()}"
    )


# --- (2) genuine principal login: own rows (incl. NULL tenant) survive -----


@pytest.mark.asyncio
async def test_genuine_principal_sees_own_notifications_including_null_tenant(
    client, tenant_a,
):
    """A real principal (no impersonation) must still see every
    notification addressed to them, including a legacy row written with a
    NULL ``tenant_id`` — the no-regression guard the fix deliberately
    preserves."""
    principal = await _seed_principal_user(tenant_a)
    n_tenant = await _seed_notification(principal, tenant_a, is_read=False)
    n_legacy = await _seed_notification(principal, None, is_read=False)
    n_read = await _seed_notification(principal, tenant_a, is_read=True)

    headers = _bearer(_principal_token(principal, tenant_a))

    res = await client.get("/notifications", headers=headers)
    assert res.status_code == 200, res.text
    ids = _ids(res.json())
    assert {n_tenant, n_legacy, n_read} <= ids, (
        f"genuine principal lost own notifications (incl. NULL tenant): {ids}"
    )

    res = await client.get("/notifications/unread-count", headers=headers)
    assert res.status_code == 200, res.text
    # Both unread rows (tenant + legacy NULL) must be counted.
    assert res.json()["unread_count"] == 2

    res = await client.get("/communication/stats", headers=headers)
    assert res.status_code == 200, res.text
    # received_messages counts ALL notifications for the user (read+unread)
    # because genuine logins keep user-only scoping.
    assert res.json()["received_messages"] == 3, res.json()


# --- (3) switching preview between two schools never carries rows across ----


@pytest.mark.asyncio
async def test_switching_preview_between_schools_never_carries_rows(
    client, tenant_a, tenant_b,
):
    """The same admin user previews school A then school B. Each preview
    must show ONLY that school's rows on every surface — never the other
    school's, and never the admin's NULL-tenant native rows."""
    admin = await _seed_platform_admin_user()
    # NULL-tenant native row that must never appear in either preview.
    await _seed_notification(admin, None, is_read=False)
    # Rows tagged per school.
    a_unread = await _seed_notification(admin, tenant_a, is_read=False)
    a_read = await _seed_notification(admin, tenant_a, is_read=True)
    b_unread1 = await _seed_notification(admin, tenant_b, is_read=False)
    b_unread2 = await _seed_notification(admin, tenant_b, is_read=False)

    # --- preview school A ---
    headers_a = _bearer(_impersonation_token(admin, tenant_a))
    res = await client.get("/notifications", headers=headers_a)
    assert res.status_code == 200, res.text
    ids_a = _ids(res.json())
    assert ids_a == {a_unread, a_read}, (
        f"preview A returned wrong rows (B/native leak?): {ids_a}"
    )
    res = await client.get("/notifications/unread-count", headers=headers_a)
    assert res.json()["unread_count"] == 1
    res = await client.get("/communication/stats", headers=headers_a)
    assert res.json()["received_messages"] == 2

    # --- preview school B (same admin) ---
    headers_b = _bearer(_impersonation_token(admin, tenant_b))
    res = await client.get("/notifications", headers=headers_b)
    assert res.status_code == 200, res.text
    ids_b = _ids(res.json())
    assert ids_b == {b_unread1, b_unread2}, (
        f"preview B returned wrong rows (A/native leak?): {ids_b}"
    )
    res = await client.get("/notifications/unread-count", headers=headers_b)
    assert res.json()["unread_count"] == 2
    res = await client.get("/communication/stats", headers=headers_b)
    assert res.json()["received_messages"] == 2

    # Cross-check: no overlap between the two previews.
    assert ids_a.isdisjoint(ids_b)
