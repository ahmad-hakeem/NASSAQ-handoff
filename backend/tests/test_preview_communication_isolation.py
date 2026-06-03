"""Regression tests for Task #789 (follow-up to the Task #788 fix).

Task #788 closed a cross-tenant disclosure bug on the notifications surface:
a Platform Admin previewing/impersonating a brand-new school saw their own
native-context notifications (and other tenants' rows) bleeding into the
previewed school. The other Communication Center tabs — صندوق الوارد /
المرسلة / المجدولة — read from the ``/communication/*`` endpoints and the
circular-acknowledgement endpoints, which had the same leak class because they
only pinned ``tenant_id`` when ``current_user.get('tenant_id')`` was truthy
(fail-open for a native platform admin carrying a stale ``X-School-Context``
header).

The fix routes every Communication Center *read* through the same fail-closed
scope used by the notifications surface:

  * ``communication_routes._comm_read_scope`` strictly scopes the message
    list (``GET /communication``), inbox (``GET /communication/received``),
    stats (``GET /communication/stats``), templates and audience by the
    previewed ``tenant_id`` (via ``resolve_school_id``) for platform-admin /
    preview sessions, and falls back to the caller's own workspace for genuine
    school users / Independent Teachers.
  * ``notification_routes_mod.list_sent_circulars`` and
    ``get_circular_acknowledgements`` apply ``_notification_read_scope`` with
    a fallback to the caller's own tenant.

These tests pin the behaviours so a future refactor cannot silently re-open
the leak:

  1. A Platform Admin impersonation token previewing an EMPTY school gets
     empty صندوق الوارد / المرسلة / المجدولة and zeroed stats.
  2. A genuine school admin still sees their own school's messages (no
     regression).
  3. Switching the preview between two schools never carries a row across.
  4. A plain platform-admin token + stale ``X-School-Context`` header FAILS
     CLOSED (403) on every read surface.
  5. The circular endpoints scope by the previewed tenant and fail closed.
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
    """Platform Admin token minted as if by ``/role-switch/switch``: carries
    ``is_impersonating=True`` and pins ``tenant_id`` to the previewed school."""
    return create_access_token({
        "sub": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": target_tenant_id,
        "is_impersonating": True,
        "original_role": UserRole.PLATFORM_ADMIN.value,
        "original_user_id": uid,
    })


async def _seed_admin_user(tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": "School Admin Test",
        "is_active": True,
        "password_hash": "x",
    })
    return uid


def _admin_token(uid: str, tenant_id: str) -> str:
    return create_access_token({
        "sub": uid,
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_id,
    })


_seq = 0


async def _seed_message(
    school_id: str | None,
    *,
    status: str = "sent",
    audience: str = "all",
    audience_ids: list | None = None,
) -> str:
    """Insert one message tagged to ``school_id`` (may be NULL for a legacy
    platform-wide row)."""
    global _seq
    _seq += 1
    now = (datetime.now(timezone.utc) + timedelta(seconds=_seq)).isoformat()
    mid = str(uuid.uuid4())
    await gd_insert(db.session, "messages", {
        "id": mid,
        "title": f"M-{mid[:6]}",
        "content": "body",
        "audience": audience,
        "audience_ids": audience_ids or [],
        "status": status,
        "school_id": school_id,
        "sent_count": 0,
        "created_at": now,
        "sent_at": now if status == "sent" else None,
    })
    return mid


async def _seed_notification(user_id: str, tenant_id: str | None) -> str:
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
        "is_read": False,
        "created_at": datetime.now(timezone.utc) + timedelta(seconds=_seq),
    })
    return nid


async def _seed_circular(sender_id: str, tenant_id: str | None, recipient_id: str) -> str:
    """Insert one per-recipient circular fan-out row for ``broadcast_id``."""
    global _seq
    _seq += 1
    bid = str(uuid.uuid4())
    await gd_insert(db.session, "notifications", {
        "id": str(uuid.uuid4()),
        "user_id": recipient_id,
        "tenant_id": tenant_id,
        "sender_id": sender_id,
        "broadcast_id": bid,
        "title": f"C-{bid[:6]}",
        "message": "circular body",
        "type": "circular",
        "priority": "medium",
        "is_read": False,
        "is_acknowledged": False,
        "created_at": datetime.now(timezone.utc) + timedelta(seconds=_seq),
    })
    return bid


def _ids(payload) -> set:
    return {row.get("id") for row in payload if isinstance(row, dict)}


# --- (1) preview of an empty school: nothing leaks in ----------------------


@pytest.mark.asyncio
async def test_impersonation_empty_preview_hides_all_comm_tabs(
    client, tenant_a, tenant_b,
):
    """Admin previously previewed school A (messages tagged there) plus a
    legacy NULL-school message. While impersonating brand-new school B, every
    Communication Center tab must come back empty."""
    admin = await _seed_platform_admin_user()
    await _seed_message(None)              # legacy platform-wide row
    await _seed_message(tenant_a)          # other school's message
    await _seed_message(tenant_a, status="scheduled")
    await _seed_notification(admin, tenant_a)  # admin's own received in A

    headers = _bearer(_impersonation_token(admin, tenant_b))

    res = await client.get("/communication", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["messages"] == [], (
        f"المرسلة/المجدولة leaked rows into empty preview: {res.json()['messages'][:3]}"
    )

    res = await client.get("/communication/received", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["messages"] == [], (
        f"صندوق الوارد leaked rows into empty preview: {res.json()['messages'][:3]}"
    )

    res = await client.get("/communication/stats", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sent"] == 0 and body["scheduled"] == 0 and body["drafts"] == 0, body
    assert body["received_messages"] == 0, body


# --- (2) genuine school admin: own school's rows survive --------------------


@pytest.mark.asyncio
async def test_genuine_admin_sees_own_school_messages(client, tenant_a, tenant_b):
    """A real school admin (no impersonation) keeps seeing their own school's
    messages and never another tenant's."""
    admin = await _seed_admin_user(tenant_a)
    mine_sent = await _seed_message(tenant_a)
    mine_sched = await _seed_message(tenant_a, status="scheduled")
    other = await _seed_message(tenant_b)  # must never appear

    headers = _bearer(_admin_token(admin, tenant_a))

    res = await client.get("/communication?limit=100", headers=headers)
    assert res.status_code == 200, res.text
    ids = _ids(res.json()["messages"])
    assert {mine_sent, mine_sched} <= ids, ids
    assert other not in ids, f"genuine admin saw another tenant's message: {ids}"

    res = await client.get("/communication/received", headers=headers)
    assert res.status_code == 200, res.text
    rids = _ids(res.json()["messages"])
    assert mine_sent in rids
    assert other not in rids

    res = await client.get("/communication/stats", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["sent"] == 1
    assert res.json()["scheduled"] == 1


# --- (3) switching preview between two schools never carries rows -----------


@pytest.mark.asyncio
async def test_switching_preview_between_schools_never_carries_rows(
    client, tenant_a, tenant_b,
):
    admin = await _seed_platform_admin_user()
    await _seed_message(None)                       # native, hide in both
    a_sent = await _seed_message(tenant_a)
    b_sent = await _seed_message(tenant_b)
    b_sent2 = await _seed_message(tenant_b)

    headers_a = _bearer(_impersonation_token(admin, tenant_a))
    res = await client.get("/communication?limit=100", headers=headers_a)
    ids_a = _ids(res.json()["messages"])
    assert ids_a == {a_sent}, f"preview A returned wrong rows: {ids_a}"

    headers_b = _bearer(_impersonation_token(admin, tenant_b))
    res = await client.get("/communication?limit=100", headers=headers_b)
    ids_b = _ids(res.json()["messages"])
    assert ids_b == {b_sent, b_sent2}, f"preview B returned wrong rows: {ids_b}"

    assert ids_a.isdisjoint(ids_b)


# --- (4) fail-closed: plain admin token + stale X-School-Context header -----


@pytest.mark.asyncio
async def test_plain_admin_with_school_context_header_fails_closed(client, tenant_a):
    """The leak's real-world trigger: a refresh replaced the short-lived
    impersonation token with a PLAIN platform-admin token, but the preview UI
    still sends an ``X-School-Context`` header. Every read must 403."""
    admin = await _seed_platform_admin_user()
    await _seed_message(tenant_a)
    await _seed_message(None)

    headers = {**_bearer(_plain_token(admin)), "X-School-Context": tenant_a}

    for path in (
        "/communication",
        "/communication/received",
        "/communication/stats",
        "/communication/templates",
        "/communication/audience",
        "/notifications/sent-circulars",
        f"/notifications/circular/{uuid.uuid4()}/acknowledgements",
    ):
        res = await client.get(path, headers=headers)
        assert res.status_code == 403, f"{path} did not fail closed: {res.status_code} {res.text}"


# --- (5) circular endpoints scope by previewed tenant ----------------------


@pytest.mark.asyncio
async def test_sent_circulars_scoped_to_preview(client, tenant_a, tenant_b):
    """The admin sent a circular in school A. Previewing empty school B must
    show no sent circulars; previewing A shows it."""
    admin = await _seed_platform_admin_user()
    recipient = await _seed_admin_user(tenant_a)
    bid_a = await _seed_circular(admin, tenant_a, recipient)

    # Preview empty school B → no circulars.
    res = await client.get(
        "/notifications/sent-circulars",
        headers=_bearer(_impersonation_token(admin, tenant_b)),
    )
    assert res.status_code == 200, res.text
    assert res.json()["circulars"] == [], res.json()

    # Preview school A → the circular appears.
    res = await client.get(
        "/notifications/sent-circulars",
        headers=_bearer(_impersonation_token(admin, tenant_a)),
    )
    assert res.status_code == 200, res.text
    bids = {c["broadcast_id"] for c in res.json()["circulars"]}
    assert bid_a in bids, res.json()

    # Acknowledgements for the A circular are visible while previewing A...
    res = await client.get(
        f"/notifications/circular/{bid_a}/acknowledgements",
        headers=_bearer(_impersonation_token(admin, tenant_a)),
    )
    assert res.status_code == 200, res.text
    assert res.json()["total"] == 1

    # ...but NOT while previewing school B (cross-tenant broadcast hidden).
    res = await client.get(
        f"/notifications/circular/{bid_a}/acknowledgements",
        headers=_bearer(_impersonation_token(admin, tenant_b)),
    )
    assert res.status_code == 200, res.text
    assert res.json()["total"] == 0, res.json()
