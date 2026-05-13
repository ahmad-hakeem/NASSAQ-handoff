"""Task #249 — IT Notifications Inbox + per-category preferences.

Covers:
  * Workspace pinning: cross-workspace by-id reads → 404 (§8 inv. 3).
  * Idempotency: marking the same notification read twice succeeds.
  * Preferences round-trip: PUT → GET reflects payload; in_app stays
    forced to True even when the client tries to disable it.
  * Suppressed-channel email skip: should_send_channel returns False
    for the suppressed (category, email) tuple while in_app stays
    True regardless of any preference toggle.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_insert
from routes.independent_teacher_notifications_routes import (
    IT_CATEGORIES,
    should_send_channel,
)

from tests._it_fixtures import headers, mk_it_workspace, now_ts


def _it_headers(ctx: dict) -> dict:
    return headers(ctx["uid"], ctx["user"]["role"], ctx["wsid"], mfa_recent_at=now_ts())


async def _seed_notif(
    *,
    user_id: str,
    tenant_id: str,
    category: str = "collab_invite",
    is_read: bool = False,
) -> str:
    nid = str(uuid.uuid4())
    await gd_insert(db.session, "notifications", {
        "id": nid,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "school_id": tenant_id,
        "title": "t",
        "message": "m",
        "type": "system",
        "category": category,
        "is_read": is_read,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return nid


# ---------------------------------------------------------------------------
# Pinning — cross-workspace by-id MUST 404 (§8 inv. 3).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_workspace_mark_read_returns_404(client):
    a = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    b = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    nid = await _seed_notif(user_id=b["uid"], tenant_id=b["wsid"])

    resp = await client.post(
        f"/independent-teacher/notifications/{nid}/read",
        headers=_it_headers(a),
    )
    assert resp.status_code == 404, resp.text

    # And the original row stays unread on workspace B.
    row = await gd_find_one(db.session, "notifications", {"id": nid})
    assert row is not None
    assert bool(row.get("is_read")) is False


@pytest.mark.asyncio
async def test_list_only_returns_own_workspace_rows(client):
    a = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    b = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    own = await _seed_notif(user_id=a["uid"], tenant_id=a["wsid"])
    await _seed_notif(user_id=b["uid"], tenant_id=b["wsid"])

    resp = await client.get(
        "/independent-teacher/notifications",
        headers=_it_headers(a),
    )
    assert resp.status_code == 200, resp.text
    ids = [r["id"] for r in resp.json()["items"]]
    assert own in ids
    assert all(r["id"] == own for r in resp.json()["items"])


# ---------------------------------------------------------------------------
# Idempotency — second mark-read returns ok with already_read flag.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_read_is_idempotent(client):
    ctx = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    nid = await _seed_notif(user_id=ctx["uid"], tenant_id=ctx["wsid"])
    h = _it_headers(ctx)

    r1 = await client.post(f"/independent-teacher/notifications/{nid}/read", headers=h)
    assert r1.status_code == 200 and r1.json()["already_read"] is False

    r2 = await client.post(f"/independent-teacher/notifications/{nid}/read", headers=h)
    assert r2.status_code == 200 and r2.json()["already_read"] is True


# ---------------------------------------------------------------------------
# Preferences round-trip — PUT then GET reflects payload; in_app forced True.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preferences_round_trip_keeps_in_app_forced_on(client):
    ctx = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    h = _it_headers(ctx)

    payload = {
        "categories": {
            "collab_invite": {"in_app": False, "email": False},
            "lesson_plan":   {"in_app": False, "email": True},
        },
    }
    put = await client.put(
        "/independent-teacher/notifications/preferences",
        json=payload, headers=h,
    )
    assert put.status_code == 200, put.text

    got = await client.get(
        "/independent-teacher/notifications/preferences", headers=h,
    )
    assert got.status_code == 200, got.text
    cats = got.json()["categories"]
    assert cats["collab_invite"]["in_app"] is True   # forced
    assert cats["collab_invite"]["email"] is False
    assert cats["lesson_plan"]["in_app"] is True     # forced
    assert cats["lesson_plan"]["email"] is True
    # Untouched categories keep defaults.
    for c in IT_CATEGORIES:
        if c in {"collab_invite", "lesson_plan"}:
            continue
        assert cats[c]["in_app"] is True
        assert cats[c]["email"] is True


# ---------------------------------------------------------------------------
# Channel suppression — should_send_channel skips email but never in_app.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cursor_pagination_and_read_all_alias(client):
    ctx = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    h = _it_headers(ctx)
    for _ in range(3):
        await _seed_notif(user_id=ctx["uid"], tenant_id=ctx["wsid"])

    # First page (limit=2 → 2 items + has_more=True + next_cursor).
    p1 = await client.get(
        "/independent-teacher/notifications?limit=2", headers=h,
    )
    assert p1.status_code == 200, p1.text
    body1 = p1.json()
    assert len(body1["items"]) == 2
    assert body1["has_more"] is True
    assert body1["next_cursor"]

    # Follow cursor → remaining row, no more.
    p2 = await client.get(
        f"/independent-teacher/notifications?limit=2&cursor={body1['next_cursor']}",
        headers=h,
    )
    assert p2.status_code == 200
    body2 = p2.json()
    assert len(body2["items"]) == 1
    assert body2["has_more"] is False
    # Cursor pages do not overlap.
    seen = {n["id"] for n in body1["items"]} | {n["id"] for n in body2["items"]}
    assert len(seen) == 3

    # /read-all canonical endpoint flips everything to read.
    ra = await client.post(
        "/independent-teacher/notifications/read-all", headers=h,
    )
    assert ra.status_code == 200, ra.text
    assert int(ra.json()["updated"]) == 3

    # Back-compat alias still works (idempotent zero update).
    alias = await client.post(
        "/independent-teacher/notifications/mark-all-read", headers=h,
    )
    assert alias.status_code == 200
    assert int(alias.json()["updated"]) == 0


@pytest.mark.asyncio
async def test_read_all_does_not_touch_cross_workspace_rows(client):
    # Task #261 — /read-all must only flip the caller's own
    # workspace-pinned unread rows; foreign-workspace rows must
    # stay unread (§8 inv. 3 — no cross-tenant writes).
    a = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    b = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)

    own_a = [
        await _seed_notif(user_id=a["uid"], tenant_id=a["wsid"]) for _ in range(2)
    ]
    foreign_b = await _seed_notif(user_id=b["uid"], tenant_id=b["wsid"])

    resp = await client.post(
        "/independent-teacher/notifications/read-all",
        headers=_it_headers(a),
    )
    assert resp.status_code == 200, resp.text
    assert int(resp.json()["updated"]) == 2

    # Caller's own rows are now read.
    for nid in own_a:
        row = await gd_find_one(db.session, "notifications", {"id": nid})
        assert row is not None
        assert bool(row.get("is_read")) is True

    # Foreign-workspace row is untouched.
    other = await gd_find_one(db.session, "notifications", {"id": foreign_b})
    assert other is not None
    assert bool(other.get("is_read")) is False


@pytest.mark.asyncio
async def test_should_send_channel_respects_email_suppression(client):
    ctx = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    h = _it_headers(ctx)

    # Suppress email for workspace_lifecycle.
    put = await client.put(
        "/independent-teacher/notifications/preferences",
        json={"categories": {"workspace_lifecycle": {"email": False}}},
        headers=h,
    )
    assert put.status_code == 200, put.text

    user = await gd_find_one(db.session, "users", {"id": ctx["uid"]})
    assert user is not None

    assert await should_send_channel(user, "workspace_lifecycle", "email") is False
    # in_app stays True regardless — the inbox is the source of truth.
    assert await should_send_channel(user, "workspace_lifecycle", "in_app") is True
    # Unaffected categories keep email enabled.
    assert await should_send_channel(user, "lesson_plan", "email") is True
