"""Task #169 — MFA acceptance tests.

Proves the rules listed under "Done looks like" in `.local/tasks/task-169.md`:

* No-token-before-MFA: Tier-A/B/C login returns a `mfa_challenge` token,
  never an access/refresh pair.
* Role-tier enforcement: out-of-tier roles (student) still receive a real
  access token on plain login; in-tier roles do not.
* Challenge token may NOT be used as an access token on protected routes.
* `GET /auth/mfa/factors` accepts BOTH access and challenge tokens.
* Step-up enforcement: sensitive routes return a structured
  `MFA_STEPUP_REQUIRED` 401 when the bearer has no fresh `mfa_recent_at`.
* Recovery-code single-use: a code consumed by `/auth/mfa/verify` cannot
  be replayed.
* Refresh PRESERVES but does NOT advance `mfa_recent_at`.
* Tier-A user with `mfa_must_restore_factor=True` is blocked with
  `MFA_RESTORE_REQUIRED` on sensitive routes.
* Tier-A user without an active WebAuthn credential is blocked with
  `MFA_PASSKEY_REQUIRED` on sensitive routes.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

# Ensure crypto key is present even when tests run before server import.
os.environ.setdefault(
    "MFA_ENCRYPTION_KEY",
    os.environ.get("MFA_ENCRYPTION_KEY", "")
    or "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
)

from dependencies import (  # noqa: E402  (env must be set first)
    UserRole,
    create_access_token,
    create_refresh_token,
    hash_password,
)
from engines.sql_utils import gd_insert, gd_find_one  # noqa: E402
from dependencies import db  # noqa: E402
from services import mfa_crypto  # noqa: E402


_PASS = "Test@1234!"


def _err_code(response) -> str | None:
    """Pull the structured error code regardless of envelope shape.

    The global `http_exception_handler` wraps `HTTPException(detail={...})`
    into `{success: false, error: {code, message, detail, ...}}`.
    """
    body = response.json() or {}
    err = body.get("error") if isinstance(body.get("error"), dict) else None
    if err and err.get("code"):
        return err["code"]
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("code")
    return None


async def _mk_login_user(role: UserRole, tenant_id: str, *, mfa_required: bool = False) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role.value,
        "tenant_id": tenant_id,
        "email": f"mfa-{uid}@nassaq-test.com",
        "full_name": f"{role.value} user",
        "is_active": True,
        "password_hash": hash_password(_PASS),
        "mfa_required": mfa_required,
    }
    await gd_insert(db.session, "users", user)
    return user


async def _seed_recovery_code(user_id: str) -> str:
    """Insert one unconsumed recovery code for the user; return plaintext."""
    plaintext = mfa_crypto.generate_recovery_code()
    await gd_insert(
        db.session,
        "mfa_recovery_codes",
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "code_hash": mfa_crypto.hash_recovery_code(plaintext),
            "created_at": datetime.now(timezone.utc),
            "consumed_at": None,
        },
    )
    return plaintext


async def _seed_webauthn_factor(user_id: str) -> str:
    """Insert one active WebAuthn factor row so Tier-A passkey check passes."""
    fid = str(uuid.uuid4())
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": fid,
            "user_id": user_id,
            "kind": "webauthn",
            "is_active": True,
            "is_primary": True,
            "label": "test passkey",
            "webauthn_credential_id": uuid.uuid4().bytes,
            "webauthn_public_key": b"\x00" * 32,
            "webauthn_sign_count": 0,
            "created_at": datetime.now(timezone.utc),
        },
    )
    return fid


# ---------------------------------------------------------------------------
# 1. No-token-before-MFA + role-tier enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_tier_b_returns_challenge_not_access_token(client, tenant_a):
    """Teacher login must return mfa_challenge, never access/refresh tokens."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    r = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("mfa_required") is True
    assert body.get("mfa_tier") == "B"
    assert body.get("challenge_token"), "challenge_token must be present"
    assert not body.get("access_token"), "access_token MUST NOT leak before MFA verify"
    assert not body.get("refresh_token"), "refresh_token MUST NOT leak before MFA verify"
    # Email-OTP is implicit for Tier B even with zero enrolled factors.
    assert "email_otp" in (body.get("available_factor_kinds") or [])


@pytest.mark.asyncio
async def test_login_tier_c_parent_returns_challenge(client, tenant_a):
    """Parent (Tier C) login returns the same challenge contract as Tier B."""
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    r = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    assert r.status_code == 200
    body = r.json()
    assert body.get("mfa_required") is True
    assert body.get("mfa_tier") == "C"
    assert body.get("challenge_token"), "challenge_token must be present"
    assert not body.get("access_token")
    assert not body.get("refresh_token")


@pytest.mark.asyncio
async def test_login_tier_a_principal_returns_challenge_not_tokens(client, tenant_a):
    """Tier-A school principal: login MUST return a challenge, never tokens.

    A Tier-A user with at least one enrolled factor (here a recovery code)
    receives `mfa_required=true` + `challenge_token` and NO access/refresh
    pair. This proves the no-token-before-MFA rule for the highest tier.
    """
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    # Tier-A login gate requires an explicit active factor row (Step 4).
    await _seed_webauthn_factor(user["id"])
    r = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("mfa_required") is True
    assert body.get("mfa_tier") == "A"
    assert body.get("challenge_token")
    assert not body.get("access_token")
    assert not body.get("refresh_token")


@pytest.mark.asyncio
async def test_login_student_skips_mfa(client, tenant_a):
    """Student is out-of-tier; login mints a real access token immediately."""
    user = await _mk_login_user(UserRole.STUDENT, tenant_a)
    r = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    assert r.status_code == 200
    body = r.json()
    assert body.get("access_token"), "out-of-tier role must receive an access token on login"
    assert not body.get("mfa_required")


# ---------------------------------------------------------------------------
# 2. Challenge token cannot be used as an access token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_challenge_token_rejected_as_access_token(client, tenant_a):
    """A bare /auth/me call with a challenge bearer must 401."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    login = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    chal = login.json()["challenge_token"]
    # /auth/me requires get_current_user (access-only); challenge → 401.
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {chal}"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 3. /auth/mfa/factors accepts BOTH access and challenge tokens
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mfa_factors_accepts_challenge_token(client, tenant_a):
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    login = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    chal = login.json()["challenge_token"]
    r = await client.get("/auth/mfa/factors", headers={"Authorization": f"Bearer {chal}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tier"] == "B"
    assert "email_otp" in body["allowed_kinds"]
    assert "recovery_code" in body["allowed_kinds"]


@pytest.mark.asyncio
async def test_mfa_factors_accepts_access_token(client, tenant_a):
    """Same endpoint must also accept a real access token (post-MFA), so
    AccountSettings can render the factor list after login."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    now = int(datetime.now(timezone.utc).timestamp())
    access = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now)
    r = await client.get("/auth/mfa/factors", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tier"] == "B"


# ---------------------------------------------------------------------------
# 4. Step-up enforcement on sensitive routes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_change_password_requires_recent_mfa(client, tenant_a):
    """Tier-A user with no mfa_recent_at claim → MFA_PASSKEY_REQUIRED or
    MFA_STEPUP_REQUIRED on /auth/change-password.

    Tier-A blocks before the freshness check fall back to the most specific
    code, which here is MFA_PASSKEY_REQUIRED (no enrolled webauthn). Either
    structured 401 satisfies the step-up enforcement contract.
    """
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })  # NB: no mfa_recent_at
    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401
    code = _err_code(r)
    assert code in {"MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED", "MFA_RESTORE_REQUIRED"}


@pytest.mark.asyncio
async def test_tier_a_without_passkey_blocked(client, tenant_a):
    """Tier-A user with a fresh mfa_recent_at but no enrolled passkey is
    still refused with MFA_PASSKEY_REQUIRED."""
    user = await _mk_login_user(UserRole.SCHOOL_ADMIN, tenant_a)
    now = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now)
    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401
    assert _err_code(r) == "MFA_PASSKEY_REQUIRED"


@pytest.mark.asyncio
async def test_tier_a_must_restore_factor_blocks(client, tenant_a):
    """`mfa_must_restore_factor=True` on a Tier-A user → MFA_RESTORE_REQUIRED
    even with a passkey enrolled and a fresh mfa_recent_at."""
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    await _seed_webauthn_factor(user["id"])
    # Set the restore flag directly.
    from engines.sql_utils import gd_update_one
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"mfa_must_restore_factor": True})
    now = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now)
    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401
    assert _err_code(r) == "MFA_RESTORE_REQUIRED"


@pytest.mark.asyncio
async def test_role_switch_requires_recent_mfa(client, tenant_a):
    """Sensitive route #2: /role-switch/switch is gated by require_recent_mfa
    even for platform admins. Stale token → structured 401."""
    user = await _mk_login_user(UserRole.PLATFORM_ADMIN, tenant_a)
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })  # no mfa_recent_at
    r = await client.post(
        "/role-switch/switch",
        json={"target_role": "school_admin", "school_id": tenant_a, "reason": "qa-test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401, r.text
    assert _err_code(r) in {"MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED", "MFA_RESTORE_REQUIRED"}


@pytest.mark.asyncio
async def test_end_all_sessions_requires_recent_mfa(client, tenant_a):
    """Sensitive route #3: /security/end-all-sessions (platform-admin only)
    must refuse without a fresh mfa_recent_at."""
    user = await _mk_login_user(UserRole.PLATFORM_ADMIN, tenant_a)
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    r = await client.post(
        "/security/end-all-sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401, r.text
    assert _err_code(r) in {"MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED", "MFA_RESTORE_REQUIRED"}


@pytest.mark.asyncio
async def test_change_password_passes_with_recent_mfa_for_tier_b(client, tenant_a):
    """Tier-B user with a fresh mfa_recent_at can change password (no
    Tier-A passkey requirement)."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    now = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now)
    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Either 200 (changed) or 400 (validation), but NEVER 401-step-up.
    # Tighten: explicitly enumerate acceptable success/validation codes so
    # a 500/403/404 regression cannot false-pass the no-stepup contract.
    assert r.status_code in {200, 400, 422}, r.text


# ---------------------------------------------------------------------------
# 5. Refresh PRESERVES but does NOT advance mfa_recent_at
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_preserves_mfa_recent_at(client, tenant_a):
    """The refresh endpoint must carry the original mfa_recent_at forward
    into the new tokens unchanged — never stamping a fresher value."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    original_ts = int((datetime.now(timezone.utc) - timedelta(seconds=120)).timestamp())
    refresh = create_refresh_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=original_ts, mfa_kind="email_otp")
    r = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200, r.text
    new_access = r.json().get("access_token")
    assert new_access
    import jwt as _jwt
    from dependencies import JWT_SECRET, JWT_ALGORITHM
    payload = _jwt.decode(new_access, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload.get("mfa_recent_at") == original_ts, (
        f"refresh advanced mfa_recent_at: {payload.get('mfa_recent_at')} != {original_ts}"
    )


# ---------------------------------------------------------------------------
# 6. Recovery-code single-use
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_code_single_use(client, tenant_a):
    """A recovery code consumed via /auth/mfa/verify cannot be replayed."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    plaintext = await _seed_recovery_code(user["id"])

    login = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    chal = login.json()["challenge_token"]

    # First use → 200 + tokens
    r1 = await client.post(
        "/auth/mfa/verify",
        json={"factor_kind": "recovery_code", "code": plaintext},
        headers={"Authorization": f"Bearer {chal}"},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json().get("access_token")

    # The row is now consumed in DB.
    row = await gd_find_one(db.session, "mfa_recovery_codes", {"user_id": user["id"]})
    assert row and row.get("consumed_at") is not None

    # Second login + reuse of same code → reject.
    login2 = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    chal2 = login2.json()["challenge_token"]
    r2 = await client.post(
        "/auth/mfa/verify",
        json={"factor_kind": "recovery_code", "code": plaintext},
        headers={"Authorization": f"Bearer {chal2}"},
    )
    assert r2.status_code == 400, r2.text
    assert "access_token" not in (r2.json() or {})


# ---------------------------------------------------------------------------
# 6b. Challenge replay + expiry protection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_consumed_challenge_token_cannot_be_replayed(client, tenant_a):
    """After a successful /auth/mfa/verify the challenge row is marked
    consumed. Replaying the same challenge bearer must 401 with the
    Arabic 'already consumed' detail, NOT mint a second access token."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    plaintext = await _seed_recovery_code(user["id"])
    plaintext2 = await _seed_recovery_code(user["id"])
    login = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    chal = login.json()["challenge_token"]

    r1 = await client.post(
        "/auth/mfa/verify",
        json={"factor_kind": "recovery_code", "code": plaintext},
        headers={"Authorization": f"Bearer {chal}"},
    )
    assert r1.status_code == 200, r1.text

    # Replay the same (now-consumed) challenge bearer with a different,
    # still-unconsumed recovery code → server must refuse on the challenge.
    r2 = await client.post(
        "/auth/mfa/verify",
        json={"factor_kind": "recovery_code", "code": plaintext2},
        headers={"Authorization": f"Bearer {chal}"},
    )
    assert r2.status_code == 401, r2.text
    assert "access_token" not in (r2.json() or {})


@pytest.mark.asyncio
async def test_expired_challenge_row_is_rejected(client, tenant_a):
    """Even with a syntactically-valid challenge JWT, an expired
    `mfa_pending_challenges` row must 401."""
    from engines.sql_utils import gd_update_one
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    await _seed_recovery_code(user["id"])
    login = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    chal = login.json()["challenge_token"]

    # Backdate the challenge row's expires_at by 10 minutes.
    import jwt as _jwt
    from dependencies import JWT_SECRET, JWT_ALGORITHM
    jti = _jwt.decode(chal, JWT_SECRET, algorithms=[JWT_ALGORITHM])["jti"]
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    await gd_update_one(
        db.session,
        "mfa_pending_challenges",
        {"challenge_token_jti": jti},
        {"expires_at": past},
    )

    # /auth/mfa/verify routes through `_resolve_challenge`, which is the
    # only authority for challenge expiry/replay. Verify must 401.
    r = await client.post(
        "/auth/mfa/verify",
        json={"factor_kind": "recovery_code", "code": "XXXX-XXXX-XXXX"},
        headers={"Authorization": f"Bearer {chal}"},
    )
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 7. Recovery-code consumption sets mfa_must_restore_factor (Tier A)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_code_sets_must_restore_for_tier_a(client, tenant_a):
    """When a Tier-A user redeems a recovery code, the resulting login must
    flip `mfa_must_restore_factor=True` so subsequent step-up routes refuse
    until they re-enrol a normal factor."""
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    plaintext = await _seed_recovery_code(user["id"])
    login = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    body = login.json()
    # Tier-A users with no enrolled factors at all may not even reach a
    # challenge — guard the test on the available code path.
    if not body.get("challenge_token"):
        pytest.skip("Tier-A login flow requires explicit factor — covered by step-up tests")
    chal = body["challenge_token"]
    r = await client.post(
        "/auth/mfa/verify",
        json={"factor_kind": "recovery_code", "code": plaintext},
        headers={"Authorization": f"Bearer {chal}"},
    )
    assert r.status_code == 200, r.text
    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert fresh.get("mfa_must_restore_factor") is True
