"""Task #374 — route-level regression tests for the revoke endpoints.

These tests exercise the actual ``DELETE /settings/sessions/{id}`` and
``POST /settings/sessions/end-all`` HTTP routes (via the ASGI test
client in ``conftest.py``) and prove the full round-trip:

    revoke → revoked_tokens / revoked_token_families populated
          → /auth/refresh rejects the matching refresh token

We use a ``student`` role so the ``require_recent_mfa()`` gate is a
no-op (students sit outside Tier A/B/C in ``services.mfa_policy``); the
revoke logic itself is role-independent — the bug was in the helper, not
in the auth tier.

Companion file: ``test_session_revocation_refresh_jti.py`` covers the
revoke primitives at the DB-layer with a live login (admin) and the
``/auth/refresh`` rejection invariants.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import (
    UserRole,
    create_access_token,
    create_refresh_token,
    db,
)
from engines.sql_utils import gd_find_one, gd_insert
from tests.conftest import _mk_user  # type: ignore


pytestmark = pytest.mark.asyncio


async def _fam_row(family_id: str):
    """``revoked_token_families`` has no ORM model, so ``gd_find_one``
    falls through to the GenericDocument backing store and won't see the
    real-table row inserted by the helper. Query the table directly.
    """
    from sqlalchemy import text as _sa_text
    res = await db.session.execute(
        _sa_text("SELECT family_id FROM revoked_token_families WHERE family_id=:f"),
        {"f": family_id},
    )
    return res.first()


async def _revoked_token_exp(jti: str):
    """Return the ``revoked_tokens.expires_at`` for ``jti`` as a tz-aware
    datetime, or ``None`` if no row exists. Direct SQL because revoked
    rows persisted by the route may carry an ISO string in the column.
    """
    from sqlalchemy import text as _sa_text
    res = await db.session.execute(
        _sa_text("SELECT expires_at FROM revoked_tokens WHERE jti=:j"),
        {"j": jti},
    )
    row = res.first()
    if not row:
        return None
    val = row[0]
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    return val


async def _seed_session(user_id: str, *, mfa_recent: bool = True) -> dict:
    """Mint matched access+refresh tokens and persist a user_sessions row.

    Returns ``{access_token, refresh_token, access_jti, refresh_jti,
    refresh_family_id, session_id}``.
    """
    now = datetime.now(timezone.utc)
    mfa_ts = int(now.timestamp()) if mfa_recent else None
    access_token = create_access_token(
        {"sub": user_id, "role": "student", "tenant_id": None},
        mfa_recent_at=mfa_ts,
    )
    import jwt as _jwt
    from dependencies import JWT_SECRET, JWT_ALGORITHM
    access_payload = _jwt.decode(
        access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM]
    )
    refresh_token = create_refresh_token(
        {"sub": user_id, "role": "student", "tenant_id": None},
        linked_access_jti=access_payload["jti"],
        family_id=str(uuid.uuid4()),
        mfa_recent_at=mfa_ts,
    )
    refresh_payload = _jwt.decode(
        refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM]
    )
    sid = str(uuid.uuid4())
    refresh_exp = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
    await gd_insert(db.session, "user_sessions", {
        "id": sid,
        "user_id": user_id,
        "jti": access_payload["jti"],
        "refresh_jti": refresh_payload["jti"],
        "refresh_family_id": refresh_payload["fid"],
        "refresh_expires_at": refresh_exp,
        "device": "Desktop",
        "browser": "Test",
        "os": "Linux",
        "ip_address": "127.0.0.1",
        "created_at": now,
        "last_seen_at": now,
        "expires_at": now + timedelta(hours=1),
    })
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_jti": access_payload["jti"],
        "refresh_jti": refresh_payload["jti"],
        "refresh_family_id": refresh_payload["fid"],
        "refresh_expires_at": refresh_exp,
        "session_id": sid,
    }


async def test_delete_session_revokes_access_and_refresh(
    client, tenant_a
):
    """``DELETE /settings/sessions/{id}`` MUST insert the OTHER session's
    refresh JTI into ``revoked_tokens`` and its family into
    ``revoked_token_families``. Without that, the device whose session
    was ended would re-authenticate on its next ``/auth/refresh``.
    """
    user = await _mk_user(UserRole.STUDENT, tenant_a)
    current = await _seed_session(user["id"])
    other = await _seed_session(user["id"])

    r = await client.delete(
        f"/settings/sessions/{other['session_id']}",
        headers={"Authorization": f"Bearer {current['access_token']}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert body.get("was_current") is False

    # Refresh JTI for the ended session must be in revoked_tokens.
    revoked_jti_row = await gd_find_one(
        db.session, "revoked_tokens", {"jti": other["refresh_jti"]},
    )
    assert revoked_jti_row is not None, (
        "DELETE /settings/sessions/{id} did not insert the session's "
        "refresh_jti into revoked_tokens — Task #374 regression"
    )

    # Refresh family must be in revoked_token_families.
    fam_row = await _fam_row(other["refresh_family_id"])
    assert fam_row is not None, (
        "DELETE /settings/sessions/{id} did not insert the session's "
        "refresh_family_id into revoked_token_families — Task #374 regression"
    )

    # And /auth/refresh with that token must now fail.
    rr = await client.post(
        "/auth/refresh",
        json={"refresh_token": other["refresh_token"]},
    )
    assert rr.status_code == 401, (
        f"refresh of an ended session must be 401, got {rr.status_code}: "
        f"{rr.text[:200]}"
    )

    # The CURRENT session's refresh token MUST still be honored.
    rc = await client.post(
        "/auth/refresh",
        json={"refresh_token": current["refresh_token"]},
    )
    assert rc.status_code == 200, (
        f"current session refresh must still succeed, got "
        f"{rc.status_code}: {rc.text[:200]}"
    )


async def test_end_all_revokes_others_but_preserves_current(
    client, tenant_a
):
    """``POST /settings/sessions/end-all`` MUST kill every OTHER refresh
    token (jti + family) and leave the caller's own refresh path alive.
    """
    user = await _mk_user(UserRole.STUDENT, tenant_a)
    current = await _seed_session(user["id"])
    other_a = await _seed_session(user["id"])
    other_b = await _seed_session(user["id"])

    r = await client.post(
        "/settings/sessions/end-all",
        headers={"Authorization": f"Bearer {current['access_token']}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert body.get("ended", 0) >= 2

    for other in (other_a, other_b):
        revoked_jti_row = await gd_find_one(
            db.session, "revoked_tokens",
            {"jti": other["refresh_jti"]},
        )
        assert revoked_jti_row is not None, (
            "end-all did not insert the other session's refresh_jti"
        )
        fam_row = await _fam_row(other["refresh_family_id"])
        assert fam_row is not None, (
            "end-all did not insert the other session's refresh_family_id"
        )
        rr = await client.post(
            "/auth/refresh",
            json={"refresh_token": other["refresh_token"]},
        )
        assert rr.status_code == 401, (
            f"refresh of an end-all'd session must be 401, got "
            f"{rr.status_code}: {rr.text[:200]}"
        )

    # The caller's own refresh JTI must NOT be in revoked_tokens at the
    # moment end-all returns. (Check this BEFORE calling /auth/refresh,
    # which would itself rotate the refresh token and insert the old jti
    # into revoked_tokens as part of normal refresh-token rotation.)
    self_revoked = await gd_find_one(
        db.session, "revoked_tokens",
        {"jti": current["refresh_jti"]},
    )
    assert self_revoked is None, (
        "end-all incorrectly revoked the caller's own session"
    )

    # And the caller's own session must still refresh successfully.
    rc = await client.post(
        "/auth/refresh",
        json={"refresh_token": current["refresh_token"]},
    )
    assert rc.status_code == 200, (
        f"caller's own refresh must survive end-all, got "
        f"{rc.status_code}: {rc.text[:200]}"
    )


async def test_revoked_refresh_jti_expiry_outlives_access_token(
    client, tenant_a
):
    """Task #374 follow-up — the ``revoked_tokens.expires_at`` recorded
    by ``DELETE /settings/sessions/{id}`` MUST be the REFRESH token's
    own expiry (days-to-30-days), NOT the access token's ~15-min expiry.

    Why: ``backend/app/lifecycle.py`` periodically purges
    ``revoked_tokens`` rows whose ``expires_at < now``. If the revoked
    refresh JTI was stamped with the access expiry, cleanup would
    delete the revocation hours-to-days BEFORE the refresh token itself
    expired — letting the ended device silently revive on its next
    ``/auth/refresh``. Regression-guards the original review finding.
    """
    user = await _mk_user(UserRole.STUDENT, tenant_a)
    current = await _seed_session(user["id"])
    other = await _seed_session(user["id"])

    r = await client.delete(
        f"/settings/sessions/{other['session_id']}",
        headers={"Authorization": f"Bearer {current['access_token']}"},
    )
    assert r.status_code == 200, r.text

    revoked_exp = await _revoked_token_exp(other["refresh_jti"])
    assert revoked_exp is not None, (
        "DELETE did not record the refresh JTI in revoked_tokens"
    )
    # The recorded expiry MUST match the refresh token's own exp
    # (allow 5s tolerance for clock skew between issuance and now), and
    # MUST be at least many hours past now — proving the cleanup loop
    # cannot purge the revocation while the refresh token is still
    # otherwise valid.
    delta = abs((revoked_exp - other["refresh_expires_at"]).total_seconds())
    assert delta < 5, (
        f"revoked_tokens.expires_at ({revoked_exp}) must equal the "
        f"refresh token's own exp ({other['refresh_expires_at']}); "
        f"delta={delta}s. Using the access token's ~15-min expiry would "
        "let the cleanup loop purge the revocation prematurely."
    )
    horizon = (revoked_exp - datetime.now(timezone.utc)).total_seconds()
    assert horizon > 60 * 60, (
        f"revoked refresh-JTI expiry must outlive the access window; "
        f"got only {horizon}s"
    )


async def test_end_all_without_current_jti_returns_400(
    client, tenant_a
):
    """If the caller's bearer carries a JTI that does not match ANY of
    their ``user_sessions`` rows, ``end-all`` cannot identify the current
    session and MUST fail closed with HTTP 400 — otherwise it would
    silently revoke EVERY session including the caller's.
    """
    user = await _mk_user(UserRole.STUDENT, tenant_a)
    # Mint a token but do NOT insert a matching user_sessions row, so its
    # jti is unknown to the server. The route's guard inspects the BEARER
    # jti, not DB presence — the bearer carries a jti either way — so to
    # actually trigger the 400 path we need the route-internal _jti_from_creds
    # to return None. The route uses HTTPBearer(auto_error=False); calling
    # without an Authorization header would 401 upstream at get_current_user.
    # So we craft a token whose jti is missing — by hand-encoding.
    import jwt as _jwt
    from dependencies import JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "role": "student",
        "tenant_id": None,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE),
        "mfa_recent_at": int(now.timestamp()),
        # no "jti" — _jti_from_creds returns None
    }
    bare_token = _jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    # Seed an OTHER session that would be ended if the guard failed open.
    other = await _seed_session(user["id"])

    r = await client.post(
        "/settings/sessions/end-all",
        headers={"Authorization": f"Bearer {bare_token}"},
    )
    assert r.status_code == 400, (
        f"end-all without an identifiable current jti must 400, got "
        f"{r.status_code}: {r.text[:200]}"
    )

    # And the other session's refresh token MUST still work — proving
    # the guard failed CLOSED (no revocation occurred).
    rr = await client.post(
        "/auth/refresh",
        json={"refresh_token": other["refresh_token"]},
    )
    assert rr.status_code == 200, (
        "end-all must not have revoked anything when current jti is unknown"
    )


async def test_delete_session_for_other_users_id_returns_404(
    client, tenant_a, tenant_b
):
    """Cross-user revocation MUST 404 — not 200, not 403. The route's
    user_id-scoped lookup is the authz boundary; a leak would let a
    student end another user's session.
    """
    me = await _mk_user(UserRole.STUDENT, tenant_a)
    other_user = await _mk_user(UserRole.STUDENT, tenant_b)
    my_session = await _seed_session(me["id"])
    other_session = await _seed_session(other_user["id"])

    r = await client.delete(
        f"/settings/sessions/{other_session['session_id']}",
        headers={"Authorization": f"Bearer {my_session['access_token']}"},
    )
    assert r.status_code == 404, (
        f"cross-user session id MUST 404, got {r.status_code}: "
        f"{r.text[:200]}"
    )

    # Other user's refresh token must STILL work.
    rr = await client.post(
        "/auth/refresh",
        json={"refresh_token": other_session["refresh_token"]},
    )
    assert rr.status_code == 200, (
        "404 path must not have revoked the other user's session"
    )
