"""Shared, cross-worker rate limiter for the public landing-page Hakim
chat endpoints.

Why this exists
---------------
``backend/middleware/rate_limiter.py`` uses an in-memory sliding-window
store. That's fine for single-worker Replit deployments, but the public
Hakim endpoints make live LLM calls on every request and the streaming
variant holds an upstream connection open per request — so the threat
model explicitly calls out abuse controls that *hold across worker
processes*. This module backs the limiter with a small Postgres counter
table (``public_hakim_rate_counters``) so the budget is shared no matter
how many uvicorn/gunicorn workers are running.

Design
------
For each request we compute up to three bucket keys and atomically
increment them with ``INSERT ... ON CONFLICT DO UPDATE SET count = count
+ 1 RETURNING count``:

* per-IP, 60-second bucket — short burst protection.
* per-IP+UA, 60-second bucket — catches a single client looping with the
  same user agent before it rotates IPs.
* per-IP, 86400-second bucket — daily ceiling so a slow scraper can't
  outrun the burst limit.

If any bucket's post-increment count is over its limit the request is
denied. Rows carry an ``expires_at`` so a tiny opportunistic cleanup
(probability-gated) keeps the table bounded without a cron.

The limiter never raises HTTP itself — callers translate ``denied=True``
into the same localized safe-error envelope they already use for other
failures so the chat UI degrades gracefully.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import random
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text

from db import async_session_factory

logger = logging.getLogger("nassaq.public_hakim_limiter")


# Limits — intentionally generous enough for legitimate exploration of
# the landing-page chat while bounding cost-abuse / scraping.
PER_IP_PER_MINUTE = 8
PER_IP_PER_DAY = 80
PER_IP_UA_PER_MINUTE = 6

# Per-fingerprint caps. The fingerprint is either a random opaque ID
# carried in a short-lived HMAC-signed cookie (preferred — stable across
# IP rotations for a real browser) or a hash of (User-Agent,
# Accept-Language) when no valid cookie is present. The cookie variant
# lets us catch a single attacker session that rotates through a
# residential-proxy pool; the header-only variant is a weaker fallback
# that still bounds the simplest "strip cookies + rotate IPs" pattern as
# long as the bot reuses the same UA/Accept-Language header pair.
# Per-fingerprint caps come in two flavours:
#   * COOKIE-derived fingerprint (`fingerprint_shared=False`) — tight,
#     because the opaque id was minted for one browser session and a
#     legitimate visitor will never collide with another user's id.
#   * HEADER-derived fingerprint (`fingerprint_shared=True`) — much
#     looser, because many real first-time visitors share the same
#     (UA, Accept-Language) tuple (e.g. all Chrome-on-Mac en-US users
#     hit the same bucket). The shared cap is high enough that normal
#     traffic from a popular browser/locale never trips it, but still
#     bounds a sustained cookie-stripping attacker who reuses the same
#     headers across an IP pool.
PER_FP_PER_MINUTE = 6
PER_FP_PER_DAY = 60
PER_FP_SHARED_PER_MINUTE = 60
PER_FP_SHARED_PER_DAY = 600

# Public-Hakim fingerprint cookie. The value is HMAC-signed with
# JWT_SECRET and carries a random 16-byte opaque ID plus an expiry —
# never an email, account id, or any cross-site stable identifier. It
# is httpOnly + SameSite=Lax + path-scoped to the Hakim public surface,
# so it can't be read by JS and won't be sent to third parties.
FINGERPRINT_COOKIE_NAME = "nhfp"
FINGERPRINT_COOKIE_PATH = "/api/public/hakim"
FINGERPRINT_COOKIE_MAX_AGE = 30 * 86400
_FINGERPRINT_TTL_S = FINGERPRINT_COOKIE_MAX_AGE

# Stream-side caps so a single request can't hold a worker indefinitely.
STREAM_MAX_DURATION_S = 60.0
STREAM_MAX_CHUNKS = 800

# How likely each request is to run the opportunistic cleanup sweep.
_CLEANUP_PROB = 0.01


@dataclass
class LimiterDecision:
    denied: bool
    # Approximate seconds the caller should wait before retrying. Surfaced
    # via Retry-After on the streaming-error path. None when allowed.
    retry_after: Optional[int] = None


def _hash_ip(ip: str) -> str:
    return hashlib.sha256((ip or "unknown").encode("utf-8")).hexdigest()[:24]


def _hash_ua(ua: str) -> str:
    # Truncate the UA before hashing so we don't burn CPU on absurdly
    # long header values, and so the resulting key stays small.
    return hashlib.sha256((ua or "")[:512].encode("utf-8")).hexdigest()[:16]


def _get_fingerprint_secret() -> bytes:
    """Resolve the HMAC key lazily so import-time circular deps don't
    matter and so tests can rebind ``JWT_SECRET`` if they need to."""
    try:
        from dependencies import JWT_SECRET  # type: ignore
    except Exception:
        JWT_SECRET = os.environ.get("JWT_SECRET_KEY", "")
    # Domain-separate from other HMAC uses of the same secret so a
    # fingerprint cookie can never be confused for any other signed
    # artifact (e.g. invitation tokens).
    return hashlib.sha256(("public_hakim_fp|" + (JWT_SECRET or "")).encode("utf-8")).digest()


def _b64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    import base64
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign_fingerprint(fp_id: str, exp_ts: int) -> str:
    payload = f"{fp_id}.{exp_ts}"
    sig = hmac.new(_get_fingerprint_secret(), payload.encode("ascii"), hashlib.sha256).digest()
    return f"v1.{payload}.{_b64url_encode(sig)[:22]}"


def _verify_fingerprint_cookie(raw: str) -> Optional[str]:
    """Return the embedded opaque ``fp_id`` if the cookie is well-formed,
    signed by the current secret, and not expired. Returns ``None``
    otherwise (caller will mint a fresh cookie)."""
    if not raw or not isinstance(raw, str) or len(raw) > 256:
        return None
    parts = raw.split(".")
    if len(parts) != 4 or parts[0] != "v1":
        return None
    fp_id, exp_s, sig = parts[1], parts[2], parts[3]
    if not fp_id or not exp_s.isdigit():
        return None
    expected = _sign_fingerprint(fp_id, int(exp_s)).split(".", 3)[3]
    if not hmac.compare_digest(expected, sig):
        return None
    if int(exp_s) < int(time.time()):
        return None
    return fp_id


def read_or_mint_fingerprint(request_cookie: Optional[str]) -> Tuple[str, Optional[str]]:
    """Resolve the per-visitor fingerprint cookie.

    Returns ``(fp_id, set_cookie_value_or_None)``. When the inbound
    cookie is valid we reuse its opaque id and emit ``None`` for the
    set-cookie value (no need to re-issue). When missing/invalid we mint
    a fresh random opaque id and return the signed cookie value so the
    caller can attach it to the response. The id is 22 base64url chars
    (~128 bits of entropy) — no PII, no cross-site identifier.
    """
    fp_id = _verify_fingerprint_cookie(request_cookie or "")
    if fp_id:
        return fp_id, None
    fp_id = _b64url_encode(secrets.token_bytes(16))
    exp_ts = int(time.time()) + _FINGERPRINT_TTL_S
    return fp_id, _sign_fingerprint(fp_id, exp_ts)


def derive_header_fingerprint(user_agent: str, accept_language: str) -> str:
    """Header-only fallback fingerprint used when no signed cookie is
    present (e.g. a bot that strips cookies). Hash of (UA,
    Accept-Language) — coarse but bounds the simplest cookie-stripping
    pattern without burdening real browsers."""
    blob = (user_agent or "")[:512] + "|" + (accept_language or "")[:128]
    return "h:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


async def check_and_increment(
    ip: str,
    user_agent: str = "",
    fingerprint: str = "",
    fingerprint_shared: bool = False,
) -> LimiterDecision:
    """Atomically increment all relevant buckets for this request and
    return whether the request must be denied.

    Failure-mode: if the database is unreachable we *fail open* (return
    ``denied=False``) and log a warning. The public Hakim endpoints
    already short-circuit a forbidden topic or missing AI config before
    they reach the LLM, and the threat model treats this surface as
    abuse-control rather than auth — failing closed would let a transient
    DB blip take the chat offline for everyone.
    """
    now = time.time()
    ip_h = _hash_ip(ip)
    ua_h = _hash_ua(user_agent)
    minute_bucket = int(now // 60)
    day_bucket = int(now // 86400)

    buckets = [
        (f"v1:m:{ip_h}:{minute_bucket}", PER_IP_PER_MINUTE,
         datetime.fromtimestamp((minute_bucket + 2) * 60, tz=timezone.utc),
         60 - int(now % 60)),
        (f"v1:mua:{ip_h}:{ua_h}:{minute_bucket}", PER_IP_UA_PER_MINUTE,
         datetime.fromtimestamp((minute_bucket + 2) * 60, tz=timezone.utc),
         60 - int(now % 60)),
        (f"v1:d:{ip_h}:{day_bucket}", PER_IP_PER_DAY,
         datetime.fromtimestamp((day_bucket + 2) * 86400, tz=timezone.utc),
         86400 - int(now % 86400)),
    ]

    # Second-axis throttle keyed on a non-IP fingerprint so an attacker
    # rotating residential proxies but reusing the same browser session
    # (or the same UA/Accept-Language fallback) still trips a budget.
    # ``fingerprint`` is opaque to this module: cookie-derived ids are
    # prefixed by the caller; header-only fallbacks come prefixed "h:".
    if fingerprint:
        fp_h = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]
        # Cookie-derived fingerprints (one browser session) get a tight
        # cap. Header-derived fingerprints are shared across many real
        # visitors with the same UA/Accept-Language, so they get a much
        # looser cap that only catches sustained cookie-stripping abuse.
        fp_min = PER_FP_SHARED_PER_MINUTE if fingerprint_shared else PER_FP_PER_MINUTE
        fp_day = PER_FP_SHARED_PER_DAY if fingerprint_shared else PER_FP_PER_DAY
        # Use a separate bucket prefix for shared vs cookie keys so a
        # tuning change to one cap can never let cookie-bucket counts
        # leak into shared-bucket reads (and vice versa) via the same key.
        prefix = "fph" if fingerprint_shared else "fpm"
        prefix_d = "fphd" if fingerprint_shared else "fpd"
        buckets.extend([
            (f"v1:{prefix}:{fp_h}:{minute_bucket}", fp_min,
             datetime.fromtimestamp((minute_bucket + 2) * 60, tz=timezone.utc),
             60 - int(now % 60)),
            (f"v1:{prefix_d}:{fp_h}:{day_bucket}", fp_day,
             datetime.fromtimestamp((day_bucket + 2) * 86400, tz=timezone.utc),
             86400 - int(now % 86400)),
        ])

    sql = text(
        """
        INSERT INTO public_hakim_rate_counters (key, count, expires_at)
        VALUES (:key, 1, :expires_at)
        ON CONFLICT (key) DO UPDATE
          SET count = public_hakim_rate_counters.count + 1
        RETURNING count
        """
    )

    try:
        async with async_session_factory() as session:
            decision = LimiterDecision(denied=False)
            for key, limit, expires_at, retry_after in buckets:
                result = await session.execute(
                    sql, {"key": key, "expires_at": expires_at}
                )
                count = int(result.scalar() or 0)
                if count > limit and not decision.denied:
                    decision = LimiterDecision(
                        denied=True,
                        retry_after=max(1, retry_after),
                    )
            await session.commit()

            if random.random() < _CLEANUP_PROB:
                try:
                    await session.execute(
                        text(
                            "DELETE FROM public_hakim_rate_counters "
                            "WHERE expires_at < :now"
                        ),
                        {"now": datetime.now(timezone.utc) - timedelta(minutes=5)},
                    )
                    await session.commit()
                except Exception:  # noqa: BLE001 - cleanup is best-effort
                    await session.rollback()

            return decision
    except Exception as exc:  # noqa: BLE001 - DB unavailable
        # Fail-degraded, NOT fail-open: the shared Postgres store is down,
        # so fall back to a conservative in-process sliding-window limiter
        # so abuse protection survives a DB blip. The fallback is
        # intentionally stricter (and per-process) — it only needs to keep
        # the worst-case blast radius bounded until the DB recovers.
        logger.warning("public_hakim_limiter db unavailable, using in-process fallback: %s", exc)
        return _fallback_check_and_increment(ip, user_agent, fingerprint, fingerprint_shared)


# ---------------------------------------------------------------------------
# In-process fallback limiter
#
# Used only when the Postgres store is unreachable. Intentionally stricter
# than the shared limits because each worker enforces it independently.
# ---------------------------------------------------------------------------
_FALLBACK_PER_IP_PER_MINUTE = 6
_FALLBACK_PER_IP_PER_DAY = 60
_FALLBACK_PER_IP_UA_PER_MINUTE = 4
_FALLBACK_PER_FP_PER_MINUTE = 4
_FALLBACK_PER_FP_PER_DAY = 40
_FALLBACK_PER_FP_SHARED_PER_MINUTE = 40
_FALLBACK_PER_FP_SHARED_PER_DAY = 400
_FALLBACK_MAX_KEYS = 50_000

_fallback_lock = asyncio.Lock()
_fallback_store: Dict[str, List[float]] = defaultdict(list)


def _fallback_check_one(key: str, limit: int, window_s: int, now: float) -> tuple[bool, int]:
    cutoff = now - window_s
    bucket = _fallback_store[key]
    bucket[:] = [t for t in bucket if t > cutoff]
    if len(bucket) >= limit:
        oldest = bucket[0]
        return True, max(1, int(oldest + window_s - now) + 1)
    bucket.append(now)
    return False, 0


def _fallback_check_and_increment(
    ip: str,
    user_agent: str = "",
    fingerprint: str = "",
    fingerprint_shared: bool = False,
) -> LimiterDecision:
    # Sync wrapper since the fallback is per-process and cheap.
    now = time.time()
    ip_h = _hash_ip(ip)
    ua_h = _hash_ua(user_agent)

    # Bounded memory: if the store has blown up, evict aggressively.
    if len(_fallback_store) > _FALLBACK_MAX_KEYS:
        cutoff = now - 86400
        for k in [k for k, v in _fallback_store.items() if not v or v[-1] < cutoff]:
            _fallback_store.pop(k, None)

    checks = [
        (f"fb:m:{ip_h}", _FALLBACK_PER_IP_PER_MINUTE, 60),
        (f"fb:mua:{ip_h}:{ua_h}", _FALLBACK_PER_IP_UA_PER_MINUTE, 60),
        (f"fb:d:{ip_h}", _FALLBACK_PER_IP_PER_DAY, 86400),
    ]
    if fingerprint:
        fp_h = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]
        if fingerprint_shared:
            checks.extend([
                (f"fb:fph:{fp_h}", _FALLBACK_PER_FP_SHARED_PER_MINUTE, 60),
                (f"fb:fphd:{fp_h}", _FALLBACK_PER_FP_SHARED_PER_DAY, 86400),
            ])
        else:
            checks.extend([
                (f"fb:fpm:{fp_h}", _FALLBACK_PER_FP_PER_MINUTE, 60),
                (f"fb:fpd:{fp_h}", _FALLBACK_PER_FP_PER_DAY, 86400),
            ])

    decision = LimiterDecision(denied=False)
    for key, limit, window in checks:
        denied, retry_after = _fallback_check_one(key, limit, window, now)
        if denied and not decision.denied:
            decision = LimiterDecision(denied=True, retry_after=retry_after)
    return decision


__all__ = [
    "LimiterDecision",
    "check_and_increment",
    "PER_IP_PER_MINUTE",
    "PER_IP_PER_DAY",
    "PER_IP_UA_PER_MINUTE",
    "PER_FP_PER_MINUTE",
    "PER_FP_PER_DAY",
    "STREAM_MAX_DURATION_S",
    "STREAM_MAX_CHUNKS",
    "FINGERPRINT_COOKIE_NAME",
    "FINGERPRINT_COOKIE_PATH",
    "FINGERPRINT_COOKIE_MAX_AGE",
    "read_or_mint_fingerprint",
    "derive_header_fingerprint",
]
