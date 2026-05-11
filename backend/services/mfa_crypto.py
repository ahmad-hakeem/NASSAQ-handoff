"""
NASSAQ — MFA cryptographic helpers (Task #169)

Three at-rest representations are used, each chosen for a different reason:

* **TOTP shared secrets** — Fernet (AES-128-CBC + HMAC-SHA256, IETF) using
  ``MFA_ENCRYPTION_KEY`` from environment. The seed must be *recoverable*
  by the server at verify time so it can recompute HOTP codes — therefore
  encryption, not hashing.

* **Recovery codes** — bcrypt. They are user-presented one-time secrets
  with high entropy; we only ever need to *check* a user-supplied value,
  never recover the original, so a one-way slow hash is appropriate.

* **Email OTPs** — salted sha256. They are short (6 digits) and very
  short-lived (10 min); bcrypt would be overkill and Fernet is wrong (we
  never need to read them back). The per-row salt prevents pre-computed
  rainbow attacks against the small 6-digit space if the table ever leaks.

All callers must use these helpers — *never* import ``cryptography`` /
``bcrypt`` directly to handle MFA secrets.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
from typing import Final

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("nassaq.mfa.crypto")

_ENV_KEY: Final[str] = "MFA_ENCRYPTION_KEY"


class MfaCryptoConfigError(RuntimeError):
    """Raised when MFA_ENCRYPTION_KEY is missing or malformed."""


_fernet_singleton: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-load the Fernet instance from MFA_ENCRYPTION_KEY.

    The variable must be a 32-byte url-safe base64 string (the value
    produced by ``Fernet.generate_key()``). We refuse to start with a
    silently-generated ephemeral key because that would make every existing
    TOTP seed in the database unrecoverable on the next process restart.
    """
    global _fernet_singleton
    if _fernet_singleton is not None:
        return _fernet_singleton

    raw = os.environ.get(_ENV_KEY)
    if not raw:
        raise MfaCryptoConfigError(
            f"{_ENV_KEY} is not set. Generate a key with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'` and store it in "
            "Replit secrets."
        )
    try:
        _fernet_singleton = Fernet(raw.encode("utf-8") if isinstance(raw, str) else raw)
    except (ValueError, TypeError) as exc:
        raise MfaCryptoConfigError(
            f"{_ENV_KEY} is malformed: must be a 32-byte url-safe base64 string"
        ) from exc
    return _fernet_singleton


# ---- TOTP secrets ----------------------------------------------------------

def encrypt_totp_secret(secret_b32: str) -> bytes:
    """Encrypt a base32-encoded TOTP shared secret for at-rest storage.

    Returns Fernet ciphertext bytes suitable for a ``LargeBinary`` column.
    """
    if not secret_b32:
        raise ValueError("secret_b32 must be a non-empty base32 string")
    return _get_fernet().encrypt(secret_b32.encode("utf-8"))


def decrypt_totp_secret(ciphertext: bytes) -> str:
    """Decrypt a stored TOTP secret. Raises ``MfaCryptoConfigError`` on
    tamper or wrong key (caller should treat this as a hard failure)."""
    if not ciphertext:
        raise ValueError("ciphertext must be non-empty")
    try:
        return _get_fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        # Surface as a config error so the caller can decide whether to
        # rotate the user out of TOTP rather than silently accept any code.
        raise MfaCryptoConfigError(
            "TOTP secret could not be decrypted (key rotated or row tampered?)"
        ) from exc


# ---- TOTP code generation / verification -----------------------------------

# pyotp + qrcode are optional-at-import-time so the module can be imported
# in environments where TOTP is disabled (e.g. unit tests of recovery codes
# only). Missing imports fail loudly when the helpers are *called*.
try:
    import pyotp as _pyotp  # type: ignore
except Exception:  # pragma: no cover
    _pyotp = None  # type: ignore

try:
    import qrcode as _qrcode  # type: ignore
    from qrcode.image.svg import SvgImage as _SvgImage  # type: ignore
except Exception:  # pragma: no cover
    _qrcode = None  # type: ignore
    _SvgImage = None  # type: ignore


def generate_totp_secret() -> str:
    """Generate a 160-bit random base32 secret suitable for RFC-6238 TOTP."""
    if _pyotp is None:
        raise RuntimeError("pyotp is not installed")
    return _pyotp.random_base32(length=32)


def build_otpauth_uri(account_label: str, secret_b32: str, issuer: str = "NASSAQ") -> str:
    """Build an ``otpauth://totp/...`` URI for QR-code provisioning.

    ``account_label`` should be the user's email (or another stable
    identifier) — it is what the authenticator app displays under the
    issuer name.
    """
    if _pyotp is None:
        raise RuntimeError("pyotp is not installed")
    return _pyotp.TOTP(secret_b32).provisioning_uri(name=account_label, issuer_name=issuer)


def qr_svg_for_otpauth(uri: str) -> str:
    """Render an otpauth URI as an inline SVG string. Returned value is
    safe to embed in HTML / React via ``dangerouslySetInnerHTML`` because
    it contains no user-controlled data — only the URI we just built."""
    if _qrcode is None or _SvgImage is None:
        raise RuntimeError("qrcode is not installed")
    img = _qrcode.make(uri, image_factory=_SvgImage, box_size=10, border=2)
    import io
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


def verify_totp_code(secret_b32: str, code: str, *, window: int = 1) -> bool:
    """Constant-time-ish verify of a 6-digit TOTP code with a +/- 1 step
    tolerance (default ``window=1`` = 30s slack on either side, total
    90s acceptance window). Wider windows are forbidden — they materially
    weaken the factor."""
    if _pyotp is None:
        raise RuntimeError("pyotp is not installed")
    if not code or not secret_b32:
        return False
    cleaned = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(cleaned) != 6:
        return False
    if window < 0 or window > 1:
        # Refuse pathological windows. The plan caller passes 1.
        window = 1
    try:
        return bool(_pyotp.TOTP(secret_b32).verify(cleaned, valid_window=window))
    except Exception as exc:  # malformed secret etc — treat as failure
        logger.warning(f"verify_totp_code: pyotp raised: {exc}")
        return False


# ---- Recovery codes --------------------------------------------------------

_RECOVERY_ALPHABET: Final[str] = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
"""Alphabet for human-friendly codes — omits 0/O/1/I to reduce transcription
errors when a user reads a printed page back."""


def generate_recovery_code() -> str:
    """Generate a single ``xxxx-xxxx-xxxx`` recovery code (60 bits of
    entropy from a 32-symbol alphabet)."""
    parts = []
    for _ in range(3):
        parts.append("".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(4)))
    return "-".join(parts)


def hash_recovery_code(code: str) -> str:
    """Bcrypt-hash a recovery code for at-rest storage. Recovery codes are
    one-shot, so a slow hash is appropriate — verification only happens
    once per code."""
    norm = _normalise_recovery_code(code)
    return bcrypt.hashpw(norm.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_recovery_code(code: str, stored_hash: str) -> bool:
    """Constant-time compare a user-supplied recovery code against a stored
    bcrypt hash. Tolerant to minor formatting variation (case, spaces,
    missing dashes) because users will type these from paper."""
    try:
        norm = _normalise_recovery_code(code)
        return bcrypt.checkpw(norm.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _normalise_recovery_code(code: str) -> str:
    """Strip whitespace, dashes, and uppercase. Re-insert dashes so that
    ``ABCD-EFGH-JKLM``, ``abcdefghjklm``, and ``abcd efgh jklm`` all hash
    to the same value."""
    if not code:
        return ""
    cleaned = "".join(ch for ch in code.upper() if ch.isalnum())
    if len(cleaned) != 12:
        # Don't try to canonicalise garbage — let verify_recovery_code
        # return False naturally.
        return cleaned
    return f"{cleaned[0:4]}-{cleaned[4:8]}-{cleaned[8:12]}"


# ---- Email OTPs ------------------------------------------------------------

def generate_email_otp() -> str:
    """Generate a 6-digit numeric OTP using the system CSPRNG."""
    # ``secrets.randbelow`` is unbiased over the inclusive range [0, 999999].
    n = secrets.randbelow(1_000_000)
    return f"{n:06d}"


def hash_email_otp(otp: str, salt: str) -> str:
    """Salted-sha256 hex digest of an email OTP. The salt is stored in the
    same row as the hash; both together let the verify route recompute the
    hash from a user-supplied value without ever decrypting anything."""
    if not otp:
        raise ValueError("otp must be non-empty")
    if not salt:
        raise ValueError("salt must be non-empty")
    h = hashlib.sha256()
    h.update(salt.encode("utf-8"))
    h.update(otp.encode("utf-8"))
    return h.hexdigest()


def generate_email_otp_salt() -> str:
    """16 random bytes as 32-char hex — large enough to make the 6-digit
    space infeasible to rainbow-table even if the table leaks."""
    return secrets.token_hex(16)


def verify_email_otp(otp: str, salt: str, stored_hash: str) -> bool:
    """Constant-time compare a user-supplied OTP against the stored hash."""
    try:
        candidate = hash_email_otp(otp, salt)
    except ValueError:
        return False
    return hmac.compare_digest(candidate, stored_hash or "")
