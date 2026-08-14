"""
NASSAQ Rate Limiter Middleware

Cross-worker (distributed) rate limiting for login and other sensitive
endpoints.

Why this is not an in-memory limiter
------------------------------------
The original store kept its sliding window in process memory. Replit
autoscale runs **one uvicorn process per machine and scales to N
machines**, and a load balancer spreads one attacker's requests across
them — so the effective budget was ``limit x instances``. Measured on this
codebase with a 10/60s login limit: 2 processes let 20 attempts through,
4 let 40, 8 let 80. Instances also scale to zero, which silently reset
every counter. Every per-account / per-email / per-user inner limit in the
auth routes shares this same store, so they multiplied the same way.

Design
------
``SharedRateLimitStore`` keeps the counters in Postgres
(``rate_limit_counters``) and increments them atomically with
``INSERT ... ON CONFLICT DO UPDATE ... RETURNING count``, so all workers
and all instances consult one budget.

* **Algorithm** — weighted two-bucket sliding window. Each check reads the
  current and previous bucket and weights the previous one by how much of
  it still overlaps the window:
  ``estimate = prev * (1 - elapsed/window) + current``. A plain fixed
  window would let 2x the limit through across a bucket boundary.
* **Only admitted requests are counted.** The decision and the increment
  happen inside one transaction under a per-key advisory lock, so two
  workers can never both read "9 of 10" and both admit, and a rejected
  attempt does not inflate the counter (which would otherwise push the
  advertised ``Retry-After`` further out on every retry). ``Retry-After``
  is solved from the decay curve, so a client that waits exactly that
  long is admitted.
* **Keys** — the caller's logical key is hashed and prefixed with a
  namespace: ``<namespace>:<sha256[:32]>:<window>:<bucket>``. Callers key
  on IP (middleware), on account/email, on user id, or on token — all of
  them now hold cluster-wide.
* **Failure mode** — fail-degraded, not fail-open. If the shared store is
  unreachable or slower than ``RATE_LIMIT_DB_TIMEOUT_MS``, the check falls
  back to the in-process window (``RateLimitStore``) and logs a warning.
  Protection weakens to the old per-process behaviour instead of
  disappearing, and a DB blip never takes login offline.
* **Flood safety** — a key that was just denied is remembered locally
  until its retry-after passes, so hammering a blocked key costs zero DB
  round-trips (the limiter cannot be turned into a DB amplifier).

Tunables (env): ``RATE_LIMIT_STORE`` (shared|memory),
``RATE_LIMIT_DB_TIMEOUT_MS``, ``RATE_LIMIT_MAX_INFLIGHT``,
``RATE_LIMIT_NAMESPACE``, ``RATE_LIMIT_LOGIN``, ``RATE_LIMIT_WINDOW``.

See ``docs/runbooks/rate-limiting.md``.
"""
import asyncio
import hashlib
import logging
import math
import random
import time
from datetime import datetime, timedelta, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.common.utils.trusted_proxy import extract_client_ip

logger = logging.getLogger("nassaq.ratelimit")


def _now() -> float:
    """Single clock source so tests can freeze time."""
    return time.time()


class RateLimitStore:
    """In-process sliding window.

    Used as the degraded fallback when the shared store is unavailable,
    and as the whole limiter when ``RATE_LIMIT_STORE=memory``. Per-process
    by construction: do not use it as the primary store in production.
    """

    MAX_KEYS = 50_000

    def __init__(self):
        self._store: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        async with self._lock:
            now = _now()
            cutoff = now - window_seconds

            if key in self._store:
                self._store[key] = [t for t in self._store[key] if t > cutoff]
            else:
                if len(self._store) >= self.MAX_KEYS:
                    await self._evict_expired(now)
                    if len(self._store) >= self.MAX_KEYS:
                        return False, max_requests, window_seconds
                self._store[key] = []

            current = len(self._store[key])
            remaining = max(0, max_requests - current)

            if current >= max_requests:
                oldest = min(self._store[key]) if self._store[key] else now
                retry_after = int(oldest + window_seconds - now) + 1
                return True, remaining, retry_after

            self._store[key].append(now)
            remaining = max(0, max_requests - current - 1)
            return False, remaining, window_seconds

    async def _evict_expired(self, now: float):
        expired = [k for k, v in self._store.items() if not v or max(v) < now - 3600]
        for k in expired:
            del self._store[k]

    async def cleanup(self, force: bool = False) -> int:
        """Evict expired local windows. Accepts (and ignores) ``force`` so the
        scheduled sweep loop can call either store polymorphically."""
        async with self._lock:
            now = _now()
            await self._evict_expired(now)
        return 0

    async def forget(self, key: str, window_seconds: int | None = None) -> None:
        """Drop a key's window (operator unblock / test reset)."""
        async with self._lock:
            self._store.pop(key, None)


# Probability that a shared-store check also runs the expired-row sweep.
# This opportunistic path is now a *backstop*: the scheduled background
# loop in app/lifecycle.py (rate-limit counter sweep) is what guarantees
# expired rows are reclaimed even with zero limiter traffic (the deny
# cache deliberately short-circuits repeat hits, so a blocked flood never
# reaches this code path at all).
_CLEANUP_PROB = 0.01
# The sweep deletes in bounded batches so it can never become a load spike
# of its own: at most _SWEEP_BATCH rows per DELETE, at most
# _SWEEP_MAX_BATCHES DELETEs per sweep, each committed separately so locks
# are held only briefly. Leftovers are picked up by the next scheduled run.
_SWEEP_BATCH = 5_000
_SWEEP_MAX_BATCHES = 10
# Don't spam the log while the DB is down; one warning per this many seconds.
_DEGRADE_LOG_COOLDOWN_S = 30.0

# Advisory-lock namespace for the limiter. The two-argument form of
# pg_advisory_xact_lock lives in a different lock space than the
# single-argument (bigint) form other features in this codebase use
# (session finalise sweep, draft-timetable ensure), so limiter locks can
# never make one of their pg_try_advisory_xact_lock calls spuriously fail.
_LOCK_CLASSID = 0x524C  # 'RL'

_LOCK_SQL = "SELECT pg_advisory_xact_lock(:classid, :objid)"

# Decide and increment in ONE statement, under the advisory lock taken by
# the previous statement in the same transaction. READ COMMITTED gives
# this statement a snapshot taken *after* the lock was granted, so it sees
# every committed increment for this key; anyone else is queued behind the
# lock. The INSERT is driven by `decision`, so the counter only ever
# records requests that were actually admitted.
_DECIDE_SQL = """
WITH counts AS (
    SELECT
        COALESCE((SELECT count FROM rate_limit_counters WHERE key = :prev_key), 0) AS prev_count,
        COALESCE((SELECT count FROM rate_limit_counters WHERE key = :cur_key), 0) AS cur_count
),
decision AS (
    SELECT
        prev_count,
        cur_count,
        (prev_count::float8 * :overlap + cur_count + 1) <= :max_requests AS admit
    FROM counts
),
bumped AS (
    INSERT INTO rate_limit_counters (key, count, expires_at)
    SELECT :cur_key, 1, :expires_at FROM decision WHERE decision.admit
    ON CONFLICT (key) DO UPDATE
      SET count = rate_limit_counters.count + 1,
          expires_at = EXCLUDED.expires_at
    RETURNING count
)
SELECT prev_count, cur_count, admit FROM decision
"""


def _seconds_until_admission(prev_count: int, cur_count: int, max_requests: int,
                             window_seconds: int, elapsed: float) -> int:
    """How long until one more request fits under the weighted window.

    Solved from the decay curve rather than guessed, so a client that
    honours ``Retry-After`` is actually admitted on the retry (a naive
    "wait for the bucket to roll" answer is wrong whenever the *current*
    bucket is the one over budget).

    Two regimes:
      A. still inside this bucket — the previous bucket keeps sliding out:
         ``prev * (1 - e/W) + cur + 1 <= max``
      B. after the roll — this bucket becomes the previous one and the new
         current bucket is empty: ``cur * (1 - e2/W) + 1 <= max``
    """
    window = float(window_seconds)
    slack = max_requests - cur_count - 1  # budget left for the decaying prev bucket

    # -- regime A -----------------------------------------------------
    if prev_count > 0 and slack >= 0:
        target_elapsed = window * (1.0 - slack / prev_count)
        if target_elapsed < window:
            return max(1, int(math.ceil(target_elapsed - elapsed - 1e-9)))

    # -- regime B -----------------------------------------------------
    to_roll = window - elapsed
    if cur_count <= 0:
        extra = 0.0
    else:
        extra = max(0.0, window * (1.0 - (max_requests - 1) / cur_count))
    return max(1, int(math.ceil(to_roll + extra - 1e-9)))


class SharedRateLimitStore:
    """Cluster-wide limiter backed by the ``rate_limit_counters`` table.

    Exposes exactly the ``is_rate_limited(key, max, window)`` contract of
    :class:`RateLimitStore` — every existing caller (per-IP middleware,
    per-account login key, per-user refresh/me keys, per-email password
    recovery keys, MFA keys) becomes distributed without changing its
    call site.
    """

    MAX_DENY_KEYS = 50_000

    def __init__(self, local: "RateLimitStore | None" = None, session_factory=None,
                 namespace: str | None = None, timeout_s: float | None = None,
                 max_inflight: int | None = None):
        from config import config as _cfg

        self._local = local or RateLimitStore()
        self._session_factory = session_factory
        self._namespace = namespace if namespace is not None else _cfg.RATE_LIMIT_NAMESPACE
        self.timeout_s = timeout_s if timeout_s is not None else _cfg.RATE_LIMIT_DB_TIMEOUT_MS / 1000.0
        # Hard ceiling on how many pooled connections the limiter can hold at
        # once. `pg_session_middleware` already owns a request-scoped session,
        # so a handler-level check (login/refresh/MFA) is a *nested* checkout;
        # without this cap a flood of unique keys could drain the app pool and
        # turn the limiter into the outage it exists to prevent. Waiters are
        # bounded by `timeout_s` and then degrade to the local window.
        self.max_inflight = max_inflight if max_inflight is not None else _cfg.RATE_LIMIT_MAX_INFLIGHT
        self._inflight = asyncio.Semaphore(self.max_inflight)
        # key -> (deny_until_epoch, retry_after_at_denial)
        self._deny_until: dict[str, tuple[float, int]] = {}
        self._last_degrade_log = 0.0
        self.metrics = {"checks": 0, "denied": 0, "degraded": 0, "short_circuited": 0}

    # -- compatibility surface: callers/tests reach for the local window ---
    @property
    def _store(self) -> dict:
        return self._local._store

    @property
    def _lock(self) -> asyncio.Lock:
        return self._local._lock

    def set_namespace(self, namespace: str) -> None:
        """Repoint the key space (tests isolate themselves this way)."""
        self._namespace = namespace

    async def reset(self) -> None:
        """Drop all local state. Shared rows expire on their own."""
        self._local._store.clear()
        self._deny_until.clear()

    # ---------------------------------------------------------------------
    def _factory(self):
        if self._session_factory is not None:
            return self._session_factory
        from db import async_session_factory
        return async_session_factory

    def _bucket_key(self, key: str, window_seconds: int, bucket: int) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return f"{self._namespace}:{digest}:{window_seconds}:{bucket}"

    def _lock_id(self, key: str, window_seconds: int) -> int:
        """Stable 32-bit advisory-lock id for a logical key.

        A collision only makes two unrelated keys serialise for a few
        milliseconds; it can never mix their counters (those are keyed by
        the full hash).
        """
        digest = hashlib.sha256(f"{self._namespace}:{key}:{window_seconds}".encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big", signed=True)

    def _note_degraded(self, exc: BaseException) -> None:
        self.metrics["degraded"] += 1
        now = _now()
        if now - self._last_degrade_log >= _DEGRADE_LOG_COOLDOWN_S:
            self._last_degrade_log = now
            logger.warning(
                "rate_limiter degraded to in-process fallback "
                "(shared store unavailable, limits are now per-instance): %r", exc,
            )

    async def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        self.metrics["checks"] += 1
        now = _now()
        deny_key = f"{key}|{window_seconds}"

        # 1. Locally remembered denial — answer without touching the DB so a
        #    flood against a blocked key cannot amplify into DB writes.
        cached = self._deny_until.get(deny_key)
        if cached is not None:
            deny_until, _retry = cached
            if deny_until > now:
                self.metrics["short_circuited"] += 1
                self.metrics["denied"] += 1
                return True, 0, max(1, int(deny_until - now) + 1)
            del self._deny_until[deny_key]

        # 2. Shared store, bounded so the auth path can never hang on it.
        try:
            limited, remaining, retry_after = await asyncio.wait_for(
                self._shared_check(key, max_requests, window_seconds, now),
                self.timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 — includes TimeoutError
            self._note_degraded(exc)
            limited, remaining, retry_after = await self._local.is_rate_limited(
                key, max_requests, window_seconds
            )
            if limited:
                self.metrics["denied"] += 1
            return limited, remaining, retry_after

        if limited:
            self.metrics["denied"] += 1
            self._remember_denial(deny_key, now, retry_after)
        return limited, remaining, retry_after

    def _remember_denial(self, deny_key: str, now: float, retry_after: int) -> None:
        if len(self._deny_until) >= self.MAX_DENY_KEYS:
            for k, (until, _r) in list(self._deny_until.items()):
                if until <= now:
                    del self._deny_until[k]
            if len(self._deny_until) >= self.MAX_DENY_KEYS:
                return
        self._deny_until[deny_key] = (now + retry_after, retry_after)

    async def _shared_check(self, key: str, max_requests: int, window_seconds: int,
                            now: float) -> tuple[bool, int, int]:
        from sqlalchemy import text

        bucket = int(now // window_seconds)
        elapsed = now - bucket * window_seconds
        overlap = 1.0 - (elapsed / window_seconds)
        cur_key = self._bucket_key(key, window_seconds, bucket)
        prev_key = self._bucket_key(key, window_seconds, bucket - 1)
        # Keep the row for one extra window so it can still be read as the
        # "previous" bucket, then let the sweep reclaim it.
        expires_at = datetime.fromtimestamp((bucket + 2) * window_seconds, tz=timezone.utc)

        factory = self._factory()
        async with self._inflight:
            async with factory() as session:
                # Serialise every decision for this logical key, cluster-wide.
                # Held until commit, i.e. for the one statement below.
                await session.execute(
                    text(_LOCK_SQL),
                    {"classid": _LOCK_CLASSID, "objid": self._lock_id(key, window_seconds)},
                )
                row = (await session.execute(
                    text(_DECIDE_SQL),
                    {
                        "cur_key": cur_key,
                        "prev_key": prev_key,
                        "expires_at": expires_at,
                        "overlap": overlap,
                        "max_requests": max_requests,
                    },
                )).one()
                await session.commit()

                if random.random() < _CLEANUP_PROB:
                    await self._sweep(session)

        prev_count = int(row[0] or 0)
        cur_count = int(row[1] or 0)
        admitted = bool(row[2])

        seconds_to_bucket_end = int(math.ceil(window_seconds - elapsed)) or 1

        if not admitted:
            retry_after = _seconds_until_admission(
                prev_count, cur_count, max_requests, window_seconds, elapsed
            )
            return True, 0, retry_after

        estimate = prev_count * overlap + cur_count + 1
        remaining = max(0, max_requests - int(math.ceil(estimate)))
        return False, remaining, seconds_to_bucket_end

    async def _sweep(self, session) -> int:
        """Delete expired counter rows in bounded batches.

        Returns the number of rows removed. Best-effort: any error rolls
        back and stops; the next sweep (opportunistic or scheduled) picks
        up where this one left off.
        """
        from sqlalchemy import text
        deleted_total = 0
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
            for _ in range(_SWEEP_MAX_BATCHES):
                res = await session.execute(
                    text(
                        "DELETE FROM rate_limit_counters WHERE key IN ("
                        "  SELECT key FROM rate_limit_counters"
                        "  WHERE expires_at < :now LIMIT :batch"
                        ")"
                    ),
                    {"now": cutoff, "batch": _SWEEP_BATCH},
                )
                await session.commit()
                deleted = getattr(res, "rowcount", 0) or 0
                deleted_total += deleted
                if deleted < _SWEEP_BATCH:
                    break
        except Exception:  # noqa: BLE001 — housekeeping is best-effort
            await session.rollback()
        return deleted_total

    async def forget(self, key: str, window_seconds: int) -> None:
        """Clear one key's budget everywhere: local window, deny cache and the
        shared buckets that still overlap the window.

        This is the operator escape hatch for "unblock this account now", and
        the only correct way for a test to reset a single bucket — popping
        ``_store`` alone leaves the shared counter running.
        """
        from sqlalchemy import text

        await self._local.forget(key)
        self._deny_until.pop(f"{key}|{window_seconds}", None)

        bucket = int(_now() // window_seconds)
        keys = [self._bucket_key(key, window_seconds, bucket + offset) for offset in (-1, 0, 1)]
        try:
            factory = self._factory()
            async with factory() as session:
                await session.execute(
                    text("DELETE FROM rate_limit_counters WHERE key = ANY(:keys)"),
                    {"keys": keys},
                )
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            self._note_degraded(exc)

    async def cleanup(self, force: bool = False) -> int:
        """Sweep expired shared rows (and the local fallback window).

        Returns the number of shared rows removed (0 when the sweep was
        skipped or failed).
        """
        await self._local.cleanup()
        if not force and random.random() >= _CLEANUP_PROB:
            return 0
        try:
            factory = self._factory()
            async with factory() as session:
                return await self._sweep(session)
        except Exception as exc:  # noqa: BLE001
            self._note_degraded(exc)
            return 0


def _build_store():
    from config import config as _cfg
    if _cfg.RATE_LIMIT_STORE == "memory":
        logger.warning(
            "RATE_LIMIT_STORE=memory — rate limits are per-process and will be "
            "multiplied by the number of running instances"
        )
        return RateLimitStore()
    return SharedRateLimitStore()


rate_store = _build_store()

from config import config as _settings

RATE_LIMITS = {
    # Wired to config so environments with legitimate login bursts (the
    # E2E gate signs in dozens of times per minute from one IP) can raise
    # it via RATE_LIMIT_LOGIN / RATE_LIMIT_WINDOW. Prod defaults: 10/60s.
    "/api/auth/login": {"max": _settings.RATE_LIMIT_LOGIN, "window": _settings.RATE_LIMIT_WINDOW},
    "/api/auth/register": {"max": 5, "window": 60},
    "/api/registration-requests": {"max": 10, "window": 60},
    "/api/reports/export": {"max": 10, "window": 120},
    "/api/hakim/analyze": {"max": 5, "window": 60},
    "/api/auth/change-password": {"max": 5, "window": 300},
    # SECURITY (audit H-3): per-IP brute-force/enumeration limit on the
    # password recovery surface. Per-email limits are layered inside the
    # handlers (mirrors the `login_account:` pattern).
    "/api/auth/forgot-password": {"max": 20, "window": 3600},
    "/api/auth/reset-password": {"max": 20, "window": 3600},
    # Parent Communication Center write surfaces. The old hard
    # "3 open requests" cap was removed (it permanently locked parents
    # out when messages never closed); these per-IP burst limits replace
    # it as an anti-abuse throttle, NOT a request quota. POST-only so the
    # sibling GET list endpoints (/absence-excuses, /meeting-requests)
    # that share the prefix are not throttled.
    "/api/parent-portal/quick-message": {"max": 10, "window": 60, "methods": {"POST"}},
    "/api/parent-portal/absence-excuse": {"max": 10, "window": 60, "methods": {"POST"}},
    "/api/parent-portal/meeting-request": {"max": 10, "window": 60, "methods": {"POST"}},
    # ----- Task #169 Step 8 — MFA brute-force / abuse limits ----------
    # These are PER-IP outer limits. Per-identity (per-user, per-challenge)
    # caps are enforced inside the handlers (challenge attempts counter,
    # OTP send budget, recovery-code first-50-rows ceiling, etc.); both
    # layers are required because a single attacker can spread guesses
    # across many accounts but is bounded by their IP, while a credential
    # stuffer rotating IPs is bounded by the per-identity counters.
    "/api/auth/mfa/verify": {"max": 30, "window": 300},
    "/api/auth/mfa/email-otp/send": {"max": 6, "window": 300},
    "/api/auth/mfa/stepup/start": {"max": 30, "window": 300},
    "/api/auth/mfa/stepup/verify": {"max": 30, "window": 300},
    "/api/auth/mfa/webauthn/register/begin": {"max": 20, "window": 300},
    "/api/auth/mfa/webauthn/register/finish": {"max": 20, "window": 300},
    "/api/auth/mfa/webauthn/verify/begin": {"max": 30, "window": 300},
    "/api/auth/mfa/webauthn/verify/finish": {"max": 30, "window": 300},
    "/api/auth/mfa/totp/enroll/begin": {"max": 20, "window": 300},
    "/api/auth/mfa/totp/enroll/confirm": {"max": 20, "window": 300},
    "/api/auth/mfa/recovery-codes/regenerate": {"max": 5, "window": 3600},
    # NDJSON export is platform-admin only, but cap it anyway to prevent
    # accidental loops from hammering the DB.
    "/api/audit/mfa-export": {"max": 10, "window": 3600},
    "/api/audit/mfa-verify-chain": {"max": 30, "window": 3600},
    "/api/teachers/create": {"max": 20, "window": 60},
    "/api/classes/create": {"max": 30, "window": 60},
    "/api/student-wizard/create": {"max": 30, "window": 60},
    "/api/student-wizard/check-parent": {"max": 60, "window": 60},
    "/api/student-wizard/search-parents": {"max": 60, "window": 60},
    # SECURITY (task #438): parent-portal child routes include AI-backed
    # endpoints (insights, weekly-story) that trigger LLM calls on every
    # request.  A per-IP outer limit prevents a single parent account from
    # running a tight loop and burning shared model quota or degrading
    # portal responsiveness for other users.  Per-child AI caching
    # (inside the handler) provides a second, complementary defence.
    #
    # NOTE (2026-05-31 parent-dropdowns audit, Finding 2): this single prefix
    # also covers the cheap read endpoints (analytics, attendance, grades,
    # schedule) that the children hub fans out on every page load (~6 calls).
    # The previous 20/60s cap was tripped by normal bursty browsing (a few
    # page loads / child-switches within a minute returned 429 with blank
    # panels).  Raised to 60/60s: still bounds a scripted tight loop, while
    # the per-child AI cache remains the real defence for the LLM endpoints.
    "/api/parent-portal/child/": {"max": 60, "window": 60},
    # SECURITY (task #446): the Hakim chat endpoint calls the live LLM on
    # every request and was previously unthrottled — any authenticated user
    # could script a tight loop and burn shared model quota.  20 requests
    # per 60 s is generous for interactive chat (≈ 1 message every 3 s)
    # while still bounding the blast radius of a single abusive account.
    # This mirrors the `/api/parent-portal/child/` limit applied in #438.
    "/api/hakim/chat": {"max": 20, "window": 60},
    # SECURITY (task #891): the subject-code suggestion endpoint may issue a
    # live LLM call per request. Per-IP outer cap so a single principal /
    # admin account cannot script a tight loop and burn shared model quota.
    # The deterministic fallback keeps the endpoint usable when AI is off.
    "/api/subjects/hakim-code": {"max": 20, "window": 60},
    # SECURITY (teacher-permissions audit 2026-07-19): POST
    # /hakim/student/{id}/ai-plans issues a live LLM call per request and
    # persists a plan_history row. 5/60s mirrors /api/hakim/analyze. POST-only
    # so the cheap sibling GET reads sharing the prefix (improvement-plan,
    # risk, behaviour, grade-trend, plan-history, longitudinal) stay
    # unthrottled for normal dashboard fan-out.
    "/api/hakim/student/": {"max": 5, "window": 60, "methods": {"POST"}},
    # SECURITY (task #483): per-IP outer caps on the auth hot path.
    # - /api/auth/refresh: bounds refresh-token rotation / family-revocation
    #   probing from an attacker holding a stolen refresh token. 30/60s
    #   leaves plenty of headroom for normal "401 → refresh once → retry"
    #   loops while rejecting tight scripted bursts.
    # - /api/auth/me: bounds hard-refresh / bootstrap storms. The route
    #   does an extra schools lookup per call, so a single tab in a loop
    #   can amplify DB load. 120/60s is generous for legitimate use
    #   (StrictMode double-mount, role-switch re-fetch, occasional poll).
    # Per-identity inner caps (keyed on the token `sub`) live inside the
    # handlers and stack on top of these — see auth_routes_mod.py.
    "/api/auth/refresh": {"max": 30, "window": 60},
    "/api/auth/me": {"max": 120, "window": 60},
}


def get_rate_limiter_health() -> dict:
    """Limiter health snapshot for the /system/metrics monitoring surface.

    Counters are **process-local since boot** — on autoscale each instance
    reports its own sample, so read them as per-instance indicators, never
    sum them into a global total. `degraded > 0` means this instance fell
    back to the per-process window at least once (shared store unreachable
    or slower than RATE_LIMIT_DB_TIMEOUT_MS): brute-force limits were
    per-instance during those checks.
    """
    from config import config as _cfg

    distributed = isinstance(rate_store, SharedRateLimitStore)
    metrics = dict(getattr(rate_store, "metrics", {}) or {})
    checks = metrics.get("checks", 0)
    degraded = metrics.get("degraded", 0)
    last_degrade = getattr(rate_store, "_last_degrade_log", 0.0) or 0.0
    return {
        "store": "shared" if distributed else "memory",
        "distributed": distributed,
        "checks": checks,
        "denied": metrics.get("denied", 0),
        "degraded": degraded,
        "short_circuited": metrics.get("short_circuited", 0),
        "degraded_rate": round(degraded / checks, 4) if checks else 0.0,
        "last_degraded_log_epoch": int(last_degrade) if last_degrade else None,
        "db_timeout_ms": _cfg.RATE_LIMIT_DB_TIMEOUT_MS,
        "scope": "per-instance-since-boot",
    }


def identity_tag(value: str) -> str:
    """Correlatable, non-reversible stand-in for an identity in logs.

    Security logs are high-volume and long-lived; raw email addresses in
    them are a PII leak in their own right. This keeps "same account,
    many attempts" greppable without storing the address.
    """
    return hashlib.sha256((value or "").strip().lower().encode("utf-8")).hexdigest()[:12]


def rate_limit_headers(max_requests: int, remaining: int, retry_after: int,
                       include_retry_after: bool = True) -> dict:
    """Standard rate-limit response headers.

    Shared by the middleware and by the handler-level limits (per-account,
    per-user, per-email) so every 429 in the system looks the same to a
    client.
    """
    headers = {
        "X-RateLimit-Limit": str(max_requests),
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Reset": str(int(_now()) + max(0, int(retry_after))),
    }
    if include_retry_after:
        headers["Retry-After"] = str(max(1, int(retry_after)))
    return headers


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # SECURITY (audit C-1): we used to refuse XFF entirely, which made
        # per-IP limits useless behind Replit's edge (every request collapsed
        # to the proxy IP). The trusted-proxy helper honours XFF only when
        # the immediate peer is itself in the configured allow-list
        # (`TRUSTED_PROXY_CIDRS`); otherwise it falls back to the un-spoofable
        # peer address.
        client_ip = extract_client_ip(request)

        matched_limits = None
        remaining = 0
        reset_in = 0
        for pattern, limits in RATE_LIMITS.items():
            if path.startswith(pattern):
                # Optional method scoping: e.g. throttle POST writes without
                # catching sibling GET reads that share the path prefix
                # (/absence-excuse vs GET /absence-excuses).
                allowed_methods = limits.get("methods")
                if allowed_methods and request.method not in allowed_methods:
                    break
                matched_limits = limits
                key = f"{client_ip}:{pattern}"
                limited, remaining, retry_after = await rate_store.is_rate_limited(
                    key, limits["max"], limits["window"]
                )
                reset_in = retry_after
                if limited:
                    # Observability: one structured line per blocked attempt so
                    # spikes (and the offending IP / surface) are greppable and
                    # alertable. The identity axis (email / user id) is logged by
                    # the handler-level limits in the auth routes.
                    logger.warning(
                        "rate_limit_denied ip=%s method=%s path=%s pattern=%s "
                        "limit=%s window=%ss retry_after=%ss scope=ip",
                        client_ip, request.method, path, pattern,
                        limits["max"], limits["window"], retry_after,
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "success": False,
                            "error": {
                                "code": "RATE_LIMITED",
                                "message": "Too many requests",
                                "message_ar": "عدد الطلبات تجاوز الحد المسموح. يرجى المحاولة لاحقاً",
                            },
                        },
                        headers=rate_limit_headers(limits["max"], 0, retry_after),
                    )
                break

        response = await call_next(request)

        # Never clobber a handler-level 429's headers with this outer per-IP
        # budget: the inner limit (per-account / per-user) is the one the
        # client actually tripped, and mixing the two ("Limit: 30" with the
        # inner Retry-After) gives clients contradictory guidance.
        if matched_limits is not None and "X-RateLimit-Limit" not in response.headers:
            for header, value in rate_limit_headers(
                matched_limits["max"], remaining, reset_in, include_retry_after=False
            ).items():
                response.headers[header] = value

        return response
