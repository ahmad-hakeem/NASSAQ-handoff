"""Task #253 — Workspace quota-history endpoint.

Validates the daily-usage time series powering the workspace-hub
QuotaBar spark-lines:

  * Default 14-day window, ISO day labels oldest→newest, all four
    series the same length as ``days``.
  * Cumulative students/classes count rises across days.
  * Per-day imports series picks up bulk-import audit rows.
  * Cross-workspace caller (different IT) sees their own zero series,
    never another workspace's counts (§8 invariant 3).
  * ``days`` query param respected, clamped to [1, 30].
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_insert

from tests._it_fixtures import headers, mk_it_workspace, now_ts


def _it_headers(ctx: dict) -> dict:
    return headers(ctx["uid"], ctx["user"]["role"], ctx["wsid"], mfa_recent_at=now_ts())


@pytest.mark.asyncio
async def test_quota_history_default_window_shape(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)

    resp = await client.get("/independent-teacher/workspace/quota-history", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["workspace_id"] == ctx["wsid"]
    assert data["days_requested"] == 14
    assert len(data["days"]) == 14
    for key in ("students", "classes", "imports", "lesson_plans"):
        assert key in data
        assert len(data[key]) == 14

    today = datetime.now(timezone.utc).date().isoformat()
    assert data["days"][-1] == today

    # The bootstrap fixture seeds 1 student + 1 class today, so the
    # cumulative tail should be at least 1 for both metrics.
    assert data["students"][-1] >= 1
    assert data["classes"][-1] >= 1


@pytest.mark.asyncio
async def test_quota_history_imports_series_picks_up_audit_rows(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)

    today = datetime.now(timezone.utc).date()
    yday_dt = datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    today_dt = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=4)

    for ts in (yday_dt, today_dt, today_dt + timedelta(hours=1)):
        await gd_insert(db.session, "audit_logs", {
            "id": str(uuid.uuid4()),
            "school_id": ctx["wsid"],
            "action": "INDEPENDENT_TEACHER_BULK_IMPORT_STUDENTS",
            "performed_by": ctx["uid"],
            "timestamp": ts.isoformat(),
        })

    resp = await client.get(
        "/independent-teacher/workspace/quota-history",
        headers=h, params={"days": 7},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["days"]) == 7
    # last day = today (2 events), second-last = yesterday (1 event).
    assert data["imports"][-1] >= 2
    assert data["imports"][-2] >= 1


@pytest.mark.asyncio
async def test_quota_history_workspace_isolation(client):
    """A second IT workspace must see only its own zeroed counts."""
    a = await mk_it_workspace()
    b = await mk_it_workspace()

    # Seed a bulk-import audit row in workspace A only.
    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "school_id": a["wsid"],
        "action": "INDEPENDENT_TEACHER_BULK_IMPORT_STUDENTS",
        "performed_by": a["uid"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    h_b = headers(b["uid"], b["user"]["role"], b["wsid"], mfa_recent_at=now_ts())
    resp = await client.get("/independent-teacher/workspace/quota-history", headers=h_b)
    assert resp.status_code == 200
    data = resp.json()
    assert data["workspace_id"] == b["wsid"]
    # B never imported anything → all-zero imports series.
    assert sum(data["imports"]) == 0


@pytest.mark.asyncio
async def test_quota_history_days_param_clamped(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)

    resp = await client.get(
        "/independent-teacher/workspace/quota-history",
        headers=h, params={"days": 7},
    )
    assert resp.status_code == 200
    assert len(resp.json()["days"]) == 7

    # Out-of-range → 422 from the FastAPI Query validator.
    resp_bad = await client.get(
        "/independent-teacher/workspace/quota-history",
        headers=h, params={"days": 999},
    )
    assert resp_bad.status_code == 422


@pytest.mark.asyncio
async def test_quota_history_requires_independent_teacher(client):
    """Non-IT callers get the 403 envelope, never tenant data."""
    from dependencies import UserRole

    other_uid = str(uuid.uuid4())
    other_school_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": other_school_id,
        "name": "Other-School",
        "code": f"OS{other_school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    await gd_insert(db.session, "users", {
        "id": other_uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": other_school_id,
        "email": f"p-{other_uid}@t.test",
        "full_name": "principal",
        "is_active": True,
        "password_hash": "x",
    })
    h = headers(other_uid, UserRole.SCHOOL_PRINCIPAL.value, other_school_id, mfa_recent_at=now_ts())

    resp = await client.get("/independent-teacher/workspace/quota-history", headers=h)
    assert resp.status_code == 403
