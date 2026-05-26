"""Automated tests for the public Hakim abuse limiter (task #676).

These pin down three things that were previously verified only by hand:

1. ``backend/utils/public_hakim_limiter.check_and_increment`` actually
   writes Postgres counter rows, flips ``denied=True`` once a bucket
   exceeds its configured ceiling, and that the in-handler opportunistic
   cleanup deletes rows whose ``expires_at`` is in the past.
2. The JSON route ``POST /api/public/hakim/chat`` translates a limiter
   denial into the canonical localized safe-error ``HakimResponse``
   (HTTP 200, not a raw 429) so the chat UI degrades gracefully.
3. The streaming route ``POST /api/public/hakim/chat/stream`` translates
   a limiter denial into a single NDJSON safe-error chunk followed by a
   ``done`` event, with the ``Retry-After`` header set; and that the
   in-loop ``STREAM_MAX_CHUNKS`` cap stops emission and reports
   ``truncated: true`` on the final ``done`` event.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from db import _get_async_url
from routes import ai_routes_mod
from utils import public_hakim_limiter
from utils.public_hakim_limiter import (
    LimiterDecision,
    PER_IP_PER_MINUTE,
    PER_IP_UA_PER_MINUTE,
    check_and_increment,
)


@pytest_asyncio.fixture
async def fresh_factory(monkeypatch):
    """Per-test session factory bound to the current event loop.

    ``utils.public_hakim_limiter`` reaches into ``db.async_session_factory``
    at call time, but that module-level factory is built on a shared
    engine whose pooled asyncpg connections are tied to the event loop
    that first opened them. pytest-asyncio creates a new loop per test,
    so re-using the shared pool across tests would surface as cryptic
    ``Event loop is closed`` / ``attached to a different loop`` errors
    and the limiter would silently degrade to its in-process fallback.
    Patching the limiter to use a NullPool factory keeps every test
    talking to the real Postgres counters under test.
    """
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(public_hakim_limiter, "async_session_factory", factory)
    try:
        yield factory
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_ip() -> str:
    """A unique RFC 5737 documentation-range IP per test invocation.

    The limiter hashes the IP, so the bucket key is unique per call —
    that keeps tests independent of any other limiter activity that
    might happen to share the wall-clock minute / day.
    """
    n = random.randint(0, 0xFFFF)
    return f"203.0.113.{n & 0xFF}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# 1. Limiter unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_limiter_increments_postgres_counter_rows(fresh_factory):
    ip = _unique_ip()
    decision = await check_and_increment(ip, "ua-x")
    assert decision.denied is False
    # The minute, minute+UA, and daily bucket should all be present.
    async with fresh_factory() as s:
        res = await s.execute(
            text(
                "SELECT key, count FROM public_hakim_rate_counters "
                "WHERE key LIKE :pat"
            ),
            # Hash is deterministic for an IP, so we can locate this
            # call's rows by the IP hash prefix used in the bucket key.
            {"pat": f"%{public_hakim_limiter._hash_ip(ip)}%"},
        )
        rows = res.fetchall()
    assert len(rows) == 3, rows
    assert {int(r[1]) for r in rows} == {1}


@pytest.mark.asyncio
async def test_limiter_flips_denied_after_per_ip_minute_threshold(fresh_factory):
    """The per-IP / per-minute bucket is the smallest of the three, so
    we cross it first by varying the user agent (so the per-IP+UA
    bucket never trips before the per-IP one does)."""
    ip = _unique_ip()
    # Up to and including the limit are allowed.
    for i in range(PER_IP_PER_MINUTE):
        d = await check_and_increment(ip, f"ua-{i}")
        assert d.denied is False, f"unexpected denial at iteration {i}"
    # The next call MUST flip to denied with a sane retry hint.
    d = await check_and_increment(ip, "ua-final")
    assert d.denied is True
    assert d.retry_after is not None and 1 <= d.retry_after <= 120


@pytest.mark.asyncio
async def test_limiter_per_ip_ua_bucket_trips_independently(fresh_factory):
    """Hammering the same IP + UA must trip the (smaller) per-IP+UA
    bucket first — proves all three bucket keys are wired."""
    ip = _unique_ip()
    ua = "scraper/1.0"
    for i in range(PER_IP_UA_PER_MINUTE):
        d = await check_and_increment(ip, ua)
        assert d.denied is False, f"unexpected denial at iteration {i}"
    d = await check_and_increment(ip, ua)
    assert d.denied is True


@pytest.mark.asyncio
async def test_limiter_cleanup_deletes_expired_rows(fresh_factory):
    """The opportunistic cleanup inside ``check_and_increment`` deletes
    rows whose ``expires_at`` is older than 5 minutes."""
    expired_key = f"v1:m:test-expired-{uuid.uuid4().hex[:10]}:0"
    async with fresh_factory() as s:
        await s.execute(
            text(
                "INSERT INTO public_hakim_rate_counters (key, count, expires_at) "
                "VALUES (:k, 1, :exp)"
            ),
            {
                "k": expired_key,
                "exp": datetime.now(timezone.utc) - timedelta(hours=2),
            },
        )
        await s.commit()

    # Force the cleanup branch (normally probability-gated at 1%).
    with patch.object(public_hakim_limiter.random, "random", return_value=0.0):
        await check_and_increment(_unique_ip(), "ua-cleanup")

    async with fresh_factory() as s:
        res = await s.execute(
            text("SELECT 1 FROM public_hakim_rate_counters WHERE key = :k"),
            {"k": expired_key},
        )
        assert res.first() is None, "expired counter row should have been deleted"


# ---------------------------------------------------------------------------
# 2. JSON route — denied -> localized safe-error HakimResponse
# ---------------------------------------------------------------------------


def _deny(retry_after: int = 30):
    async def _fake(*_a, **_k):
        return LimiterDecision(denied=True, retry_after=retry_after)
    return _fake


@pytest.mark.asyncio
async def test_public_hakim_chat_json_returns_safe_error_envelope_on_denial(client):
    with patch.object(
        ai_routes_mod, "_public_hakim_check_and_increment", _deny(retry_after=42)
    ):
        resp = await client.post(
            "/public/hakim/chat",
            json={"message": "مرحبا", "locale": "ar"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Canonical localized Arabic safe-error envelope, plus suggestions.
    assert body["response"] == ai_routes_mod._PUBLIC_HAKIM_ERROR["ar"]
    assert isinstance(body.get("suggestions"), list) and body["suggestions"]


@pytest.mark.asyncio
async def test_public_hakim_chat_json_returns_english_safe_error_when_locale_en(client):
    with patch.object(
        ai_routes_mod, "_public_hakim_check_and_increment", _deny()
    ):
        resp = await client.post(
            "/public/hakim/chat",
            json={"message": "hello", "locale": "en"},
        )
    assert resp.status_code == 200
    assert resp.json()["response"] == ai_routes_mod._PUBLIC_HAKIM_ERROR["en"]


# ---------------------------------------------------------------------------
# 3. Streaming route — denied -> safe-error NDJSON + done + Retry-After
# ---------------------------------------------------------------------------


def _parse_ndjson(body: str) -> list[dict]:
    return [json.loads(line) for line in body.splitlines() if line.strip()]


@pytest.mark.asyncio
async def test_public_hakim_chat_stream_denied_emits_safe_error_and_retry_after(client):
    with patch.object(
        ai_routes_mod, "_public_hakim_check_and_increment", _deny(retry_after=17)
    ):
        resp = await client.post(
            "/public/hakim/chat/stream",
            json={"message": "مرحبا", "locale": "ar"},
        )
    assert resp.status_code == 200
    assert resp.headers.get("retry-after") == "17"
    assert resp.headers.get("content-type", "").startswith("application/x-ndjson")
    events = _parse_ndjson(resp.text)
    assert len(events) == 2
    assert events[0] == {
        "type": "chunk",
        "text": ai_routes_mod._PUBLIC_HAKIM_ERROR["ar"],
    }
    assert events[1]["type"] == "done"
    assert isinstance(events[1].get("suggestions"), list)


# ---------------------------------------------------------------------------
# Streaming truncation: STREAM_MAX_CHUNKS cap stops emission and reports
# truncated: true on the final `done` event.
# ---------------------------------------------------------------------------


class _FakeStream:
    """Iterable that yields many chunk-shaped events — enough to trip
    the chunk-cap guard inside the streaming handler."""

    def __init__(self, n: int):
        self._n = n

    def __iter__(self):
        for _ in range(self._n):
            class _Delta:
                content = "x"

            class _Choice:
                delta = _Delta()

            class _Event:
                choices = [_Choice()]

            yield _Event()

    def close(self):  # mirrors the OpenAI SDK surface used by the route
        pass


class _FakeCompletions:
    def __init__(self, n: int):
        self._n = n

    def create(self, **_kwargs):
        return _FakeStream(self._n)


class _FakeChat:
    def __init__(self, n: int):
        self.completions = _FakeCompletions(n)


class _FakeClient:
    def __init__(self, n: int = 50):
        self._n = n
        self.chat = _FakeChat(n)

    def with_options(self, **_kwargs):
        # The handler calls ``client.with_options(timeout=...)`` before
        # ``chat.completions.create`` — return self so the chain works.
        return self


@pytest.mark.asyncio
async def test_public_hakim_chat_stream_truncates_at_chunk_cap(client, monkeypatch):
    # Squeeze the chunk cap down so we can hit it without faking
    # hundreds of events. The route reads the constant via the imported
    # alias on the routes module, so we patch *there*.
    monkeypatch.setattr(ai_routes_mod, "_PUBLIC_HAKIM_STREAM_MAX_CHUNKS", 3)
    monkeypatch.setattr(
        ai_routes_mod, "get_openai_client", lambda: _FakeClient(n=50)
    )
    # Pass the limiter check (no denial).
    monkeypatch.setattr(
        ai_routes_mod,
        "_public_hakim_check_and_increment",
        lambda *_a, **_k: _coro(LimiterDecision(denied=False)),
    )

    resp = await client.post(
        "/public/hakim/chat/stream",
        json={"message": "hi", "locale": "en"},
    )
    assert resp.status_code == 200
    events = _parse_ndjson(resp.text)
    chunk_events = [e for e in events if e.get("type") == "chunk"]
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(chunk_events) == 3, events
    assert len(done_events) == 1
    assert done_events[0].get("truncated") is True


async def _coro(value):
    """Tiny helper: build a coroutine that resolves to ``value`` so we
    can patch ``_public_hakim_check_and_increment`` with a plain lambda."""
    return value


# ---------------------------------------------------------------------------
# Streaming truncation: STREAM_MAX_DURATION_S wall-clock cap stops emission
# independently of the chunk cap and reports truncated: true on done.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_hakim_chat_stream_truncates_at_duration_cap(client, monkeypatch):
    # Keep the chunk cap well out of the way so this test exercises the
    # *wall-clock* guard exclusively.
    monkeypatch.setattr(ai_routes_mod, "_PUBLIC_HAKIM_STREAM_MAX_CHUNKS", 9999)
    monkeypatch.setattr(ai_routes_mod, "_PUBLIC_HAKIM_STREAM_MAX_DURATION_S", 1.0)

    # Deterministic clock: first call is `started`, second is below the
    # cap (one chunk emitted), third is way over (loop breaks).
    fake_clock = iter([0.0, 0.25, 5.0, 5.0, 5.0, 5.0])

    class _Clock:
        def monotonic(self):
            try:
                return next(fake_clock)
            except StopIteration:
                return 5.0

    monkeypatch.setattr(ai_routes_mod, "_time", _Clock())
    monkeypatch.setattr(
        ai_routes_mod, "get_openai_client", lambda: _FakeClient(n=50)
    )
    monkeypatch.setattr(
        ai_routes_mod,
        "_public_hakim_check_and_increment",
        lambda *_a, **_k: _coro(LimiterDecision(denied=False)),
    )

    resp = await client.post(
        "/public/hakim/chat/stream",
        json={"message": "hi", "locale": "en"},
    )
    assert resp.status_code == 200
    events = _parse_ndjson(resp.text)
    chunk_events = [e for e in events if e.get("type") == "chunk"]
    done_events = [e for e in events if e.get("type") == "done"]
    # The duration guard fires inside the loop *before* yielding the
    # next chunk, so at most one chunk made it through.
    assert len(chunk_events) <= 1, events
    assert len(done_events) == 1
    assert done_events[0].get("truncated") is True
