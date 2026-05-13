"""Independent-Teacher §6.8 workspace archive email + reactivation reminder
loop tests (Task #223).

Covers the two email surfaces and daily background sweep added by Task #218:

  * POST /independent-teacher/workspace/soft-delete
      - Invokes ``send_workspace_archived_email`` with the freshly minted
        download URL, a 24h ``download_expires_at``, and the 30-day
        reactivation deadline.
      - Stamps ``schools.reactivation_reminder_sent_at = NULL`` so the
        daily sweep treats the new archive cycle as "not yet reminded".

  * app.lifecycle._sweep_reactivation_reminders (daily sweep)
      - in-window-not-yet-sent → sends + stamps
      - already-stamped → skipped (no send, stamp unchanged)
      - past-deadline → skipped (no send, stamp left NULL)
      - placeholder/invite-pending email → stamped without sending

  * POST /independent-teacher/workspace/reactivate clears the reminder
    stamp so the next archive cycle starts fresh.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_update_one

from app import lifecycle as lifecycle_mod
from routes import independent_teacher_workspace_lifecycle_routes as wlr
import engines.email_service as email_service

from tests._it_fixtures import headers, mk_it_workspace, now_ts


def _it_headers(ctx: dict, *, with_mfa: bool = True) -> dict:
    return headers(
        ctx["uid"], ctx["user"]["role"], ctx["wsid"],
        mfa_recent_at=now_ts() if with_mfa else None,
    )


# ---------------------------------------------------------------------------
# Soft-delete → archive email
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_delete_sends_archive_email_and_clears_reminder_stamp(
    client, monkeypatch,
):
    """Soft-delete must dispatch the archive email with the fresh
    24h download URL and stamp ``reactivation_reminder_sent_at = NULL``
    so the sweep treats the new archive cycle as un-reminded."""
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})

    # Pre-stamp a fake reminder timestamp from a previous archive cycle —
    # the soft-delete must clear it back to NULL.
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {
            "last_export_at": datetime.now(timezone.utc).isoformat(),
            "reactivation_reminder_sent_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    captured: dict = {}

    def _spy(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(wlr, "send_workspace_archived_email", _spy)

    resp = await client.post(
        "/independent-teacher/workspace/soft-delete",
        json={"confirm_workspace_name": school["name"]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Email was invoked with the fresh token URL and the 24h expiry +
    # 30-day reactivation deadline returned in the response body.
    assert captured, "send_workspace_archived_email was not invoked"
    assert captured["to_email"] == ctx["user"]["email"]
    assert captured["workspace_name"] == school["name"]
    assert captured["download_url"] == body["download_url"]
    assert captured["download_url"].startswith("/api/public/workspace-export/")
    assert captured["download_expires_at"] == body["download_expires_at"]
    assert captured["reactivation_deadline"] == body["reactivation_deadline"]
    assert captured["reactivation_window_days"] == 30

    after = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert after["reactivation_reminder_sent_at"] is None


@pytest.mark.asyncio
async def test_soft_delete_skips_email_for_placeholder_invite_address(
    client, monkeypatch,
):
    """The archive email must never be sent to the
    ``invite+...@invite.nassaq.invalid`` placeholder addresses."""
    ctx = await mk_it_workspace()
    placeholder = "invite+abc@invite.nassaq.invalid"
    await gd_update_one(
        db.session, "users", {"id": ctx["uid"]}, {"email": placeholder},
    )
    ctx["user"]["email"] = placeholder
    h = _it_headers(ctx)
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {"last_export_at": datetime.now(timezone.utc).isoformat()},
    )

    calls: list = []
    monkeypatch.setattr(
        wlr, "send_workspace_archived_email",
        lambda **kw: calls.append(kw) or True,
    )

    resp = await client.post(
        "/independent-teacher/workspace/soft-delete",
        json={"confirm_workspace_name": school["name"]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert calls == []


# ---------------------------------------------------------------------------
# _sweep_reactivation_reminders
# ---------------------------------------------------------------------------

async def _archive_with(
    wsid: str,
    *,
    archived_days_ago: float,
    reminder_sent_at=None,
    pending_hard_delete: bool = False,
):
    archived_at = datetime.now(timezone.utc) - timedelta(days=archived_days_ago)
    await gd_update_one(
        db.session, "schools", {"id": wsid},
        {
            "status": "archived",
            "archived_at": archived_at.isoformat(),
            "reactivation_reminder_sent_at": (
                reminder_sent_at.isoformat() if reminder_sent_at else None
            ),
            "pending_hard_delete": pending_hard_delete,
        },
    )


@pytest.mark.asyncio
async def test_sweep_in_window_not_yet_sent_sends_and_stamps(monkeypatch):
    """Archived 28 days ago, reminder NULL → sweep sends + stamps."""
    ctx = await mk_it_workspace()
    await _archive_with(ctx["wsid"], archived_days_ago=28)

    calls: list = []

    def _spy(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(
        email_service, "send_workspace_reactivation_reminder_email", _spy,
    )

    sent = await lifecycle_mod._sweep_reactivation_reminders()
    assert sent == 1
    assert len(calls) == 1
    call = calls[0]
    assert call["to_email"] == ctx["user"]["email"]
    assert call["days_left"] >= 1
    assert call["days_left"] <= 3
    # reactivation_deadline = archived_at + 30 days, so it's roughly 2
    # days from now — must be a parseable iso timestamp.
    datetime.fromisoformat(call["reactivation_deadline"])

    after = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert after["reactivation_reminder_sent_at"] is not None


@pytest.mark.asyncio
async def test_sweep_already_stamped_is_skipped(monkeypatch):
    """A row whose ``reactivation_reminder_sent_at`` is non-NULL must
    not be re-emailed even if it's still inside the threshold window."""
    ctx = await mk_it_workspace()
    prior_stamp = datetime.now(timezone.utc) - timedelta(hours=12)
    await _archive_with(
        ctx["wsid"], archived_days_ago=28, reminder_sent_at=prior_stamp,
    )

    calls: list = []
    monkeypatch.setattr(
        email_service, "send_workspace_reactivation_reminder_email",
        lambda **kw: calls.append(kw) or True,
    )

    sent = await lifecycle_mod._sweep_reactivation_reminders()
    assert sent == 0
    assert calls == []

    after = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    # Stamp is unchanged (we don't re-stamp already-stamped rows).
    stamp = after["reactivation_reminder_sent_at"]
    assert stamp is not None
    parsed = stamp if isinstance(stamp, datetime) else datetime.fromisoformat(
        str(stamp).replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    assert abs((parsed - prior_stamp).total_seconds()) < 5


@pytest.mark.asyncio
async def test_sweep_past_deadline_is_skipped(monkeypatch):
    """Once the archive is past the 30-day window the sweep must NOT
    send a reminder — the on-login sweep flips pending_hard_delete and
    platform-admin tooling takes over from there."""
    ctx = await mk_it_workspace()
    await _archive_with(ctx["wsid"], archived_days_ago=45)

    calls: list = []
    monkeypatch.setattr(
        email_service, "send_workspace_reactivation_reminder_email",
        lambda **kw: calls.append(kw) or True,
    )

    sent = await lifecycle_mod._sweep_reactivation_reminders()
    assert sent == 0
    assert calls == []

    after = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert after["reactivation_reminder_sent_at"] is None


@pytest.mark.asyncio
async def test_sweep_placeholder_email_stamps_without_sending(monkeypatch):
    """Workspaces whose owner only has a placeholder
    ``invite+...@invite.nassaq.invalid`` address get stamped anyway so
    the sweep doesn't re-scan them every day for an unreachable
    recipient."""
    ctx = await mk_it_workspace()
    await gd_update_one(
        db.session, "users", {"id": ctx["uid"]},
        {"email": "invite+xyz@invite.nassaq.invalid"},
    )
    await _archive_with(ctx["wsid"], archived_days_ago=28)

    calls: list = []
    monkeypatch.setattr(
        email_service, "send_workspace_reactivation_reminder_email",
        lambda **kw: calls.append(kw) or True,
    )

    sent = await lifecycle_mod._sweep_reactivation_reminders()
    assert sent == 0  # nothing was actually emailed
    assert calls == []

    after = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert after["reactivation_reminder_sent_at"] is not None


# ---------------------------------------------------------------------------
# Reactivate clears the reminder stamp
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reactivate_clears_reminder_stamp(client):
    """A workspace that has already been reminded once and is then
    reactivated must have its reminder stamp cleared, so a future
    archive cycle starts fresh and is eligible for a new reminder."""
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    prior_stamp = datetime.now(timezone.utc) - timedelta(hours=6)
    await _archive_with(
        ctx["wsid"], archived_days_ago=28, reminder_sent_at=prior_stamp,
    )

    resp = await client.post(
        "/independent-teacher/workspace/reactivate", headers=h,
    )
    assert resp.status_code == 200, resp.text

    after = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert (after["status"] or "").lower() == "active"
    assert after["reactivation_reminder_sent_at"] is None
