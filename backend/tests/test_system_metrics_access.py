"""`/system/metrics` must separate "no credential" from "not allowed".

Reported symptom: a logged-in platform admin typed the monitoring URL into the
address bar and got ``{"success": false, "error": {"code": "HTTP_401",
"message": "Not authenticated"}}``.

Root cause: the monitoring router is mounted twice — under ``/api`` (what the
SPA calls, with its bearer token) and at the root, so ``/system/metrics`` sits
inside the SPA's URL space. Auth is a bearer token held by the frontend, not a
cookie, so a plain browser navigation carries no credential at all and the
route correctly answers 401 — but as raw JSON, which reads like the app has
forgotten the session.

Contract locked down here:

* browser navigation with no credential  → redirect to the monitoring UI,
* API call with no credential            → 401 JSON,
* API call by a signed-in non-admin      → 403 JSON (never masked by a bounce),
* API call by a platform admin           → 200 with the metrics payload.
"""
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("ENVIRONMENT", "development")

from server import app  # noqa: E402

_HTML = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
_MONITORING_UI = "/admin/monitoring"


@pytest_asyncio.fixture
async def root_client():
    """Client rooted at ``/`` — the conftest ``client`` fixture is ``/api``."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_browser_navigation_without_token_goes_to_the_monitoring_ui(root_client):
    resp = await root_client.get(
        "/system/metrics",
        headers={
            "accept": _HTML,
            "sec-fetch-mode": "navigate",
            "sec-fetch-dest": "document",
        },
    )
    assert resp.status_code == 302, resp.text
    assert resp.headers["location"] == _MONITORING_UI


@pytest.mark.asyncio
async def test_non_browser_client_accepting_html_still_gets_json(root_client):
    """``Sec-Fetch-*`` is the proof of a real navigation.

    Scripts, probes and SDKs do not send it — some of them do send
    ``Accept: */*`` or even ``text/html``. Without positive browser evidence
    the response must stay machine-readable.
    """
    resp = await root_client.get("/system/metrics", headers={"accept": _HTML})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "HTTP_401"


@pytest.mark.asyncio
async def test_cors_fetch_is_not_redirected(root_client):
    resp = await root_client.get(
        "/system/metrics",
        headers={"accept": _HTML, "sec-fetch-mode": "cors", "sec-fetch-dest": "empty"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_endpoints_outside_the_allow_list_keep_answering_json(root_client):
    """Only paths a human might type are mapped; the rest stay pure API."""
    resp = await root_client.get(
        "/system/deployment-safety",
        headers={
            "accept": _HTML,
            "sec-fetch-mode": "navigate",
            "sec-fetch-dest": "document",
        },
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "HTTP_401"


@pytest.mark.asyncio
async def test_api_client_without_token_still_gets_401_json(root_client):
    resp = await root_client.get("/system/metrics", headers={"accept": "application/json"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "HTTP_401"


@pytest.mark.asyncio
async def test_xhr_from_the_spa_is_never_redirected(root_client):
    """An in-app fetch must keep receiving JSON even if it accepts HTML."""
    resp = await root_client.get(
        "/system/metrics",
        headers={"accept": _HTML, "x-requested-with": "XMLHttpRequest"},
    )
    assert resp.status_code == 401
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_api_namespace_is_untouched_by_the_redirect(root_client):
    """``/api/...`` belongs to machines only — always JSON, never a bounce."""
    resp = await root_client.get(
        "/api/system/metrics",
        headers={"accept": _HTML, "sec-fetch-mode": "navigate"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "HTTP_401"


@pytest.mark.asyncio
async def test_signed_in_non_admin_gets_403_not_401(client, teacher_headers):
    resp = await client.get("/system/metrics", headers=teacher_headers)
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_signed_in_non_admin_browser_navigation_is_not_masked(
    root_client, teacher_headers
):
    """A real authorization failure must not be hidden behind a redirect."""
    resp = await root_client.get(
        "/system/metrics",
        headers={**teacher_headers, "accept": _HTML, "sec-fetch-mode": "navigate"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_platform_admin_receives_the_metrics_payload(client, platform_admin_headers):
    resp = await client.get("/system/metrics", headers=platform_admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("uptime_seconds", "response_metrics", "ai_metrics", "database_counts"):
        assert key in body, f"missing {key} in metrics payload"
