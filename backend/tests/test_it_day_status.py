"""Independent-Teacher (IT) `/school/day-status` progress-bar regression tests.

Before the fix, the handler returned a static neutral payload for
`independent_teacher` callers (progress bar stuck at defaults). IT workspaces
never persist a ``time_slots`` collection, so the handler must resolve the
synthetic per-user workspace id and synthesize slots from the teacher's own
period configuration — exactly like the ``/time-slots`` route already does.

These tests exercise the handler directly with monkeypatched data access, so
they neither read nor write the database.
"""
import pytest

import src.modules.schools.controllers.school_settings_mod as ssm

from tests.test_independent_teacher_schedule import (
    _headers,
    _mk_independent_teacher_with_workspace,
)

DAY_STATUS_PATH = "/school/day-status"


def _make_gd_stubs(settings, time_slots):
    async def _gd_find_one(session, collection, query, *args, **kwargs):
        if collection == "school_settings":
            return settings
        return None

    async def _gd_find(session, collection, query, *args, **kwargs):
        if collection == "time_slots":
            return list(time_slots)
        return []

    return _gd_find_one, _gd_find


@pytest.mark.asyncio
async def test_it_day_status_synthesizes_slots(monkeypatch):
    """IT caller with no persisted time_slots gets a computed payload built
    from its own period configuration, not the neutral fallback."""
    settings = {
        "school_id": "itw_u123",
        "custom_settings": {
            "periods_per_day": 6,
            "period_duration_minutes": 40,
            "school_day_start": "08:00",
        },
    }
    gd_find_one, gd_find = _make_gd_stubs(settings, [])
    monkeypatch.setattr(ssm, "gd_find_one", gd_find_one)
    monkeypatch.setattr(ssm, "gd_find", gd_find)

    current_user = {"role": "independent_teacher", "id": "u123"}
    result = await ssm.get_school_day_status(current_user=current_user, x_school_context=None)

    # Not the neutral payload: the day window reflects the IT's own config.
    assert result["total_periods"] == 6
    assert result["day_start"] == "08:00"
    assert result["is_working_day"] is True
    # Synthesized virtual slots are returned so the timeline renders.
    assert len(result["time_slots"]) == 6
    assert all(s["start_time"] and s["end_time"] for s in result["time_slots"])


@pytest.mark.asyncio
async def test_it_day_status_defaults_when_no_settings(monkeypatch):
    """IT caller with no school_settings still returns a computed default
    window (7 periods) rather than an empty neutral payload."""
    gd_find_one, gd_find = _make_gd_stubs(None, [])
    monkeypatch.setattr(ssm, "gd_find_one", gd_find_one)
    monkeypatch.setattr(ssm, "gd_find", gd_find)

    current_user = {"role": "independent_teacher", "id": "u999"}
    result = await ssm.get_school_day_status(current_user=current_user, x_school_context=None)

    assert result["total_periods"] == 7
    assert result["day_start"] == "07:00"
    assert len(result["time_slots"]) == 7


@pytest.mark.asyncio
async def test_non_it_without_tenant_returns_neutral(monkeypatch):
    """A non-IT caller with no tenant context still gets the neutral payload
    (the IT branch must not change the regular-school contract)."""
    gd_find_one, gd_find = _make_gd_stubs({}, [])
    monkeypatch.setattr(ssm, "gd_find_one", gd_find_one)
    monkeypatch.setattr(ssm, "gd_find", gd_find)

    current_user = {"role": "teacher", "id": "t1"}  # no tenant_id / school_id
    result = await ssm.get_school_day_status(current_user=current_user, x_school_context=None)

    assert result["total_periods"] == 0
    assert result["day_start"] is None
    assert result["time_slots"] == []


@pytest.mark.asyncio
async def test_it_caller_reaches_day_status_over_http(client):
    """The router-gate regression: an IT caller must NOT get the full-tenant
    403 on ``/school/day-status`` and must receive a computed payload built
    from its own workspace settings. This is the HTTP-level guard that a
    direct handler call cannot provide — it exercises the router mount."""
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])

    resp = await client.get(DAY_STATUS_PATH, headers=h)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Workspace seeded with periods_per_day=7 → computed window, not neutral.
    assert body["total_periods"] == 7
    assert body["day_start"] == "07:00"
    assert body["is_working_day"] is True
    class_slots = [s for s in body["time_slots"] if not s.get("is_break")]
    assert class_slots, f"expected synthesised class slots, got {body['time_slots']}"
    assert all(s["start_time"] and s["end_time"] for s in class_slots)
