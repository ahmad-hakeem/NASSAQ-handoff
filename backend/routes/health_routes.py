"""Unauthenticated health probes for infrastructure tooling.

Load balancers, container orchestrators and uptime monitors are not users:
they hold no account, no token and no session, and they expect one cheap URL
that answers ``200`` when the instance may receive traffic and ``5xx`` when it
may not. This module is that contract, and nothing else.

Two endpoints, because the two questions are different:

``GET /healthz`` — **liveness**. "Is this process alive and serving HTTP?"
    Never touches a dependency, so a database blip can never convince an
    orchestrator to kill an otherwise-healthy pod. Answers 200 as long as the
    event loop can run the handler.

``GET /readyz`` — **readiness**. "Should this instance receive traffic *now*?"
    Pings the database on its own connection, under a hard timeout, and
    answers 503 when that fails so the load balancer drains the instance
    instead of feeding it requests that are guaranteed to fail.

Both are read-only, mutate nothing, and return a fixed minimal body — no
version, environment, hostname, config, counts, stack traces or timings, since
anyone on the internet can read them. Detailed diagnostics stay on the
admin-gated monitoring routes (`/system/status`, `/system/metrics`).
"""
import asyncio
import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text as sa_text

from db import async_session_factory

logger = logging.getLogger("nassaq")

router = APIRouter(tags=["Health"])

# Probes are polled every few seconds; a cached answer would defeat the point.
_NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}

_DEFAULT_READINESS_TIMEOUT_S = 2.0
_MIN_READINESS_TIMEOUT_S = 0.25
_MAX_READINESS_TIMEOUT_S = 10.0


def readiness_timeout_s() -> float:
    """Hard ceiling for the dependency check, clamped to a sane band.

    The probe must never become the bottleneck it is supposed to detect: an
    unbounded check would hang for as long as the database does, and the
    orchestrator's own probe timeout would fire first, turning a slow database
    into an ambiguous timeout instead of a clean 503.
    """
    raw = os.environ.get("READINESS_TIMEOUT_S", "")
    try:
        value = float(raw) if raw else _DEFAULT_READINESS_TIMEOUT_S
    except ValueError:
        logger.warning("Invalid READINESS_TIMEOUT_S=%r, using default", raw)
        value = _DEFAULT_READINESS_TIMEOUT_S
    return max(_MIN_READINESS_TIMEOUT_S, min(_MAX_READINESS_TIMEOUT_S, value))


async def _ping_database() -> None:
    """``SELECT 1`` on a connection of its own.

    Deliberately not the request-scoped session: a probe that borrows an
    already-open session would report "ready" from a pool that can no longer
    hand out new connections.
    """
    async with async_session_factory() as session:
        await session.execute(sa_text("SELECT 1"))


async def check_database() -> bool:
    """True when the database answered within the timeout."""
    try:
        await asyncio.wait_for(_ping_database(), timeout=readiness_timeout_s())
        return True
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        logger.error("Readiness probe: database ping exceeded %.2fs", readiness_timeout_s())
        return False
    except Exception as exc:  # noqa: BLE001 — any failure means "not ready"
        logger.error("Readiness probe: database unreachable (%s)", type(exc).__name__)
        return False


#: Several uptime monitors and load balancers probe with HEAD rather than GET;
#: FastAPI does not add it implicitly, so both verbs are declared.
_PROBE_METHODS = ["GET", "HEAD"]

#: Canonical probe paths. `pg_session_middleware` reads this to skip opening a
#: request-scoped session for them — see the comment there.
PROBE_PATHS = frozenset({"/healthz", "/readyz"})


@router.api_route("/healthz", methods=_PROBE_METHODS, include_in_schema=False)
async def liveness():
    """Process-level liveness. No dependencies, no auth, no payload."""
    return JSONResponse({"status": "ok"}, headers=_NO_STORE)


@router.api_route("/readyz", methods=_PROBE_METHODS, include_in_schema=False)
async def readiness():
    """Readiness for traffic: 200 when critical dependencies answer, else 503."""
    if await check_database():
        return JSONResponse({"status": "ok"}, headers=_NO_STORE)
    # `failed` names the dependency class only — enough for an operator
    # reading probe logs, useless to anyone else.
    return JSONResponse(
        {"status": "unavailable", "failed": ["database"]},
        status_code=503,
        headers=_NO_STORE,
    )
