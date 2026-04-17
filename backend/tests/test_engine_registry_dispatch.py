"""Task 6 — engine placement loop wires HardConstraintRegistry."""

import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.engines.smart_scheduling_engine import (
    AcademicDemand,
    ConflictSeverity,
    ResourceAvailability,
    SmartSchedulingEngine,
)


def _mk_engine():
    db = MagicMock()
    db.session = MagicMock()
    return SmartSchedulingEngine(db)


def _settings(periods=5, working_days=None):
    if working_days is None:
        working_days = ["sunday"]
    time_slots = [
        {"period": p, "start_time": f"08:{p:02d}", "end_time": f"08:{p+1:02d}", "type": "class"}
        for p in range(1, periods + 1)
    ]
    return {
        "working_days": working_days,
        "periods_per_day": periods,
        "time_slots": time_slots,
        "teaching_period_numbers": list(range(1, periods + 1)),
    }


def _resource(teacher_id, subject_ids, weekly_load=20, working_days=None, periods=5):
    if working_days is None:
        working_days = ["sunday"]
    avail = {d: list(range(1, periods + 1)) for d in working_days}
    return ResourceAvailability(
        teacher_id=teacher_id,
        teacher_name=f"T-{teacher_id}",
        subject_ids=subject_ids,
        weekly_load=weekly_load,
        current_load=0,
        availability=avail,
    )


def _demand(class_id, grade_id, subjects):
    return AcademicDemand(
        class_id=class_id,
        class_name=f"C-{class_id}",
        grade_id=grade_id,
        subjects=subjects,
        total_periods_required=sum(s["weekly_periods"] for s in subjects),
    )


@pytest.mark.asyncio
async def test_engine_rejects_candidate_violating_active_hard_constraint():
    """daily_period_limit set to 1 + active hard constraint row → engine
    cannot stack >1 session for a teacher per day."""
    engine = _mk_engine()
    teacher = "teacher-1"
    subject_a, subject_b = "subj-A", "subj-B"
    class_id, grade_id = "class-1", "grade-1"

    settings = _settings(periods=5, working_days=["sunday"])
    settings["max_daily_periods"] = 1

    demands = [_demand(class_id, grade_id, [
        {"subject_id": subject_a, "weekly_periods": 2, "suitable_teachers": [teacher], "priority": 1},
        {"subject_id": subject_b, "weekly_periods": 2, "suitable_teachers": [teacher], "priority": 1},
    ])]
    resources = [_resource(teacher, [subject_a, subject_b], weekly_load=10, periods=5)]

    constraints = [
        {"validation_key": "daily_period_limit", "is_active": True},
    ]

    _, sessions, _conflicts, _unsched, _under = await engine.generate_draft_timetable(
        "school-x", "run-1", demands, resources, settings, constraints,
    )

    by_day = {}
    for s in sessions:
        by_day.setdefault(s.day_of_week, []).append(s)
    for day, day_sessions in by_day.items():
        per_teacher = {}
        for s in day_sessions:
            per_teacher[s.teacher_id] = per_teacher.get(s.teacher_id, 0) + 1
        for tid, cnt in per_teacher.items():
            assert cnt <= 1, f"Teacher {tid} has {cnt} sessions on {day} despite daily_period_limit=1"


@pytest.mark.asyncio
async def test_engine_skips_inactive_hard_constraint():
    """Same fixture but is_active=False → daily_period_limit NOT enforced;
    teacher gets multiple sessions in the same day."""
    engine = _mk_engine()
    teacher = "teacher-1"
    subject_a, subject_b = "subj-A", "subj-B"
    class_id, grade_id = "class-1", "grade-1"

    settings = _settings(periods=5, working_days=["sunday"])
    settings["max_daily_periods"] = 1

    demands = [_demand(class_id, grade_id, [
        {"subject_id": subject_a, "weekly_periods": 2, "suitable_teachers": [teacher], "priority": 1},
        {"subject_id": subject_b, "weekly_periods": 2, "suitable_teachers": [teacher], "priority": 1},
    ])]
    resources = [_resource(teacher, [subject_a, subject_b], weekly_load=10, periods=5)]

    constraints = [
        {"validation_key": "daily_period_limit", "is_active": False},
    ]

    _, sessions, _c, _u, _under = await engine.generate_draft_timetable(
        "school-x", "run-2", demands, resources, settings, constraints,
    )

    teacher_sessions = [s for s in sessions if s.teacher_id == teacher]
    assert len(teacher_sessions) >= 2, (
        f"Inactive constraint should be skipped; expected >=2 sessions, got {len(teacher_sessions)}"
    )


@pytest.mark.asyncio
async def test_engine_still_honours_school_no_first_period_constraint():
    """REGRESSION: a school_constraints row with rule_key='no_first_period'
    on a subject must continue to block that subject from period 1."""
    engine = _mk_engine()
    teacher = "teacher-math"
    math = "subj-math"
    other = "subj-other"
    class_id, grade_id = "class-1", "grade-1"

    settings = _settings(periods=5, working_days=["sunday", "monday"])

    demands = [_demand(class_id, grade_id, [
        {"subject_id": math, "weekly_periods": 2, "suitable_teachers": [teacher], "priority": 1},
        {"subject_id": other, "weekly_periods": 2, "suitable_teachers": [teacher], "priority": 1},
    ])]
    resources = [_resource(teacher, [math, other], weekly_load=10, periods=5,
                           working_days=["sunday", "monday"])]

    constraints = [
        {"rule_key": "no_first_period", "subject_id": math, "is_active": True},
    ]

    _, sessions, _c, _u, _under = await engine.generate_draft_timetable(
        "school-x", "run-3", demands, resources, settings, constraints,
    )

    for s in sessions:
        if s.subject_id == math:
            assert s.period_number != 1, (
                f"Math session placed at period 1 on {s.day_of_week} despite no_first_period ban"
            )


def test_engine_no_longer_uses_inline_no_first_period_chain():
    """Grep guard: literal rule_key string-comparison chain MUST be gone."""
    src = Path(__file__).resolve().parent.parent / "engines" / "smart_scheduling_engine.py"
    text = src.read_text(encoding="utf-8")
    assert '== "no_first_period"' not in text, (
        "Inline rule_key chain still present for no_first_period"
    )
    assert '== "no_last_period"' not in text, (
        "Inline rule_key chain still present for no_last_period"
    )


@pytest.mark.asyncio
async def test_full_generation_still_succeeds_on_clean_fixture():
    """End-to-end happy-path on a tiny school via generate_draft_timetable.

    Records a wall-clock reading so the +25% perf budget can be tracked.
    """
    engine = _mk_engine()
    t1, t2 = "teacher-1", "teacher-2"
    s1, s2, s3 = "subj-1", "subj-2", "subj-3"
    c1, c2 = "class-1", "class-2"
    grade = "grade-1"

    working_days = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    settings = _settings(periods=5, working_days=working_days)

    demands = [
        _demand(c1, grade, [
            {"subject_id": s1, "weekly_periods": 3, "suitable_teachers": [t1], "priority": 1},
            {"subject_id": s2, "weekly_periods": 3, "suitable_teachers": [t2], "priority": 1},
            {"subject_id": s3, "weekly_periods": 2, "suitable_teachers": [t1, t2], "priority": 1},
        ]),
        _demand(c2, grade, [
            {"subject_id": s1, "weekly_periods": 3, "suitable_teachers": [t1], "priority": 1},
            {"subject_id": s2, "weekly_periods": 3, "suitable_teachers": [t2], "priority": 1},
            {"subject_id": s3, "weekly_periods": 2, "suitable_teachers": [t1, t2], "priority": 1},
        ]),
    ]
    resources = [
        _resource(t1, [s1, s3], weekly_load=20, periods=5, working_days=working_days),
        _resource(t2, [s2, s3], weekly_load=20, periods=5, working_days=working_days),
    ]
    constraints = []

    samples = []
    for run_idx in range(3):
        t0 = time.perf_counter()
        _, sessions, conflicts, _u, _under = await engine.generate_draft_timetable(
            "school-x", f"run-clean-{run_idx}", demands, resources, settings, constraints,
        )
        samples.append(time.perf_counter() - t0)

    median = sorted(samples)[1]
    print(f"\n[perf] generate_draft_timetable median = {median*1000:.2f} ms (samples={[f'{s*1000:.1f}' for s in samples]})")

    assert len(sessions) > 0, "clean fixture should produce sessions"
    critical = [c for c in conflicts if c.severity == ConflictSeverity.CRITICAL.value]
    assert critical == [], f"clean fixture produced CRITICAL conflicts: {critical}"
