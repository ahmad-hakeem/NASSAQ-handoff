"""
NASSAQ — WebAuthn helpers (Task #169, Step 4)

A thin wrapper around the ``webauthn`` python package that pins our
ceremony defaults and centralises the Relying Party (RP) configuration
so register/verify routes cannot drift apart.

RP configuration
----------------
The RP is identified to the browser by ``rp_id`` (a domain string, no
scheme/port) and ``rp_name`` (the human-readable label shown in the
Passkey prompt). The browser refuses ceremonies whose ``origin`` does
not match the visible page origin AND whose ``rp_id`` is not a
suffix-match of that origin's host.

We support multiple acceptable origins (dev tunnel + prod custom
domain) via the ``MFA_WEBAUTHN_ORIGINS`` env var (comma-separated).
``rp_id`` is one canonical host (no scheme, no port). Defaults are
derived from ``REPLIT_DOMAINS`` so the dev environment Just Works
without extra config.

Tier A defaults — security choices
----------------------------------
* ``user_verification = REQUIRED`` — every Passkey ceremony must prove
  user presence + verification (biometric/PIN). Anything weaker would
  make the Tier A "phishing-resistant" claim untrue.
* ``resident_key = PREFERRED`` — let the authenticator decide whether
  to store a discoverable credential. Required-resident-key locks out
  some legacy devices for no security gain.
* ``attestation = NONE`` — we don't need to verify the authenticator's
  manufacturer chain; the user's account already exists and the cred
  is bound to a specific user.id. Asking for attestation harms
  privacy and adds zero defence against phishing.
* No ``authenticator_attachment`` filter — both platform passkeys
  (Face ID, Touch ID, Windows Hello, Android biometric) and
  cross-platform USB/NFC keys are first-class Tier A credentials per
  the brief.
"""
from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

logger = logging.getLogger("nassaq.mfa.webauthn")

# Optional-at-import — the route handlers raise 501 with a clear Arabic
# message if the package is missing instead of crashing the whole app.
try:
    from webauthn import (  # type: ignore
        generate_registration_options,
        verify_registration_response,
        generate_authentication_options,
        verify_authentication_response,
        options_to_json,
    )
    from webauthn.helpers.structs import (  # type: ignore
        AuthenticatorSelectionCriteria,
        ResidentKeyRequirement,
        UserVerificationRequirement,
        AttestationConveyancePreference,
        PublicKeyCredentialDescriptor,
    )
    _WEBAUTHN_OK = True
except Exception as _exc:  # pragma: no cover
    _WEBAUTHN_OK = False
    _IMPORT_ERR = str(_exc)


class WebauthnUnavailable(RuntimeError):
    """Raised when the ``webauthn`` package is not importable."""


def _ensure_lib() -> None:
    if not _WEBAUTHN_OK:
        raise WebauthnUnavailable(
            f"webauthn package not available: {_IMPORT_ERR}"
        )


@dataclass(frozen=True)
class RpConfig:
    rp_id: str
    rp_name: str
    origins: Tuple[str, ...]


def _default_origins() -> Tuple[str, ...]:
    """Build the default acceptable-origin list from REPLIT_DOMAINS.

    REPLIT_DOMAINS is a comma-separated list of bare hosts (no scheme).
    We mint ``https://{host}`` for each. We also accept
    ``http://localhost:5000`` so that local dev against
    ``localhost`` stays usable without extra config — but only if the
    process is NOT in production mode.
    """
    raw = os.environ.get("REPLIT_DOMAINS") or ""
    hosts = [h.strip() for h in raw.split(",") if h.strip()]
    origins = [f"https://{h}" for h in hosts]
    if (os.environ.get("NODE_ENV") or "").lower() != "production":
        origins.extend(["http://localhost:5000", "http://localhost:3000"])
    return tuple(origins)


def _default_rp_id() -> str:
    raw = os.environ.get("REPLIT_DOMAINS") or ""
    hosts = [h.strip() for h in raw.split(",") if h.strip()]
    if hosts:
        return hosts[0]
    return "localhost"


def get_rp_config() -> RpConfig:
    """Return the active RP config, with env overrides honoured.

    Env vars:
      * ``MFA_WEBAUTHN_RP_ID`` — overrides the default canonical host.
      * ``MFA_WEBAUTHN_RP_NAME`` — overrides "NASSAQ".
      * ``MFA_WEBAUTHN_ORIGINS`` — comma-separated full origins (with
        scheme); overrides the REPLIT_DOMAINS-derived default.
    """
    rp_id = os.environ.get("MFA_WEBAUTHN_RP_ID") or _default_rp_id()
    rp_name = os.environ.get("MFA_WEBAUTHN_RP_NAME") or "NASSAQ"
    origins_env = os.environ.get("MFA_WEBAUTHN_ORIGINS")
    if origins_env:
        origins = tuple(o.strip() for o in origins_env.split(",") if o.strip())
    else:
        origins = _default_origins()
    if not origins:
        # Last-resort fallback so the route can still respond — but log
        # loudly because this means WebAuthn ceremonies will be refused
        # by every browser.
        logger.warning("WebAuthn RP config has no acceptable origins; ceremonies will fail")
        origins = (f"https://{rp_id}",)
    return RpConfig(rp_id=rp_id, rp_name=rp_name, origins=origins)


# ---- ceremony helpers ------------------------------------------------------

def new_challenge_bytes(n: int = 32) -> bytes:
    """Cryptographically random challenge for a WebAuthn ceremony."""
    return secrets.token_bytes(n)


def _user_id_to_bytes(user_id: str) -> bytes:
    """WebAuthn requires a stable opaque user.id (≤ 64 bytes). Our user
    IDs are UUID strings; encode them as utf-8 (36 bytes)."""
    if not user_id:
        raise ValueError("user_id must be non-empty")
    return user_id.encode("utf-8")


def _exclude_descriptors(credential_ids: Iterable[bytes]) -> List["PublicKeyCredentialDescriptor"]:
    out: List[PublicKeyCredentialDescriptor] = []
    for cid in credential_ids:
        if not cid:
            continue
        out.append(PublicKeyCredentialDescriptor(id=bytes(cid), transports=None))
    return out


def make_registration_options(
    *,
    user_id: str,
    user_name: str,
    user_display_name: Optional[str] = None,
    exclude_credential_ids: Iterable[bytes] = (),
) -> Tuple[str, bytes]:
    """Build the JSON the browser passes to ``navigator.credentials.create``.

    Returns ``(options_json, challenge_bytes)``. The caller stores
    ``challenge_bytes`` in ``mfa_webauthn_challenges`` keyed by
    ``user_id`` + ``purpose='enroll'``. The browser receives only the
    JSON; the raw bytes never leave the server.
    """
    _ensure_lib()
    cfg = get_rp_config()
    challenge = new_challenge_bytes()
    options = generate_registration_options(
        rp_id=cfg.rp_id,
        rp_name=cfg.rp_name,
        user_id=_user_id_to_bytes(user_id),
        user_name=user_name,
        user_display_name=user_display_name or user_name,
        challenge=challenge,
        timeout=60_000,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
            # No authenticator_attachment filter — both platform passkeys
            # and cross-platform keys are valid Tier A credentials.
        ),
        exclude_credentials=_exclude_descriptors(exclude_credential_ids),
    )
    return options_to_json(options), challenge


def verify_registration(
    *, credential: dict, expected_challenge: bytes,
):
    """Verify the attestation returned by the browser. Returns the
    ``VerifiedRegistration`` object whose ``.credential_id`` /
    ``.credential_public_key`` / ``.sign_count`` / ``.aaguid`` /
    ``.credential_device_type`` fields the caller must persist.

    Raises whatever the underlying ``webauthn`` package raises on
    failure — caller turns that into a 400 with an Arabic message.
    """
    _ensure_lib()
    cfg = get_rp_config()
    return verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_rp_id=cfg.rp_id,
        expected_origin=list(cfg.origins),
        require_user_verification=True,
    )


def make_authentication_options(
    *, allow_credential_ids: Iterable[bytes] = (),
) -> Tuple[str, bytes]:
    """Build the JSON the browser passes to ``navigator.credentials.get``.

    Returns ``(options_json, challenge_bytes)``. The challenge is stored
    by the caller in ``mfa_webauthn_challenges`` with ``purpose='verify'``.
    """
    _ensure_lib()
    cfg = get_rp_config()
    challenge = new_challenge_bytes()
    options = generate_authentication_options(
        rp_id=cfg.rp_id,
        challenge=challenge,
        timeout=60_000,
        allow_credentials=_exclude_descriptors(allow_credential_ids),
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return options_to_json(options), challenge


def verify_authentication(
    *,
    credential: dict,
    expected_challenge: bytes,
    stored_public_key: bytes,
    stored_sign_count: int,
):
    """Verify the assertion returned by the browser against a stored
    credential. Returns the ``VerifiedAuthentication`` whose
    ``.new_sign_count`` the caller MUST persist (and refuse further
    use of the credential if the new count is not strictly greater
    than the stored count, which indicates a cloned authenticator)."""
    _ensure_lib()
    cfg = get_rp_config()
    return verify_authentication_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_rp_id=cfg.rp_id,
        expected_origin=list(cfg.origins),
        credential_public_key=stored_public_key,
        credential_current_sign_count=stored_sign_count,
        require_user_verification=True,
    )
