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
import logging
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from db import async_session_factory

logger = logging.getLogger("nassaq.public_hakim_limiter")


# Limits — intentionally generous enough for legitimate exploration of
# the landing-page chat while bounding cost-abuse / scraping.
PER_IP_PER_MINUTE = 8
PER_IP_PER_DAY = 80
PER_IP_UA_PER_MINUTE = 6

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


async def check_and_increment(ip: str, user_agent: str = "") -> LimiterDecision:
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
        return _fallback_check_and_increment(ip, user_agent)


# ---------------------------------------------------------------------------
# In-process fallback limiter
#
# Used only when the Postgres store is unreachable. Intentionally stricter
# than the shared limits because each worker enforces it independently.
# ---------------------------------------------------------------------------
_FALLBACK_PER_IP_PER_MINUTE = 6
_FALLBACK_PER_IP_PER_DAY = 60
_FALLBACK_PER_IP_UA_PER_MINUTE = 4
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


def _fallback_check_and_increment(ip: str, user_agent: str = "") -> LimiterDecision:
    # Sync wrapper since the fallback is per-process and cheap.
    now = time.time()
    ip_h = _hash_ip(ip)
    ua_h = _hash_ua(user_agent)

    # Bounded memory: if the store has blown up, evict aggressively.
    if len(_fallback_store) > _FALLBACK_MAX_KEYS:
        cutoff = now - 86400
        for k in [k for k, v in _fallback_store.items() if not v or v[-1] < cutoff]:
            _fallback_store.pop(k, None)

    decision = LimiterDecision(denied=False)
    for key, limit, window in (
        (f"fb:m:{ip_h}", _FALLBACK_PER_IP_PER_MINUTE, 60),
        (f"fb:mua:{ip_h}:{ua_h}", _FALLBACK_PER_IP_UA_PER_MINUTE, 60),
        (f"fb:d:{ip_h}", _FALLBACK_PER_IP_PER_DAY, 86400),
    ):
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
    "STREAM_MAX_DURATION_S",
    "STREAM_MAX_CHUNKS",
]
