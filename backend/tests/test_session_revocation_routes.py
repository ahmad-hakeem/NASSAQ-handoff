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


async def _login(client, email: str, password: str) -> dict:
    """POST /auth/login and return the parsed token body.

    Asserts a normal token issuance (no MFA challenge) so the test fails
    loudly if the role we picked happens to fall under an MFA tier in
    some future config change.
    """
    r = await client.post(
        "/auth/login", json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("access_token"), (
        f"expected access_token in /auth/login response, got: {body}"
    )
    assert body.get("refresh_token"), (
        f"expected refresh_token in /auth/login response, got: {body}"
    )
    return body


async def _student_with_password(tenant_id: str, password: str) -> dict:
    """Insert a STUDENT user with a real bcrypt password hash so it can
    actually sign in via /auth/login (the conftest helper stores
    ``password_hash="x"`` which fails ``verify_password``).

    STUDENT is chosen because it sits outside the MFA tier policy, so
    /auth/login returns real tokens and the session-revoke routes'
    ``require_recent_mfa()`` gate is a no-op — the same reason
    ``test_delete_session_revokes_access_and_refresh`` above uses STUDENT.
    """
    from dependencies import hash_password
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.STUDENT.value,
        "tenant_id": tenant_id,
        "email": f"twobrowser-{uid}@example.com",
        "full_name": "Two Browser Student",
        "is_active": True,
        "password_hash": hash_password(password),
    }
    await gd_insert(db.session, "users", user)
    return user


async def test_two_browser_login_then_end_other_blocks_refresh_and_authed_calls(
    client, tenant_a
):
    """Task #375 — full two-browser end-to-end regression.

    Simulates the exact scenario Task #374 fixed: the same user signs in
    on Browser A and Browser B (two independent /auth/login calls →
    independent access+refresh pairs and independent ``user_sessions``
    rows). Browser A then ends Browser B's session via the real
    ``DELETE /settings/sessions/{id}`` route after discovering the id
    through ``GET /settings/sessions``.

    After the revoke we assert BOTH halves of the original bug:

      * Browser B's next ``/auth/refresh`` is rejected (401) — the bug
        Task #374 fixed (refresh token used to silently re-authenticate
        within ~15 minutes).
      * Browser B's still-non-expired access token can no longer be used
        to call an authenticated endpoint (``/auth/me``) — proves the
        access JTI is in ``revoked_tokens`` too, so the device is
        immediately locked out, not merely on its next refresh.

    And, critically, Browser A's own session keeps working — both
    ``/auth/refresh`` and ``/auth/me``.
    """
    password = "Stud3nt!Pass-" + uuid.uuid4().hex[:8]
    user = await _student_with_password(tenant_a, password)

    # Two independent logins == two simulated browsers.
    a = await _login(client, user["email"], password)
    b = await _login(client, user["email"], password)

    a_access = a["access_token"]
    b_access = b["access_token"]
    b_refresh = b["refresh_token"]
    a_refresh = a["refresh_token"]

    # Browser A discovers Browser B's session id via the real list
    # endpoint, the same way the Settings UI does it. We MUST NOT take
    # the id from a backdoor lookup — the id round-trip is part of the
    # flow we are regression-guarding.
    list_resp = await client.get(
        "/settings/sessions",
        headers={"Authorization": f"Bearer {a_access}"},
    )
    assert list_resp.status_code == 200, list_resp.text
    sessions = list_resp.json().get("sessions", [])
    assert len(sessions) >= 2, (
        f"expected at least 2 active sessions for the user after two "
        f"logins, got {len(sessions)}: {sessions}"
    )
    other_ids = [s["id"] for s in sessions if not s.get("is_current")]
    assert other_ids, (
        f"GET /settings/sessions did not flag any session as non-current "
        f"for Browser A; sessions={sessions}"
    )
    # Pick the non-current session that corresponds to Browser B. There
    # should be exactly one, but tolerate >1 by ending all of them via
    # the same path the UI would.
    target_id = other_ids[0]

    r = await client.delete(
        f"/settings/sessions/{target_id}",
        headers={"Authorization": f"Bearer {a_access}"},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("was_current") is False

    # Browser B's refresh MUST be rejected — the Task #374 bug.
    rb_refresh = await client.post(
        "/auth/refresh", json={"refresh_token": b_refresh},
    )
    assert rb_refresh.status_code == 401, (
        f"Browser B's refresh must be 401 after Browser A ends its "
        f"session, got {rb_refresh.status_code}: {rb_refresh.text[:200]}"
    )

    # Browser B's still-non-expired access token MUST also be rejected
    # on any authenticated call. /auth/me is the lightest such call.
    rb_me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {b_access}"},
    )
    assert rb_me.status_code == 401, (
        f"Browser B's access token must be 401 after its session is "
        f"ended, got {rb_me.status_code}: {rb_me.text[:200]}"
    )

    # Browser A is unaffected — both refresh and authed calls still work.
    ra_me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {a_access}"},
    )
    assert ra_me.status_code == 200, (
        f"Browser A's session must survive ending Browser B, got "
        f"{ra_me.status_code}: {ra_me.text[:200]}"
    )
    ra_refresh = await client.post(
        "/auth/refresh", json={"refresh_token": a_refresh},
    )
    assert ra_refresh.status_code == 200, (
        f"Browser A's refresh must survive ending Browser B, got "
        f"{ra_refresh.status_code}: {ra_refresh.text[:200]}"
    )


async def test_two_browser_login_then_end_all_blocks_others_only(
    client, tenant_a
):
    """Task #375 — full end-to-end regression for ``end-all``.

    Three independent ``/auth/login`` calls (Browser A is the caller;
    B and C are "other devices"). ``POST /settings/sessions/end-all``
    from A MUST:

      * Reject Browser B and Browser C on both ``/auth/refresh`` AND any
        authenticated call (their access JTIs and refresh JTIs/families
        are revoked together — the Task #374 fix).
      * Leave Browser A's own refresh + authed calls fully working.
    """
    password = "Stud3nt!Pass-" + uuid.uuid4().hex[:8]
    user = await _student_with_password(tenant_a, password)

    a = await _login(client, user["email"], password)
    b = await _login(client, user["email"], password)
    c = await _login(client, user["email"], password)

    r = await client.post(
        "/settings/sessions/end-all",
        headers={"Authorization": f"Bearer {a['access_token']}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert body.get("ended", 0) >= 2, (
        f"end-all should have ended at least 2 other sessions, got "
        f"{body.get('ended')}"
    )

    for label, other in (("B", b), ("C", c)):
        rr = await client.post(
            "/auth/refresh", json={"refresh_token": other["refresh_token"]},
        )
        assert rr.status_code == 401, (
            f"Browser {label}'s refresh must be 401 after end-all, got "
            f"{rr.status_code}: {rr.text[:200]}"
        )
        rm = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {other['access_token']}"},
        )
        assert rm.status_code == 401, (
            f"Browser {label}'s access token must be 401 after end-all, "
            f"got {rm.status_code}: {rm.text[:200]}"
        )

    # Browser A (the caller) keeps working on both surfaces.
    ra_me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {a['access_token']}"},
    )
    assert ra_me.status_code == 200, (
        f"Browser A's access token must survive end-all, got "
        f"{ra_me.status_code}: {ra_me.text[:200]}"
    )
    ra_refresh = await client.post(
        "/auth/refresh", json={"refresh_token": a["refresh_token"]},
    )
    assert ra_refresh.status_code == 200, (
        f"Browser A's refresh must survive end-all, got "
        f"{ra_refresh.status_code}: {ra_refresh.text[:200]}"
    )


async def test_two_browser_end_other_revokes_whole_refresh_family(
    client, tenant_a
):
    """Task #375 follow-up — explicit family-chain assertion.

    The Task #374 helper revokes the session's ``refresh_jti`` AND its
    ``refresh_family_id`` so any sibling refresh token already spawned
    from the same lineage (e.g. via a normal rotation that happened
    between login and revoke) is also blocked. The earlier two-browser
    test only proves the rejection of the LAST refresh token; it does
    not prove that an EARLIER, already-rotated sibling is rejected too.

    This test rotates Browser B's refresh once (so we now hold an
    "old" and a "new" refresh token in the same family), then ends
    Browser B from Browser A, and asserts BOTH refresh tokens are
    rejected. The old token's JTI is no longer the one persisted on the
    user_sessions row, so the only thing that can block it is the
    family-id revocation — that's what we're regression-guarding.
    """
    password = "Stud3nt!Pass-" + uuid.uuid4().hex[:8]
    user = await _student_with_password(tenant_a, password)

    a = await _login(client, user["email"], password)
    b = await _login(client, user["email"], password)
    b_refresh_old = b["refresh_token"]

    # Rotate Browser B's refresh once. The new refresh token shares
    # ``fid`` with the old one but carries a different ``jti``.
    rotate = await client.post(
        "/auth/refresh", json={"refresh_token": b_refresh_old},
    )
    assert rotate.status_code == 200, rotate.text
    b_refresh_new = rotate.json()["refresh_token"]

    # Browser A discovers the (still single) Browser B session row and
    # ends it. The user_sessions.refresh_jti now matches b_refresh_new,
    # NOT b_refresh_old.
    list_resp = await client.get(
        "/settings/sessions",
        headers={"Authorization": f"Bearer {a['access_token']}"},
    )
    assert list_resp.status_code == 200, list_resp.text
    other_ids = [
        s["id"] for s in list_resp.json().get("sessions", [])
        if not s.get("is_current")
    ]
    assert other_ids, "expected at least one non-current session for A"

    r = await client.delete(
        f"/settings/sessions/{other_ids[0]}",
        headers={"Authorization": f"Bearer {a['access_token']}"},
    )
    assert r.status_code == 200, r.text

    # Sanity: the LATEST refresh is rejected (per-jti revocation path).
    rr_new = await client.post(
        "/auth/refresh", json={"refresh_token": b_refresh_new},
    )
    assert rr_new.status_code == 401, (
        f"rotated refresh must be 401 after revoke, got "
        f"{rr_new.status_code}: {rr_new.text[:200]}"
    )

    # The CRITICAL assertion: the OLD, already-rotated sibling refresh
    # is rejected too. Its jti is NOT on the user_sessions row any more,
    # so only the family-id revocation can block it.
    rr_old = await client.post(
        "/auth/refresh", json={"refresh_token": b_refresh_old},
    )
    assert rr_old.status_code == 401, (
        f"already-rotated sibling refresh must also be 401 (refresh "
        f"family must be revoked, not just the latest jti); got "
        f"{rr_old.status_code}: {rr_old.text[:200]}"
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
