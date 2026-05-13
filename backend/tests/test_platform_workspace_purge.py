"""Platform-admin workspace hard-delete (purge) end-to-end tests.

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.8
(hard-delete trust boundary).
Task: #226.

Covers the platform-admin purge router
(`backend/routes/platform_workspace_purge_routes.py`):

  * Happy path — an archived + pending_hard_delete workspace is fully
    cascade-deleted, every whitelisted child table is empty, and a
    second IT workspace is left completely untouched.
  * Confirm-mismatch (422) when the body's ``confirm_workspace_id``
    does not equal the path param verbatim.
  * Not-pending (409) when the schools row exists but has not been
    flipped to ``pending_hard_delete=TRUE``.
  * Missing row (404) for an unknown workspace id.
  * Trust-boundary gate (403) when an Independent-Teacher caller
    hits the platform-admin route (it must never be reachable from
    the IT API surface, even with a valid bearer).
  * The pending-hard-delete listing endpoint shows only the
    archived + pending row.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text as _sql

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one

from tests._it_fixtures import headers, mk_it_workspace, now_ts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Whitelisted (table, scope_column) pairs the purge handler walks.
# Mirrors `_PURGE_TABLES` in the router but excludes the parent
# `schools` row (asserted separately) and the dual-FK
# workspace_collaborators row (validated by both columns).
_CHILD_SCOPED = (
    ("workspace_quota", "workspace_school_id"),
    ("parent_invitations", "workspace_school_id"),
    ("attendance", "school_id"),
    ("assessments", "school_id"),
    ("behaviour_records", "school_id"),
    ("schedule_sessions", "school_id"),
    ("guardian_links", "tenant_id"),
    ("calendar_events", "tenant_id"),
    ("students", "school_id"),
    ("parents", "school_id"),
    ("teachers", "school_id"),
    ("classes", "school_id"),
    ("subjects", "school_id"),
    ("school_settings", "school_id"),
    ("academic_terms", "school_id"),
    ("academic_years", "school_id"),
    ("users", "tenant_id"),
)


async def _count(table: str, col: str, value: str) -> int:
    r = await db.session.execute(
        _sql(f"SELECT COUNT(*) FROM {table} WHERE {col} = :v"),
        {"v": value},
    )
    return int(r.scalar() or 0)


async def _flip_pending_hard_delete(wsid: str) -> None:
    """Mark a workspace as past its 30-day reactivation window so the
    purge handler is willing to hard-delete it."""
    now = datetime.now(timezone.utc).isoformat()
    await gd_update_one(
        db.session, "schools", {"id": wsid},
        {
            "status": "archived",
            "archived_at": now,
            "pending_hard_delete": True,
        },
    )


async def _seed_extra_rows(wsid: str) -> None:
    """Drop a row into a couple of the whitelisted child tables so the
    happy-path test is exercising real cascade work, not just the
    parent row."""
    await gd_insert(db.session, "workspace_quota", {
        "workspace_school_id": wsid,
        "max_students": 200,
        "max_classes": 5,
        "max_imports_per_day": 5,
        "max_rows_per_import": 200,
        "imports_today": 0,
    })
    await gd_insert(db.session, "calendar_events", {
        "id": str(uuid.uuid4()),
        "tenant_id": wsid,
        "title": "تجربة",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "is_personal": True,
    })


# ---------------------------------------------------------------------------
# Trust-boundary gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_purge_403_for_independent_teacher_caller(client):
    """The §6.8 trust boundary: an IT bearer must never reach the
    platform-admin purge router, even with a valid Tier-A token."""
    ctx = await mk_it_workspace()
    h = headers(
        ctx["uid"], ctx["user"]["role"], ctx["wsid"],
        mfa_recent_at=now_ts(),
    )
    await _flip_pending_hard_delete(ctx["wsid"])

    resp = await client.post(
        f"/platform/workspaces/{ctx['wsid']}/hard-delete",
        json={"confirm_workspace_id": ctx["wsid"]},
        headers=h,
    )
    assert resp.status_code == 403, resp.text

    listing = await client.get(
        "/platform/workspaces/pending-hard-delete", headers=h,
    )
    assert listing.status_code == 403


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_purge_404_when_workspace_missing(client, platform_admin_headers):
    fake = f"itw_{uuid.uuid4().hex}"
    resp = await client.post(
        f"/platform/workspaces/{fake}/hard-delete",
        json={"confirm_workspace_id": fake},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_purge_409_when_not_pending_hard_delete(
    client, platform_admin_headers,
):
    ctx = await mk_it_workspace()
    # Workspace is `active` and pending_hard_delete=FALSE by default.
    resp = await client.post(
        f"/platform/workspaces/{ctx['wsid']}/hard-delete",
        json={"confirm_workspace_id": ctx["wsid"]},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 409, resp.text

    # Even merely-archived (without pending_hard_delete=True) must
    # still 409 — only the lazy on-login sweep is allowed to flip
    # that flag, and the purge handler refuses to act before then.
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {"status": "archived",
         "archived_at": datetime.now(timezone.utc).isoformat()},
    )
    resp2 = await client.post(
        f"/platform/workspaces/{ctx['wsid']}/hard-delete",
        json={"confirm_workspace_id": ctx["wsid"]},
        headers=platform_admin_headers,
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_purge_422_on_confirm_mismatch(client, platform_admin_headers):
    ctx = await mk_it_workspace()
    await _flip_pending_hard_delete(ctx["wsid"])

    resp = await client.post(
        f"/platform/workspaces/{ctx['wsid']}/hard-delete",
        json={"confirm_workspace_id": "totally-different-id"},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 422, resp.text

    # The schools row must NOT have been deleted by the rejected call.
    still = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert still is not None


# ---------------------------------------------------------------------------
# Pending-hard-delete listing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pending_hard_delete_listing_only_returns_pending(
    client, platform_admin_headers,
):
    ready = await mk_it_workspace()
    not_ready = await mk_it_workspace()
    await _flip_pending_hard_delete(ready["wsid"])

    resp = await client.get(
        "/platform/workspaces/pending-hard-delete",
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {w["id"] for w in body["workspaces"]}
    assert ready["wsid"] in ids
    assert not_ready["wsid"] not in ids


# ---------------------------------------------------------------------------
# Happy path — purge cascades and isolates other workspaces
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_purge_happy_path_cascades_and_preserves_sibling_workspace(
    client, platform_admin_headers,
):
    """The two-workspace fixture from the spec: A is archived +
    pending_hard_delete and gets purged; B is fully populated and
    must survive byte-identically."""
    a = await mk_it_workspace()
    b = await mk_it_workspace()
    await _seed_extra_rows(a["wsid"])
    await _seed_extra_rows(b["wsid"])
    await _flip_pending_hard_delete(a["wsid"])

    # Snapshot B's whitelisted tables BEFORE the purge.
    before_b = {
        (t, c): await _count(t, c, b["wsid"]) for t, c in _CHILD_SCOPED
    }
    # Sanity: A actually has rows worth deleting in at least the
    # core roster tables.
    for table, col in (
        ("schools", "id"), ("teachers", "school_id"),
        ("classes", "school_id"), ("students", "school_id"),
        ("workspace_quota", "workspace_school_id"),
        ("calendar_events", "tenant_id"),
    ):
        assert await _count(table, col, a["wsid"]) >= 1, (table, col)

    resp = await client.post(
        f"/platform/workspaces/{a['wsid']}/hard-delete",
        json={"confirm_workspace_id": a["wsid"]},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["workspace_id"] == a["wsid"]
    assert "schools.id" in body["deleted_counts"]
    assert body["deleted_counts"]["schools.id"] == 1

    # Parent row gone.
    assert await gd_find_one(db.session, "schools", {"id": a["wsid"]}) is None

    # Every whitelisted child table for A is now empty.
    for table, col in _CHILD_SCOPED:
        try:
            n = await _count(table, col, a["wsid"])
        except Exception:
            # Tolerate schema-drift skips the same way the handler does
            # (missing table/column). The handler reports them under
            # ``skipped_tables`` so a missing table here is not a bug.
            assert f"{table}.{col}" in body.get("skipped_tables", [])
            continue
        assert n == 0, f"{table}.{col} still has {n} rows for purged workspace"

    # workspace_collaborators (dual-FK): both sides must be empty for A.
    for col in ("host_school_id", "collaborator_school_id"):
        try:
            n = await _count("workspace_collaborators", col, a["wsid"])
        except Exception:
            continue
        assert n == 0

    # B is completely untouched.
    after_b = {
        (t, c): await _count(t, c, b["wsid"]) for t, c in _CHILD_SCOPED
    }
    assert before_b == after_b, (
        f"sibling workspace B was modified by purge of A: "
        f"before={before_b} after={after_b}"
    )
    assert await gd_find_one(db.session, "schools", {"id": b["wsid"]}) is not None

    # An audit trail row was written for the destructive op.
    audit_rows = await gd_find(
        db.session, "audit_logs",
        {"action": "INDEPENDENT_TEACHER_HARD_DELETED",
         "entity_id": a["wsid"]},
    )
    assert len(audit_rows) >= 1


@pytest.mark.asyncio
async def test_recent_purges_listing_returns_purged_workspace(
    client, platform_admin_headers,
):
    """After a successful purge, the audit-backed history endpoint
    must surface the row with snapshot + per-table counts so a
    platform admin can answer 'did we already purge X?' without
    leaving the page."""
    ctx = await mk_it_workspace()
    await _seed_extra_rows(ctx["wsid"])
    await _flip_pending_hard_delete(ctx["wsid"])

    purge = await client.post(
        f"/platform/workspaces/{ctx['wsid']}/hard-delete",
        json={"confirm_workspace_id": ctx["wsid"]},
        headers=platform_admin_headers,
    )
    assert purge.status_code == 200, purge.text

    resp = await client.get(
        "/platform/workspaces/recent-purges",
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "purges" in body
    match = next(
        (p for p in body["purges"] if p.get("workspace_id") == ctx["wsid"]),
        None,
    )
    assert match is not None, body
    assert isinstance(match.get("snapshot"), dict)
    assert match["snapshot"].get("status") == "archived"
    assert match.get("deleted_counts", {}).get("schools.id") == 1
    assert match.get("purged_at")


@pytest.mark.asyncio
async def test_recent_purges_403_for_independent_teacher_caller(client):
    """The history endpoint shares the platform-admin trust boundary;
    an IT bearer must not be able to enumerate purged workspaces."""
    ctx = await mk_it_workspace()
    h = headers(
        ctx["uid"], ctx["user"]["role"], ctx["wsid"],
        mfa_recent_at=now_ts(),
    )
    resp = await client.get(
        "/platform/workspaces/recent-purges", headers=h,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_purge_idempotent_404_after_first_success(
    client, platform_admin_headers,
):
    """Once a workspace is purged the schools row is gone, so a
    repeat call must 404 — never silently succeed."""
    ctx = await mk_it_workspace()
    await _flip_pending_hard_delete(ctx["wsid"])

    first = await client.post(
        f"/platform/workspaces/{ctx['wsid']}/hard-delete",
        json={"confirm_workspace_id": ctx["wsid"]},
        headers=platform_admin_headers,
    )
    assert first.status_code == 200

    second = await client.post(
        f"/platform/workspaces/{ctx['wsid']}/hard-delete",
        json={"confirm_workspace_id": ctx["wsid"]},
        headers=platform_admin_headers,
    )
    assert second.status_code == 404
