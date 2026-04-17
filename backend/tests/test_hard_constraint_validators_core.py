"""Task 2 — core hard-constraint validators tests."""

from backend.engines.hard_constraints.validators import (
    class_overlap,
    daily_period_limit,
    room_overlap,
    subject_weekly_periods,
    teacher_overlap,
)
from backend.engines.hard_constraints.types import ConstraintContext


def _ctx(sessions=None, demands=None, settings=None):
    return ConstraintContext(
        school_id="school-test",
        sessions=sessions or [],
        demands=demands or [],
        resources={},
        time_slots=[],
        settings=settings or {},
        active_validation_keys=set(),
    )


def test_teacher_overlap_detects_collision():
    sessions = [
        {"id": "s1", "teacher_id": "t1", "day_of_week": 0, "period_number": 1, "class_id": "c1"},
        {"id": "s2", "teacher_id": "t1", "day_of_week": 0, "period_number": 1, "class_id": "c2"},
    ]
    violations = teacher_overlap.validate(_ctx(sessions=sessions))
    assert len(violations) == 1
    v = violations[0]
    assert v.code == "HC-01"
    assert v.validation_key == "teacher_overlap"
    ids = v.refs.get("session_ids", [])
    assert "s1" in ids and "s2" in ids


def test_teacher_overlap_no_collision():
    sessions = [
        {"id": "s1", "teacher_id": "t1", "day_of_week": 0, "period_number": 1, "class_id": "c1"},
        {"id": "s2", "teacher_id": "t1", "day_of_week": 0, "period_number": 2, "class_id": "c2"},
    ]
    assert teacher_overlap.validate(_ctx(sessions=sessions)) == []


def test_class_overlap_detects_collision():
    sessions = [
        {"id": "s1", "class_id": "c1", "day_of_week": 0, "period_number": 1, "teacher_id": "t1"},
        {"id": "s2", "class_id": "c1", "day_of_week": 0, "period_number": 1, "teacher_id": "t2"},
    ]
    violations = class_overlap.validate(_ctx(sessions=sessions))
    assert len(violations) == 1
    assert violations[0].code == "HC-02"
    assert violations[0].validation_key == "class_overlap"


def test_room_overlap_detects_collision():
    sessions = [
        {"id": "s1", "room_id": "r1", "day_of_week": 0, "period_number": 1},
        {"id": "s2", "room_id": "r1", "day_of_week": 0, "period_number": 1},
    ]
    violations = room_overlap.validate(_ctx(sessions=sessions))
    assert len(violations) == 1
    assert violations[0].code == "HC-03"


def test_room_overlap_skips_null_room():
    sessions = [
        {"id": "s1", "room_id": None, "day_of_week": 0, "period_number": 1},
        {"id": "s2", "room_id": None, "day_of_week": 0, "period_number": 1},
    ]
    assert room_overlap.validate(_ctx(sessions=sessions)) == []


def test_subject_weekly_periods_under_target():
    sessions = [
        {"class_id": "c1", "subject_id": "math"} for _ in range(3)
    ]
    demands = [{"class_id": "c1", "subject_id": "math", "weekly_periods": 5}]
    violations = subject_weekly_periods.validate(_ctx(sessions=sessions, demands=demands))
    assert len(violations) == 1
    refs = violations[0].refs
    assert refs["class_id"] == "c1"
    assert refs["subject_id"] == "math"
    assert refs["expected"] == 5
    assert refs["actual"] == 3
    assert refs["delta"] == -2


def test_subject_weekly_periods_over_target():
    sessions = [
        {"class_id": "c1", "subject_id": "math"} for _ in range(6)
    ]
    demands = [{"class_id": "c1", "subject_id": "math", "weekly_periods": 5}]
    violations = subject_weekly_periods.validate(_ctx(sessions=sessions, demands=demands))
    assert len(violations) == 1
    assert violations[0].refs["delta"] == 1


def test_daily_period_limit_default_six():
    sessions_7 = [
        {"teacher_id": "t1", "day_of_week": 0, "period_number": p} for p in range(1, 8)
    ]
    violations = daily_period_limit.validate(_ctx(sessions=sessions_7))
    assert len(violations) == 1

    sessions_6 = [
        {"teacher_id": "t1", "day_of_week": 0, "period_number": p} for p in range(1, 7)
    ]
    assert daily_period_limit.validate(_ctx(sessions=sessions_6)) == []


def test_daily_period_limit_respects_school_setting():
    sessions = [
        {"teacher_id": "t1", "day_of_week": 0, "period_number": p} for p in range(1, 6)
    ]
    violations = daily_period_limit.validate(
        _ctx(sessions=sessions, settings={"max_daily_periods": 4})
    )
    assert len(violations) == 1
    assert violations[0].refs["limit"] == 4
