"""Task: alert admins when email delivery starts failing instead of failing silently.

Covers:
  * sliding-window health snapshot (ok vs degraded, min-calls guard),
  * one-shot alert latch — the Sentry/log alert fires once per degradation
    episode and re-arms after recovery,
  * health surfaced inside get_email_metrics() for the monitoring endpoint.
"""
import pytest

import services.email_client as email_client
from services.email_client import (
    get_email_health,
    get_email_metrics,
    reset_email_metrics,
)


@pytest.fixture(autouse=True)
def _clean_metrics():
    reset_email_metrics()
    yield
    reset_email_metrics()


def _fail(n=1):
    for _ in range(n):
        email_client._record("test", "errors", 10)


def _ok(n=1):
    for _ in range(n):
        email_client._record("test", "successes", 10)


def test_healthy_below_min_calls_even_if_all_failures(monkeypatch):
    monkeypatch.setenv("EMAIL_ALERT_MIN_CALLS", "5")
    _fail(4)
    health = get_email_health()
    assert health["status"] == "ok"
    assert health["window_failures"] == 4


def test_degraded_when_rate_crosses_threshold(monkeypatch):
    monkeypatch.setenv("EMAIL_ALERT_MIN_CALLS", "5")
    monkeypatch.setenv("EMAIL_ALERT_FAILURE_RATE", "0.25")
    _ok(6)
    _fail(2)  # 2/8 = 25% ≥ 25%
    health = get_email_health()
    assert health["status"] == "degraded"
    assert health["alert_active"] is True


def test_alert_fires_once_per_episode_and_rearms(monkeypatch):
    monkeypatch.setenv("EMAIL_ALERT_MIN_CALLS", "3")
    monkeypatch.setenv("EMAIL_ALERT_FAILURE_RATE", "0.5")
    emitted = []
    monkeypatch.setattr(email_client, "_emit_health_alert", lambda snap: emitted.append(snap))

    _fail(3)  # crosses threshold → one alert
    _fail(3)  # still degraded → latched, no second alert
    assert len(emitted) == 1
    assert emitted[0]["status"] == "degraded"

    _ok(email_client._HEALTH_WINDOW)  # window recovers → latch resets
    assert get_email_health()["status"] == "ok"

    _fail(email_client._HEALTH_WINDOW)  # degrades again → second alert
    assert len(emitted) == 2


def test_health_included_in_metrics_snapshot():
    _ok(2)
    metrics = get_email_metrics()
    assert metrics["health"]["status"] == "ok"
    assert metrics["health"]["window_calls"] == 2


def test_threshold_env_clamped(monkeypatch):
    monkeypatch.setenv("EMAIL_ALERT_FAILURE_RATE", "garbage")
    assert email_client.resolve_alert_failure_rate() == 0.25
    monkeypatch.setenv("EMAIL_ALERT_FAILURE_RATE", "5")
    assert email_client.resolve_alert_failure_rate() == 1.0
    monkeypatch.setenv("EMAIL_ALERT_MIN_CALLS", "0")
    assert email_client.resolve_alert_min_calls() == 1
