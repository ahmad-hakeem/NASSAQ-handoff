"""NASSAQ — optional error/alert sink (Sentry).

Wiring is entirely opt-in: without ``SENTRY_DSN`` every function here is a
no-op, so development and tests behave exactly as before. When the DSN is set
we forward *handled* AI-provider failures (timeouts, provider errors) with the
tags an on-call alert needs — provider, endpoint, model, purpose, request id —
so a rise in ``ai_provider_timeout`` can be alerted on directly.

Nothing in here may raise: observability must never break a request.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("nassaq.observability")

_initialised = False
_enabled = False


def is_enabled() -> bool:
    return _enabled


def init_observability() -> bool:
    """Initialise Sentry when configured. Safe to call more than once."""
    global _initialised, _enabled
    if _initialised:
        return _enabled
    _initialised = True

    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    environment = os.environ.get("ENVIRONMENT", "development")
    # The DSN is visible in every environment, and the workspace's own backend
    # runs with ENVIRONMENT=production — so gate on "am I a published app?"
    # (REPLIT_DEPLOYMENT is only set inside a deployment) rather than on the
    # environment name. ``SENTRY_ENABLE_DEV=true`` forces it on for testing.
    dev_override = os.environ.get("SENTRY_ENABLE_DEV", "").lower() == "true"
    if os.environ.get("TESTING") == "1" and not dev_override:
        return False
    is_deployment = os.environ.get("REPLIT_DEPLOYMENT", "") == "1"
    if not is_deployment and environment != "staging" and not dev_override:
        logger.info(
            f"Sentry disabled outside deployments (environment={environment}); "
            "set SENTRY_ENABLE_DEV=true to force"
        )
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.info("SENTRY_DSN is set but sentry-sdk is not installed — skipping")
        return False

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=os.environ.get("REPLIT_DEPLOYMENT_ID") or None,
            # Errors only by default; tracing is opt-in so we never add
            # latency or cost without an explicit decision.
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
            send_default_pii=False,
        )
        _enabled = True
        logger.info(f"Sentry initialised (environment={environment})")
    except Exception as exc:  # pragma: no cover — never break boot
        logger.warning(f"Sentry initialisation failed: {exc}")
    return _enabled


def capture_ai_failure(error: Any, *, purpose: str = "", request_id: str = "-") -> None:
    """Report a handled AI-provider failure to the alert sink."""
    if not _enabled:
        return
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_tag("ai.provider", getattr(error, "provider", "unknown"))
            scope.set_tag("ai.endpoint", getattr(error, "endpoint", "unknown"))
            scope.set_tag("ai.error_code", getattr(error, "code", "ai_provider_error"))
            scope.set_tag("ai.purpose", purpose or "unknown")
            scope.set_tag("request_id", request_id)
            scope.set_context(
                "ai_call",
                {
                    "model": getattr(error, "model", None),
                    "timeout_s": getattr(error, "timeout_s", None),
                    "elapsed_ms": getattr(error, "elapsed_ms", None),
                },
            )
            sentry_sdk.capture_exception(error)
    except Exception:  # pragma: no cover
        pass


def capture_exception(exc: BaseException, **tags: Optional[str]) -> None:
    """Generic escape hatch for handled exceptions worth alerting on."""
    if not _enabled:
        return
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            for key, value in tags.items():
                if value is not None:
                    scope.set_tag(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:  # pragma: no cover
        pass
