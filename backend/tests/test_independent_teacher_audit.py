"""IT Phase 2 §6.x — Workspace audit-log view (Task #248).

Coverage:
  (a) list returns only the caller's own-workspace rows
  (b) by-id detail returns 200 for own row + 404 for foreign row
  (c) sensitive-key stripping in details
  (d) non-IT role on every endpoint → 403
  (e) category filter narrows result set
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db, UserRole
from engines.sql_utils import gd_insert
from tests._it_fixtures import mk_it_workspace, headers, now_ts


def _it_h(ctx: dict) -> dict:
    return headers(ctx["uid"], ctx["user"]["role"], ctx["wsid"])


async def _seed_log(
    *,
    school_id: str | None,
    action: str,
    details: dict | None = None,
    timestamp: datetime | None = None,
    actor_name: str = "T",
) -> str:
    log_id = str(uuid.uuid4())
    await gd_insert(db.session, "audit_logs", {
        "id": log_id,
        "school_id": school_id,
        "action": action,
        "severity": "low",
        "actor_name": actor_name,
        "actor_role": UserRole.INDEPENDENT_TEACHER.value,
        "details": details or {},
        "timestamp": timestamp or datetime.now(timezone.utc),
    })
    return log_id


# ----------------------------------------------------------------------
# (a) Own-workspace filter
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_returns_only_own_workspace_rows(client):
    own = await mk_it_workspace()
    other = await mk_it_workspace()

    own_id = await _seed_log(school_id=own["wsid"], action="auth.login")
    foreign_id = await _seed_log(school_id=other["wsid"], action="auth.login")
    null_id = await _seed_log(school_id=None, action="auth.login")

    resp = await client.get(
        "/independent-teacher/audit-logs",
        headers=_it_h(own),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {row["id"] for row in body["logs"]}
    assert own_id in ids
    assert foreign_id not in ids
    assert null_id not in ids
    assert "categories" in body and len(body["categories"]) > 0


# ----------------------------------------------------------------------
# (b) Cross-workspace by-id → 404 (spec §8 inv. 3)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_by_id_cross_workspace_returns_404(client):
    own = await mk_it_workspace()
    other = await mk_it_workspace()

    own_id = await _seed_log(school_id=own["wsid"], action="auth.login")
    foreign_id = await _seed_log(school_id=other["wsid"], action="auth.login")

    ok = await client.get(
        f"/independent-teacher/audit-logs/{own_id}",
        headers=_it_h(own),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["log"]["id"] == own_id

    nope = await client.get(
        f"/independent-teacher/audit-logs/{foreign_id}",
        headers=_it_h(own),
    )
    assert nope.status_code == 404, nope.text

    missing = await client.get(
        f"/independent-teacher/audit-logs/{uuid.uuid4()}",
        headers=_it_h(own),
    )
    assert missing.status_code == 404


# ----------------------------------------------------------------------
# (c) Sensitive-key stripping
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sensitive_keys_stripped_from_details(client):
    own = await mk_it_workspace()
    # Mix of allowlisted-safe metadata, classic secret-y keys we used to
    # blacklist, AND novel/unknown keys (e.g. `safe_key`, `notes`,
    # `email`) that the whitelist must drop by default.
    log_id = await _seed_log(
        school_id=own["wsid"],
        action="INDEPENDENT_TEACHER_EXPORT",
        details={
            # Allowlisted: kept verbatim.
            "school_id": own["wsid"],
            "tenant_id": own["wsid"],
            "user_id": "u-123",
            "ttl_hours": 24,
            # Classic blacklist hits — must still be dropped.
            "token_hash": "abc123",
            "password": "p@ss",
            "raw_token": "t",
            # Novel keys not on the allowlist — must be dropped too,
            # because we now default-deny.
            "safe_key": "kept-no-more",
            "notes": "free-form text we never want to surface",
            "email": "leak@example.com",
            "phone": "+966500000000",
        },
    )

    detail = await client.get(
        f"/independent-teacher/audit-logs/{log_id}",
        headers=_it_h(own),
    )
    assert detail.status_code == 200, detail.text
    d = detail.json()["log"]["details"]
    # Allowlisted survived.
    assert d["school_id"] == own["wsid"]
    assert d["ttl_hours"] == 24
    assert d["user_id"] == "u-123"
    # Default-deny: blacklisted AND unknown keys are gone.
    for forbidden in (
        "token_hash", "password", "raw_token",
        "safe_key", "notes", "email", "phone",
    ):
        assert forbidden not in d, forbidden

    listing = await client.get(
        "/independent-teacher/audit-logs",
        headers=_it_h(own),
    )
    row = next(r for r in listing.json()["logs"] if r["id"] == log_id)
    assert "token_hash" not in row["details"]
    assert "safe_key" not in row["details"]
    assert row["category"] == "lifecycle"
    assert row["action_label_ar"]


# ----------------------------------------------------------------------
# (c2) IP masking — raw IP addresses (top-level OR nested) are
# truncated to a /24 (IPv4) or /48 (IPv6) before serialization. The
# `ip_address` column is sanitized via the same path.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ip_addresses_are_masked(client):
    own = await mk_it_workspace()
    log_id = await _seed_log(
        school_id=own["wsid"],
        action="INDEPENDENT_TEACHER_EXPORT_DOWNLOADED",
        details={
            "client_ip": "203.0.113.42",
            "ip_address": "198.51.100.7",
            "x_forwarded_for": "192.0.2.99, 10.0.0.1",
            "ip": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "bytes": 4096,
        },
    )

    detail = await client.get(
        f"/independent-teacher/audit-logs/{log_id}",
        headers=_it_h(own),
    )
    assert detail.status_code == 200, detail.text
    d = detail.json()["log"]["details"]

    # IPv4: last octet masked, first three preserved.
    assert d["client_ip"] == "203.0.113.x"
    assert d["ip_address"] == "198.51.100.x"
    # XFF: only the leftmost hop survives, masked.
    assert d["x_forwarded_for"] == "192.0.2.x"
    # IPv6: keep first three hextets, mask the rest.
    assert d["ip"].startswith("2001:0db8:85a3"), d["ip"]
    assert d["ip"].endswith("::xxxx")
    # No raw addresses anywhere in the serialized blob.
    blob = repr(d)
    for raw in ("203.0.113.42", "198.51.100.7", "192.0.2.99", "10.0.0.1",
                "8a2e:0370:7334"):
        assert raw not in blob, raw


# ----------------------------------------------------------------------
# (d) Non-IT role → 403
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_non_it_role_is_forbidden(client):
    own = await mk_it_workspace()
    own_id = await _seed_log(school_id=own["wsid"], action="auth.login")

    # School-principal token — not an IT.
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": "S", "code": f"S{sid[:8]}",
        "status": "active", "country": "SA", "language": "ar",
    })
    p_uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": p_uid, "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": sid, "email": f"p-{p_uid}@t.test",
        "full_name": "P", "is_active": True, "password_hash": "x",
    })
    p_h = headers(p_uid, UserRole.SCHOOL_PRINCIPAL.value, sid)

    r1 = await client.get("/independent-teacher/audit-logs", headers=p_h)
    assert r1.status_code == 403

    r2 = await client.get(
        f"/independent-teacher/audit-logs/{own_id}", headers=p_h,
    )
    assert r2.status_code == 403


# ----------------------------------------------------------------------
# (e) Category filter
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_category_filter_narrows_results(client):
    own = await mk_it_workspace()
    auth_id = await _seed_log(school_id=own["wsid"], action="auth.login")
    collab_id = await _seed_log(
        school_id=own["wsid"], action="INDEPENDENT_TEACHER_COLLAB_INVITED",
    )
    write_id = await _seed_log(
        school_id=own["wsid"], action="academic.grade_recorded",
    )
    other_id = await _seed_log(
        school_id=own["wsid"], action="something.unmapped",
    )

    resp = await client.get(
        "/independent-teacher/audit-logs?category=collaborators",
        headers=_it_h(own),
    )
    assert resp.status_code == 200, resp.text
    ids = {r["id"] for r in resp.json()["logs"]}
    assert collab_id in ids
    assert auth_id not in ids
    assert write_id not in ids

    # The renamed `data-write` category (spec) catches academic.* and
    # other dotted data write families. Hyphenated, not snake_cased.
    resp_dw = await client.get(
        "/independent-teacher/audit-logs?category=data-write",
        headers=_it_h(own),
    )
    assert resp_dw.status_code == 200, resp_dw.text
    dw_rows = resp_dw.json()["logs"]
    dw_ids = {r["id"] for r in dw_rows}
    assert write_id in dw_ids
    assert auth_id not in dw_ids
    assert collab_id not in dw_ids
    assert all(r["category"] == "data-write" for r in dw_rows)

    # `other` excludes the four mapped buckets (auth/lifecycle/collab/dw).
    resp_other = await client.get(
        "/independent-teacher/audit-logs?category=other",
        headers=_it_h(own),
    )
    assert resp_other.status_code == 200, resp_other.text
    other_ids = {r["id"] for r in resp_other.json()["logs"]}
    assert other_id in other_ids
    assert auth_id not in other_ids
    assert collab_id not in other_ids
    assert write_id not in other_ids


# ----------------------------------------------------------------------
# (f) Date-range filter — `from` / `to` are pushed to SQL so they
# compose correctly with cursor pagination over deep history.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_date_range_filter(client):
    own = await mk_it_workspace()
    now = datetime.now(timezone.utc)

    old_id = await _seed_log(
        school_id=own["wsid"], action="auth.login",
        timestamp=now - timedelta(days=10),
    )
    mid_id = await _seed_log(
        school_id=own["wsid"], action="auth.login",
        timestamp=now - timedelta(days=3),
    )
    new_id = await _seed_log(
        school_id=own["wsid"], action="auth.login",
        timestamp=now - timedelta(hours=1),
    )

    # Use Z suffix so the literal '+' in `+00:00` isn't decoded as a
    # space by the URL parser.
    from_iso = (now - timedelta(days=5)).replace(tzinfo=None).isoformat() + "Z"
    to_iso = (now - timedelta(minutes=30)).replace(tzinfo=None).isoformat() + "Z"
    resp = await client.get(
        f"/independent-teacher/audit-logs?from={from_iso}&to={to_iso}",
        headers=_it_h(own),
    )
    assert resp.status_code == 200, resp.text
    ids = {r["id"] for r in resp.json()["logs"]}
    assert mid_id in ids
    assert new_id in ids
    assert old_id not in ids

    # Bad date → 422 with safe Arabic message, never 500.
    bad = await client.get(
        "/independent-teacher/audit-logs?from=not-a-date",
        headers=_it_h(own),
    )
    assert bad.status_code == 422


# ----------------------------------------------------------------------
# (g) Actor substring filter — case-insensitive, workspace-pinned, and
# safe against LIKE metacharacters smuggled in the query string.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_actor_filter_substring_match(client):
    own = await mk_it_workspace()
    other = await mk_it_workspace()

    fatima_id = await _seed_log(
        school_id=own["wsid"], action="auth.login", actor_name="Fatima Al-Zahra",
    )
    farah_id = await _seed_log(
        school_id=own["wsid"], action="auth.login", actor_name="Farah Khan",
    )
    omar_id = await _seed_log(
        school_id=own["wsid"], action="auth.login", actor_name="Omar Said",
    )
    # Same substring in a foreign workspace must NOT leak.
    foreign_fatima = await _seed_log(
        school_id=other["wsid"], action="auth.login", actor_name="Fatima Foreign",
    )

    resp = await client.get(
        "/independent-teacher/audit-logs?actor=fati",
        headers=_it_h(own),
    )
    assert resp.status_code == 200, resp.text
    ids = {r["id"] for r in resp.json()["logs"]}
    assert fatima_id in ids
    assert farah_id not in ids
    assert omar_id not in ids
    assert foreign_fatima not in ids

    # Bare "%" must be treated as a literal — not a wildcard that
    # widens the match back to "all rows".
    pct = await client.get(
        "/independent-teacher/audit-logs?actor=%25",
        headers=_it_h(own),
    )
    assert pct.status_code == 200
    assert pct.json()["logs"] == []

    # Whitespace-only filter is a no-op (returns all own-workspace rows).
    blank = await client.get(
        "/independent-teacher/audit-logs?actor=%20%20",
        headers=_it_h(own),
    )
    assert blank.status_code == 200
    blank_ids = {r["id"] for r in blank.json()["logs"]}
    assert fatima_id in blank_ids and farah_id in blank_ids and omar_id in blank_ids


# ----------------------------------------------------------------------
# (h) Task #255 — CSV export pins workspace, strips sensitive keys,
# honours filters, and refuses non-IT callers.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_export_csv_returns_only_own_rows_and_strips_sensitive(client):
    own = await mk_it_workspace()
    other = await mk_it_workspace()

    own_login = await _seed_log(
        school_id=own["wsid"], action="auth.login",
    )
    own_export = await _seed_log(
        school_id=own["wsid"],
        action="INDEPENDENT_TEACHER_EXPORT",
        details={
            "school_id": own["wsid"],
            "ttl_hours": 24,
            # Sensitive — must be stripped from the CSV cell too.
            "token_hash": "secret-abc",
            "password": "p@ss",
            "email": "leak@example.com",
        },
    )
    foreign = await _seed_log(
        school_id=other["wsid"], action="auth.login",
    )

    resp = await client.get(
        "/independent-teacher/audit-logs/export.csv",
        headers=_it_h(own),
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers.get("content-disposition", "")

    body = resp.content.decode("utf-8-sig")
    lines = body.splitlines()
    assert lines, body
    header = lines[0].split(",")
    assert header[0] == "id"
    assert "category" in header
    assert "details" in header

    assert own_login in body
    assert own_export in body
    # Cross-workspace row must not leak into the export.
    assert foreign not in body
    # Sensitive keys must not appear anywhere in the CSV payload.
    for forbidden in ("token_hash", "secret-abc", "password", "p@ss",
                      "leak@example.com"):
        assert forbidden not in body, forbidden


@pytest.mark.asyncio
async def test_export_csv_honours_category_filter(client):
    own = await mk_it_workspace()
    auth_id = await _seed_log(school_id=own["wsid"], action="auth.login")
    write_id = await _seed_log(
        school_id=own["wsid"], action="academic.grade_recorded",
    )

    resp = await client.get(
        "/independent-teacher/audit-logs/export.csv?category=auth",
        headers=_it_h(own),
    )
    assert resp.status_code == 200, resp.text
    body = resp.content.decode("utf-8-sig")
    assert auth_id in body
    assert write_id not in body


@pytest.mark.asyncio
async def test_export_csv_caps_very_large_workspaces(client, monkeypatch):
    """Task #265 — when a workspace's filtered history exceeds the
    server-side export cap, the endpoint MUST refuse with 413 + a safe
    Arabic message (never quietly truncate, never time out trying to
    materialise the whole result set in memory).

    We monkeypatch the cap to a tiny value so the test is fast.
    """
    from routes import independent_teacher_audit_routes as audit_mod

    monkeypatch.setattr(audit_mod, "_MAX_EXPORT_ROWS", 3)

    own = await mk_it_workspace()
    # Seed cap+1 rows so the over-fetch (cap+1 select limit) trips the
    # "too large" guard.
    for _ in range(4):
        await _seed_log(school_id=own["wsid"], action="auth.login")

    resp = await client.get(
        "/independent-teacher/audit-logs/export.csv",
        headers=_it_h(own),
    )
    assert resp.status_code == 413, resp.text
    body = resp.json()
    # Custom envelope: ``error.message`` carries the safe Arabic copy.
    msg = (body.get("error") or {}).get("message", "")
    assert "النطاق" in msg and "from/to" in msg, body

    # And the cap is inclusive: exactly cap rows must still succeed.
    own2 = await mk_it_workspace()
    for _ in range(3):
        await _seed_log(school_id=own2["wsid"], action="auth.login")
    ok = await client.get(
        "/independent-teacher/audit-logs/export.csv",
        headers=_it_h(own2),
    )
    assert ok.status_code == 200, ok.text
    # Header row + 3 data rows.
    lines = ok.content.decode("utf-8-sig").splitlines()
    assert len(lines) == 4, lines


@pytest.mark.asyncio
async def test_export_csv_non_it_role_is_forbidden(client):
    own = await mk_it_workspace()
    await _seed_log(school_id=own["wsid"], action="auth.login")

    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": "S", "code": f"S{sid[:8]}",
        "status": "active", "country": "SA", "language": "ar",
    })
    p_uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": p_uid, "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": sid, "email": f"p-{p_uid}@t.test",
        "full_name": "P", "is_active": True, "password_hash": "x",
    })
    p_h = headers(p_uid, UserRole.SCHOOL_PRINCIPAL.value, sid)

    r = await client.get(
        "/independent-teacher/audit-logs/export.csv", headers=p_h,
    )
    assert r.status_code == 403
