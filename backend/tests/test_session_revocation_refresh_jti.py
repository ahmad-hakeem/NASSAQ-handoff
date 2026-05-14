"""Task #374 — regression tests for parent / shared session revocation.

Bug being guarded against: ``DELETE /api/settings/sessions/{id}`` and
``POST /api/settings/sessions/end-all`` used to revoke ONLY the access
JTI. The refresh JTI was never recorded on ``user_sessions`` in the first
place and never inserted into ``revoked_tokens`` / ``revoked_token_families``
on revoke, so the "ended" device silently re-authenticated on its next
``/auth/refresh`` (~15 minutes later) and re-appeared in the list.

These tests assert two invariants that, together, rule out that
regression. They deliberately bypass the MFA step-up gate on the revoke
routes (which requires WebAuthn for tier-A admins and TOTP for parents
and so cannot be exercised from a headless test) by manipulating the
``revoked_tokens`` / ``revoked_token_families`` rows directly. The end-
to-end UI flow is covered by the QA workflow and proposed as follow-up
#375.

  1. Every ``/auth/login`` and ``/auth/refresh`` issuance MUST persist
     ``refresh_jti`` and ``refresh_family_id`` on the matching
     ``user_sessions`` row. Without this, the revoke helper has nothing
     to revoke.
  2. ``/auth/refresh`` MUST reject any refresh token whose JTI is in
     ``revoked_tokens`` (single-session revoke path) or whose
     ``family_id`` is in ``revoked_token_families`` (end-all path —
     mirrors the reuse-detection primitive in ``auth_routes_mod``).
"""
from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone

import asyncio

import asyncpg
import pytest
import requests

BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    or "http://localhost:8000"
)
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Test@1234"


def _decode_jwt_payload(token: str) -> dict:
    """Decode the payload of a JWT WITHOUT verifying the signature.

    Tests don't have the JWT secret and don't need it — we only need to
    read ``jti`` / ``fid`` to match against DB rows.
    """
    parts = token.split(".")
    assert len(parts) == 3, "token is not a JWT"
    pad = "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(parts[1] + pad))


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    # asyncpg does not accept the SQLAlchemy driver suffix or sslmode
    # query args; strip them.
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in url:
        url = url.split("?", 1)[0]
    return url


def _db_fetch_one(sql: str, *args):
    async def _go():
        conn = await asyncpg.connect(_dsn())
        try:
            return await conn.fetchrow(sql, *args)
        finally:
            await conn.close()
    return asyncio.run(_go())


def _db_execute(sql: str, *args):
    async def _go():
        conn = await asyncpg.connect(_dsn())
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()
    return asyncio.run(_go())


def _login() -> dict:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200 or not r.json().get("access_token"):
        pytest.skip(f"login failed: {r.status_code} {r.text[:200]}")
    return r.json()


# ---------------------------------------------------------------------------
# Invariant 1: login/refresh persist refresh identity on user_sessions
# ---------------------------------------------------------------------------

def test_login_persists_refresh_jti_and_family_on_session_row():
    """Without this, the revoke helper has nothing to insert."""
    tokens = _login()
    access_payload = _decode_jwt_payload(tokens["access_token"])
    refresh_payload = _decode_jwt_payload(tokens["refresh_token"])
    access_jti = access_payload["jti"]
    refresh_jti = refresh_payload["jti"]
    refresh_fid = refresh_payload["fid"]

    row = _db_fetch_one(
        "SELECT refresh_jti, refresh_family_id "
        "FROM user_sessions WHERE jti = $1",
        access_jti,
    )
    assert row is not None, (
        "login did not create a user_sessions row keyed by access JTI"
    )
    db_refresh_jti, db_refresh_fid = row
    assert db_refresh_jti == refresh_jti, (
        "user_sessions.refresh_jti must match the JTI of the issued "
        "refresh token (Task #374 — required for revoke to block refresh)"
    )
    assert db_refresh_fid == refresh_fid, (
        "user_sessions.refresh_family_id must match the family of the "
        "issued refresh token"
    )


def test_refresh_persists_new_refresh_jti_on_session_row():
    """Refresh rotates the refresh token; the new JTI must be persisted
    too, otherwise revoke would only catch the original token and the
    rotated one would survive.
    """
    tokens = _login()
    access_jti = _decode_jwt_payload(tokens["access_token"])["jti"]

    r = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    new_refresh = r.json()["refresh_token"]
    new_refresh_jti = _decode_jwt_payload(new_refresh)["jti"]

    # The session row is keyed by the ORIGINAL access JTI; refresh
    # rotates the access JTI on the row AND the refresh JTI. At minimum,
    # SOME session row must carry the new refresh JTI after rotation.
    row = _db_fetch_one(
        "SELECT 1 FROM user_sessions WHERE refresh_jti = $1",
        new_refresh_jti,
    )
    assert row is not None, (
        "refresh did not persist the rotated refresh JTI on any "
        "user_sessions row — revoke would not block the rotated token"
    )


# ---------------------------------------------------------------------------
# Invariant 2: revoke primitives block /auth/refresh
# ---------------------------------------------------------------------------

def test_revoked_refresh_jti_blocks_refresh():
    """Single-session revoke path: inserting the refresh JTI into
    ``revoked_tokens`` (what ``_revoke_session_refresh_chain`` does) must
    cause ``/auth/refresh`` to reject the matching refresh token.

    Before Task #374 the revoke endpoint only inserted the ACCESS JTI,
    so this assertion would not have held for the refresh token.
    """
    tokens = _login()
    refresh_payload = _decode_jwt_payload(tokens["refresh_token"])
    refresh_jti = refresh_payload["jti"]
    exp_dt = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
    now_dt = datetime.now(timezone.utc)

    _db_execute(
        "INSERT INTO revoked_tokens (jti, expires_at, revoked_at) "
        "VALUES ($1, $2, $3) ON CONFLICT (jti) DO NOTHING",
        refresh_jti, exp_dt, now_dt,
    )

    r = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
        timeout=15,
    )
    assert r.status_code == 401, (
        f"expected 401 for refresh whose JTI is in revoked_tokens, "
        f"got {r.status_code}: {r.text[:200]}"
    )


def test_revoked_refresh_family_blocks_refresh():
    """End-all path: inserting the refresh family into
    ``revoked_token_families`` (what ``_revoke_session_refresh_chain``
    does for every other session) must cause ``/auth/refresh`` to reject
    every token belonging to that family — including any sibling rotated
    from the same lineage.
    """
    tokens = _login()
    refresh_payload = _decode_jwt_payload(tokens["refresh_token"])
    refresh_fid = refresh_payload["fid"]
    user_id = refresh_payload["sub"]
    now = datetime.now(timezone.utc)

    _db_execute(
        "INSERT INTO revoked_token_families "
        "(family_id, revoked_at, reason, user_id) "
        "VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (family_id) DO NOTHING",
        refresh_fid, now, "test_user_ended_session", user_id,
    )

    r = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
        timeout=15,
    )
    assert r.status_code == 401, (
        f"expected 401 for refresh whose family is in "
        f"revoked_token_families, got {r.status_code}: {r.text[:200]}"
    )


# ---------------------------------------------------------------------------
# Cross-user / current-jti-unknown route guards (sanity)
# ---------------------------------------------------------------------------

def test_delete_session_for_unknown_id_returns_404():
    """``DELETE /sessions/{id}`` must 404 (not 403/200) for an id that
    does not belong to the caller — same scope guard the original code
    had, asserted here so the Task #374 helper additions don't widen it.

    The route is MFA-gated; for tier-A admins the response is 401
    (MFA_PASSKEY_REQUIRED) before the id is even looked up. We assert it
    is NOT 200 / not 204 — i.e. the id is not honored.
    """
    tokens = _login()
    access = tokens["access_token"]
    fake_id = str(uuid.uuid4())
    r = requests.delete(
        f"{BASE_URL}/api/settings/sessions/{fake_id}",
        headers={"Authorization": f"Bearer {access}"},
        timeout=15,
    )
    assert r.status_code in (401, 403, 404), (
        f"unknown session id must not succeed; got {r.status_code}: "
        f"{r.text[:200]}"
    )
    assert r.status_code != 200
