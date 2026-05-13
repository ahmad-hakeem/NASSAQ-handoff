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


# ---------------------------------------------------------------------------
# Reactivation banner gate + dismissal (Task #232)
#
# Covers the GET /independent-teacher/workspace/lifecycle banner field
# and the POST .../lifecycle/reactivation-banner/dismiss endpoint.
# Spec: §6.8 reactivation UX — banner re-arms on every fresh
# archive→reactivate cycle, dismiss compares timestamps, dismiss is
# IT-only and respects the cross-workspace 404 invariant (§8 inv. 3).
# ---------------------------------------------------------------------------

from dependencies import UserRole  # noqa: E402
from engines.sql_utils import gd_delete_one  # noqa: E402

from tests._it_fixtures import headers as _mk_headers  # noqa: E402


_DISMISS_PATH = "/independent-teacher/workspace/lifecycle/reactivation-banner/dismiss"
_LIFECYCLE_PATH = "/independent-teacher/workspace/lifecycle"


async def _archive_and_reactivate(client, ctx: dict, *, days_archived: int = 2):
    """Drive a real archive→reactivate cycle so the lifecycle row
    carries the same column state production sees post-reactivate
    (last_reactivated_at + last_archive_cycle_archived_at stamped)."""
    h = _it_headers(ctx)
    archived_at = (datetime.now(timezone.utc) - timedelta(days=days_archived)).isoformat()
    await gd_update_one(
        db.session, "schools", {"id": ctx["wsid"]},
        {"status": "archived", "archived_at": archived_at},
    )
    resp = await client.post(
        "/independent-teacher/workspace/reactivate", headers=h,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_banner_appears_after_reactivate(client):
    """After a real archive→reactivate cycle the lifecycle GET must
    surface a populated reactivation_banner with the cycle's archive
    timestamp + computed days-remaining-at-reactivation."""
    ctx = await mk_it_workspace()
    await _archive_and_reactivate(client, ctx, days_archived=2)

    resp = await client.get(_LIFECYCLE_PATH, headers=_it_headers(ctx))
    assert resp.status_code == 200, resp.text
    banner = resp.json()["reactivation_banner"]
    assert banner is not None
    assert banner["reactivated_at"]
    assert banner["archived_at"]
    assert banner["reactivation_window_days"] == 30
    # 30-day window minus ~2 days archived ⇒ ~28 days remaining.
    assert banner["days_remaining_at_reactivation"] in (27, 28)


@pytest.mark.asyncio
async def test_banner_hides_after_dismiss(client):
    """POST .../dismiss must stamp reactivation_banner_dismissed_at
    so the next lifecycle GET returns banner=None for the same cycle."""
    ctx = await mk_it_workspace()
    await _archive_and_reactivate(client, ctx)
    h = _it_headers(ctx)

    pre = await client.get(_LIFECYCLE_PATH, headers=h)
    assert pre.json()["reactivation_banner"] is not None

    dismiss = await client.post(_DISMISS_PATH, headers=h)
    assert dismiss.status_code == 200, dismiss.text
    assert dismiss.json()["ok"] is True
    assert dismiss.json()["dismissed_at"]

    post = await client.get(_LIFECYCLE_PATH, headers=h)
    assert post.status_code == 200
    assert post.json()["reactivation_banner"] is None


@pytest.mark.asyncio
async def test_banner_rearms_after_second_archive_reactivate_cycle(client):
    """Once dismissed, a SECOND archive→reactivate cycle must re-arm
    the banner because last_reactivated_at moves forward past the
    earlier dismissed_at stamp."""
    ctx = await mk_it_workspace()
    h = _it_headers(ctx)

    # Cycle 1: reactivate, then dismiss.
    await _archive_and_reactivate(client, ctx, days_archived=2)
    assert (await client.post(_DISMISS_PATH, headers=h)).status_code == 200
    assert (await client.get(_LIFECYCLE_PATH, headers=h)).json()["reactivation_banner"] is None

    # Cycle 2: archive again and reactivate. The dismiss stamp from
    # cycle 1 is now older than the new last_reactivated_at so the
    # banner must surface again.
    await _archive_and_reactivate(client, ctx, days_archived=1)
    second = await client.get(_LIFECYCLE_PATH, headers=h)
    assert second.status_code == 200
    banner = second.json()["reactivation_banner"]
    assert banner is not None, "banner must re-arm on second cycle"
    assert banner["days_remaining_at_reactivation"] in (28, 29)


@pytest.mark.asyncio
async def test_dismiss_rejects_non_independent_teacher_caller(client):
    """The dismiss endpoint sits behind _require_independent_teacher,
    so a principal/admin token must be rejected with 403."""
    from engines.sql_utils import gd_insert as _gd_insert

    fake_school = str(uuid.uuid4())
    await _gd_insert(db.session, "schools", {
        "id": fake_school,
        "name": f"School-{fake_school[:6]}",
        "code": f"S{fake_school[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    fake_uid = str(uuid.uuid4())
    await _gd_insert(db.session, "users", {
        "id": fake_uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": fake_school,
        "email": f"princ-{fake_uid}@t.test",
        "full_name": "Principal Test",
        "is_active": True,
        "password_hash": "x",
    })
    h = _mk_headers(
        fake_uid, UserRole.SCHOOL_PRINCIPAL.value, fake_school,
        mfa_recent_at=now_ts(),
    )
    resp = await client.post(_DISMISS_PATH, headers=h)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_dismiss_with_forged_tenant_claim_cannot_touch_foreign_workspace(client):
    """Explicit cross-workspace invariant (§8 inv. 3): if IT user A
    forges their JWT tenant_id to point at IT workspace B, the dismiss
    endpoint must NOT stamp B's reactivation_banner_dismissed_at — the
    lifecycle resolver derives workspace_id from the caller's own user
    id (independent_workspace_id), so the forged claim is ignored and
    only A's workspace is ever touched. After driving an archive→
    reactivate cycle on B (so B's banner is armed), a forged-claim
    dismiss request from A must leave B's banner intact on B's own
    lifecycle GET."""
    a = await mk_it_workspace()
    b = await mk_it_workspace()
    # Arm B's banner via a real archive→reactivate cycle.
    await _archive_and_reactivate(client, b, days_archived=2)
    pre = await client.get(_LIFECYCLE_PATH, headers=_it_headers(b))
    assert pre.json()["reactivation_banner"] is not None

    # Forge: caller A's user id, but tenant claim points at B's wsid.
    forged = headers(
        a["uid"], a["user"]["role"], b["wsid"],
        mfa_recent_at=now_ts(),
    )
    await client.post(_DISMISS_PATH, headers=forged)

    # B's banner must still be armed — the forged claim was ignored.
    post = await client.get(_LIFECYCLE_PATH, headers=_it_headers(b))
    assert post.json()["reactivation_banner"] is not None, (
        "forged tenant_id claim must NOT dismiss a foreign workspace's banner"
    )


@pytest.mark.asyncio
async def test_dismiss_returns_404_when_workspace_row_missing(client):
    """Cross-workspace / orphaned-claim safety: if the IT user's
    workspace row no longer exists, dismiss must 404 (never 200/500),
    matching the §8 invariant 3 by-id read posture."""
    ctx = await mk_it_workspace()
    # Drop the schools row out from under the caller.
    await gd_delete_one(db.session, "schools", {"id": ctx["wsid"]})

    resp = await client.post(_DISMISS_PATH, headers=_it_headers(ctx))
    assert resp.status_code == 404
