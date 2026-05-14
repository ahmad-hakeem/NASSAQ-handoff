"""
NASSAQ — MFA Policy (Task #169)

Single source of truth for which roles must complete a second factor and
which tier of factor each role is held to. Both the login route and the
``require_recent_mfa`` step-up dependency import from here so the policy
cannot drift between the two surfaces.

Tier A — phishing-resistant required (WebAuthn primary; TOTP + recovery codes
         mandatory backups)
Tier B — standard staff (authenticator-app TOTP every login; passkey allowed
         where supported; recovery codes mandatory). NOTE 2026-05-13: email
         OTP was the historical Tier B factor but has been removed because
         email delivery is unreliable and many stored teacher emails are
         placeholders. Existing teacher accounts with no enrolled non-email
         factor are routed to TOTP enrolment after password login (FE
         ProtectedRoute → ``/auth/mfa/enroll``) instead of being handed a
         dead email-code challenge.
Tier C — parents (authenticator-app TOTP every login; passkey allowed
         where supported; recovery codes mandatory). NOTE 2026: email OTP
         was the historical Tier C factor but has been removed for the
         same reason it was removed from Tier B on 2026-05-13 — email
         delivery is unreliable in this deployment and many stored parent
         email addresses are placeholders, so the email-code path was
         effectively locking parents out of the portal. Existing parent
         accounts with no enrolled non-email factor are routed to TOTP
         enrolment after password login (FE ProtectedRoute →
         ``/auth/mfa/enroll``) instead of being handed a dead email-code
         challenge.

Roles outside Tier A/B/C (student, driver, gatekeeper, ministry_rep,
testing_account, etc.) are intentionally NOT enrolled in MFA in this task —
they are out of scope per the brief. ``required_for`` returns ``None`` for
those.
"""
from __future__ import annotations

import os
from enum import Enum
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Temporary demo kill switch
# ---------------------------------------------------------------------------
# When ``MFA_ENFORCEMENT_DISABLED`` is truthy in the environment, this
# module reports every role as out-of-scope for MFA. This is the single
# source of truth: ``required_for()`` returns ``None`` for everyone, which
# in turn makes:
#
#   * the login MFA challenge gate
#     (``backend/routes/auth_routes_mod.py`` — uses ``required_for``)
#   * the step-up dependency
#     (``backend/dependencies.py:require_recent_mfa`` — uses
#     ``is_required`` and ``is_tier_a``)
#
# fall through without forcing a second factor or a recent-MFA proof. The
# IT bootstrap route reads ``is_enforcement_disabled()`` directly to skip
# its own ``mfa_enrollment_required`` / step-up emits.
#
# The bypass is reversible: unsetting / setting ``MFA_ENFORCEMENT_DISABLED``
# back to ``false`` restores the existing enforcement behaviour through the
# same code paths — no deletion of MFA factors, routes, or recovery codes.

_TRUTHY = {"1", "true", "yes", "on"}


def is_enforcement_disabled() -> bool:
    """Return True when the demo kill switch is engaged.

    Driven by the ``MFA_ENFORCEMENT_DISABLED`` env var. Read fresh on every
    call so a Replit secret toggle takes effect on the next request without
    a process restart in non-cached test contexts; in production the env
    is loaded at process start and is stable for the lifetime of the worker.
    """
    return (os.getenv("MFA_ENFORCEMENT_DISABLED") or "").strip().lower() in _TRUTHY


class MfaTier(str, Enum):
    A = "A"  # WebAuthn required, TOTP + recovery mandatory backups
    B = "B"  # authenticator-app TOTP every login + recovery mandatory
    C = "C"  # authenticator-app TOTP every login + recovery mandatory


# ---- role membership -------------------------------------------------------

# Tier A: every platform_* role + school principals/admins/sub-admins +
# independent teacher (their account is platform-issued and they administer
# their own micro-tenant, so they get the strongest factor).
_TIER_A_ROLES: frozenset[str] = frozenset({
    "platform_admin",
    "platform_sub_admin",
    "platform_operations_manager",
    "platform_technical_admin",
    "platform_support_specialist",
    "platform_data_analyst",
    "platform_security_officer",
    "platform_sales",
    "platform_marketing",
    "platform_quality",
    "school_principal",
    "school_admin",
    "school_sub_admin",
    "independent_teacher",
})

# Tier B: school-employed teachers — email OTP every login.
_TIER_B_ROLES: frozenset[str] = frozenset({"teacher"})

# Tier C: parents — authenticator-app TOTP every login (passkey allowed
# where supported); recovery codes mandatory backup. Email OTP was the
# historical Tier C factor but was removed in 2026 (see module docstring).
_TIER_C_ROLES: frozenset[str] = frozenset({"parent"})


def _normalised_role(user: dict) -> str:
    role = user.get("role") or ""
    return role.strip().lower()


def required_for(user: dict) -> Optional[MfaTier]:
    """Return the MFA tier this user is held to, or ``None`` if MFA is not
    required for this role.

    The caller MUST treat ``None`` as "second factor not required" — never
    "policy unknown / fail open". Roles that are neither A, B, nor C are
    deliberately out-of-scope for this task (student, driver, gatekeeper,
    ministry_rep, testing_account).
    """
    # Demo kill switch — when enforcement is disabled, no role is held
    # to MFA. This single check short-circuits the login challenge gate
    # and the ``require_recent_mfa`` step-up dependency without
    # touching either of those code paths.
    if is_enforcement_disabled():
        return None
    role = _normalised_role(user)
    if role in _TIER_A_ROLES:
        return MfaTier.A
    if role in _TIER_B_ROLES:
        return MfaTier.B
    if role in _TIER_C_ROLES:
        return MfaTier.C
    return None


def is_tier_a(user: dict) -> bool:
    return required_for(user) is MfaTier.A


def is_required(user: dict) -> bool:
    return required_for(user) is not None


# ---- per-tier factor allow-list -------------------------------------------

def allowed_factor_kinds(user: dict) -> frozenset[str]:
    """Which ``mfa_factors.kind`` values are allowed to satisfy this user's
    login second factor. Used by the verify route to refuse a factor kind
    that the user's tier has not enabled. As of 2026 every tier (A/B/C)
    accepts ``{webauthn, totp, recovery_code}``; ``email_otp`` was removed
    from Tier B (2026-05-13) and Tier C (2026) because email delivery is
    unreliable and many stored email addresses are placeholders."""
    tier = required_for(user)
    if tier is MfaTier.A:
        return frozenset({"webauthn", "totp", "recovery_code"})
    if tier is MfaTier.B:
        # 2026-05-13: Tier B no longer accepts email OTP at login. Teachers
        # authenticate with authenticator-app TOTP (and may use a passkey
        # where the WebAuthn stack is available); recovery codes remain a
        # mandatory backup. The historical email_otp factor was removed
        # because email delivery is unreliable in this deployment and many
        # stored teacher email addresses are not real.
        return frozenset({"webauthn", "totp", "recovery_code"})
    if tier is MfaTier.C:
        # 2026: Tier C no longer accepts email OTP at login. Parents
        # authenticate with authenticator-app TOTP (and may use a passkey
        # where the WebAuthn stack is available); recovery codes remain a
        # mandatory backup. The historical email_otp factor was removed
        # because email delivery is unreliable in this deployment and many
        # stored parent email addresses are placeholders.
        return frozenset({"webauthn", "totp", "recovery_code"})
    return frozenset()


# ---- Tier A "must hold a passkey" enforcement -----------------------------

def tier_a_passkey_satisfied(active_factor_rows: Iterable[dict]) -> bool:
    """Tier A policy outcome check.

    The plan is explicit: enforcement keys off the *existence count* of
    active WebAuthn credentials, NOT off any "is_primary" label. The
    ``is_primary`` column is a UX hint only.

    Pass in the user's currently-active mfa_factors rows; returns True if at
    least one of them is an active WebAuthn credential.
    """
    for row in active_factor_rows:
        if (row.get("kind") == "webauthn") and bool(row.get("is_active")):
            return True
    return False
