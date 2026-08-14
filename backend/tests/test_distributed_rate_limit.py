"""Distributed (cross-worker) rate limiting for auth & sensitive endpoints.

Root cause these tests pin down
-------------------------------
``middleware.rate_limiter.RateLimitStore`` kept its sliding window in
process memory. Replit autoscale runs one uvicorn process per machine and
scales to N machines, so a single attacker IP spread across N instances
got N x the intended budget (measured: 2 processes -> 20 allowed for a
10/60s limit, 8 processes -> 80). Every per-account / per-email / per-user
inner limit in the auth routes shares that same store, so they multiplied
too.

The fix is a Postgres-backed shared counter store with the same
``is_rate_limited(key, max, window)`` contract, fail-degrading to the
in-process window when the DB is unreachable.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from db import _get_async_url
from src.core.middleware import rate_limiter as rl
from src.core.middleware.rate_limiter import (
    RATE_LIMITS,
    RateLimitStore,
    SharedRateLimitStore,
    rate_store,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def factory():
    """Loop-local NullPool session factory.

    The shared module-level pool binds asyncpg connections to the loop
    that opened them; pytest-asyncio gives each test a fresh loop, so a
    pooled factory would surface as "attached to a different loop" and
    the limiter would silently degrade to its in-process fallback —
    hiding the very behaviour under test.
    """
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    f = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield f
    finally:
        await engine.dispose()


def _worker(factory, namespace: str) -> SharedRateLimitStore:
    """A store instance modelling one independent backend process."""
    return SharedRateLimitStore(session_factory=factory, namespace=namespace)


async def _spread(workers: list, key: str, attempts: int, limit: int, window: int) -> int:
    """Round-robin `attempts` requests across `workers` (what a load
    balancer does to one attacker IP). Returns how many were allowed."""
    allowed = 0
    for i in range(attempts):
        limited, _remaining, _retry = await workers[i % len(workers)].is_rate_limited(
            key, limit, window
        )
        if not limited:
            allowed += 1
    return allowed


# ---------------------------------------------------------------------------
# 1. The store the app actually uses is the shared one
# ---------------------------------------------------------------------------

async def test_process_global_store_is_shared_by_default():
    assert isinstance(rate_store, SharedRateLimitStore), (
        "the process-global rate_store must be the cross-worker store; "
        "an in-memory store multiplies every limit by the worker count"
    )


async def test_shared_store_keeps_local_store_api_for_existing_callers():
    # Nine route modules and several test fixtures poke `_store` / `_lock`.
    assert isinstance(rate_store._store, dict)
    assert isinstance(rate_store._lock, asyncio.Lock)


# ---------------------------------------------------------------------------
# 2. The bypass is closed: N workers share one budget
# ---------------------------------------------------------------------------

async def test_two_workers_share_one_budget(factory):
    ns = f"t{uuid.uuid4().hex[:12]}"
    workers = [_worker(factory, ns), _worker(factory, ns)]
    allowed = await _spread(workers, "203.0.113.5:/api/auth/login", 30, 10, 60)
    assert allowed == 10, f"two processes let {allowed} attempts through, expected 10"


@pytest.mark.parametrize("n_workers", [1, 2, 4, 8])
async def test_scaling_workers_does_not_change_effective_limit(factory, n_workers):
    ns = f"t{uuid.uuid4().hex[:12]}"
    workers = [_worker(factory, ns) for _ in range(n_workers)]
    allowed = await _spread(workers, "198.51.100.9:/api/auth/login", 10 * n_workers + 5, 10, 60)
    assert allowed == 10


async def test_per_account_key_is_shared_across_workers(factory):
    """An attacker rotating IPs still hits one per-credential budget."""
    ns = f"t{uuid.uuid4().hex[:12]}"
    workers = [_worker(factory, ns) for _ in range(4)]
    allowed = await _spread(workers, "login_account:victim@example.com", 40, 10, 60)
    assert allowed == 10


async def test_distinct_keys_do_not_share_a_budget(factory):
    ns = f"t{uuid.uuid4().hex[:12]}"
    w = _worker(factory, ns)
    for i in range(10):
        limited, _, _ = await w.is_rate_limited("ip-a:/api/auth/login", 10, 60)
        assert not limited
    limited, _, _ = await w.is_rate_limited("ip-b:/api/auth/login", 10, 60)
    assert not limited, "an unrelated key must keep its own budget"


# ---------------------------------------------------------------------------
# 3. Window semantics
# ---------------------------------------------------------------------------

async def test_remaining_counts_down_and_retry_after_is_positive(factory):
    ns = f"t{uuid.uuid4().hex[:12]}"
    w = _worker(factory, ns)
    key = f"{ns}:remaining"
    _, remaining, _ = await w.is_rate_limited(key, 3, 60)
    assert remaining == 2
    _, remaining, _ = await w.is_rate_limited(key, 3, 60)
    assert remaining == 1
    _, remaining, _ = await w.is_rate_limited(key, 3, 60)
    assert remaining == 0
    limited, remaining, retry_after = await w.is_rate_limited(key, 3, 60)
    assert limited and remaining == 0
    # Weighted-window worst case is > one window: when the denial lands at
    # the very start of a bucket (wall-clock minute) with prev_count=0, the
    # earliest admission is after the roll (up to `window`) PLUS the decay
    # of the now-previous bucket — window*(1 - (max-1)/cur) — e.g. +20s for
    # 3/60s. So the honest bound is 2x the window, not window+1.
    assert 1 <= retry_after <= 2 * 60


async def test_window_boundary_does_not_double_the_budget(factory, monkeypatch):
    """A naive fixed-window counter lets 2x the limit through across a
    bucket boundary. The weighted two-bucket window must not."""
    ns = f"t{uuid.uuid4().hex[:12]}"
    w = _worker(factory, ns)
    key = "boundary-ip:/api/auth/login"

    base = (int(time.time()) // 60) * 60
    now = float(base + 55)  # 5s before the bucket rolls over
    monkeypatch.setattr(rl, "_now", lambda: now)
    allowed_first = 0
    for _ in range(10):
        limited, _, _ = await w.is_rate_limited(key, 10, 60)
        allowed_first += 0 if limited else 1
    assert allowed_first == 10

    now = float(base + 61)  # 1s into the next bucket
    allowed_second = 0
    for _ in range(10):
        limited, _, _ = await w.is_rate_limited(key, 10, 60)
        allowed_second += 0 if limited else 1
    assert allowed_second == 0, (
        f"{allowed_second} extra attempts slipped through the window boundary"
    )


async def test_client_that_waits_the_advertised_retry_after_is_admitted(factory, monkeypatch):
    """Retry-After must be a promise, not a guess.

    If rejected attempts were counted, or the retry time were "wait for the
    bucket to roll", a well-behaved client would come back at the advertised
    moment and be rejected again — indefinitely, under a steady retry loop.
    """
    ns = f"t{uuid.uuid4().hex[:12]}"
    w = _worker(factory, ns)
    key = "retry-ip:/api/auth/login"

    base = (int(time.time()) // 60) * 60
    now = float(base + 55)  # deliberately near the boundary
    monkeypatch.setattr(rl, "_now", lambda: now)
    for _ in range(10):
        limited, _, _ = await w.is_rate_limited(key, 10, 60)
        assert not limited
    limited, _, retry_after = await w.is_rate_limited(key, 10, 60)
    assert limited and retry_after >= 1

    now = float(base + 55 + retry_after - 1)
    w._deny_until.clear()
    early, _, _ = await w.is_rate_limited(key, 10, 60)
    assert early, "Retry-After is too short — the budget is not free yet"

    now = float(base + 55 + retry_after)
    w._deny_until.clear()
    on_time, _, _ = await w.is_rate_limited(key, 10, 60)
    assert not on_time, "a client that waited Retry-After was still rejected"


async def test_rejected_attempts_do_not_consume_the_budget(factory):
    """Only admitted requests are counted, so hammering a blocked key
    cannot push its own unblock time further and further out."""
    ns = f"t{uuid.uuid4().hex[:12]}"
    w = _worker(factory, ns)
    key = "nocount-ip:/api/auth/login"

    for _ in range(10):
        await w.is_rate_limited(key, 10, 60)
    for _ in range(5):
        w._deny_until.clear()  # model separate instances / an expired deny cache
        limited, _, _ = await w.is_rate_limited(key, 10, 60)
        assert limited

    async with factory() as s:
        total = (await s.execute(
            text("SELECT COALESCE(sum(count), 0) FROM rate_limit_counters WHERE key LIKE :p"),
            {"p": f"{ns}%"},
        )).scalar()
    assert int(total) == 10, f"counter reached {total}; rejected attempts were counted"


async def test_concurrent_workers_never_exceed_the_budget(factory):
    """The read-decide-increment must be atomic cluster-wide: 8 workers
    firing at once must not all see 'budget left' and all be admitted."""
    ns = f"t{uuid.uuid4().hex[:12]}"
    workers = [_worker(factory, ns) for _ in range(8)]
    key = "race-ip:/api/auth/login"

    results = await asyncio.gather(*[
        workers[i % len(workers)].is_rate_limited(key, 5, 60) for i in range(24)
    ])
    allowed = sum(1 for limited, _, _ in results if not limited)
    assert allowed == 5, f"{allowed} concurrent requests were admitted for a limit of 5"


async def test_limiter_cannot_drain_the_connection_pool(factory):
    """The limiter borrows a connection while the request-scoped session
    already holds one. Its concurrency is capped so a flood of *unique*
    keys (which the deny cache cannot absorb) can never starve the app."""
    live = {"now": 0, "peak": 0}

    class _Tracking:
        def __call__(self):
            outer = self

            class _Ctx:
                async def __aenter__(self_inner):
                    live["now"] += 1
                    live["peak"] = max(live["peak"], live["now"])
                    self_inner._s = factory()
                    return await self_inner._s.__aenter__()

                async def __aexit__(self_inner, *exc):
                    live["now"] -= 1
                    return await self_inner._s.__aexit__(*exc)

            return _Ctx()

    ns = f"t{uuid.uuid4().hex[:12]}"
    w = SharedRateLimitStore(session_factory=_Tracking(), namespace=ns, max_inflight=3)
    await asyncio.gather(*[
        w.is_rate_limited(f"unique-key-{i}", 10, 60) for i in range(30)
    ])
    assert live["peak"] <= 3, f"limiter held {live['peak']} connections at once (cap 3)"


async def test_counter_decays_after_the_window(factory, monkeypatch):
    ns = f"t{uuid.uuid4().hex[:12]}"
    w = _worker(factory, ns)
    key = "decay-ip:/api/auth/login"

    base = (int(time.time()) // 60) * 60
    now = float(base + 1)
    monkeypatch.setattr(rl, "_now", lambda: now)
    for _ in range(10):
        await w.is_rate_limited(key, 10, 60)
    limited, _, _ = await w.is_rate_limited(key, 10, 60)
    assert limited

    now = float(base + 125)  # two full windows later
    w._deny_until.clear()
    limited, _, _ = await w.is_rate_limited(key, 10, 60)
    assert not limited, "the budget must recover once the window has passed"


# ---------------------------------------------------------------------------
# 4. Fail-degraded behaviour (DB down / slow) — never an auth outage
# ---------------------------------------------------------------------------

async def test_falls_back_to_local_window_when_db_unavailable(caplog):
    class _Boom:
        def __call__(self):
            raise RuntimeError("db down")

    w = SharedRateLimitStore(session_factory=_Boom(), namespace="fallback")
    with caplog.at_level(logging.WARNING, logger="nassaq.ratelimit"):
        allowed = 0
        for _ in range(15):
            limited, _, _ = await w.is_rate_limited("ip:/api/auth/login", 10, 60)
            allowed += 0 if limited else 1
    assert allowed == 10, "the in-process fallback must still enforce the limit"
    assert any("degrad" in r.message.lower() or "fallback" in r.message.lower()
               for r in caplog.records), "degradation must be observable in logs"


async def test_slow_db_does_not_hang_the_request(monkeypatch):
    class _Slow:
        def __call__(self):
            raise AssertionError("unused")

    w = SharedRateLimitStore(session_factory=_Slow(), namespace="slow")

    async def _sleepy(*_args, **_kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(w, "_shared_check", _sleepy)
    monkeypatch.setattr(w, "timeout_s", 0.05)
    t0 = time.perf_counter()
    limited, _, _ = await w.is_rate_limited("ip:/api/auth/login", 10, 60)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"limiter blocked the request for {elapsed:.2f}s"
    assert limited is False


async def test_denied_key_short_circuits_without_hitting_the_db(factory):
    """A flood must not amplify into one DB write per attempt."""
    ns = f"t{uuid.uuid4().hex[:12]}"
    w = _worker(factory, ns)
    key = "flood-ip:/api/auth/login"
    for _ in range(11):
        await w.is_rate_limited(key, 10, 60)

    calls = {"n": 0}
    original = w._shared_check

    async def _counting(*args, **kwargs):
        calls["n"] += 1
        return await original(*args, **kwargs)

    w._shared_check = _counting  # type: ignore[assignment]
    for _ in range(20):
        limited, _, _ = await w.is_rate_limited(key, 10, 60)
        assert limited
    assert calls["n"] == 0, f"{calls['n']} DB round-trips during a flood of a blocked key"


# ---------------------------------------------------------------------------
# 5. Housekeeping: the counter table stays bounded
# ---------------------------------------------------------------------------

async def test_expired_counter_rows_are_cleaned_up(factory):
    ns = f"t{uuid.uuid4().hex[:12]}"
    w = _worker(factory, ns)
    await w.is_rate_limited("cleanup-ip:/api/auth/login", 10, 60)

    async with factory() as s:
        rows = (await s.execute(
            text("SELECT count(*) FROM rate_limit_counters WHERE key LIKE :p"),
            {"p": f"{ns}%"},
        )).scalar()
        assert rows and rows >= 1, "the shared counter row must be persisted"

        await s.execute(
            text("UPDATE rate_limit_counters SET expires_at = now() - interval '1 day' "
                 "WHERE key LIKE :p"),
            {"p": f"{ns}%"},
        )
        await s.commit()

    await w.cleanup(force=True)

    async with factory() as s:
        rows = (await s.execute(
            text("SELECT count(*) FROM rate_limit_counters WHERE key LIKE :p"),
            {"p": f"{ns}%"},
        )).scalar()
    assert rows == 0, "expired rows must be swept so the table stays bounded"

async def test_scheduled_sweep_removes_expired_rows_without_limiter_traffic(factory):
    """The background loop's sweep must reclaim expired rows even when the
    limiter itself sees zero traffic (the deny cache short-circuits floods
    against blocked keys, so opportunistic sweeps cannot be relied on)."""
    ns = f"t{uuid.uuid4().hex[:12]}"

    # Seed expired rows directly — no is_rate_limited() call ever happens.
    async with factory() as s:
        for i in range(7):
            await s.execute(
                text("INSERT INTO rate_limit_counters (key, count, expires_at) "
                     "VALUES (:k, 1, now() - interval '1 day')"),
                {"k": f"{ns}:seed{i}:60:0"},
            )
        await s.commit()

    w = _worker(factory, ns)
    deleted = await w.cleanup(force=True)  # what the lifecycle loop calls
    assert deleted >= 7, f"sweep reported {deleted} deletions, expected >= 7"

    async with factory() as s:
        rows = (await s.execute(
            text("SELECT count(*) FROM rate_limit_counters WHERE key LIKE :p"),
            {"p": f"{ns}%"},
        )).scalar()
    assert rows == 0, "scheduled sweep must remove expired rows with zero limiter traffic"
async def test_429_carries_rate_limit_headers(client):
    limit = RATE_LIMITS["/api/auth/register"]["max"]
    last = None
    for _ in range(limit + 1):
        last = await client.post("/auth/register", json={})
    assert last.status_code == 429, f"expected 429 after {limit} attempts, got {last.status_code}"
    assert last.headers.get("X-RateLimit-Limit") == str(limit)
    assert last.headers.get("X-RateLimit-Remaining") == "0"
    assert int(last.headers["X-RateLimit-Reset"]) > int(time.time())
    assert int(last.headers["Retry-After"]) >= 1
    body = last.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RATE_LIMITED"


async def test_allowed_response_carries_rate_limit_headers(client):
    r = await client.post("/auth/login", json={"email": "nobody@nassaq-test.com", "password": "x"})
    assert r.status_code != 429
    assert r.headers.get("X-RateLimit-Limit") == str(RATE_LIMITS["/api/auth/login"]["max"])
    assert "X-RateLimit-Remaining" in r.headers
    assert int(r.headers["X-RateLimit-Reset"]) > int(time.time())


async def test_handler_level_429_headers_survive_the_middleware():
    """Inner (per-account / per-user) limits are stricter than the outer
    per-IP one. The middleware must not repaint their 429 with the outer
    budget, or the client is told 'limit 30, retry in 7s' for a limit of 20.
    """
    import httpx
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse as _JSON
    from starlette.routing import Route

    from src.core.middleware.rate_limiter import RateLimitMiddleware, rate_limit_headers

    async def _inner_limited(_request):
        return _JSON({"detail": "inner"}, status_code=429,
                     headers=rate_limit_headers(20, 0, 7))

    app = Starlette(routes=[Route("/api/auth/refresh", _inner_limited, methods=["POST"])])
    app.add_middleware(RateLimitMiddleware)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/api/auth/refresh")

    assert r.status_code == 429
    assert r.headers["X-RateLimit-Limit"] == "20", "outer per-IP limit overwrote the inner one"
    assert r.headers["Retry-After"] == "7"


# ---------------------------------------------------------------------------
# 7. Coverage of the sensitive-endpoint surface
# ---------------------------------------------------------------------------

async def test_sensitive_auth_surfaces_are_all_throttled():
    required = [
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/change-password",
        "/api/auth/refresh",
        "/api/auth/mfa/verify",
        "/api/auth/mfa/email-otp/send",
    ]
    for path in required:
        assert path in RATE_LIMITS, f"{path} has no rate limit entry"
        assert RATE_LIMITS[path]["max"] >= 1
        assert RATE_LIMITS[path]["window"] >= 60


def test_in_memory_store_remains_available_as_the_fallback():
    """The local window is still a valid object — it is the degraded mode,
    not dead code."""
    assert issubclass(RateLimitStore, object)
    assert hasattr(RateLimitStore(), "is_rate_limited")


# ---------------------------------------------------------------------------
# 7. Monitoring surface — limiter health exposed on /system/metrics
# ---------------------------------------------------------------------------

async def test_health_snapshot_reports_degraded_and_denied_counts():
    class _Boom:
        def __call__(self):
            raise RuntimeError("db down")

    w = SharedRateLimitStore(session_factory=_Boom(), namespace="health")
    for _ in range(12):
        await w.is_rate_limited("ip:/api/auth/login", 10, 60)

    import src.core.middleware.rate_limiter as _rl_mod
    original = _rl_mod.rate_store
    _rl_mod.rate_store = w
    try:
        health = _rl_mod.get_rate_limiter_health()
    finally:
        _rl_mod.rate_store = original

    assert health["store"] == "shared"
    assert health["distributed"] is True
    assert health["checks"] == 12
    assert health["degraded"] == 12, "every failed shared check must count as degraded"
    assert health["denied"] == 2, "the local fallback still denies over-limit checks"
    assert health["degraded_rate"] == 1.0
    assert health["scope"] == "per-instance-since-boot"


def test_health_snapshot_flags_memory_store_as_not_distributed():
    import src.core.middleware.rate_limiter as _rl_mod
    original = _rl_mod.rate_store
    _rl_mod.rate_store = RateLimitStore()
    try:
        health = _rl_mod.get_rate_limiter_health()
    finally:
        _rl_mod.rate_store = original
    assert health["store"] == "memory"
    assert health["distributed"] is False

async def test_sweep_is_bounded_per_batch(factory, monkeypatch):
    """The sweep deletes in bounded batches (LIMITed subselect) so a huge
    backlog cannot turn one sweep into a single giant DELETE."""
    ns = f"t{uuid.uuid4().hex[:12]}"
    async with factory() as s:
        for i in range(5):
            await s.execute(
                text("INSERT INTO rate_limit_counters (key, count, expires_at) "
                     "VALUES (:k, 1, now() - interval '1 day')"),
                {"k": f"{ns}:batch{i}:60:0"},
            )
        await s.commit()

    # Shrink the batch so 5 rows require multiple bounded DELETEs.
    monkeypatch.setattr(rl, "_SWEEP_BATCH", 2)
    w = _worker(factory, ns)
    deleted = await w.cleanup(force=True)
    assert deleted >= 5

    async with factory() as s:
        rows = (await s.execute(
            text("SELECT count(*) FROM rate_limit_counters WHERE key LIKE :p"),
            {"p": f"{ns}%"},
        )).scalar()
    assert rows == 0

    # A backlog larger than batch*max_batches is left for the next run —
    # the ceiling is what keeps the sweep from ever being a load spike.
    assert rl._SWEEP_MAX_BATCHES * rl._SWEEP_BATCH < 10**6
