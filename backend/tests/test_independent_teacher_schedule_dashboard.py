"""HTTP-level tests for the IT teacher schedule read surface (Task #775).

Task #772 pinned the IT schedule read *helpers*. This suite drives the full
HTTP endpoints an Independent-Teacher actually hits — the dedicated teacher
schedule endpoint (جدولي / إدارة الحصص) and the teacher dashboard "today"
block — end-to-end through the real routes and auth gates, and documents which
schedule read endpoints an IT role can reach vs. which are blocked by the
workspace perimeter (`require_full_school_tenant`).
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from auth_scope import INDEPENDENT_TEACHER_DENIED_AR
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert

from tests._it_fixtures import mk_it_workspace, it_headers


# Full day name -> the short code the IT editor stores.
_FULL_TO_SHORT = {
    "sunday": "sun", "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat",
}
# Same Python-weekday -> full-name mapping the dashboard uses for "today".
_DAY_MAP = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
            4: "friday", 5: "saturday", 6: "sunday"}


def _today_full() -> str:
    return _DAY_MAP.get(datetime.now().weekday(), "sunday")


def _other_full(today: str) -> str:
    for full in _DAY_MAP.values():
        if full != today:
            return full
    return "monday"


async def _seed_it_settings(school_id: str, *, periods=7, duration=45,
                            start="07:00") -> None:
    await gd_insert(db.session, "school_settings", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "working_days": ["sun", "mon", "tue", "wed", "thu"],
        "periods_per_day": periods,
        "period_duration": duration,
        "custom_settings": {"school_day_start": start},
        "language": "ar",
    })


async def _seed_it_session(ctx: dict, *, day, slot, class_id=None,
                           subject_id=None) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schedule_sessions", {
        "id": sid,
        "school_id": ctx["wsid"],
        "schedule_id": f"itw_schedule_{ctx['wsid']}",
        "teacher_id": ctx["teacher_id"],
        "status": "scheduled",
        "day_of_week": day,
        "slot_number": slot,
        "class_id": class_id,
        "subject_id": subject_id,
    })
    return sid


@pytest.mark.asyncio
async def test_teacher_schedule_endpoint_returns_it_sessions(client):
    """GET /teacher/schedule/{teacher_id} returns the IT workspace sessions
    with short day codes normalized and derived slot times."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"], periods=7, duration=45, start="07:00")
    await _seed_it_session(ctx, day="sun", slot=1, class_id=ctx["class_id"])
    await _seed_it_session(ctx, day="mon", slot=2, class_id=ctx["class_id"])

    h = it_headers(ctx)
    resp = await client.get(f"/teacher/schedule/{ctx['teacher_id']}", headers=h)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 2
    days = {r["day_of_week"] for r in rows}
    assert days == {"sunday", "monday"}  # short codes normalized
    first = next(r for r in rows if r["day_of_week"] == "sunday")
    assert first["slot_number"] == 1
    assert first["start_time"] == "07:00"
    assert first["end_time"] == "07:45"


@pytest.mark.asyncio
async def test_teacher_dashboard_today_filters_to_current_weekday(client):
    """The teacher dashboard 'today' block returns only sessions for the
    current weekday, normalized from the stored short codes."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"])

    today = _today_full()
    other = _other_full(today)
    await _seed_it_session(
        ctx, day=_FULL_TO_SHORT[today], slot=1, class_id=ctx["class_id"])
    await _seed_it_session(
        ctx, day=_FULL_TO_SHORT[other], slot=2, class_id=ctx["class_id"])

    h = it_headers(ctx)
    resp = await client.get(
        f"/teacher/dashboard/{ctx['teacher_id']}", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    today_schedule = body["today_schedule"]
    assert len(today_schedule) == 1
    assert today_schedule[0]["day_of_week"] == today
    assert today_schedule[0]["slot_number"] == 1
    assert body["stats"]["today_lessons"] == 1


@pytest.mark.asyncio
async def test_dashboard_and_schedule_agree_on_today(client):
    """The dashboard 'today' block is a subset of the full schedule endpoint —
    both read the same IT source of truth, so they can never disagree."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"])
    today = _today_full()
    await _seed_it_session(
        ctx, day=_FULL_TO_SHORT[today], slot=3, class_id=ctx["class_id"])

    h = it_headers(ctx)
    sched = await client.get(
        f"/teacher/schedule/{ctx['teacher_id']}", headers=h)
    dash = await client.get(
        f"/teacher/dashboard/{ctx['teacher_id']}", headers=h)
    assert sched.status_code == 200 and dash.status_code == 200

    sched_today = [r for r in sched.json() if r["day_of_week"] == today]
    dash_today = dash.json()["today_schedule"]
    assert len(sched_today) == 1
    assert len(dash_today) == 1
    assert sched_today[0]["id"] == dash_today[0]["id"]


@pytest.mark.asyncio
async def test_time_slots_blocked_for_it_role_but_schedule_reachable(client):
    """Perimeter documentation guard: the /time-slots router is gated by
    `require_full_school_tenant` and denies IT callers, while the teacher
    schedule endpoint (mounted without that gate) is reachable. This pins the
    boundary so a future remount can't silently break IT schedule reads or
    open a gated surface."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"])
    h = it_headers(ctx)

    blocked = await client.get(
        f"/time-slots?school_id={ctx['wsid']}", headers=h)
    assert blocked.status_code == 403
    body = blocked.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert INDEPENDENT_TEACHER_DENIED_AR in msg

    reachable = await client.get(
        f"/teacher/schedule/{ctx['teacher_id']}", headers=h)
    assert reachable.status_code == 200, reachable.text
