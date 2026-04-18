"""Task 3 — detect_conflicts delegates to HardConstraintRegistry."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.engines.smart_scheduling_engine import (
    AcademicDemand,
    ConflictType,
    ResourceAvailability,
    SmartSchedulingEngine,
    TimetableSession,
)


def _mk_engine():
    db = MagicMock()
    db.session = MagicMock()
    return SmartSchedulingEngine(db)


def _session(
    *,
    sid: str,
    teacher_id: str = "t1",
    class_id: str = "c1",
    subject_id: str = "subj-1",
    day: str = "sunday",
    period: int = 1,
    room_id=None,
    timetable_id: str = "tt-1",
):
    """Build a session as a plain dict so room_id and other ad-hoc fields
    flow through detect_conflicts without fighting Pydantic schema."""
    return {
        "id": sid,
        "timetable_id": timetable_id,
        "school_id": "school-x",
        "class_id": class_id,
        "grade_id": "g1",
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "day_of_week": day,
        "period_number": period,
        "start_time": "08:00",
        "end_time": "08:45",
        "room_id": room_id,
    }


def _resource(teacher_id: str, subject_ids, weekly_load: int = 20):
    return ResourceAvailability(
        teacher_id=teacher_id,
        teacher_name=f"T-{teacher_id}",
        subject_ids=list(subject_ids),
        weekly_load=weekly_load,
        current_load=0,
        availability={"sunday": list(range(1, 8))},
    )


def _demand(class_id: str, subjects):
    return AcademicDemand(
        class_id=class_id,
        class_name=f"C-{class_id}",
        grade_id="g1",
        subjects=subjects,
        total_periods_required=sum(s["weekly_periods"] for s in subjects),
    )


@pytest.mark.asyncio
async def test_room_overlap_now_a_conflict():
    engine = _mk_engine()
    sessions = [
        _session(sid="s1", teacher_id="t1", class_id="c1", room_id="r1"),
        _session(sid="s2", teacher_id="t2", class_id="c2", room_id="r1"),
    ]
    resources = [_resource("t1", ["subj-1"]), _resource("t2", ["subj-1"])]
    constraints = [{"validation_key": "room_overlap", "is_active": True}]

    conflicts = await engine.detect_conflicts(
        sessions, resources, constraints, run_id="r-1"
    )

    types = [c.conflict_type for c in conflicts]
    assert ConflictType.ROOM_OVERLAP.value in types


@pytest.mark.asyncio
async def test_subject_quota_violation_emitted():
    engine = _mk_engine()
    sessions = [
        _session(sid=f"s{i}", teacher_id="t1", class_id="c1", subject_id="math",
                 day="sunday", period=i)
        for i in range(1, 4)  # 3 sessions placed, demand says 5
    ]
    resources = [_resource("t1", ["math"], weekly_load=30)]
    demands = [_demand("c1", [
        {"subject_id": "math", "weekly_periods": 5, "suitable_teachers": ["t1"]},
    ])]
    constraints = [
        {"validation_key": "subject_weekly_periods", "is_active": True},
    ]

    conflicts = await engine.detect_conflicts(
        sessions, resources, constraints, run_id="r-2",
        demands=demands,
    )

    types = [c.conflict_type for c in conflicts]
    assert ConflictType.SUBJECT_QUOTA_VIOLATION.value in types


@pytest.mark.asyncio
async def test_daily_period_limit_exceeded_emitted():
    engine = _mk_engine()
    sessions = [
        _session(sid=f"s{i}", teacher_id="t1", class_id=f"c{i}",
                 subject_id="subj-1", day="sunday", period=i)
        for i in range(1, 8)  # 7 sessions on sunday
    ]
    resources = [_resource("t1", ["subj-1"], weekly_load=30)]
    constraints = [
        {"validation_key": "daily_period_limit", "is_active": True},
    ]

    conflicts = await engine.detect_conflicts(
        sessions, resources, constraints, run_id="r-3",
        engine_settings={"max_daily_periods": 6},
    )

    types = [c.conflict_type for c in conflicts]
    assert ConflictType.DAILY_PERIOD_LIMIT_EXCEEDED.value in types


@pytest.mark.asyncio
async def test_teacher_overload_still_emitted():
    """Teacher exceeds weekly_load → TEACHER_OVERLOAD conflict (now via HC-08)."""
    engine = _mk_engine()
    sessions = [
        _session(sid=f"s{i}", teacher_id="t1", class_id=f"c{i % 2}",
                 subject_id="subj-1", day="sunday", period=((i % 5) + 1))
        for i in range(6)  # 6 sessions, weekly_load=3
    ]
    resources = [_resource("t1", ["subj-1"], weekly_load=3)]
    constraints = [
        {"validation_key": "teacher_weekly_load", "is_active": True},
    ]

    conflicts = await engine.detect_conflicts(
        sessions, resources, constraints, run_id="r-4",
    )

    types = [c.conflict_type for c in conflicts]
    assert ConflictType.TEACHER_OVERLOAD.value in types


def test_no_inline_teacher_overload_loop():
    """Grep guard: the inline TEACHER_OVERLOAD emit-site must be gone.

    The literal 'TEACHER_OVERLOAD' should appear EXACTLY ONCE in the source —
    namely the enum definition itself. The previous inline weekly-load loop
    used `ConflictType.TEACHER_OVERLOAD.value` and must be deleted; the
    teacher_weekly_load validator (HC-08) is now the single source of truth.
    """
    src = Path(__file__).resolve().parent.parent / "engines" / "smart_scheduling_engine.py"
    text = src.read_text(encoding="utf-8")
    count = text.count("TEACHER_OVERLOAD")
    assert count == 1, (
        f"Expected exactly 1 occurrence of 'TEACHER_OVERLOAD' (enum definition), "
        f"found {count}. The inline weekly-load loop must be removed."
    )


