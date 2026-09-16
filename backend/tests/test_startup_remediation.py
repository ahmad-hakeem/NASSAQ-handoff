"""Focused startup guards for deferred, best-effort observability setup."""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_observability_init_runs_off_event_loop(monkeypatch) -> None:
    from app import lifecycle

    def slow_sync_initialization() -> None:
        time.sleep(0.15)

    monkeypatch.setattr(
        lifecycle,
        "_init_observability_sync",
        slow_sync_initialization,
    )

    started = time.monotonic()
    task = asyncio.create_task(lifecycle._deferred_observability_init())
    await asyncio.sleep(0)
    elapsed = time.monotonic() - started

    assert elapsed < 0.10
    await task


@pytest.mark.asyncio
async def test_observability_failure_is_warning_only(caplog, monkeypatch) -> None:
    from app import lifecycle

    def failing_initialization() -> None:
        raise RuntimeError("observability unavailable")

    monkeypatch.setattr(lifecycle, "_init_observability_sync", failing_initialization)

    with caplog.at_level(logging.WARNING, logger="nassaq"):
        await lifecycle._deferred_observability_init()

    assert "Observability init skipped" in caplog.text
    assert "observability unavailable" in caplog.text


@pytest.mark.asyncio
async def test_observability_init_cancellation_is_preserved(monkeypatch) -> None:
    from app import lifecycle

    started = threading.Event()
    release = threading.Event()

    def blocking_initialization() -> None:
        started.set()
        release.wait(timeout=1)

    monkeypatch.setattr(
        lifecycle,
        "_init_observability_sync",
        blocking_initialization,
    )

    task = asyncio.create_task(lifecycle._deferred_observability_init())
    await asyncio.to_thread(started.wait, 1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    release.set()
    await asyncio.to_thread(release.wait, 1)


def test_observability_is_deferred_until_after_schema_gate() -> None:
    from app.lifecycle import startup_tasks

    source = inspect.getsource(startup_tasks)
    assert source.index("config.validate()") < source.index("init_pg_tables()")
    assert source.index("init_pg_tables()") < source.index(
        "_schedule_deferred_observability()"
    )


@pytest.mark.asyncio
async def test_startup_waits_for_schema_gate_before_scheduling_observability(
    monkeypatch,
) -> None:
    from app import lifecycle
    from config import config
    from src.core.database import db as database
    from src.core.middleware import query_monitor

    events: list[str] = []
    release_gate = asyncio.Event()
    real_create_task = asyncio.create_task

    async def schema_gate():
        events.append("gate-start")
        await release_gate.wait()
        events.append("gate-end")
        return {"schema_ready": True}

    def schedule_observability():
        events.append("observability-scheduled")

    def no_background_task(coro):
        coro.close()
        return SimpleNamespace(done=lambda: True)

    monkeypatch.setattr(type(config), "ENVIRONMENT", "development")
    monkeypatch.setattr(lifecycle, "init_pg_tables", schema_gate)
    monkeypatch.setattr(lifecycle, "is_replit_managed_deployment", lambda: False)
    monkeypatch.setattr(lifecycle, "schema_verification_is_fatal", lambda **_: False)
    monkeypatch.setattr(database, "ensure_runtime_sequences", lambda: _done())
    monkeypatch.setattr(database, "get_sync_engine", lambda: object())
    monkeypatch.setattr(query_monitor, "install_query_timing", lambda _engine: None)
    monkeypatch.setattr(query_monitor, "start_pool_monitor", lambda _engine: None)
    monkeypatch.setattr(
        lifecycle,
        "_schedule_deferred_observability",
        schedule_observability,
    )

    startup = real_create_task(lifecycle.startup_tasks())
    await asyncio.sleep(0)
    assert events == ["gate-start"]
    assert not startup.done()

    monkeypatch.setattr(asyncio, "create_task", no_background_task)
    release_gate.set()
    await startup

    assert events == ["gate-start", "gate-end", "observability-scheduled"]


async def _done():
    return None