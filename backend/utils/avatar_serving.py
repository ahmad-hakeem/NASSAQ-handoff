"""Signed URLs + image-access cookie for serving avatars / logos cacheably.

Design: signed URL (what) + HttpOnly cookie (who)
-------------------------------------------------
A plain ``<img src>`` cannot attach an Authorization header, so image access
uses two independent factors:

* Every serializer that returns a user/school mints an HMAC-signed URL. The
  signature binds the entity id, the content version and an expiry — photo
  URLs cannot be guessed or forged (HMAC-SHA256 over a ``JWT_SECRET``-derived
  key), and the URL is self-contained and browser-cacheable.
* The signed URL alone is deliberately NOT sufficient: it is a shareable
  string. The image endpoints additionally require the HttpOnly image-access
  cookie (set on login / refresh / ``/auth/me`` / MFA verify — the browser
  attaches it to ``<img>`` requests automatically) and enforce the same
  tenant rule as the serializers: self, same tenant, or platform role.
  A forwarded URL is useless without it (401), and a cross-tenant
  authenticated requester gets the same 404 as a missing image.

The cookie is read-only capability (images only, tenant-checked), HttpOnly,
SameSite=Lax and scoped to ``/api`` — no CSRF surface, no session semantics.

Cacheability: a naive ``exp = now + ttl`` would change the URL on every
response and defeat the browser cache entirely. The expiry is therefore
aligned to the start of the current UTC day plus 48 h — the URL is byte-stable
for a whole day, and always has at least 24 h of remaining validity when
minted. The content hash ``v`` busts the cache the moment the image changes;
the endpoint additionally answers conditional requests with 304 via ETag.

Transition: values that are not ``data:`` URIs (legacy plain URLs, empty,
None) pass through unchanged, and the frontend keeps rendering inline
``data:`` values wherever they still appear.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Optional, Tuple

from dependencies import JWT_SECRET

_DATA_PREFIX = "data:image/"

# URL is stable within a UTC day; minted URLs carry 24-48 h of validity.
_EXP_HORIZON_SECONDS = 48 * 3600
_DAY = 24 * 3600

_KINDS = {
    "avatar": ("users", "avatar"),
    "logo": ("schools", "logo"),
}


def _signing_key() -> bytes:
    # Domain-separated from every other JWT_SECRET use.
    return hashlib.sha256(b"nassaq-image-url-v1:" + JWT_SECRET.encode()).digest()


def content_version(value: str) -> str:
    """Short stable hash of the stored image payload (cache buster + ETag)."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _signature(kind: str, entity_id: str, version: str, exp: int) -> str:
    msg = f"{kind}|{entity_id}|{version}|{exp}".encode()
    return hmac.new(_signing_key(), msg, hashlib.sha256).hexdigest()[:32]


def verify_signature(kind: str, entity_id: str, version: str, exp: int, sig: str) -> bool:
    """True iff the signature is authentic AND not expired."""
    if exp < int(time.time()):
        return False
    expected = _signature(kind, entity_id, version, exp)
    return hmac.compare_digest(expected, sig or "")


def signed_image_url(kind: str, entity_id: str, value: Optional[str]) -> Optional[str]:
    """Serializer-facing: replace an inline ``data:`` image with a signed URL.

    Non-``data:`` values (None, empty, legacy plain URLs) pass through
    unchanged — that is the documented transition behaviour.
    """
    if not value or not isinstance(value, str) or not value.startswith(_DATA_PREFIX):
        return value
    if kind not in _KINDS:
        raise ValueError(f"unknown image kind: {kind}")
    collection, segment = _KINDS[kind]
    version = content_version(value)
    # Day-aligned expiry so the URL (and thus the browser cache key) is
    # stable across every response minted on the same UTC day.
    exp = (int(time.time()) // _DAY) * _DAY + _EXP_HORIZON_SECONDS
    sig = _signature(kind, entity_id, version, exp)
    return f"/api/{collection}/{entity_id}/{segment}?v={version}&exp={exp}&sig={sig}"


def decode_data_url(value: str) -> Tuple[bytes, str]:
    """Decode a stored ``data:image/...;base64,`` value → (bytes, media_type).

    Raises ValueError on a malformed value.
    """
    if not value.startswith(_DATA_PREFIX) or "," not in value:
        raise ValueError("not an image data URL")
    header, b64 = value.split(",", 1)
    mime = header[len("data:"):].split(";", 1)[0] or "image/jpeg"
    return base64.b64decode(b64), mime


def is_internal_image_url(value) -> bool:
    """True when a client echoed back one of OUR signed image URLs.

    Transition guard: serializers now return ``/api/users/{id}/avatar?...`` /
    ``/api/schools/{id}/logo?...`` instead of the inline base64. Older
    frontend flows re-submit the whole profile object on save, so without
    this check the signed URL string would OVERWRITE the stored image.
    Write paths treat such a value as "unchanged" and skip the field.
    """
    if not isinstance(value, str):
        return False
    return (value.startswith("/api/users/") and "/avatar?" in value) or (
        value.startswith("/api/schools/") and "/logo?" in value
    )


# ---------------------------------------------------------------------------
# Image-access cookie (requester authentication)
# ---------------------------------------------------------------------------
# The signed URL alone binds WHAT may be fetched (entity + content version +
# expiry) but is a shareable bearer string. To stop a legitimately minted URL
# from being replayed by an unauthenticated third party or a cross-tenant
# user, the image endpoints ALSO require an HttpOnly cookie identifying the
# requester, set alongside login/refresh//auth/me. A cookie (not a bearer
# header) because <img src> cannot attach headers; CSRF is a non-issue as the
# cookie only grants image READS which are then tenant-checked server-side.

IMAGE_COOKIE_NAME = "nassaq_img"
IMAGE_COOKIE_TTL = 12 * 3600


def _cookie_key() -> bytes:
    return hashlib.sha256(b"nassaq-image-cookie-v1:" + JWT_SECRET.encode()).digest()


def mint_image_access_cookie(user_id: str, tenant_id: Optional[str], role: Optional[str]) -> str:
    exp = int(time.time()) + IMAGE_COOKIE_TTL
    payload = f"{user_id}|{tenant_id or ''}|{role or ''}|{exp}"
    mac = hmac.new(_cookie_key(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return base64.urlsafe_b64encode(payload.encode()).decode() + "." + mac


def verify_image_access_cookie(token: Optional[str]) -> Optional[dict]:
    """Return ``{user_id, tenant_id, role}`` or None. Fails closed."""
    if not token or "." not in token:
        return None
    b64, mac = token.rsplit(".", 1)
    try:
        payload = base64.urlsafe_b64decode(b64.encode()).decode()
    except Exception:
        return None
    expected = hmac.new(_cookie_key(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, mac):
        return None
    parts = payload.split("|")
    if len(parts) != 4:
        return None
    user_id, tenant_id, role, exp_s = parts
    try:
        if int(exp_s) < int(time.time()):
            return None
    except ValueError:
        return None
    return {"user_id": user_id, "tenant_id": tenant_id or None, "role": role or None}


def attach_image_access_cookie(response, user: dict) -> None:
    """Set the image-access cookie on an outgoing auth response."""
    import os
    token = mint_image_access_cookie(
        user.get("id") or "", user.get("tenant_id"), user.get("role")
    )
    response.set_cookie(
        IMAGE_COOKIE_NAME,
        token,
        max_age=IMAGE_COOKIE_TTL,
        httponly=True,
        samesite="lax",
        path="/api",
        secure=os.environ.get("ENVIRONMENT") == "production",
    )
