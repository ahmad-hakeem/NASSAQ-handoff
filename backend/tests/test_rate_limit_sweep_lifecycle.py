"""Lifecycle wiring for the scheduled rate-limit counter sweep (Task: keep
`rate_limit_counters` bounded without relying on limiter traffic).

The sweep loop itself is exercised end-to-end in
test_distributed_rate_limit.py (expired rows disappear via
``cleanup(force=True)``). These tests pin the *scheduling* contract:

1. The loop invokes the store's forced cleanup on its interval.
2. Cancelling it via the shutdown helper never propagates CancelledError
   (which is a BaseException on Python 3.8+, so a bare ``except Exception``
   around ``await task`` would abort the rest of shutdown).
"""
from __future__ import annotations

import asyncio

import pytest

from app import lifecycle
from middleware import rate_limiter as rl

pytestmark = pytest.mark.asyncio


async def test_sweep_loop_calls_forced_cleanup(monkeypatch):
    calls = []

    async def _fake_cleanup(force: bool = False):
        calls.append(force)
        return 0

    monkeypatch.setattr(rl.rate_store, "cleanup", _fake_cleanup)

    task = asyncio.create_task(
        lifecycle._rate_limit_sweep_loop(initial_delay_s=0, interval_s=0.01)
    )
    try:
        for _ in range(200):
            if len(calls) >= 2:
                break
            await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert len(calls) >= 2, "the loop must sweep repeatedly on its interval"
    assert all(f is True for f in calls), (
        "the scheduled sweep must FORCE the cleanup — the probabilistic path "
        "is exactly what this loop exists to not depend on"
    )


async def test_cancel_helper_absorbs_cancellation():
    """The shutdown path must not let CancelledError escape the await."""
    started = asyncio.Event()

    async def _forever():
        started.set()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise  # same contract as the real loop

    task = asyncio.create_task(_forever())
    await started.wait()

    # Must not raise — a leaked CancelledError here would abort shutdown_tasks
    # midway and skip the remaining cleanup blocks.
    await lifecycle._cancel_background_task(task)
    assert task.cancelled()

    # Idempotent / defensive on edge inputs.
    await lifecycle._cancel_background_task(task)   # already done
    await lifecycle._cancel_background_task(None)   # never scheduled


async def test_sweep_loop_survives_cleanup_errors(monkeypatch):
    """A failing sweep logs and retries; it must not kill the loop."""
    calls = {"n": 0}

    async def _boom(force: bool = False):
        calls["n"] += 1
        raise RuntimeError("db down")

    monkeypatch.setattr(rl.rate_store, "cleanup", _boom)

    task = asyncio.create_task(
        lifecycle._rate_limit_sweep_loop(initial_delay_s=0, interval_s=0.01)
    )
    try:
        for _ in range(200):
            if calls["n"] >= 2:
                break
            await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert calls["n"] >= 2, "the loop must survive sweep errors and keep running"
