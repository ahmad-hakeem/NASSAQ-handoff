"""Regression tests: the day-centric projection must expose multiple standby
teachers assigned to the same (day, period) across separate slot rows and
survive a fetch/projection round-trip.

Task: Let principals assign multiple teachers to one waiting period. The
backend already supports slot-addressable overrides; these tests lock in that
`project_day_centric_roster` renders each teacher of the same period on its own
slot_index row, grows `slot_count` accordingly, and that removing one teacher
leaves the others in that period intact.
"""
from __future__ import annotations

from services.standby_roster_service import project_day_centric_roster


DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
PERIODS = [1, 2, 3]


def _teachers():
    return [
        {"id": "t-1", "full_name": "أحمد", "specialization": "رياضيات"},
        {"id": "t-2", "full_name": "سارة", "specialization": "علوم"},
        {"id": "t-3", "full_name": "خالد", "specialization": "لغتي"},
    ]


def _add_override(tid, day, period, slot_index):
    return {
        "teacher_id": tid,
        "day": day,
        "period": period,
        "action": "add",
        "slot_index": slot_index,
    }


def _sunday(payload):
    return next(d for d in payload["days"] if d["day"] == "sunday")


def test_multiple_teachers_same_period_render_on_separate_slot_rows():
    """Two teachers pinned to sunday-period-1 (slots 1 and 2) must both appear,
    one per slot row, and slot_count must grow to 2."""
    overrides = [
        _add_override("t-1", "sunday", 1, 1),
        _add_override("t-2", "sunday", 1, 2),
    ]
    # Both teachers are legitimately on the final roster for this slot, so no
    # stale-override warnings fire.
    final_roster = {"t-1": {("sunday", 1)}, "t-2": {("sunday", 1)}}

    payload = project_day_centric_roster(
        final_roster=final_roster,
        teachers=_teachers(),
        overrides=overrides,
        busy={},
        periods=PERIODS,
        days=DAYS,
    )

    sunday = _sunday(payload)
    assert sunday["slot_count"] == 2, (
        f"expected slot_count=2 for two teachers, got {sunday['slot_count']}"
    )
    rows_by_slot = {r["slot_index"]: r for r in sunday["rows"]}
    assert rows_by_slot[1]["cells"]["1"]["teacher_id"] == "t-1"
    assert rows_by_slot[2]["cells"]["1"]["teacher_id"] == "t-2"
    assert payload["warnings"] == []


def test_three_teachers_same_period_all_survive_projection():
    """A third teacher stacks onto slot 3 of the same period without dropping
    the first two."""
    overrides = [
        _add_override("t-1", "sunday", 1, 1),
        _add_override("t-2", "sunday", 1, 2),
        _add_override("t-3", "sunday", 1, 3),
    ]
    final_roster = {
        "t-1": {("sunday", 1)},
        "t-2": {("sunday", 1)},
        "t-3": {("sunday", 1)},
    }

    payload = project_day_centric_roster(
        final_roster=final_roster,
        teachers=_teachers(),
        overrides=overrides,
        busy={},
        periods=PERIODS,
        days=DAYS,
    )

    sunday = _sunday(payload)
    assert sunday["slot_count"] == 3
    teacher_ids = {
        r["cells"]["1"]["teacher_id"]
        for r in sunday["rows"]
        if r["cells"].get("1")
    }
    assert teacher_ids == {"t-1", "t-2", "t-3"}


def test_removing_one_teacher_leaves_the_other_in_the_same_period():
    """Dropping the slot-2 override (simulating a remove) keeps the slot-1
    teacher pinned to the period — the remaining teacher is untouched."""
    overrides = [
        _add_override("t-1", "sunday", 1, 1),
    ]
    final_roster = {"t-1": {("sunday", 1)}}

    payload = project_day_centric_roster(
        final_roster=final_roster,
        teachers=_teachers(),
        overrides=overrides,
        busy={},
        periods=PERIODS,
        days=DAYS,
    )

    sunday = _sunday(payload)
    rows_by_slot = {r["slot_index"]: r for r in sunday["rows"]}
    assert rows_by_slot[1]["cells"]["1"]["teacher_id"] == "t-1"
    # No lingering second teacher anywhere in the period.
    all_period1_teachers = [
        r["cells"]["1"]["teacher_id"]
        for r in sunday["rows"]
        if r["cells"].get("1")
    ]
    assert all_period1_teachers == ["t-1"]
