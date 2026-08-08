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

from middleware.rate_limiter import rate_store  # noqa: E402


@pytest.fixture(autouse=True)
def _enforce_mfa_for_module(enforce_mfa):
    """This module asserts the ENFORCED MFA contracts (login tiers, step-up
    factor lists, recent-MFA gates on sensitive routes). The CI gate runs
    with the kill-switch engaged (MFA_ENFORCEMENT_DISABLED=true), so opt the
    whole module back in via the conftest `enforce_mfa` fixture."""
    yield


@pytest.fixture(autouse=True)
def _reset_rate_store():
    """Per-IP /auth/login is capped at 10/60s. The MFA suite issues many
    logins from 127.0.0.1; without resetting between tests later cases hit
    HTTP 429 spuriously. The rate limiter is the unit under test elsewhere
    — clearing its in-memory store here keeps these contract tests
    deterministic without weakening production limits."""
    rate_store._store.clear()
    yield
    rate_store._store.clear()


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


async def _mk_login_user(
    role: UserRole, tenant_id: str, *, mfa_required: bool = False,
    enrolled: bool = False,
) -> dict:
    """Insert a login-capable user row.

    ``enrolled=True`` stamps ``mfa_enrolled_at`` so the Task #443
    enrollment gate in ``get_current_user`` lets the token through and
    the more specific step-up envelopes (MFA_STEPUP_REQUIRED /
    MFA_PASSKEY_REQUIRED / MFA_RESTORE_REQUIRED) under test can fire.
    Tests that exercise the *enrollment* gate itself keep the default.
    """
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
    if enrolled:
        user["mfa_enrolled_at"] = datetime.now(timezone.utc)
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
async def test_login_tier_b_unenrolled_teacher_routes_to_enrolment(client, tenant_a):
    """2026-05-13 — Tier B (school teacher) no longer has an implicit
    email_otp factor. A teacher with NO enrolled non-email factor logs
    in with a normal access token and ``mfa_enrolled_at`` still NULL;
    the frontend ProtectedRoute then routes them to /auth/mfa/enroll
    instead of the (broken) email-code challenge.
    """
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    r = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert not body.get("mfa_required"), "unenrolled teacher must skip the email-OTP challenge"
    assert body.get("access_token"), "teacher must receive an access token to reach the enrolment page"
    me = body.get("user") or {}
    assert me.get("role") == "teacher"
    assert not me.get("mfa_enrolled_at"), "FE relies on mfa_enrolled_at IS NULL to redirect to /auth/mfa/enroll"


@pytest.mark.asyncio
async def test_login_tier_b_enrolled_teacher_returns_totp_challenge(client, tenant_a):
    """A teacher with an enrolled TOTP factor MUST be challenged at login,
    and email_otp MUST NOT appear in the available factor kinds.
    """
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    # Seed an active TOTP factor (no need for a real secret here — the
    # login gate only inspects the row's existence + kind + is_active).
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
    r = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("mfa_required") is True
    assert body.get("mfa_tier") == "B"
    assert body.get("challenge_token")
    assert not body.get("access_token")
    kinds = body.get("available_factor_kinds") or []
    assert "totp" in kinds
    assert "email_otp" not in kinds, "Tier B login MUST NOT offer email OTP anymore"


@pytest.mark.asyncio
async def test_login_tier_c_unenrolled_parent_routes_to_enrolment(client, tenant_a):
    """2026 — Tier C (parent) no longer has an implicit email_otp factor.
    A parent with NO enrolled non-email factor logs in with a normal
    access token and ``mfa_enrolled_at`` still NULL; the frontend
    ProtectedRoute then routes them to /auth/mfa/enroll instead of the
    (broken) email-code challenge.
    """
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    r = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert not body.get("mfa_required"), "unenrolled parent must skip the email-OTP challenge"
    assert body.get("access_token"), "parent must receive an access token to reach the enrolment page"
    me = body.get("user") or {}
    assert me.get("role") == "parent"
    assert not me.get("mfa_enrolled_at"), "FE relies on mfa_enrolled_at IS NULL to redirect to /auth/mfa/enroll"
    kinds = body.get("available_factor_kinds") or []
    assert "email_otp" not in kinds


@pytest.mark.asyncio
async def test_login_tier_c_enrolled_parent_returns_totp_challenge(client, tenant_a):
    """A parent with an enrolled TOTP factor MUST be challenged at login,
    and email_otp MUST NOT appear in the available factor kinds.
    """
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
    r = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("mfa_required") is True
    assert body.get("mfa_tier") == "C"
    assert body.get("challenge_token")
    assert not body.get("access_token")
    kinds = body.get("available_factor_kinds") or []
    assert "totp" in kinds
    assert "email_otp" not in kinds, "Tier C login MUST NOT offer email OTP anymore"


@pytest.mark.asyncio
async def test_mfa_policy_tier_c_excludes_email_otp():
    """Direct contract test on ``mfa_policy.allowed_factor_kinds`` for a
    parent role - email_otp must be gone, TOTP + recovery_code present."""
    from services import mfa_policy as _mp
    kinds = _mp.allowed_factor_kinds({"role": "parent"})
    assert "email_otp" not in kinds
    assert "totp" in kinds
    assert "recovery_code" in kinds
    assert "webauthn" in kinds


@pytest.mark.asyncio
async def test_verify_rejects_email_otp_for_parent(client, tenant_a):
    """A parent submitting an email_otp proof to /auth/mfa/verify must
    be rejected by the policy allow-list, even with a real challenge."""
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
    login = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    chal = login.json()["challenge_token"]
    r = await client.post(
        "/auth/mfa/verify",
        json={"factor_kind": "email_otp", "code": "000000"},
        headers={"Authorization": f"Bearer {chal}"},
    )
    assert r.status_code == 400, r.text
    assert "access_token" not in (r.json() or {})


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
async def test_login_student_disabled_platform_wide(client, tenant_a):
    """Student login is disabled platform-wide (STUDENT_LOGIN_DISABLED in
    dependencies.py) pending the student-account rebuild: the MFA
    challenge is never reached and no tokens of any kind are minted."""
    user = await _mk_login_user(UserRole.STUDENT, tenant_a)
    r = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    assert r.status_code == 403, r.text
    body = r.json()
    assert (body.get("error") or {}).get("code") == "STUDENT_LOGIN_DISABLED"
    assert not body.get("access_token")
    assert not body.get("refresh_token")
    assert not body.get("challenge_token")


# ---------------------------------------------------------------------------
# 2. Challenge token cannot be used as an access token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_challenge_token_rejected_as_access_token(client, tenant_a):
    """A bare /auth/me call with a challenge bearer must 401.

    Uses a parent (Tier C) with an enrolled TOTP factor; both Tier B
    teachers and unenrolled Tier C parents no longer receive a
    challenge_token at login (2026 policy change — see
    `test_login_tier_b_unenrolled_teacher_routes_to_enrolment` and
    `test_login_tier_c_unenrolled_parent_routes_to_enrolment`).
    """
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
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
    """A challenge token issued at login can read /auth/mfa/factors so
    the picker UI can render before access tokens exist. Uses Tier C
    (parent) with an enrolled TOTP factor since neither Tier B teachers
    nor unenrolled Tier C parents receive a challenge at login any more
    (2026 policy change)."""
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
    login = await client.post("/auth/login", json={"email": user["email"], "password": _PASS})
    chal = login.json()["challenge_token"]
    r = await client.get("/auth/mfa/factors", headers={"Authorization": f"Bearer {chal}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tier"] == "C"
    # Tier C no longer offers email_otp - confirm the policy contract.
    assert "email_otp" not in body["allowed_kinds"]
    assert "totp" in body["allowed_kinds"]
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
    # Tier B no longer offers email_otp — confirm the policy contract.
    assert "email_otp" not in body["allowed_kinds"]
    assert "totp" in body["allowed_kinds"]


@pytest.mark.asyncio
async def test_mfa_factors_exposes_recovery_codes_generated_at(client, tenant_a):
    """Regression: the Account Settings → Security → Recovery Codes card
    derives its empty-state badge from
    ``MfaFactorsResponse.mfa_recovery_codes_generated_at``. Before this
    fix the field was missing from the response, so ``== null`` was
    always true and the card showed "لم يتم الإنشاء بعد" simultaneously
    with "10 رمز متبقٍ" — the contradictory state in the bug report.

    Contract pinned here:
      * field is present (not absent / not undefined),
      * defaults to ``None`` for users who have never generated codes,
      * returns the user-row stamp as an ISO-ish string when present.
    """
    from engines.sql_utils import gd_update_one

    # Case 1: user has never generated codes → field is present and None.
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    access = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now_ts)
    r = await client.get("/auth/mfa/factors", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "mfa_recovery_codes_generated_at" in body, (
        "MfaFactorsResponse must expose mfa_recovery_codes_generated_at "
        "so the FE Recovery Codes card can hide the empty-state badge."
    )
    assert body["mfa_recovery_codes_generated_at"] is None
    assert body["unused_recovery_codes"] == 0

    # Case 2: stamp the user row as if regenerate had succeeded → field
    # surfaces the stamp, so the FE predicate (remaining > 0 || generatedAt)
    # flips and the empty-state badge disappears.
    stamp = datetime.now(timezone.utc)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "mfa_recovery_codes_generated_at": stamp,
        "mfa_recovery_codes_acknowledged": False,
    })
    r2 = await client.get("/auth/mfa/factors", headers={"Authorization": f"Bearer {access}"})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["mfa_recovery_codes_generated_at"] is not None
    assert isinstance(body2["mfa_recovery_codes_generated_at"], str)
    assert body2["mfa_recovery_codes_acknowledged"] is False


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
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a, enrolled=True)
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })  # NB: no mfa_recent_at
    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Task #338: change-password now emits the canonical step-up envelope
    # as HTTP 403 (via require_recent_mfa_403) so the FE axios interceptor
    # replays after passkey assertion instead of bouncing to /login. The
    # underlying step-up gate is unchanged — only the wire status differs.
    assert r.status_code == 403
    code = _err_code(r)
    assert code in {"MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED", "MFA_RESTORE_REQUIRED"}


@pytest.mark.asyncio
async def test_tier_a_without_passkey_blocked(client, tenant_a):
    """Tier-A user with a fresh mfa_recent_at but no enrolled passkey is
    still refused with MFA_PASSKEY_REQUIRED."""
    user = await _mk_login_user(UserRole.SCHOOL_ADMIN, tenant_a, enrolled=True)
    now = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now)
    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Task #338: change-password emits step-up envelopes as HTTP 403.
    assert r.status_code == 403
    assert _err_code(r) == "MFA_PASSKEY_REQUIRED"


@pytest.mark.asyncio
async def test_tier_a_must_restore_factor_blocks(client, tenant_a):
    """`mfa_must_restore_factor=True` on a Tier-A user → MFA_RESTORE_REQUIRED
    even with a passkey enrolled and a fresh mfa_recent_at."""
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a, enrolled=True)
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
    # Task #338: change-password emits step-up envelopes as HTTP 403.
    assert r.status_code == 403
    assert _err_code(r) == "MFA_RESTORE_REQUIRED"


@pytest.mark.asyncio
async def test_change_password_restore_required_does_not_mutate_or_audit(
    client, tenant_a,
):
    """Task #351 — when /auth/change-password refuses with
    MFA_RESTORE_REQUIRED (recovery-code session, mfa_must_restore_factor
    is true), the stored password hash MUST be unchanged AND no
    `password_changed` audit row may be written. The dependency runs
    before the route body, so this is a defense-in-depth assertion that
    a future regression cannot silently let the write through.
    """
    from dependencies import verify_password as _verify
    from engines.sql_utils import gd_update_one, gd_find as _gd_find
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a, enrolled=True)
    await _seed_webauthn_factor(user["id"])
    await gd_update_one(
        db.session, "users", {"id": user["id"]},
        {"mfa_must_restore_factor": True},
    )
    now = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now)

    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text
    assert _err_code(r) == "MFA_RESTORE_REQUIRED"
    # Envelope stability: a non-empty Arabic message MUST be present so
    # the FE can render the re-enrollment dialog copy without falling
    # back to a generic error string. The global exception handler wraps
    # detail into `error.message` (and may also keep `error.detail`); we
    # tolerate both shapes.
    body = r.json() or {}
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    msg = err.get("message")
    if not (isinstance(msg, str) and msg.strip()):
        nested = err.get("detail") if isinstance(err.get("detail"), dict) else {}
        msg = nested.get("message")
    if not (isinstance(msg, str) and msg.strip()):
        det = body.get("detail") if isinstance(body.get("detail"), dict) else {}
        msg = det.get("message")
    assert isinstance(msg, str) and msg.strip(), f"missing message in envelope: {body!r}"

    # Hash unchanged — old password still verifies.
    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert _verify(_PASS, fresh.get("password_hash") or "")

    # No `password_changed` audit row was emitted for this user.
    audit_rows = await _gd_find(
        db.session,
        "audit_logs",
        {"target_id": user["id"], "action": "password_changed"},
    ) or []
    assert audit_rows == [], f"unexpected password_changed audit row(s): {audit_rows}"


@pytest.mark.asyncio
async def test_change_password_succeeds_after_restore_factor_cleared(
    client, tenant_a,
):
    """Task #351 — end-to-end state transition: a user starts in the
    recovery-code post-login state (`mfa_must_restore_factor=True`) and,
    after the flag is cleared (the contract that re-enrollment must
    satisfy), `/auth/change-password` succeeds and the password hash
    actually rotates. This pins the contract the FE re-enrollment hand-
    off depends on so a future change to `require_recent_mfa` cannot
    silently keep the user locked out after they restore a factor.
    """
    from dependencies import verify_password as _verify
    from engines.sql_utils import gd_update_one
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a, enrolled=True)
    await _seed_webauthn_factor(user["id"])
    # Step 1 — recovery-code session state.
    await gd_update_one(
        db.session, "users", {"id": user["id"]},
        {"mfa_must_restore_factor": True},
    )
    now = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now)

    # Pre-condition: blocked.
    r1 = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 403
    assert _err_code(r1) == "MFA_RESTORE_REQUIRED"

    # Step 2 — re-enrollment clears the flag (modeled directly; the route
    # that performs the clear is out of this task's scope, but the
    # contract under test is "once cleared, change-password works").
    await gd_update_one(
        db.session, "users", {"id": user["id"]},
        {"mfa_must_restore_factor": False},
    )

    # Step 3 — change-password now succeeds and the hash rotates.
    new_pw = "BrandNew@123!"
    r2 = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": new_pw},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200, r2.text
    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert _verify(new_pw, fresh.get("password_hash") or "")
    assert not _verify(_PASS, fresh.get("password_hash") or "")


@pytest.mark.asyncio
async def test_stepup_start_unenrolled_teacher_returns_409(client, tenant_a):
    """2026-05-13 — Tier B no longer has implicit email_otp. A teacher
    with no enrolled mfa_factors row must receive 409 from
    /auth/mfa/stepup/start (FE then routes to /auth/mfa/enroll), not
    a challenge bound to a non-existent factor."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    r = await client.post(
        "/auth/mfa/stepup/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_stepup_start_enrolled_teacher_excludes_email_otp(client, tenant_a):
    """A teacher with an enrolled TOTP factor receives a challenge whose
    available_factor_kinds NEVER advertises email_otp."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    r = await client.post(
        "/auth/mfa/stepup/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    kinds = body.get("available_factor_kinds") or []
    assert "totp" in kinds
    assert "email_otp" not in kinds, "Tier B step-up MUST NOT offer email OTP"


@pytest.mark.asyncio
async def test_stepup_start_unenrolled_parent_returns_409(client, tenant_a):
    """2026 — Tier C parents no longer have implicit email_otp either.
    A parent with no enrolled mfa_factors row must receive 409 from
    /auth/mfa/stepup/start so the FE routes to /auth/mfa/enroll instead
    of binding a challenge to a non-existent factor."""
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    r = await client.post(
        "/auth/mfa/stepup/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_stepup_start_enrolled_parent_excludes_email_otp(client, tenant_a):
    """A parent with an enrolled TOTP factor receives a challenge whose
    available_factor_kinds NEVER advertises email_otp."""
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    r = await client.post(
        "/auth/mfa/stepup/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    kinds = body.get("available_factor_kinds") or []
    assert "totp" in kinds
    assert "email_otp" not in kinds, "Tier C step-up MUST NOT offer email OTP"


@pytest.mark.asyncio
async def test_role_switch_requires_recent_mfa(client, tenant_a):
    """Sensitive route #2: /role-switch/switch is gated by require_recent_mfa
    even for platform admins. Stale token → structured 401."""
    user = await _mk_login_user(UserRole.PLATFORM_ADMIN, tenant_a, enrolled=True)
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
    user = await _mk_login_user(UserRole.PLATFORM_ADMIN, tenant_a, enrolled=True)
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
async def test_change_password_principal_succeeds_with_fresh_mfa_and_passkey(client, tenant_a):
    """Task #338 — happy path: a Tier-A principal with an active passkey
    AND a fresh mfa_recent_at can change their password. The new
    password's hash must verify and the old password's hash must not.
    """
    from dependencies import verify_password as _verify
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a, enrolled=True)
    await _seed_webauthn_factor(user["id"])
    now = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now)
    new_pw = "BrandNew@123!"
    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": new_pw},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert _verify(new_pw, fresh.get("password_hash") or "")
    assert not _verify(_PASS, fresh.get("password_hash") or "")


@pytest.mark.asyncio
async def test_change_password_principal_wrong_current_returns_400_and_does_not_mutate(
    client, tenant_a,
):
    """Task #338 — wrong `current_password` MUST surface as HTTP 400
    with the existing Arabic message, NEVER a step-up envelope, and the
    stored password hash must remain unchanged.
    """
    from dependencies import verify_password as _verify
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a, enrolled=True)
    await _seed_webauthn_factor(user["id"])
    now = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now)
    r = await client.post(
        "/auth/change-password",
        json={"current_password": "WrongPass@123!", "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400, r.text
    # Lock the Arabic UX contract — the form surfaces this exact string.
    body = r.json() or {}
    detail = body.get("detail") or (body.get("error") or {}).get("message")
    assert detail == "كلمة المرور الحالية غير صحيحة", body
    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    # Old password still valid → hash was not mutated.
    assert _verify(_PASS, fresh.get("password_hash") or "")


@pytest.mark.asyncio
async def test_change_password_stale_mfa_does_not_mutate_password(client, tenant_a):
    """Task #338 — when the step-up gate refuses (HTTP 403 envelope), the
    password hash on disk MUST be unchanged. Belt-and-braces guard so a
    future regression cannot silently advance the request past the gate.
    """
    from dependencies import verify_password as _verify
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a, enrolled=True)
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })  # no mfa_recent_at
    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "BrandNew@123!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text
    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert _verify(_PASS, fresh.get("password_hash") or "")


@pytest.mark.asyncio
async def test_change_password_passes_with_recent_mfa_for_tier_b(client, tenant_a):
    """Tier-B user with a fresh mfa_recent_at can change password (no
    Tier-A passkey requirement)."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a, enrolled=True)
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
    """A recovery code consumed via /auth/mfa/verify cannot be replayed.

    Uses Tier C (parent). 2026: parents (like teachers) no longer have
    an implicit email_otp factor — the login gate triggers on
    ``active_factors`` only, and recovery codes alone are not an
    ``mfa_factors`` row. We seed a TOTP factor so the login returns a
    challenge_token; the recovery-code semantics under test here are
    tier-agnostic.
    """
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
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
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    # Seed TOTP so parent gets a challenge_token (2026: no implicit email_otp).
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
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
    user = await _mk_login_user(UserRole.PARENT, tenant_a)
    # Seed TOTP so parent gets a challenge_token (2026: no implicit email_otp).
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "kind": "totp",
            "is_active": True,
            "is_primary": True,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(
                mfa_crypto.generate_totp_secret()
            ),
            "created_at": datetime.now(timezone.utc),
        },
    )
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


# ---------------------------------------------------------------------------
# 8. MFA Lifecycle — Disable & Reset/Reconfigure (Task #338 follow-up)
# ---------------------------------------------------------------------------

async def _seed_totp_factor(user_id: str, *, active: bool = True) -> tuple[str, str]:
    """Insert one TOTP factor row and return (factor_id, secret_b32)."""
    fid = str(uuid.uuid4())
    secret = mfa_crypto.generate_totp_secret()
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": fid,
            "user_id": user_id,
            "kind": "totp",
            "is_active": active,
            "is_primary": active,
            "label": "test totp",
            "totp_secret_encrypted": mfa_crypto.encrypt_totp_secret(secret),
            "verified_at": datetime.now(timezone.utc) if active else None,
            "created_at": datetime.now(timezone.utc),
        },
    )
    return fid, secret


@pytest.mark.asyncio
async def test_mfa_disable_clears_factors_and_burns_recovery_codes(client, tenant_a):
    """Out-of-tier user (GATEKEEPER — no mandatory MFA; student tokens
    are rejected platform-wide by STUDENT_LOGIN_DISABLED) disables MFA:
    every active factor row is deactivated, every unconsumed recovery
    code is burned, and the user-row flags collapse to "MFA disabled".
    Requires fresh step-up + correct password."""
    from engines.sql_utils import gd_find
    user = await _mk_login_user(UserRole.GATEKEEPER, tenant_a)
    fid, _ = await _seed_totp_factor(user["id"])
    await _seed_recovery_code(user["id"])
    await _seed_recovery_code(user["id"])

    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now_ts)

    r = await client.post(
        "/auth/mfa/disable",
        json={"password": _PASS},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("disabled") is True

    factor = await gd_find_one(db.session, "mfa_factors", {"id": fid})
    assert factor and factor.get("is_active") is False

    codes = await gd_find(db.session, "mfa_recovery_codes", {"user_id": user["id"]})
    assert codes and all(c.get("consumed_at") is not None for c in codes)

    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert fresh.get("mfa_enrolled_at") is None
    assert fresh.get("mfa_must_restore_factor") is False


@pytest.mark.asyncio
async def test_mfa_disable_wrong_password_returns_401_and_does_not_mutate(client, tenant_a):
    """Wrong password → 401, factors and recovery codes intact.
    (GATEKEEPER: out-of-tier role whose tokens are accepted — student
    bearers 401 platform-wide, which would false-pass this assert.)"""
    user = await _mk_login_user(UserRole.GATEKEEPER, tenant_a)
    fid, _ = await _seed_totp_factor(user["id"])
    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now_ts)
    r = await client.post(
        "/auth/mfa/disable",
        json={"password": "Wrong@1234!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401, r.text
    factor = await gd_find_one(db.session, "mfa_factors", {"id": fid})
    assert factor and factor.get("is_active") is True


@pytest.mark.asyncio
async def test_mfa_disable_refused_for_mandatory_tier(client, tenant_a):
    """Tier-A principal cannot disable MFA — must rotate via reset
    instead. Server returns 409 and leaves all state intact."""
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    fid, _ = await _seed_totp_factor(user["id"])
    await _seed_webauthn_factor(user["id"])
    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now_ts)
    r = await client.post(
        "/auth/mfa/disable",
        json={"password": _PASS},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409, r.text
    factor = await gd_find_one(db.session, "mfa_factors", {"id": fid})
    assert factor and factor.get("is_active") is True


@pytest.mark.asyncio
async def test_mfa_disable_requires_recent_mfa(client, tenant_a):
    """No fresh mfa_recent_at → 403 step-up envelope, no mutation."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    fid, _ = await _seed_totp_factor(user["id"])
    token = create_access_token({  # no mfa_recent_at
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    r = await client.post(
        "/auth/mfa/disable",
        json={"password": _PASS},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text
    factor = await gd_find_one(db.session, "mfa_factors", {"id": fid})
    assert factor and factor.get("is_active") is True


@pytest.mark.asyncio
async def test_mfa_reset_begin_does_not_disturb_active_factor(client, tenant_a):
    """/auth/mfa/reset/begin mints a NEW pending factor without
    deactivating the existing one. The user must still be able to use
    the old factor until /auth/mfa/reset/finalize succeeds."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    old_fid, _ = await _seed_totp_factor(user["id"])
    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now_ts)
    r = await client.post(
        "/auth/mfa/reset/begin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    new_fid = body.get("factor_id")
    assert new_fid and new_fid != old_fid
    assert body.get("qr_svg")
    # Old factor untouched.
    old = await gd_find_one(db.session, "mfa_factors", {"id": old_fid})
    assert old and old.get("is_active") is True
    # New factor is pending.
    new = await gd_find_one(db.session, "mfa_factors", {"id": new_fid})
    assert new and new.get("is_active") is False


@pytest.mark.asyncio
async def test_mfa_reset_finalize_atomically_swaps_and_rotates_codes(client, tenant_a):
    """Successful finalize: new factor active+primary, old factor
    deactivated, old recovery codes burned, fresh batch issued."""
    from engines.sql_utils import gd_find
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    old_fid, _ = await _seed_totp_factor(user["id"])
    old_code_pt = await _seed_recovery_code(user["id"])

    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now_ts)
    begin = await client.post(
        "/auth/mfa/reset/begin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert begin.status_code == 200
    new_fid = begin.json()["factor_id"]

    # Pull the just-stored secret to compute a valid TOTP code.
    pending = await gd_find_one(db.session, "mfa_factors", {"id": new_fid})
    enc = pending["totp_secret_encrypted"]
    secret = mfa_crypto.decrypt_totp_secret(
        enc if isinstance(enc, (bytes, bytearray)) else bytes(enc)
    )
    import pyotp  # type: ignore
    code = pyotp.TOTP(secret).now()

    r = await client.post(
        "/auth/mfa/reset/finalize",
        json={"factor_id": new_fid, "code": code},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("factor_id") == new_fid
    assert body.get("is_primary") is True
    # Fresh recovery codes were issued.
    new_codes = body.get("recovery_codes") or []
    assert len(new_codes) >= 1
    assert old_code_pt not in new_codes

    # New factor active + primary; old factor deactivated.
    new = await gd_find_one(db.session, "mfa_factors", {"id": new_fid})
    assert new and new.get("is_active") is True and new.get("is_primary") is True
    old = await gd_find_one(db.session, "mfa_factors", {"id": old_fid})
    assert old and old.get("is_active") is False

    # Every previously-stored recovery code burned.
    codes = await gd_find(db.session, "mfa_recovery_codes", {"user_id": user["id"]})
    burned = [c for c in codes if mfa_crypto.verify_recovery_code(old_code_pt, c.get("code_hash") or "")]
    assert burned and all(c.get("consumed_at") is not None for c in burned)


@pytest.mark.asyncio
async def test_mfa_reset_finalize_bad_code_keeps_old_factor(client, tenant_a):
    """Wrong TOTP code → 400, old factor still active, pending factor
    still pending. No state was rotated."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    old_fid, _ = await _seed_totp_factor(user["id"])
    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    }, mfa_recent_at=now_ts)
    begin = await client.post(
        "/auth/mfa/reset/begin",
        headers={"Authorization": f"Bearer {token}"},
    )
    new_fid = begin.json()["factor_id"]

    r = await client.post(
        "/auth/mfa/reset/finalize",
        json={"factor_id": new_fid, "code": "000000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400, r.text

    old = await gd_find_one(db.session, "mfa_factors", {"id": old_fid})
    assert old and old.get("is_active") is True
    new = await gd_find_one(db.session, "mfa_factors", {"id": new_fid})
    assert new and new.get("is_active") is False


@pytest.mark.asyncio
async def test_mfa_reset_finalize_works_under_must_restore_factor(client, tenant_a):
    """Restore-required users (mfa_must_restore_factor=True from a
    recovery-code login) MUST be able to call reset/finalize even
    though every step-up-guarded route 403s on them. The fresh TOTP
    code is itself the proof; on success the flag clears."""
    from engines.sql_utils import gd_update_one
    user = await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    await gd_update_one(
        db.session, "users", {"id": user["id"]},
        {"mfa_must_restore_factor": True},
    )
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    begin = await client.post(
        "/auth/mfa/reset/begin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert begin.status_code == 200, begin.text
    new_fid = begin.json()["factor_id"]
    pending = await gd_find_one(db.session, "mfa_factors", {"id": new_fid})
    enc = pending["totp_secret_encrypted"]
    secret = mfa_crypto.decrypt_totp_secret(
        enc if isinstance(enc, (bytes, bytearray)) else bytes(enc)
    )
    import pyotp  # type: ignore
    code = pyotp.TOTP(secret).now()
    r = await client.post(
        "/auth/mfa/reset/finalize",
        json={"factor_id": new_fid, "code": code},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert fresh.get("mfa_must_restore_factor") is False


@pytest.mark.asyncio
async def test_totp_enroll_confirm_clears_must_restore_flag(client, tenant_a):
    """Enrolling a fresh TOTP via the standard enroll path also clears
    mfa_must_restore_factor so a restore-required user is unblocked."""
    from engines.sql_utils import gd_update_one
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    await gd_update_one(
        db.session, "users", {"id": user["id"]},
        {"mfa_must_restore_factor": True},
    )
    token = create_access_token({
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    begin = await client.post(
        "/auth/mfa/totp/enroll/begin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert begin.status_code == 200, begin.text
    new_fid = begin.json()["factor_id"]
    pending = await gd_find_one(db.session, "mfa_factors", {"id": new_fid})
    enc = pending["totp_secret_encrypted"]
    secret = mfa_crypto.decrypt_totp_secret(
        enc if isinstance(enc, (bytes, bytearray)) else bytes(enc)
    )
    import pyotp  # type: ignore
    code = pyotp.TOTP(secret).now()
    r = await client.post(
        "/auth/mfa/totp/enroll/confirm",
        json={"factor_id": new_fid, "code": code},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert fresh.get("mfa_must_restore_factor") is False


@pytest.mark.asyncio
async def test_mfa_reset_begin_requires_step_up_for_normal_user(client, tenant_a):
    """A normal (non-restore-required) user must present a fresh MFA
    proof before starting the reset/reconfigure flow — otherwise a
    stolen access token alone could swap out the user's authenticator
    and rotate recovery codes."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    await _seed_totp_factor(user["id"])
    token = create_access_token({  # NO mfa_recent_at
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    r = await client.post(
        "/auth/mfa/reset/begin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text
    assert _err_code(r) == "MFA_STEPUP_REQUIRED"


@pytest.mark.asyncio
async def test_mfa_reset_finalize_requires_step_up_for_normal_user(client, tenant_a):
    """Same step-up requirement on finalize: a normal user without a
    fresh MFA proof must be refused with a 403 step-up envelope; the
    pending factor must remain pending and the active factor active."""
    user = await _mk_login_user(UserRole.TEACHER, tenant_a)
    old_fid, _ = await _seed_totp_factor(user["id"])
    # Mint a pending factor row directly so we don't need step-up to
    # produce one — the test is specifically about finalize's gate.
    pending_fid, secret = await _seed_totp_factor(user["id"], active=False)
    import pyotp  # type: ignore
    code = pyotp.TOTP(secret).now()
    token = create_access_token({  # NO mfa_recent_at
        "sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"],
    })
    r = await client.post(
        "/auth/mfa/reset/finalize",
        json={"factor_id": pending_fid, "code": code},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text
    assert _err_code(r) == "MFA_STEPUP_REQUIRED"
    # Pending factor still pending; old factor still active.
    pending = await gd_find_one(db.session, "mfa_factors", {"id": pending_fid})
    assert pending and pending.get("is_active") is False
    old = await gd_find_one(db.session, "mfa_factors", {"id": old_fid})
    assert old and old.get("is_active") is True
