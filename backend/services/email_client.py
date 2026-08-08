"""NASSAQ — bounded, observable access to the email provider (Resend).

Why this module exists
----------------------
The AI provider audit (see ``services.ai_client``) found the same
unbounded-third-party-call pattern in the email path: ``resend.Emails.send``
was invoked with the SDK's implicit defaults straight inside ``async def``
handlers. Two consequences:

* No explicit, environment-configurable timeout — a slow mail provider held
  the request for as long as the SDK default allowed.
* The *synchronous* SDK ran on the event loop, so one hung send froze the
  whole worker: endpoints with no email involvement stalled behind it.

Everything that talks to the mail provider must therefore go through here:

* ``deliver_resend_email(params, kind=...)`` — the synchronous, bounded,
  observed core used by every template function in
  ``engines.email_service`` in place of a raw ``resend.Emails.send``.
* ``send_email_off_loop(fn, ...)`` — the async offload used by ``async``
  call sites: it runs the (blocking) send in a dedicated worker pool with a
  hard outer ceiling, so the event loop keeps serving other requests and a
  provider outage degrades email only, never the worker.

Configuration (all optional, seconds):
    EMAIL_CONNECT_TIMEOUT_SECONDS   default 5   — TCP/TLS connect
    EMAIL_SEND_TIMEOUT_SECONDS      default 15  — full provider round-trip
    EMAIL_MAX_CONCURRENT_SENDS      default 4   — dedicated worker threads
"""
from __future__ import annotations

import asyncio
import collections
import functools
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("nassaq.email")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
_CONNECT_ENV = ("EMAIL_CONNECT_TIMEOUT_SECONDS", 5.0)
_SEND_ENV = ("EMAIL_SEND_TIMEOUT_SECONDS", 15.0)
_MAX_CONCURRENCY_ENV = ("EMAIL_MAX_CONCURRENT_SENDS", 4)

# Absolute sanity bounds — a misconfigured env var must never reintroduce an
# effectively unbounded call.
_MIN_TIMEOUT_S = 1.0
_MAX_TIMEOUT_S = 120.0


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(f"Invalid {name}={raw!r}; falling back to {default}s")
        return default
    if value <= 0:
        logger.warning(f"Non-positive {name}={raw!r}; falling back to {default}s")
        return default
    return min(max(value, _MIN_TIMEOUT_S), _MAX_TIMEOUT_S)


def resolve_connect_timeout() -> float:
    return _env_float(*_CONNECT_ENV)


def resolve_send_timeout() -> float:
    return _env_float(*_SEND_ENV)


def resolve_max_concurrency() -> int:
    raw = os.environ.get(_MAX_CONCURRENCY_ENV[0], "")
    if not raw:
        return _MAX_CONCURRENCY_ENV[1]
    try:
        return max(1, min(int(raw), 16))
    except (TypeError, ValueError):
        return _MAX_CONCURRENCY_ENV[1]


def timeout_settings() -> Dict[str, Any]:
    """Effective timeout configuration — surfaced by the monitoring endpoint."""
    return {
        "connect_seconds": resolve_connect_timeout(),
        "send_seconds": resolve_send_timeout(),
        "max_concurrent_sends": resolve_max_concurrency(),
    }


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
class EmailProviderError(RuntimeError):
    """A call to the email provider failed in a controlled way."""

    code = "email_provider_error"

    def __init__(
        self,
        message: str,
        *,
        provider: str = "resend",
        kind: str = "generic",
        elapsed_ms: int = 0,
        timeout_s: Optional[float] = None,
        code: Optional[str] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.kind = kind
        self.elapsed_ms = elapsed_ms
        self.timeout_s = timeout_s
        if code:
            self.code = code


class EmailProviderTimeout(EmailProviderError):
    """The provider did not answer within the configured budget."""

    code = "email_provider_timeout"


_TIMEOUT_MARKERS = ("timed out", "timeout", "connecttimeout", "readtimeout")


def map_provider_exception(
    exc: BaseException,
    *,
    kind: str,
    elapsed_ms: int = 0,
    timeout_s: Optional[float] = None,
) -> EmailProviderError:
    """Translate an SDK/transport exception into our structured error type.

    The resend SDK wraps ``requests`` transport failures (including socket
    timeouts) into a generic ``ResendError`` whose message carries the
    original exception text — so timeouts are detected by name *and* by
    message content.
    """
    if isinstance(exc, EmailProviderError):
        return exc
    name = type(exc).__name__
    text = f"{name}: {exc}"
    lowered = str(exc).lower()
    if (
        isinstance(exc, (asyncio.TimeoutError, TimeoutError))
        or name in ("ConnectTimeout", "ReadTimeout", "Timeout")
        or any(marker in lowered for marker in _TIMEOUT_MARKERS)
    ):
        return EmailProviderTimeout(
            text or f"provider did not respond within {timeout_s}s",
            kind=kind, elapsed_ms=elapsed_ms, timeout_s=timeout_s,
        )
    return EmailProviderError(
        text, kind=kind, elapsed_ms=elapsed_ms, timeout_s=timeout_s,
    )


# --------------------------------------------------------------------------
# Metrics (process-local, same model as services.ai_client)
# --------------------------------------------------------------------------
_METRICS_WINDOW = 200
_metrics_lock = threading.Lock()
_totals = {"calls": 0, "successes": 0, "timeouts": 0, "errors": 0}
_by_kind: Dict[str, Dict[str, Any]] = {}

# ---- delivery-health alerting (sliding window over recent outcomes) -------
# 1 = failure (timeout or error), 0 = success. When the failure rate over the
# last _HEALTH_WINDOW sends crosses the threshold (with a minimum number of
# calls so one flaky send can't page anyone), we emit ONE alert — a structured
# ERROR log plus a Sentry event — and latch until the window recovers.
_HEALTH_WINDOW = 50
_recent_outcomes: "collections.deque[int]" = collections.deque(maxlen=_HEALTH_WINDOW)
_alert_latched = False


def resolve_alert_failure_rate() -> float:
    """Failure-rate threshold (0..1] that trips the delivery-health alert."""
    raw = os.environ.get("EMAIL_ALERT_FAILURE_RATE", "")
    try:
        value = float(raw) if raw else 0.25
    except (TypeError, ValueError):
        value = 0.25
    return min(max(value, 0.01), 1.0)


def resolve_alert_min_calls() -> int:
    """Minimum sends in the window before the alert can fire."""
    raw = os.environ.get("EMAIL_ALERT_MIN_CALLS", "")
    try:
        value = int(raw) if raw else 5
    except (TypeError, ValueError):
        value = 5
    return max(1, min(value, _HEALTH_WINDOW))


def _health_snapshot_locked() -> Dict[str, Any]:
    """Delivery health over the sliding window. Caller holds _metrics_lock."""
    window_calls = len(_recent_outcomes)
    window_failures = sum(_recent_outcomes)
    rate = (window_failures / window_calls) if window_calls else 0.0
    threshold = resolve_alert_failure_rate()
    min_calls = resolve_alert_min_calls()
    unhealthy = window_calls >= min_calls and rate >= threshold
    return {
        "status": "degraded" if unhealthy else "ok",
        "window_calls": window_calls,
        "window_failures": window_failures,
        "failure_rate": round(rate, 4),
        "threshold": threshold,
        "min_calls": min_calls,
        "window_size": _HEALTH_WINDOW,
        "alert_active": _alert_latched or unhealthy,
    }


def get_email_health() -> Dict[str, Any]:
    """Public snapshot of delivery health for monitoring/alert endpoints."""
    with _metrics_lock:
        return _health_snapshot_locked()


def _emit_health_alert(snapshot: Dict[str, Any]) -> None:
    message = (
        "Email delivery degraded: "
        f"{snapshot['window_failures']}/{snapshot['window_calls']} recent sends failed "
        f"(rate {snapshot['failure_rate']:.0%} ≥ threshold {snapshot['threshold']:.0%})"
    )
    logger.error(message, extra={"email_health": snapshot})
    try:
        import sentry_sdk

        sentry_sdk.capture_message(message, level="error")
    except Exception:  # pragma: no cover — Sentry is best-effort
        pass


def _bucket(kind: str) -> Dict[str, Any]:
    bucket = _by_kind.get(kind)
    if bucket is None:
        bucket = {
            "calls": 0,
            "successes": 0,
            "timeouts": 0,
            "errors": 0,
            "latencies": collections.deque(maxlen=_METRICS_WINDOW),
        }
        _by_kind[kind] = bucket
    return bucket


def _record(kind: str, outcome: str, elapsed_ms: int) -> None:
    global _alert_latched
    snapshot = None
    with _metrics_lock:
        _totals["calls"] += 1
        _totals[outcome] = _totals.get(outcome, 0) + 1
        bucket = _bucket(kind)
        bucket["calls"] += 1
        bucket[outcome] = bucket.get(outcome, 0) + 1
        bucket["latencies"].append(elapsed_ms)
        _recent_outcomes.append(0 if outcome == "successes" else 1)
        health = _health_snapshot_locked()
        if health["status"] == "degraded":
            if not _alert_latched:
                _alert_latched = True
                snapshot = health  # emit outside the lock
        else:
            _alert_latched = False
    if snapshot is not None:
        _emit_health_alert(snapshot)


def _percentile(values, pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(len(ordered) * pct))
    return float(ordered[idx])


def get_email_metrics() -> Dict[str, Any]:
    """Snapshot of email provider health: counts, timeout rate, latencies."""
    with _metrics_lock:
        totals = dict(_totals)
        health = _health_snapshot_locked()
        kinds = {}
        for key, bucket in _by_kind.items():
            latencies = list(bucket["latencies"])
            kinds[key] = {
                "calls": bucket["calls"],
                "successes": bucket["successes"],
                "timeouts": bucket["timeouts"],
                "errors": bucket["errors"],
                "latency_ms_p50": _percentile(latencies, 0.50),
                "latency_ms_p95": _percentile(latencies, 0.95),
                "latency_ms_max": float(max(latencies)) if latencies else 0.0,
            }
    calls = totals.get("calls", 0)
    failures = totals.get("timeouts", 0) + totals.get("errors", 0)
    return {
        "totals": totals,
        "by_kind": kinds,
        "timeout_rate": round(totals.get("timeouts", 0) / calls, 4) if calls else 0.0,
        "error_rate": round(failures / calls, 4) if calls else 0.0,
        "window": _METRICS_WINDOW,
        "config": timeout_settings(),
        "health": health,
    }


def reset_email_metrics() -> None:
    """Test helper — never called by application code."""
    global _alert_latched
    with _metrics_lock:
        for key in _totals:
            _totals[key] = 0
        _by_kind.clear()
        _recent_outcomes.clear()
        _alert_latched = False


def _request_id() -> str:
    try:
        from middleware.request_tracing import request_id_var

        return request_id_var.get("-")
    except Exception:  # pragma: no cover
        return "-"


def _log_failure(err: EmailProviderError) -> None:
    logger.error(
        f"Email provider {err.code} provider={err.provider} kind={err.kind} "
        f"timeout_s={err.timeout_s} elapsed_ms={err.elapsed_ms} "
        f"request_id={_request_id()}: {err}",
        extra={
            "email_provider": err.provider,
            "email_kind": err.kind,
            "email_error_code": err.code,
            "email_timeout_s": err.timeout_s,
            "email_elapsed_ms": err.elapsed_ms,
        },
    )


# --------------------------------------------------------------------------
# Bounded synchronous core
# --------------------------------------------------------------------------
def _apply_bounded_transport() -> float:
    """Install an explicitly-bounded HTTP client on the resend SDK.

    The SDK routes every request through the module-level
    ``resend.default_http_client`` (default: ``RequestsClient(timeout=30)``,
    not configurable via env). We replace it with one carrying an explicit
    ``(connect, read)`` tuple — ``requests`` accepts tuples — resolved from
    the environment on every send so config changes apply without restart.

    Returns the effective read timeout in seconds.
    """
    import resend
    from resend.http_client_requests import RequestsClient

    connect = resolve_connect_timeout()
    read = resolve_send_timeout()
    resend.default_http_client = RequestsClient(timeout=(connect, read))
    return read


def deliver_resend_email(params: Dict[str, Any], *, kind: str) -> Dict[str, Any]:
    """Send one email through Resend — bounded, mapped and observed.

    Synchronous by design: the template functions in
    ``engines.email_service`` are synchronous (and monkeypatched as such in
    tests); async call sites must go through :func:`send_email_off_loop`
    so this never runs on the event loop.

    Raises :class:`EmailProviderTimeout` / :class:`EmailProviderError`
    instead of leaking SDK internals; records latency and outcome in
    :func:`get_email_metrics`.
    """
    import resend

    timeout_s = _apply_bounded_transport()
    started = time.perf_counter()
    try:
        result = resend.Emails.send(params)
    except BaseException as exc:  # noqa: BLE001 — mapped and re-raised below
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        err = map_provider_exception(
            exc, kind=kind, elapsed_ms=elapsed_ms, timeout_s=timeout_s,
        )
        _record(kind, "timeouts" if isinstance(err, EmailProviderTimeout) else "errors", elapsed_ms)
        _log_failure(err)
        raise err from None

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    _record(kind, "successes", elapsed_ms)
    return result if isinstance(result, dict) else {}


# --------------------------------------------------------------------------
# Async offload — keep the event loop free
# --------------------------------------------------------------------------
# Dedicated worker pool: ``asyncio.to_thread`` uses the loop's *default*
# executor, which the rest of the app relies on — a mail provider hanging
# past its socket timeout would starve unrelated offloaded work. A bounded
# private pool contains the damage to email capacity only.
_executor_lock = threading.Lock()
_email_executor: Optional[ThreadPoolExecutor] = None


def _get_executor() -> ThreadPoolExecutor:
    global _email_executor
    with _executor_lock:
        if _email_executor is None:
            _email_executor = ThreadPoolExecutor(
                max_workers=resolve_max_concurrency(),
                thread_name_prefix="email-send",
            )
        return _email_executor


def _hard_ceiling() -> float:
    """Outer ceiling: connect + read budget plus a small grace margin.

    The transport timeout should fire first (it aborts the socket and frees
    the thread); the ceiling exists so a client that ignores its timeout —
    or a stub in a test — can still never pin the awaiting request.
    """
    return resolve_connect_timeout() + resolve_send_timeout() + 2.0


async def send_email_off_loop(fn: Callable[..., Any], *args, **kwargs) -> Any:
    """Run a blocking email-send function off the event loop, bounded.

    ``fn`` is one of the best-effort ``send_*`` template functions (they
    swallow provider failures and return ``bool``); this wrapper adds the
    off-loop execution and a hard outer ceiling. On ceiling breach or an
    unexpected escape it logs, counts and returns ``False`` — email is
    best-effort everywhere, so degrading is always the right answer here.
    """
    kind = getattr(fn, "__name__", "email_send")
    started = time.perf_counter()
    loop = asyncio.get_running_loop()
    call = functools.partial(fn, *args, **kwargs) if (args or kwargs) else fn
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_get_executor(), call),
            timeout=_hard_ceiling(),
        )
    except asyncio.CancelledError:
        raise
    except BaseException as exc:  # noqa: BLE001 — degraded, never fatal
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        err = map_provider_exception(
            exc, kind=kind, elapsed_ms=elapsed_ms, timeout_s=_hard_ceiling(),
        )
        _record(kind, "timeouts" if isinstance(err, EmailProviderTimeout) else "errors", elapsed_ms)
        _log_failure(err)
        return False
