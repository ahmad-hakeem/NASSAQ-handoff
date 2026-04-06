"""
NASSAQ — Slow query detection and connection-pool monitoring.

* Hooks into SQLAlchemy ``before_cursor_execute`` / ``after_cursor_execute``
  events and logs any statement that takes longer than ``SLOW_QUERY_THRESHOLD_MS``
  (default 500 ms).
* ``start_pool_monitor`` launches an asyncio background task that logs pool
  stats (size, checked-out, overflow) every ``POOL_LOG_INTERVAL_SEC`` seconds.
* ``get_pool_stats`` returns current pool metrics for the health endpoint.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("nassaq.query_monitor")

SLOW_QUERY_THRESHOLD_MS = 500
POOL_LOG_INTERVAL_SEC = 60

_pool_monitor_task: Optional[asyncio.Task] = None


def install_query_timing(sync_engine: Engine) -> None:
    """Attach before/after cursor-execute listeners to *sync_engine*."""

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        stack = conn.info.get("query_start_time")
        if not stack:
            return
        start = stack.pop()
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms >= SLOW_QUERY_THRESHOLD_MS:
            logger.warning(
                "Slow query detected (%.1f ms): %s | params=%s",
                elapsed_ms,
                statement,
                _safe_params(parameters),
            )


_SENSITIVE_KEYS = frozenset({
    "password", "password_hash", "token", "secret", "api_key",
    "access_token", "refresh_token", "authorization", "credit_card",
})


def _safe_params(params) -> str:
    """Redact sensitive keys and truncate param repr."""
    try:
        if isinstance(params, dict):
            redacted = {
                k: "***" if any(s in k.lower() for s in _SENSITIVE_KEYS) else v
                for k, v in params.items()
            }
            s = repr(redacted)
        else:
            s = repr(params)
        return (s[:300] + "…") if len(s) > 300 else s
    except Exception:
        return "<unprintable>"


def get_pool_stats(sync_engine: Engine) -> Dict[str, Any]:
    """Return current connection-pool metrics."""
    pool = sync_engine.pool
    return {
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checked_in": pool.checkedin(),
        "invalid": pool.status(),
    }


async def _pool_log_loop(sync_engine: Engine) -> None:
    """Periodically log pool statistics."""
    while True:
        await asyncio.sleep(POOL_LOG_INTERVAL_SEC)
        try:
            stats = get_pool_stats(sync_engine)
            logger.info(
                "Pool stats: size=%d checked_out=%d overflow=%d checked_in=%d",
                stats["pool_size"],
                stats["checked_out"],
                stats["overflow"],
                stats["checked_in"],
            )
        except Exception as e:
            logger.debug("Pool stats collection error: %s", e)


def start_pool_monitor(sync_engine: Engine) -> None:
    """Start the background pool-stats logger (call once at startup)."""
    global _pool_monitor_task
    if _pool_monitor_task is None or _pool_monitor_task.done():
        _pool_monitor_task = asyncio.create_task(_pool_log_loop(sync_engine))
        logger.info("Connection-pool monitor started (interval=%ds)", POOL_LOG_INTERVAL_SEC)


def stop_pool_monitor() -> None:
    """Cancel the background task (call on shutdown)."""
    global _pool_monitor_task
    if _pool_monitor_task and not _pool_monitor_task.done():
        _pool_monitor_task.cancel()
        _pool_monitor_task = None
