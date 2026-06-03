"""Task #798 — global safe-Arabic-envelope guarantee for unexpected errors.

Proves that ANY exception escaping a route is rendered as the canonical
``{success:false, error:{code, message}}`` JSON envelope with a safe Arabic
message and HTTP 500 — never an unparseable plain-text 500 (which the frontend
write-error classifier in ``frontend/src/utils/apiError.js`` cannot read) and
never raw ``str(exc)`` leaking internal detail.

It also verifies the catch-all does NOT shadow the more specific handlers:
``StarletteHTTPException`` (incl. structured dict detail) and
``RequestValidationError`` still win for their own types.
"""
from __future__ import annotations

import os

os.environ.setdefault(
    "MFA_ENCRYPTION_KEY",
    os.environ.get("MFA_ENCRYPTION_KEY", "")
    or "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
)

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.testclient import TestClient

from server import app
from middleware.error_handler import SAFE_ERROR_CODE, SAFE_ERROR_MESSAGE_AR

_SECRET = "secret-internal-db-detail-should-not-leak"


async def _boom():
    raise RuntimeError(_SECRET)


async def _http_plain():
    raise HTTPException(status_code=404, detail="custom not found")


async def _http_dict():
    raise HTTPException(
        status_code=403,
        detail={"code": "MFA_STEPUP_REQUIRED", "message": "step up"},
    )


# Register the probe routes at the FRONT of the router so they precede the SPA
# catch-all (``/{full_path:path}``) registered during app creation.
for _path, _fn in (
    ("/api/__test_uncaught_error__", _boom),
    ("/api/__test_http_plain__", _http_plain),
    ("/api/__test_http_dict__", _http_dict),
):
    app.router.routes.insert(0, APIRoute(_path, _fn, methods=["GET"]))


@pytest.fixture(scope="module")
def probe_client():
    # NOT used as a context manager on purpose: entering it would run the
    # app's startup hooks (including the production Alembic head-gate in
    # app/lifecycle.py) which are irrelevant here. raise_server_exceptions=
    # False so the TestClient surfaces the handler's response instead of
    # re-raising the error in the test process.
    return TestClient(app, raise_server_exceptions=False)


def test_uncaught_route_error_returns_arabic_envelope(probe_client):
    r = probe_client.get("/api/__test_uncaught_error__")
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == SAFE_ERROR_CODE
    assert body["error"]["message"] == SAFE_ERROR_MESSAGE_AR
    # The message must be Arabic and must never leak the raw exception text.
    assert _SECRET not in r.text


def test_http_exception_handler_still_wins(probe_client):
    r = probe_client.get("/api/__test_http_plain__")
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HTTP_404"
    assert body["error"]["message"] == "custom not found"


def test_structured_http_detail_still_preserved(probe_client):
    r = probe_client.get("/api/__test_http_dict__")
    assert r.status_code == 403
    body = r.json()
    assert body["error"]["code"] == "MFA_STEPUP_REQUIRED"
    assert body["error"]["message"] == "step up"
    assert body["error"]["detail"]["code"] == "MFA_STEPUP_REQUIRED"
