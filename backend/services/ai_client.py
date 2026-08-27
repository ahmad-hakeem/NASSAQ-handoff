"""NASSAQ — bounded, observable access to external AI providers.

Why this module exists
----------------------
Every OpenAI call used to be made with a client built as
``OpenAI(api_key=..., base_url=...)`` — no ``timeout``, no ``max_retries`` —
and the *synchronous* SDK was invoked straight inside ``async def`` handlers.
Two consequences, both audited on 2026-07-30:

* The SDK default is ``Timeout(connect=5, read=600, write=600, pool=600)`` with
  ``max_retries=2``: a hung provider could hold one call for ~30 minutes.
* Because the blocking SDK ran on the event loop, that hung call froze the
  *whole* worker — endpoints with no AI involvement stalled behind it. That is
  the cascading failure a per-call timeout alone would not have prevented.

Everything that talks to a provider must therefore go through here:

    client = build_openai_client(purpose=PURPOSE_INTERACTIVE)
    response = await ai_chat_completion(client, purpose=PURPOSE_INTERACTIVE,
                                        model=..., messages=[...])

``build_openai_client`` bakes an explicit, environment-configurable timeout
into the transport; ``ai_chat_completion`` offloads the blocking call to a
worker thread, puts a hard ceiling on it, maps failures onto structured errors
and records metrics. Streaming responses keep their own duration caps but must
still be built from a factory client.

Configuration (all optional, seconds):
    AI_CONNECT_TIMEOUT_SECONDS      default 10   — TCP/TLS connect
    AI_REQUEST_TIMEOUT_SECONDS      default 60   — synchronous UI-facing calls
    AI_BACKGROUND_TIMEOUT_SECONDS   default 180  — long generations (plans/reports)
    AI_STREAM_TIMEOUT_SECONDS       default 120  — streamed replies
    AI_MAX_RETRIES                  default 1    — SDK-level retries per call
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

logger = logging.getLogger("nassaq.ai")

# --------------------------------------------------------------------------
# Purposes & configuration
# --------------------------------------------------------------------------
PURPOSE_INTERACTIVE = "interactive"
PURPOSE_BACKGROUND = "background"
PURPOSE_STREAM = "stream"

_PURPOSE_ENV = {
    PURPOSE_INTERACTIVE: ("AI_REQUEST_TIMEOUT_SECONDS", 60.0),
    PURPOSE_BACKGROUND: ("AI_BACKGROUND_TIMEOUT_SECONDS", 180.0),
    PURPOSE_STREAM: ("AI_STREAM_TIMEOUT_SECONDS", 120.0),
}

_CONNECT_ENV = ("AI_CONNECT_TIMEOUT_SECONDS", 10.0)
_MAX_RETRIES_ENV = ("AI_MAX_RETRIES", 1)
_MAX_CONCURRENCY_ENV = ("AI_MAX_CONCURRENT_CALLS", 8)

DEFAULT_MODEL = os.environ.get("AI_MODEL") or os.environ.get("OPENAI_MODEL") or os.environ.get("AI_INTEGRATIONS_OPENAI_MODEL") or "gemini-3.5-flash"


def resolve_model(override: Optional[str] = None) -> str:
    """Resolve effective AI model (env override or default)."""
    env_model = os.environ.get("AI_MODEL") or os.environ.get("OPENAI_MODEL") or os.environ.get("AI_INTEGRATIONS_OPENAI_MODEL")
    if env_model:
        return env_model
    if override and override != "gpt-5-mini":
        return override
    return DEFAULT_MODEL

# Absolute sanity bounds — a misconfigured env var must never reintroduce an
# effectively unbounded call.
_MIN_TIMEOUT_S = 1.0
_MAX_TIMEOUT_S = 600.0


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


def resolve_timeout(purpose: str = PURPOSE_INTERACTIVE,
                    override: Optional[float] = None) -> float:
    """Seconds a single provider call may take. Explicit override wins."""
    if override is not None:
        try:
            value = float(override)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return min(value, _MAX_TIMEOUT_S)
    env_name, default = _PURPOSE_ENV.get(purpose, _PURPOSE_ENV[PURPOSE_INTERACTIVE])
    return _env_float(env_name, default)


def resolve_connect_timeout() -> float:
    return _env_float(*_CONNECT_ENV)


def resolve_max_concurrency() -> int:
    raw = os.environ.get(_MAX_CONCURRENCY_ENV[0], "")
    if not raw:
        return _MAX_CONCURRENCY_ENV[1]
    try:
        return max(1, min(int(raw), 64))
    except (TypeError, ValueError):
        return _MAX_CONCURRENCY_ENV[1]


def resolve_max_retries() -> int:
    raw = os.environ.get(_MAX_RETRIES_ENV[0], "")
    if not raw:
        return _MAX_RETRIES_ENV[1]
    try:
        return max(0, min(int(raw), 2))
    except (TypeError, ValueError):
        return _MAX_RETRIES_ENV[1]


def timeout_settings() -> Dict[str, Any]:
    """Effective timeout configuration — surfaced by the monitoring endpoint."""
    return {
        "connect_seconds": resolve_connect_timeout(),
        "interactive_seconds": resolve_timeout(PURPOSE_INTERACTIVE),
        "background_seconds": resolve_timeout(PURPOSE_BACKGROUND),
        "stream_seconds": resolve_timeout(PURPOSE_STREAM),
        "max_retries": resolve_max_retries(),
        "max_concurrent_calls": resolve_max_concurrency(),
    }


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
#: Shown to end users when the provider is slow or unavailable.
AI_DEGRADED_MESSAGE_AR = "خدمة الذكاء الاصطناعي بطيئة حالياً. يرجى المحاولة بعد قليل."
AI_DEGRADED_MESSAGE_EN = "The AI service is currently slow. Please try again shortly."


class AIProviderError(RuntimeError):
    """A call to an external AI provider failed in a controlled way."""

    code = "ai_provider_error"

    def __init__(
        self,
        message: str,
        *,
        provider: str = "openai",
        endpoint: str = "chat.completions",
        model: Optional[str] = None,
        elapsed_ms: int = 0,
        timeout_s: Optional[float] = None,
        code: Optional[str] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.endpoint = endpoint
        self.model = model
        self.elapsed_ms = elapsed_ms
        self.timeout_s = timeout_s
        if code:
            self.code = code

    def payload(self, language: str = "ar") -> Dict[str, Any]:
        """Controlled, bounded body for a degraded AI response."""
        return {
            "success": False,
            "error_code": self.code,
            "error": AI_DEGRADED_MESSAGE_AR if language == "ar" else AI_DEGRADED_MESSAGE_EN,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "elapsed_ms": self.elapsed_ms,
        }


class AIProviderTimeout(AIProviderError):
    """The provider did not answer within the configured budget."""

    code = "ai_provider_timeout"


class AIProviderRateLimited(AIProviderError):
    """The provider rejected the call because we are over its quota."""

    code = "ai_provider_rate_limited"


# --------------------------------------------------------------------------
# Metrics (process-local, same model as middleware.request_tracing)
# --------------------------------------------------------------------------
_METRICS_WINDOW = 200
_metrics_lock = threading.Lock()
_totals = {"calls": 0, "successes": 0, "timeouts": 0, "errors": 0}
_by_endpoint: Dict[str, Dict[str, Any]] = {}


def _bucket(key: str) -> Dict[str, Any]:
    bucket = _by_endpoint.get(key)
    if bucket is None:
        bucket = {
            "calls": 0,
            "successes": 0,
            "timeouts": 0,
            "errors": 0,
            "latencies": collections.deque(maxlen=_METRICS_WINDOW),
        }
        _by_endpoint[key] = bucket
    return bucket


def _record(provider: str, endpoint: str, outcome: str, elapsed_ms: int) -> None:
    key = f"{provider}:{endpoint}"
    with _metrics_lock:
        _totals["calls"] += 1
        _totals[outcome] = _totals.get(outcome, 0) + 1
        bucket = _bucket(key)
        bucket["calls"] += 1
        bucket[outcome] = bucket.get(outcome, 0) + 1
        bucket["latencies"].append(elapsed_ms)


def _percentile(values, pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(len(ordered) * pct))
    return float(ordered[idx])


def get_ai_metrics() -> Dict[str, Any]:
    """Snapshot of AI provider health: counts, timeout rate, latency spread."""
    with _metrics_lock:
        totals = dict(_totals)
        endpoints = {}
        for key, bucket in _by_endpoint.items():
            latencies = list(bucket["latencies"])
            endpoints[key] = {
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
        "by_endpoint": endpoints,
        "timeout_rate": round(totals.get("timeouts", 0) / calls, 4) if calls else 0.0,
        "error_rate": round(failures / calls, 4) if calls else 0.0,
        "window": _METRICS_WINDOW,
        "config": timeout_settings(),
    }


def reset_ai_metrics() -> None:
    """Test helper — never called by application code."""
    with _metrics_lock:
        for key in _totals:
            _totals[key] = 0
        _by_endpoint.clear()


# --------------------------------------------------------------------------
# Client factory
# --------------------------------------------------------------------------
def _timeout_object(purpose: str, override: Optional[float]):
    """httpx.Timeout with every phase bounded (never ``None``)."""
    read = resolve_timeout(purpose, override)
    connect = min(resolve_connect_timeout(), read)
    try:
        import httpx

        return httpx.Timeout(read, connect=connect, read=read, write=read, pool=read)
    except Exception:  # pragma: no cover — httpx ships with the SDK
        return read


def build_openai_client(
    purpose: str = PURPOSE_INTERACTIVE,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
):
    """Build an OpenAI client with an explicit, bounded transport timeout.

    Returns ``None`` when no API key is configured, so callers keep their
    existing "AI not configured" behaviour instead of raising.
    """
    key = api_key if api_key is not None else (
        os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    )
    if not key:
        return None
    url = base_url if base_url is not None else (
        os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "") or os.environ.get("OPENAI_BASE_URL", "")
    )
    try:
        from openai import OpenAI

        return OpenAI(
            api_key=key,
            base_url=url or None,
            timeout=_timeout_object(purpose, timeout),
            max_retries=resolve_max_retries(),
        )
    except Exception as exc:
        logger.error(f"Failed to build OpenAI client (purpose={purpose}): {exc}")
        return None


# --------------------------------------------------------------------------
# Bounded, non-blocking call
# --------------------------------------------------------------------------
def _hard_ceiling(timeout_s: float) -> float:
    """Outer ceiling: a little beyond the transport timeout.

    The SDK's own timeout should fire first (it aborts the socket and frees the
    thread); the ceiling exists so a client that ignores its timeout — or a
    stub in a test — can still never pin the awaiting request.
    """
    return timeout_s + min(2.0, max(0.25, timeout_s * 0.2))


# Dedicated worker pool. ``asyncio.to_thread`` uses the loop's *default*
# executor, which the rest of the app also relies on — a provider that hangs
# past its socket timeout would keep those threads busy and starve unrelated
# offloaded work. Giving AI calls their own bounded pool contains the damage:
# a provider outage can only exhaust AI capacity, and the outer ``wait_for``
# still returns a fast 503 to every caller queued behind it.
_executor_lock = threading.Lock()
_ai_executor: Optional[ThreadPoolExecutor] = None


def _get_executor() -> ThreadPoolExecutor:
    global _ai_executor
    with _executor_lock:
        if _ai_executor is None:
            _ai_executor = ThreadPoolExecutor(
                max_workers=resolve_max_concurrency(),
                thread_name_prefix="ai-call",
            )
        return _ai_executor


def _request_id() -> str:
    try:
        from src.core.middleware.request_tracing import request_id_var

        return request_id_var.get("-")
    except Exception:  # pragma: no cover
        return "-"


def _log_failure(err: AIProviderError, purpose: str) -> None:
    logger.error(
        f"AI provider {err.code} provider={err.provider} endpoint={err.endpoint} "
        f"model={err.model} purpose={purpose} timeout_s={err.timeout_s} "
        f"elapsed_ms={err.elapsed_ms} request_id={_request_id()}: {err}",
        extra={
            "ai_provider": err.provider,
            "ai_endpoint": err.endpoint,
            "ai_model": err.model,
            "ai_purpose": purpose,
            "ai_error_code": err.code,
            "ai_timeout_s": err.timeout_s,
            "ai_elapsed_ms": err.elapsed_ms,
        },
    )
    try:
        from services.observability import capture_ai_failure

        capture_ai_failure(err, purpose=purpose, request_id=_request_id())
    except Exception:  # pragma: no cover — observability must never break a request
        pass


async def ai_chat_completion(
    client,
    *,
    purpose: str = PURPOSE_INTERACTIVE,
    timeout: Optional[float] = None,
    provider: str = "openai",
    endpoint: str = "chat.completions",
    **kwargs,
):
    """Run ``client.chat.completions.create(**kwargs)`` safely.

    * bounded — the transport timeout plus an outer hard ceiling,
    * non-blocking — the synchronous SDK runs in a worker thread, so the event
      loop keeps serving every other request while the provider thinks,
    * observable — latency and failures land in :func:`get_ai_metrics`,
    * mappable — failures raise :class:`AIProviderTimeout` /
      :class:`AIProviderError` instead of leaking SDK internals.
    """
    timeout_s = resolve_timeout(purpose, timeout)
    model = resolve_model(kwargs.get("model"))
    kwargs["model"] = model
    call_client = client
    # Per-call timeout on the SDK itself, so the socket is actually aborted.
    with_options = getattr(client, "with_options", None)
    if callable(with_options):
        try:
            call_client = with_options(timeout=timeout_s)
        except Exception:  # pragma: no cover — never fail on an optional hint
            call_client = client

    def _invoke():
        return call_client.chat.completions.create(**kwargs)

    return await run_bounded_sync(
        _invoke,
        purpose=purpose,
        timeout=timeout_s,
        provider=provider,
        endpoint=endpoint,
        model=model,
    )


def map_provider_exception(
    exc: BaseException,
    *,
    provider: str = "openai",
    endpoint: str = "chat.completions",
    model: Optional[str] = None,
    elapsed_ms: int = 0,
    timeout_s: Optional[float] = None,
) -> AIProviderError:
    """Translate an SDK/transport exception into our structured error type."""
    name = type(exc).__name__
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or name in (
        "APITimeoutError", "Timeout", "ReadTimeout", "ConnectTimeout",
    ):
        return AIProviderTimeout(
            str(exc) or f"provider did not respond within {timeout_s}s",
            provider=provider, endpoint=endpoint, model=model,
            elapsed_ms=elapsed_ms, timeout_s=timeout_s,
        )
    if name == "RateLimitError":
        return AIProviderRateLimited(
            str(exc) or "provider rate limited",
            provider=provider, endpoint=endpoint, model=model,
            elapsed_ms=elapsed_ms, timeout_s=timeout_s,
        )
    return AIProviderError(
        f"{name}: {exc}",
        provider=provider, endpoint=endpoint, model=model,
        elapsed_ms=elapsed_ms, timeout_s=timeout_s,
    )


def record_ai_outcome(
    outcome: str,
    *,
    provider: str = "openai",
    endpoint: str = "chat.completions",
    elapsed_ms: int = 0,
) -> None:
    """Record a call handled outside :func:`run_bounded_sync` (e.g. streaming).

    ``outcome`` is one of ``successes`` / ``timeouts`` / ``errors``.
    """
    if outcome not in ("successes", "timeouts", "errors"):
        outcome = "errors"
    _record(provider, endpoint, outcome, elapsed_ms)


def report_ai_failure(
    exc: BaseException,
    *,
    purpose: str = PURPOSE_STREAM,
    provider: str = "openai",
    endpoint: str = "chat.completions.stream",
    model: Optional[str] = None,
    elapsed_ms: int = 0,
    timeout_s: Optional[float] = None,
) -> AIProviderError:
    """Map, count and log a failure from a call this module did not drive.

    Used by the SSE streaming paths, which own their own chunk loop but must
    still show up in the AI metrics, the structured logs and Sentry.
    """
    err = map_provider_exception(
        exc, provider=provider, endpoint=endpoint, model=model,
        elapsed_ms=elapsed_ms, timeout_s=timeout_s,
    )
    _record(provider, endpoint, "timeouts" if isinstance(err, AIProviderTimeout) else "errors", elapsed_ms)
    _log_failure(err, purpose)
    return err


async def run_bounded_sync(
    fn: Callable[..., Any],
    *args,
    purpose: str = PURPOSE_INTERACTIVE,
    timeout: Optional[float] = None,
    provider: str = "openai",
    endpoint: str = "chat.completions",
    model: Optional[str] = None,
    **kwargs,
):
    """Run a *blocking* provider call off the event loop, bounded and observed.

    Same guarantees as :func:`ai_chat_completion`, for call sites that need to
    drive the SDK themselves (multi-step parsing, non-chat endpoints).
    """
    timeout_s = resolve_timeout(purpose, timeout)
    started = time.perf_counter()
    loop = asyncio.get_running_loop()
    call = functools.partial(fn, *args, **kwargs) if (args or kwargs) else fn
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(_get_executor(), call),
            timeout=_hard_ceiling(timeout_s),
        )
    except BaseException as exc:  # noqa: BLE001 — mapped and re-raised below
        if isinstance(exc, asyncio.CancelledError):
            raise
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        err = map_provider_exception(
            exc, provider=provider, endpoint=endpoint, model=model,
            elapsed_ms=elapsed_ms, timeout_s=timeout_s,
        )
        _record(provider, endpoint, "timeouts" if isinstance(err, AIProviderTimeout) else "errors", elapsed_ms)
        _log_failure(err, purpose)
        raise err from None

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    _record(provider, endpoint, "successes", elapsed_ms)
    logger.info(
        f"AI call ok provider={provider} endpoint={endpoint} model={model} "
        f"purpose={purpose} elapsed_ms={elapsed_ms} request_id={_request_id()}"
    )
    return result
