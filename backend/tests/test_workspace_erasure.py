"""Task #276 — IT account erasure (GDPR right-to-be-forgotten) tests.

Covers:
  * Happy-path: POST /independent-teacher/workspace/request-erasure
    stamps `erasure_requested_at`, `pending_hard_delete=TRUE`,
    `status='archived'`, writes audit row with full forensics
    snapshot mirroring `_EXPORT_TABLES`.
  * 409 idempotency when erasure already requested.
  * 422 verbatim-name mismatch and 422 unacknowledged checkbox.
  * 403 step-up envelope when MFA is missing; 403 when caller is not
    an independent teacher.
  * Reactivate 410s with a distinct erasure-pending message once
    erasure has been requested.
  * Daily sweep `_sweep_erasure_purges` physically purges workspaces
    whose grace window has elapsed and writes the
    `INDEPENDENT_TEACHER_ERASURE_COMPLETED` audit row.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one

from tests._it_fixtures import (
    headers, mk_it_workspace, now_ts, STEP_UP_CODES,
)


def _it_headers(ctx: dict, *, with_mfa: bool = True) -> dict:
    return headers(
        ctx["uid"], ctx["user"]["role"], ctx["wsid"],
        mfa_recent_at=now_ts() if with_mfa else None,
    )


async def _audit_row(action: str, workspace_id: str) -> dict | None:
    # `tenant_id` filter is not portable here — the post-purge
    # ERASURE_COMPLETED row stores `school_id=NULL` (the schools row
    # is gone before the audit insert) and stashes the workspace id
    # in `entity_id` + `details`. Filter on `entity_id` so both the
    # REQUESTED and COMPLETED rows resolve.
    rows = await gd_find(
        db.session, "audit_logs",
        {"action": action, "entity_id": workspace_id},
    )
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Request-erasure: happy path + forensics snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_erasure_happy_path_stamps_columns_and_audit(client):
    ctx = await mk_it_workspace()
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    h = _it_headers(ctx)

    resp = await client.post(
        "/independent-teacher/workspace/request-erasure",
        json={
            "confirm_workspace_name": school["name"],
            "acknowledged": True,
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == "archived"
    assert body["erasure_requested_at"]
    assert body["erasure_deadline"]
    assert body["erasure_window_days"] >= 1

    # Lifecycle columns flipped.
    after = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert after["status"] == "archived"
    assert after["pending_hard_delete"] is True
    assert after["erasure_requested_at"] is not None
    assert after["archived_at"] is not None

    # Audit row carries the full forensics snapshot.
    row = await _audit_row(
        "INDEPENDENT_TEACHER_ERASURE_REQUESTED", ctx["wsid"],
    )
    assert row is not None
    details = row["details"] if isinstance(row["details"], dict) \
        else __import__("json").loads(row["details"])
    snap = details["snapshot"]
    assert snap["school"]["id"] == ctx["wsid"]
    assert snap["school"]["name"] == school["name"]
    # Per-table row counts cover the §6.8 _EXPORT_TABLES whitelist.
    counts = snap["table_row_counts"]
    assert "schools.id" in counts
    assert counts["schools.id"] == 1
    assert "students.school_id" in counts
    assert "teachers.school_id" in counts
    # Whitelist + redaction list are persisted for forensics.
    assert "schools.id" in snap["export_tables_whitelist"]
    assert "password_hash" in snap["redacted_columns_whitelist"]


@pytest.mark.asyncio
async def test_request_erasure_idempotent_409(client):
    ctx = await mk_it_workspace()
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    h = _it_headers(ctx)

    payload = {
        "confirm_workspace_name": school["name"],
        "acknowledged": True,
    }
    first = await client.post(
        "/independent-teacher/workspace/request-erasure",
        json=payload, headers=h,
    )
    assert first.status_code == 200
    second = await client.post(
        "/independent-teacher/workspace/request-erasure",
        json=payload, headers=h,
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_request_erasure_name_mismatch_422(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    resp = await client.post(
        "/independent-teacher/workspace/request-erasure",
        json={
            "confirm_workspace_name": "wrong-name",
            "acknowledged": True,
        },
        headers=h,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_request_erasure_unacknowledged_422(client):
    ctx = await mk_it_workspace()
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    h = _it_headers(ctx)
    resp = await client.post(
        "/independent-teacher/workspace/request-erasure",
        json={
            "confirm_workspace_name": school["name"],
            "acknowledged": False,
        },
        headers=h,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_request_erasure_requires_recent_mfa(client):
    ctx = await mk_it_workspace()
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    h = _it_headers(ctx, with_mfa=False)
    resp = await client.post(
        "/independent-teacher/workspace/request-erasure",
        json={
            "confirm_workspace_name": school["name"],
            "acknowledged": True,
        },
        headers=h,
    )
    assert resp.status_code == 403
    code = resp.json().get("error", {}).get("code")
    assert code in STEP_UP_CODES


@pytest.mark.asyncio
async def test_request_erasure_role_denied_for_non_it(client, tenant_a):
    # School-admin token must be rejected — IT-only router.
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_a,
        "email": f"{uid}@t.test",
        "full_name": "Admin",
        "is_active": True,
        "password_hash": "x",
    })
    token = create_access_token({
        "sub": uid, "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_a,
    }, mfa_recent_at=now_ts(), mfa_kind="webauthn")
    resp = await client.post(
        "/independent-teacher/workspace/request-erasure",
        json={"confirm_workspace_name": "x", "acknowledged": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in {401, 403}


# ---------------------------------------------------------------------------
# Reactivate 410 once erasure has been requested
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reactivate_410_once_erasure_requested(client):
    ctx = await mk_it_workspace()
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    h = _it_headers(ctx)

    # Trigger erasure.
    req = await client.post(
        "/independent-teacher/workspace/request-erasure",
        json={
            "confirm_workspace_name": school["name"],
            "acknowledged": True,
        },
        headers=h,
    )
    assert req.status_code == 200

    # Reactivate must now 410 — the workspace is on a one-way path.
    resp = await client.post(
        "/independent-teacher/workspace/reactivate", headers=h,
    )
    assert resp.status_code == 410


# ---------------------------------------------------------------------------
# Daily sweep: auto-purge once grace window has elapsed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sweep_purges_after_grace_and_writes_audit(client):
    from app.lifecycle import _sweep_erasure_purges

    ctx = await mk_it_workspace()
    # Backdate erasure to past the window so the sweep picks it up.
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {
            "status": "archived",
            "archived_at": past,
            "pending_hard_delete": True,
            "erasure_requested_at": past,
            "erasure_window_days": 7,
        },
    )

    # Sanity: the workspace exists.
    pre = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert pre is not None

    await _sweep_erasure_purges()

    # School row physically gone.
    post = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert post is None

    # Audit row written by the sweep.
    row = await _audit_row(
        "INDEPENDENT_TEACHER_ERASURE_COMPLETED", ctx["wsid"],
    )
    assert row is not None
    details = row["details"] if isinstance(row["details"], dict) \
        else __import__("json").loads(row["details"])
    assert details["school_id"] == ctx["wsid"]
    assert "deleted_counts" in details


@pytest.mark.asyncio
async def test_sweep_skips_workspaces_inside_grace_window(client):
    from app.lifecycle import _sweep_erasure_purges

    ctx = await mk_it_workspace()
    # Erasure requested today — well inside the 7-day window.
    today = datetime.now(timezone.utc).isoformat()
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {
            "status": "archived",
            "archived_at": today,
            "pending_hard_delete": True,
            "erasure_requested_at": today,
            "erasure_window_days": 7,
        },
    )

    await _sweep_erasure_purges()

    # Still present — sweep must respect the grace window.
    post = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert post is not None
