"""End-of-school-day lesson auto-close — decision-logic unit tests.

These cover the pure resolver/decision helpers that drive the background sweep
which finalises lessons left open past the end of the school day. They need no
DB: they validate that (a) the day-end is resolved the same way as the live
``/school/day-status`` banner, and (b) a session closes only once its own
calendar day has ended (in the school timezone, plus a grace margin).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.lifecycle import (
    _compute_day_end_minutes,
    _session_should_close,
    _AUTO_CLOSE_GRACE_MINUTES,
)

_RIYADH = ZoneInfo("Asia/Riyadh")


def test_day_end_from_period_time_slots_wins():
    # Real schools: the last period's end_time is authoritative.
    settings = {"periods_per_day": 7, "period_duration": 45}
    slots = [
        {"start_time": "07:00", "end_time": "07:45", "is_break": False},
        {"start_time": "07:45", "end_time": "08:05", "is_break": True},
        {"start_time": "08:05", "end_time": "08:50", "is_break": False},
        {"start_time": "12:30", "end_time": "13:15", "is_break": False},
    ]
    assert _compute_day_end_minutes(settings, slots) == 13 * 60 + 15


def test_day_end_formula_when_no_time_slots():
    # IT workspaces (and un-generated schools) have no time_slots → formula:
    # start 07:00 + 6*40 + 25 break = 07:00 + 265min = 11:25.
    settings = {
        "school_day_start": "07:00",
        "periods_per_day": 6,
        "period_duration": 40,
        "break_duration": 25,
    }
    assert _compute_day_end_minutes(settings, []) == 7 * 60 + 265


def test_day_end_uses_safe_defaults_when_settings_missing():
    # No settings row at all → 07:00 + 7*45 + 20 = 12:35.
    assert _compute_day_end_minutes(None, []) == 7 * 60 + 7 * 45 + 20


def test_session_stays_open_before_day_end():
    day_end = 13 * 60 + 15  # 13:15
    now = datetime(2026, 6, 30, 10, 0, tzinfo=_RIYADH)  # mid-morning
    assert _session_should_close("2026-06-30", day_end, _RIYADH, now, _AUTO_CLOSE_GRACE_MINUTES) is False


def test_session_stays_open_within_grace_after_day_end():
    day_end = 13 * 60 + 15  # 13:15
    # 13:20 is past day-end but within the 15-minute grace window.
    now = datetime(2026, 6, 30, 13, 20, tzinfo=_RIYADH)
    assert _session_should_close("2026-06-30", day_end, _RIYADH, now, _AUTO_CLOSE_GRACE_MINUTES) is False


def test_session_closes_after_day_end_plus_grace():
    day_end = 13 * 60 + 15  # 13:15 → +15 grace = 13:30
    now = datetime(2026, 6, 30, 13, 31, tzinfo=_RIYADH)
    assert _session_should_close("2026-06-30", day_end, _RIYADH, now, _AUTO_CLOSE_GRACE_MINUTES) is True


def test_previous_day_session_always_closes():
    day_end = 13 * 60 + 15
    # Even early next morning, yesterday's lesson is well past its day-end.
    now = datetime(2026, 6, 30, 6, 0, tzinfo=_RIYADH)
    assert _session_should_close("2026-06-29", day_end, _RIYADH, now, _AUTO_CLOSE_GRACE_MINUTES) is True


def test_unparseable_date_defers_to_stale_fallback():
    day_end = 13 * 60 + 15
    now = datetime(2026, 6, 30, 23, 0, tzinfo=_RIYADH)
    assert _session_should_close(None, day_end, _RIYADH, now, _AUTO_CLOSE_GRACE_MINUTES) is False
    assert _session_should_close("not-a-date", day_end, _RIYADH, now, _AUTO_CLOSE_GRACE_MINUTES) is False
