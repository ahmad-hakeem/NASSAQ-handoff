"""Task #275 — IT scheduled weekly auto-export.

Covers:
* GET /workspace/auto-export/settings defaults for fresh workspaces.
* PUT validation (dow / hour bounds, persists, returns next_run_at).
* Disabling stops future runs (sweep skips disabled rows).
* Hourly sweep mints export + stamps last_run_at when (dow, hour) match.
* 6h idempotency guard.
* Placeholder email (@invite.nassaq.invalid) records email_skipped status.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.lifecycle import _sweep_auto_exports
from engines.sql_utils import gd_find_one, gd_insert, gd_update_one
from dependencies import db

from tests._it_fixtures import it_headers, mk_it_workspace


pytestmark = pytest.mark.asyncio


async def _ensure_quota(wsid: str) -> dict:
    row = await gd_find_one(db.session, "workspace_quota", {"workspace_school_id": wsid})
    if row:
        return row
    await gd_insert(db.session, "workspace_quota", {"workspace_school_id": wsid})
    return await gd_find_one(db.session, "workspace_quota", {"workspace_school_id": wsid})


async def test_get_returns_defaults(client):
    ctx = await mk_it_workspace()
    await _ensure_quota(ctx["wsid"])
    r = await client.get(
        "/independent-teacher/workspace/auto-export/settings",
        headers=it_headers(ctx),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is False
    assert body["day_of_week"] == 0
    assert body["hour"] == 2
    assert body["last_run_at"] is None
    assert body["next_run_at"] is None  # disabled => no next-run shown


async def test_put_validates_and_persists(client):
    ctx = await mk_it_workspace()
    await _ensure_quota(ctx["wsid"])
    # Bad dow
    r = await client.put(
        "/independent-teacher/workspace/auto-export/settings",
        headers=it_headers(ctx),
        json={"enabled": True, "day_of_week": 9, "hour": 2},
    )
    assert r.status_code == 422
    # Bad hour
    r = await client.put(
        "/independent-teacher/workspace/auto-export/settings",
        headers=it_headers(ctx),
        json={"enabled": True, "day_of_week": 0, "hour": 24},
    )
    assert r.status_code == 422
    # Happy path
    r = await client.put(
        "/independent-teacher/workspace/auto-export/settings",
        headers=it_headers(ctx),
        json={"enabled": True, "day_of_week": 3, "hour": 14},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    assert body["day_of_week"] == 3
    assert body["hour"] == 14
    assert body["next_run_at"] is not None  # enabled => projected


async def test_sweep_skips_when_disabled(client, monkeypatch):
    ctx = await mk_it_workspace()
    q = await _ensure_quota(ctx["wsid"])
    now = datetime.now(timezone.utc)
    today_dow = (now.weekday() + 1) % 7
    await gd_update_one(
        db.session, "workspace_quota",
        {"workspace_school_id": ctx["wsid"]},
        {
            "auto_export_enabled": False,
            "auto_export_dow": today_dow,
            "auto_export_hour": now.hour,
        },
    )
    await _sweep_auto_exports()
    fresh = await gd_find_one(db.session, "workspace_quota",
                              {"workspace_school_id": ctx["wsid"]})
    assert fresh.get("auto_export_last_run_at") in (None, "")


async def test_sweep_runs_on_match_and_is_idempotent(client, monkeypatch):
    ctx = await mk_it_workspace()
    await _ensure_quota(ctx["wsid"])
    now = datetime.now(timezone.utc)
    today_dow = (now.weekday() + 1) % 7
    await gd_update_one(
        db.session, "workspace_quota",
        {"workspace_school_id": ctx["wsid"]},
        {
            "auto_export_enabled": True,
            "auto_export_dow": today_dow,
            "auto_export_hour": now.hour,
        },
    )
    sent_log = []

    def _fake_email(**kw):
        sent_log.append(kw)
        return True

    monkeypatch.setattr(
        "engines.email_service.send_workspace_auto_export_email", _fake_email,
    )

    await _sweep_auto_exports()

    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert school.get("last_export_at"), "manual-export columns should be stamped"
    assert school.get("last_export_token_hash"), "fresh token hash must be set"
    assert school.get("last_export_consumed_at") in (None, "")

    q1 = await gd_find_one(db.session, "workspace_quota",
                           {"workspace_school_id": ctx["wsid"]})
    assert q1.get("auto_export_last_run_at") is not None
    first_status = q1.get("auto_export_last_status")
    assert first_status in {"success", "email_failed", "email_skipped_placeholder"}
    first_run_at = q1.get("auto_export_last_run_at")
    first_hash = school.get("last_export_token_hash")

    # Second tick within 6h must NOT mint a new token.
    await _sweep_auto_exports()
    school2 = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    q2 = await gd_find_one(db.session, "workspace_quota",
                           {"workspace_school_id": ctx["wsid"]})
    assert school2.get("last_export_token_hash") == first_hash
    assert q2.get("auto_export_last_run_at") == first_run_at


async def test_sweep_marks_placeholder_email(client, monkeypatch):
    ctx = await mk_it_workspace()
    await _ensure_quota(ctx["wsid"])
    # Stomp the owner email to the placeholder form.
    placeholder = f"invite+{uuid.uuid4()}@invite.nassaq.invalid"
    await gd_update_one(
        db.session, "users", {"id": ctx["uid"]}, {"email": placeholder},
    )
    now = datetime.now(timezone.utc)
    today_dow = (now.weekday() + 1) % 7
    await gd_update_one(
        db.session, "workspace_quota",
        {"workspace_school_id": ctx["wsid"]},
        {
            "auto_export_enabled": True,
            "auto_export_dow": today_dow,
            "auto_export_hour": now.hour,
        },
    )

    def _should_not_send(**kw):
        raise AssertionError("placeholder must not trigger email send")

    monkeypatch.setattr(
        "engines.email_service.send_workspace_auto_export_email", _should_not_send,
    )

    await _sweep_auto_exports()
    q = await gd_find_one(db.session, "workspace_quota",
                          {"workspace_school_id": ctx["wsid"]})
    assert q.get("auto_export_last_status") == "email_skipped_placeholder"
