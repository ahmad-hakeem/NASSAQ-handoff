"""Task: stop email sending from hanging the server (mirror of ai_client).

Covers:
  * env-configurable timeouts with sanity clamps,
  * bounded transport installed on the resend SDK per send,
  * failure mapping to structured EmailProviderError / EmailProviderTimeout,
  * observability — failures land in the metrics counters,
  * best-effort contract preserved — template send_* still return False,
  * async offload — send_email_off_loop runs off-loop and enforces a hard
    ceiling instead of pinning the awaiting request.
"""
import asyncio
import time

import pytest

import resend

import services.email_client as email_client
from services.email_client import (
    EmailProviderError,
    EmailProviderTimeout,
    deliver_resend_email,
    get_email_metrics,
    map_provider_exception,
    reset_email_metrics,
    send_email_off_loop,
)


@pytest.fixture(autouse=True)
def _clean_metrics():
    reset_email_metrics()
    yield
    reset_email_metrics()


# ---------------------------------------------------------------- config
def test_timeouts_env_configurable_and_clamped(monkeypatch):
    monkeypatch.setenv("EMAIL_CONNECT_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("EMAIL_SEND_TIMEOUT_SECONDS", "20")
    assert email_client.resolve_connect_timeout() == 3.0
    assert email_client.resolve_send_timeout() == 20.0

    # garbage / non-positive fall back to defaults
    monkeypatch.setenv("EMAIL_SEND_TIMEOUT_SECONDS", "not-a-number")
    assert email_client.resolve_send_timeout() == 15.0
    monkeypatch.setenv("EMAIL_SEND_TIMEOUT_SECONDS", "-5")
    assert email_client.resolve_send_timeout() == 15.0

    # absurdly large values clamp — never effectively unbounded
    monkeypatch.setenv("EMAIL_SEND_TIMEOUT_SECONDS", "99999")
    assert email_client.resolve_send_timeout() == 120.0


def test_bounded_transport_installed_per_send(monkeypatch):
    monkeypatch.setenv("EMAIL_CONNECT_TIMEOUT_SECONDS", "4")
    monkeypatch.setenv("EMAIL_SEND_TIMEOUT_SECONDS", "9")
    monkeypatch.setattr(resend.Emails, "send", staticmethod(lambda p: {"id": "x"}))
    deliver_resend_email({"to": ["a@b.c"]}, kind="test")
    client = resend.default_http_client
    assert client._timeout == (4.0, 9.0)


# ---------------------------------------------------------------- mapping
def test_map_timeout_from_wrapped_requests_error():
    # resend wraps transport failures into a generic error whose message
    # carries the original requests text.
    err = map_provider_exception(
        RuntimeError("Request failed: HTTPSConnectionPool ... Read timed out."),
        kind="password_reset", timeout_s=9.0,
    )
    assert isinstance(err, EmailProviderTimeout)
    assert err.code == "email_provider_timeout"

    plain = map_provider_exception(ValueError("boom"), kind="k")
    assert isinstance(plain, EmailProviderError)
    assert not isinstance(plain, EmailProviderTimeout)
    assert plain.code == "email_provider_error"


# ---------------------------------------------------------------- deliver
def test_deliver_records_success_metrics(monkeypatch):
    monkeypatch.setattr(resend.Emails, "send", staticmethod(lambda p: {"id": "ok-1"}))
    result = deliver_resend_email({"to": ["a@b.c"]}, kind="password_reset")
    assert result["id"] == "ok-1"
    metrics = get_email_metrics()
    assert metrics["totals"]["successes"] == 1
    assert metrics["by_kind"]["password_reset"]["calls"] == 1


def test_deliver_maps_failure_and_counts(monkeypatch):
    def _boom(params):
        raise RuntimeError("Request failed: Read timed out.")

    monkeypatch.setattr(resend.Emails, "send", staticmethod(_boom))
    with pytest.raises(EmailProviderTimeout):
        deliver_resend_email({"to": ["a@b.c"]}, kind="mfa_email_otp")
    metrics = get_email_metrics()
    assert metrics["totals"]["timeouts"] == 1
    assert metrics["by_kind"]["mfa_email_otp"]["timeouts"] == 1


def test_template_send_still_returns_false_on_provider_failure(monkeypatch):
    """Best-effort contract preserved: callers keep getting a bool."""
    import engines.email_service as email_service

    def _boom(params):
        raise RuntimeError("Request failed: Read timed out.")

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "test-key")
    monkeypatch.setattr(resend.Emails, "send", staticmethod(_boom))
    ok = email_service.send_mfa_email_otp("user@example.com", "مستخدم", "123456")
    assert ok is False
    assert get_email_metrics()["totals"]["timeouts"] == 1


# ---------------------------------------------------------------- offload
def test_send_email_off_loop_runs_off_the_event_loop():
    import threading

    loop_thread = threading.current_thread()
    seen = {}

    def _fake_send(to_email):
        seen["thread"] = threading.current_thread()
        return True

    result = asyncio.run(send_email_off_loop(_fake_send, to_email="a@b.c"))
    assert result is True
    assert seen["thread"] is not loop_thread


def test_send_email_off_loop_ceiling_degrades_not_hangs(monkeypatch):
    monkeypatch.setenv("EMAIL_CONNECT_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("EMAIL_SEND_TIMEOUT_SECONDS", "1")
    monkeypatch.setattr(email_client, "_hard_ceiling", lambda: 0.2)

    def _hangs():
        time.sleep(2)
        return True

    started = time.perf_counter()
    result = asyncio.run(send_email_off_loop(_hangs))
    elapsed = time.perf_counter() - started
    assert result is False
    assert elapsed < 1.5
    assert get_email_metrics()["totals"]["timeouts"] == 1
