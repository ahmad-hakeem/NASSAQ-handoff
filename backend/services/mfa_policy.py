"""
NASSAQ — MFA Policy (Task #169)

Single source of truth for which roles must complete a second factor and
which tier of factor each role is held to. Both the login route and the
``require_recent_mfa`` step-up dependency import from here so the policy
cannot drift between the two surfaces.

Tier A — phishing-resistant required (WebAuthn primary; TOTP + recovery codes
         mandatory backups)
Tier B — standard staff (email OTP every login; recovery codes mandatory;
         TOTP optional upgrade)
Tier C — simple end-user (email OTP every login; recovery codes mandatory)

Roles outside Tier A/B/C (student, driver, gatekeeper, ministry_rep,
testing_account, etc.) are intentionally NOT enrolled in MFA in this task —
they are out of scope per the brief. ``required_for`` returns ``None`` for
those.
"""
from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional


class MfaTier(str, Enum):
    A = "A"  # WebAuthn required, TOTP + recovery mandatory backups
    B = "B"  # email OTP login + recovery mandatory
    C = "C"  # email OTP login + recovery mandatory


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

# Tier C: parents — email OTP every login.
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
    login second factor. Used by the verify route to refuse, e.g., a parent
    who tries to log in with a TOTP code (parents are email-OTP only)."""
    tier = required_for(user)
    if tier is MfaTier.A:
        return frozenset({"webauthn", "totp", "recovery_code"})
    if tier is MfaTier.B:
        # Teachers may upgrade to TOTP from settings; once enrolled it's a
        # valid login factor alongside email OTP. Recovery codes are always
        # accepted.
        return frozenset({"email_otp", "totp", "recovery_code"})
    if tier is MfaTier.C:
        return frozenset({"email_otp", "recovery_code"})
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
