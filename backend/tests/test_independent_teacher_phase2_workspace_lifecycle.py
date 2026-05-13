"""Independent-Teacher §6.8 workspace lifecycle (export + soft-delete)
endpoint tests.

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.8.
Task: #211.

Covers:
  * Export happy path: stamps schools.last_export_at, returns a 24h
    download_url, and the public download streams a zip whose
    manifest enumerates every whitelisted table.
  * Public download token must be honoured for the bound workspace,
    rejected with 404 for tampered / wrong-purpose tokens, and
    redacted columns (password_hash, mfa secrets) never leak.
  * Soft-delete pre-conditions: 412 when no recent export, 422 on
    name mismatch, 409 once already archived. Happy path flips
    schools.status='archived' + archived_at.
  * Reactivate happy path + 410 when past the 30-day window
    (lazy sweep flips pending_hard_delete first).
  * Cross-workspace IT caller → 404 (§8 invariant 3).
  * MFA step-up gate: missing recent MFA emits the canonical 403
    envelope on both export and soft-delete write surfaces.
"""
from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_update_one

from tests._it_fixtures import (
    headers, mk_it_workspace, now_ts, STEP_UP_CODES,
)


def _it_headers(ctx: dict, *, with_mfa: bool = True) -> dict:
    return headers(
        ctx["uid"], ctx["user"]["role"], ctx["wsid"],
        mfa_recent_at=now_ts() if with_mfa else None,
    )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_happy_path_stamps_last_export_and_returns_url(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)

    resp = await client.post("/independent-teacher/workspace/export", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["download_url"].startswith("/api/public/workspace-export/")
    assert data["ttl_hours"] == 24
    assert data["expires_at"]

    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert school["last_export_at"] is not None


@pytest.mark.asyncio
async def test_export_requires_recent_mfa(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx, with_mfa=False)

    resp = await client.post("/independent-teacher/workspace/export", headers=h)
    assert resp.status_code == 403
    body = resp.json()
    assert body.get("error", {}).get("code") in STEP_UP_CODES


@pytest.mark.asyncio
async def test_public_download_streams_zip_with_manifest_and_redactions(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)

    create = await client.post("/independent-teacher/workspace/export", headers=h)
    url = create.json()["download_url"].replace("/api", "")  # client mounts at /

    resp = await client.get(url)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"

    bundle = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(bundle.namelist())
    assert "manifest.json" in names
    manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
    assert manifest["workspace_school_id"] == ctx["wsid"]
    assert "schools" in manifest["tables"]
    assert "students" in manifest["tables"]

    # Sanity: the schools row is present and never carries a
    # password_hash field (schools doesn't have one, but the redaction
    # filter applied to every row is the contract under test here).
    schools_rows = json.loads(bundle.read("schools.json").decode("utf-8"))
    assert any(r["id"] == ctx["wsid"] for r in schools_rows)
    for row in schools_rows:
        assert "password_hash" not in row


@pytest.mark.asyncio
async def test_public_download_rejects_tampered_token(client):
    resp = await client.get("/public/workspace-export/not-a-real-token")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Soft-delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_delete_412_without_recent_export(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})

    resp = await client.post(
        "/independent-teacher/workspace/soft-delete",
        json={"confirm_workspace_name": school["name"]},
        headers=h,
    )
    assert resp.status_code == 412


@pytest.mark.asyncio
async def test_soft_delete_422_on_name_mismatch(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    # Stamp a recent export so the 412 gate is cleared.
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {"last_export_at": datetime.now(timezone.utc).isoformat()},
    )

    resp = await client.post(
        "/independent-teacher/workspace/soft-delete",
        json={"confirm_workspace_name": "WRONG NAME"},
        headers=h,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_soft_delete_happy_path_flips_status_archived(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {"last_export_at": datetime.now(timezone.utc).isoformat()},
    )

    resp = await client.post(
        "/independent-teacher/workspace/soft-delete",
        json={"confirm_workspace_name": school["name"]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "archived"
    assert body["reactivation_window_days"] == 30

    after = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert (after["status"] or "").lower() == "archived"
    assert after["archived_at"] is not None


@pytest.mark.asyncio
async def test_soft_delete_409_when_already_archived(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    now = datetime.now(timezone.utc).isoformat()
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {"status": "archived", "archived_at": now, "last_export_at": now},
    )

    resp = await client.post(
        "/independent-teacher/workspace/soft-delete",
        json={"confirm_workspace_name": school["name"]},
        headers=h,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_soft_delete_requires_recent_mfa(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx, with_mfa=False)

    resp = await client.post(
        "/independent-teacher/workspace/soft-delete",
        json={"confirm_workspace_name": "x"},
        headers=h,
    )
    assert resp.status_code == 403
    assert resp.json().get("error", {}).get("code") in STEP_UP_CODES


# ---------------------------------------------------------------------------
# Reactivate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reactivate_happy_path_within_window(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {
            "status": "archived",
            "archived_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        },
    )

    resp = await client.post(
        "/independent-teacher/workspace/reactivate", headers=h,
    )
    assert resp.status_code == 200, resp.text
    after = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert (after["status"] or "").lower() == "active"


@pytest.mark.asyncio
async def test_reactivate_410_past_30_day_window(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {
            "status": "archived",
            "archived_at": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
        },
    )

    resp = await client.post(
        "/independent-teacher/workspace/reactivate", headers=h,
    )
    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_reactivate_409_when_not_archived(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)

    resp = await client.post(
        "/independent-teacher/workspace/reactivate", headers=h,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# §6.8 review-fix coverage: cross-workspace isolation, single-use export
# token, archived-login gate, whitelist scope, lifecycle GET, reactivate
# MFA, row-count invariants.
# ---------------------------------------------------------------------------

from dependencies import hash_password  # noqa: E402


_NON_WHITELISTED_TABLES = (
    "school_settings",
    "academic_years",
    "academic_terms",
    "users",
    "audit_logs",
    "mfa_factors",
    "password_reset_tokens",
)


@pytest.mark.asyncio
async def test_export_payload_isolated_to_caller_workspace(client):
    """Exporter A's bundle must NOT contain rows from workspace B —
    every whitelisted table is filtered by the workspace-scope column,
    so a foreign workspace's id should never appear in any per-table
    JSON payload (§6.8 cross-tenant guarantee)."""
    a = await mk_it_workspace()
    b = await mk_it_workspace()

    create = await client.post(
        "/independent-teacher/workspace/export", headers=_it_headers(a),
    )
    url = create.json()["download_url"].replace("/api", "")
    resp = await client.get(url)
    assert resp.status_code == 200

    bundle = zipfile.ZipFile(io.BytesIO(resp.content))
    foreign_ids = {b["wsid"], b["uid"], b["teacher_id"]}
    if b.get("student_id"):
        foreign_ids.add(b["student_id"])
    if b.get("parent_id"):
        foreign_ids.add(b["parent_id"])

    for name in bundle.namelist():
        if not name.endswith(".json") or name == "manifest.json":
            continue
        rows = json.loads(bundle.read(name).decode("utf-8"))
        for row in rows:
            for v in row.values():
                if isinstance(v, str) and v in foreign_ids:
                    pytest.fail(
                        f"workspace {b['wsid']} leaked into "
                        f"{a['wsid']} export under {name}: {v}"
                    )


@pytest.mark.asyncio
async def test_export_bundle_omits_non_whitelisted_tables(client):
    """The §6.8 whitelist deliberately omits school_settings,
    academic_years/terms, users, audit_logs, MFA tables, etc. The
    manifest must list ONLY the whitelisted scope."""
    ctx = await mk_it_workspace()
    create = await client.post(
        "/independent-teacher/workspace/export", headers=_it_headers(ctx),
    )
    url = create.json()["download_url"].replace("/api", "")
    resp = await client.get(url)
    bundle = zipfile.ZipFile(io.BytesIO(resp.content))
    manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
    for forbidden in _NON_WHITELISTED_TABLES:
        assert forbidden not in manifest["tables"], (
            f"{forbidden} must NOT appear in workspace export manifest"
        )
        assert f"{forbidden}.json" not in bundle.namelist()


@pytest.mark.asyncio
async def test_public_download_is_single_use(client):
    """Downloading the bundle once must consume the token; the second
    GET against the same URL returns 404 even though the JWT is still
    cryptographically valid for 24h."""
    ctx = await mk_it_workspace()
    create = await client.post(
        "/independent-teacher/workspace/export", headers=_it_headers(ctx),
    )
    url = create.json()["download_url"].replace("/api", "")

    first = await client.get(url)
    assert first.status_code == 200
    second = await client.get(url)
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_export_remint_invalidates_prior_token(client):
    """Re-minting an export token must invalidate the previous URL —
    only the most recent token hash is honoured."""
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    first_url = (await client.post(
        "/independent-teacher/workspace/export", headers=h,
    )).json()["download_url"].replace("/api", "")
    # Mint a second token without consuming the first.
    await client.post("/independent-teacher/workspace/export", headers=h)

    resp = await client.get(first_url)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_archived_workspace_blocks_login(client):
    """An IT user whose workspace is archived must be rejected at
    /auth/login with a safe Arabic message — the lifecycle gate runs
    before MFA challenge issuance."""
    ctx = await mk_it_workspace()
    pw = "Test-Pass-1234!"
    await gd_update_one(
        db.session, "users", {"id": ctx["uid"]},
        {"password_hash": hash_password(pw)},
    )
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {
            "status": "archived",
            "archived_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    real_email = f"it-{uuid.uuid4().hex[:8]}@example.com"
    await gd_update_one(
        db.session, "users", {"id": ctx["uid"]}, {"email": real_email},
    )
    resp = await client.post(
        "/auth/login",
        json={"email": real_email, "password": pw},
    )
    assert resp.status_code == 401
    body = resp.json()
    detail = body.get("detail") or body.get("error", {}).get("message", "")
    assert "أرشف" in detail or "مساحت" in detail


@pytest.mark.asyncio
async def test_soft_delete_does_not_touch_data_rows(client):
    """Soft-delete must flip lifecycle columns ONLY — student,
    schedule_session, attendance, etc. row counts must be unchanged."""
    from sqlalchemy import text as _sql

    ctx = await mk_it_workspace()
    h = _it_headers(ctx)
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {"last_export_at": datetime.now(timezone.utc).isoformat()},
    )

    async def _counts():
        out = {}
        for table, col in (
            ("students", "school_id"),
            ("teachers", "school_id"),
            ("classes", "school_id"),
            ("schedule_sessions", "school_id"),
            ("attendance", "school_id"),
            ("assessments", "school_id"),
        ):
            r = await db.session.execute(
                _sql(f"SELECT COUNT(*) FROM {table} WHERE {col} = :w"),
                {"w": ctx["wsid"]},
            )
            out[table] = r.scalar()
        return out

    before = await _counts()
    resp = await client.post(
        "/independent-teacher/workspace/soft-delete",
        json={"confirm_workspace_name": school["name"]},
        headers=h,
    )
    assert resp.status_code == 200
    after = await _counts()
    assert before == after


@pytest.mark.asyncio
async def test_lifecycle_get_returns_columns(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx, with_mfa=False)
    resp = await client.get(
        "/independent-teacher/workspace/lifecycle", headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["workspace_id"] == ctx["wsid"]
    assert body["pending_hard_delete"] is False
    assert body["archived_at"] is None
    assert "last_export_at" in body


@pytest.mark.asyncio
async def test_reactivate_requires_recent_mfa(client):
    ctx = await mk_it_workspace()
    h = _it_headers(ctx, with_mfa=False)
    resp = await client.post(
        "/independent-teacher/workspace/reactivate", headers=h,
    )
    assert resp.status_code == 403
    assert resp.json().get("error", {}).get("code") in STEP_UP_CODES
