"""Regression tests: auto standby slots must only land on periods that
actually exist in the school's active timetable.

Bug: `compute_standby_roster` used a hardcoded ``PERIODS = 1..12`` universe,
so the fairness allocator could place standby slots at periods no class ever
meets at (e.g. period 12 in a school whose day ends at period 9). Such
phantom slots can never be covered and surface to teachers as a permanent
"بانتظار الإسناد" row. The eligible-period universe must instead be derived
from the timetable's own sessions.
"""
from __future__ import annotations

import uuid

import pytest


def _session(school_id, timetable_id, *, teacher_id, day, period):
    return {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "timetable_id": timetable_id,
        "teacher_id": teacher_id,
        "day_of_week": day,
        "period_number": period,
    }


@pytest.mark.asyncio
async def test_auto_standby_never_lands_on_absent_periods(tenant_a):
    """A timetable whose only periods are {1,2,3} must never yield standby
    slots at periods 4..12, even under allocation/cap pressure from many
    fully-free teachers."""
    from dependencies import db
    from services.standby_roster_service import compute_standby_roster

    school_id = tenant_a
    timetable_id = str(uuid.uuid4())
    real_periods = {1, 2, 3}

    # Establish the timetable's period universe with sessions owned by a
    # teacher NOT in our roster set, so none of the teachers below are
    # marked busy by them.
    universe_owner = str(uuid.uuid4())
    sessions = [
        _session(school_id, timetable_id, teacher_id=universe_owner,
                 day="sunday", period=p)
        for p in real_periods
    ]

    # 20 fully-free teachers: pre-fix the fairness allocator spread these
    # across the full 1..12 range (least-loaded first), filling phantom
    # periods 4..12 that don't exist in the timetable.
    teachers = [
        {"id": str(uuid.uuid4()), "school_id": school_id,
         "full_name": f"T{i:02d}", "weekly_periods": 24, "is_active": True}
        for i in range(20)
    ]

    roster = await compute_standby_roster(
        db.session,
        school_id=school_id,
        timetable_id=timetable_id,
        teachers=teachers,
        sessions=sessions,
        apply_overrides=False,
    )

    bad = sorted(
        (d, p)
        for slots in roster.values()
        for (d, p) in slots
        if p not in real_periods
    )
    assert not bad, f"standby assigned at periods absent from timetable: {bad}"


@pytest.mark.asyncio
async def test_auto_standby_still_fills_real_free_periods(tenant_a):
    """No-regression: real free periods are still used for standby."""
    from dependencies import db
    from services.standby_roster_service import compute_standby_roster

    school_id = tenant_a
    timetable_id = str(uuid.uuid4())
    real_periods = {1, 2, 3}

    universe_owner = str(uuid.uuid4())
    sessions = [
        _session(school_id, timetable_id, teacher_id=universe_owner,
                 day=d, period=p)
        for d in ("sunday", "monday", "tuesday", "wednesday", "thursday")
        for p in real_periods
    ]

    teacher_id = str(uuid.uuid4())
    teachers = [{
        "id": teacher_id, "school_id": school_id, "full_name": "Solo",
        "weekly_periods": 24, "is_active": True,
    }]

    roster = await compute_standby_roster(
        db.session,
        school_id=school_id,
        timetable_id=timetable_id,
        teachers=teachers,
        sessions=sessions,
        apply_overrides=False,
    )
    chosen = roster.get(teacher_id, set())
    assert chosen, "expected standby slots at real free periods"
    assert all(p in real_periods for (_, p) in chosen), (
        f"standby landed on a period absent from the timetable: {sorted(chosen)}"
    )
