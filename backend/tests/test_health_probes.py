"""Public infrastructure probes: `/healthz` (liveness) and `/readyz` (readiness).

Contract these tests defend:

* both answer without any credential — infra tools have no account,
* liveness never depends on the database, so a database blip can't get a
  healthy process killed,
* readiness answers 503 when the database is unreachable or slow, so the load
  balancer drains the instance instead of feeding it doomed requests,
* the dependency check is time-bounded — the probe must not become the
  bottleneck it exists to detect,
* the bodies leak nothing (no version, environment, host, config, counts,
  timings or exception text),
* the admin-gated diagnostics routes stay admin-gated.
"""
import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("ENVIRONMENT", "development")

from routes import health_routes  # noqa: E402
from server import app  # noqa: E402

# Anything that would turn the probe into an information-disclosure surface.
_FORBIDDEN_BODY_TOKENS = (
    "version", "environment", "python", "host", "traceback", "postgres",
    "password", "token", "secret", "sqlalchemy", "connect", "user",
)


@pytest_asyncio.fixture
async def root_client():
    """Rooted at ``/`` — probes are never mounted under ``/api``."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _assert_minimal(body: dict) -> None:
    blob = str(body).lower()
    for token in _FORBIDDEN_BODY_TOKENS:
        assert token not in blob, f"probe body leaks {token!r}: {body}"


@pytest.mark.asyncio
async def test_liveness_is_public_and_returns_ok(root_client):
    resp = await root_client.get("/healthz")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "ok"}
    _assert_minimal(resp.json())


@pytest.mark.asyncio
async def test_liveness_is_not_cached(root_client):
    resp = await root_client.get("/healthz")
    assert "no-store" in resp.headers.get("cache-control", "")


@pytest.mark.asyncio
async def test_liveness_survives_a_dead_database(root_client, monkeypatch):
    """Liveness must never consult a dependency — that's readiness' job."""
    async def _explode():
        raise RuntimeError("database is down")

    monkeypatch.setattr(health_routes, "_ping_database", _explode)
    resp = await root_client.get("/healthz")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_liveness_ignores_a_garbage_authorization_header(root_client):
    """No auth means no auth — a stale token must not turn a probe into a 401."""
    resp = await root_client.get("/healthz", headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_head_liveness_is_supported(root_client):
    """Several uptime monitors probe with HEAD."""
    resp = await root_client.head("/healthz")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_readiness_ok_when_database_answers(root_client):
    resp = await root_client.get("/readyz")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_is_503_when_the_database_is_unreachable(root_client, monkeypatch):
    async def _explode():
        raise ConnectionError("connection refused")

    monkeypatch.setattr(health_routes, "_ping_database", _explode)
    resp = await root_client.get("/readyz")
    assert resp.status_code == 503, resp.text
    assert resp.json() == {"status": "unavailable", "failed": ["database"]}


@pytest.mark.asyncio
async def test_readiness_is_503_and_fast_when_the_database_hangs(root_client, monkeypatch):
    """A hung dependency must produce a prompt 503, not a hung probe."""
    async def _hang():
        await asyncio.sleep(30)

    monkeypatch.setattr(health_routes, "_ping_database", _hang)
    monkeypatch.setenv("READINESS_TIMEOUT_S", "0.25")

    loop = asyncio.get_running_loop()
    started = loop.time()
    resp = await root_client.get("/readyz")
    elapsed = loop.time() - started

    assert resp.status_code == 503
    assert elapsed < 5, f"probe took {elapsed:.2f}s — timeout not enforced"


@pytest.mark.asyncio
async def test_failure_body_stays_minimal(root_client, monkeypatch):
    async def _explode():
        raise RuntimeError("FATAL: password authentication failed for user 'nassaq'")

    monkeypatch.setattr(health_routes, "_ping_database", _explode)
    resp = await root_client.get("/readyz")
    _assert_minimal(resp.json())


def test_readiness_timeout_is_clamped(monkeypatch):
    monkeypatch.setenv("READINESS_TIMEOUT_S", "900")
    assert health_routes.readiness_timeout_s() == 10.0
    monkeypatch.setenv("READINESS_TIMEOUT_S", "0")
    assert health_routes.readiness_timeout_s() == 0.25
    monkeypatch.setenv("READINESS_TIMEOUT_S", "not-a-number")
    assert health_routes.readiness_timeout_s() == 2.0
    monkeypatch.delenv("READINESS_TIMEOUT_S")
    assert health_routes.readiness_timeout_s() == 2.0


@pytest.mark.asyncio
async def test_probes_are_read_only(root_client):
    """No state changes: the write verbs must not exist on a probe path."""
    for path in ("/healthz", "/readyz"):
        for verb in ("post", "put", "delete", "patch"):
            resp = await getattr(root_client, verb)(path)
            assert resp.status_code in (404, 405), f"{verb.upper()} {path} → {resp.status_code}"


@pytest.mark.asyncio
async def test_probes_do_not_borrow_a_request_scoped_session(root_client, monkeypatch):
    """Each probe must cost at most the one connection it actually needs.

    `pg_session_middleware` opens a session for ordinary requests and holds it
    for the whole handler. On a probe that checkout is pure overhead: liveness
    needs no database at all, and readiness opens its own connection on purpose
    (to prove the pool can still hand one out). Leaving the middleware session
    in place would make frequent probing amplify pool exhaustion into the very
    outage the probe is meant to report.
    """
    from app import middleware as mw

    opened = []
    real_factory = mw.async_session_factory

    def _counting_factory(*args, **kwargs):
        opened.append(1)
        return real_factory(*args, **kwargs)

    monkeypatch.setattr(mw, "async_session_factory", _counting_factory)

    await root_client.get("/healthz")
    assert opened == [], "liveness opened a request-scoped session"

    await root_client.get("/readyz")
    assert opened == [], "readiness borrowed a request-scoped session"


@pytest.mark.asyncio
async def test_probe_paths_and_middleware_exemption_agree():
    """One list, so a renamed probe can't silently regain the middleware."""
    from app.routes import register_routes  # noqa: F401 — import sanity
    from routes.health_routes import PROBE_PATHS

    routed = {
        route.path
        for route in app.routes
        if getattr(route, "path", "") in ("/healthz", "/readyz")
    }
    assert routed == set(PROBE_PATHS)


@pytest.mark.asyncio
async def test_detailed_diagnostics_remain_admin_gated(root_client):
    """Public probes must not become a bypass for the admin surfaces."""
    for path in ("/system/status", "/system/metrics", "/system/deployment-safety"):
        resp = await root_client.get(path)
        assert resp.status_code == 401, f"{path} is not protected ({resp.status_code})"


@pytest.mark.asyncio
async def test_non_admin_cannot_reach_detailed_diagnostics(client, teacher_headers):
    resp = await client.get("/system/status", headers=teacher_headers)
    assert resp.status_code == 403
