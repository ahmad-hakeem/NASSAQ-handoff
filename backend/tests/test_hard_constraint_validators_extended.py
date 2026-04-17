"""Task 4 — tests for the 12 remaining hard-constraint validators."""

from backend.engines.hard_constraints import VALIDATION_REGISTRY
from backend.engines.hard_constraints.types import ConstraintContext
from backend.engines.hard_constraints.validators import (
    academic_structure_match,
    block_publish_on_conflict,
    entity_integrity,
    no_consecutive_subject,
    non_teaching_period,
    resource_single_booking,
    schedule_completeness,
    school_day_boundary,
    teacher_class_assignment,
    teacher_subject_match,
    teacher_weekly_load,
    working_days,
)


def _ctx(**overrides):
    base = dict(
        school_id="s1",
        sessions=[],
        demands=[],
        resources={
            "teachers": {},
            "classes": {},
            "subjects": {},
            "rooms": {},
            "teacher_assignments": set(),
        },
        time_slots=[],
        settings={},
        active_validation_keys=set(VALIDATION_REGISTRY.keys()),
    )
    base.update(overrides)
    return ConstraintContext(**base)


# ---------- HC-04 school_day_boundary ----------

def test_hc04_school_day_boundary_ok():
    ctx = _ctx(time_slots=[{"day_of_week": "sunday", "period_number": 1}])
    cand = {"day_of_week": "sunday", "period_number": 1}
    assert school_day_boundary.validate(ctx, cand) == []


def test_hc04_school_day_boundary_violation():
    ctx = _ctx(time_slots=[{"day_of_week": "sunday", "period_number": 1}])
    cand = {"day_of_week": "sunday", "period_number": 99}
    out = school_day_boundary.validate(ctx, cand)
    assert len(out) >= 1
    assert out[0].validation_key == "school_day_boundary"


# ---------- HC-05 non_teaching_period ----------

def test_hc05_non_teaching_period_ok():
    ctx = _ctx(time_slots=[
        {"day_of_week": "sunday", "period_number": 1, "is_break": False, "is_prayer": False},
    ])
    cand = {"day_of_week": "sunday", "period_number": 1}
    assert non_teaching_period.validate(ctx, cand) == []


def test_hc05_non_teaching_period_violation():
    ctx = _ctx(time_slots=[
        {"day_of_week": "sunday", "period_number": 3, "is_break": True, "is_prayer": False},
    ])
    cand = {"day_of_week": "sunday", "period_number": 3}
    out = non_teaching_period.validate(ctx, cand)
    assert len(out) >= 1
    assert out[0].validation_key == "non_teaching_period"


# ---------- HC-07 working_days ----------

def test_hc07_working_days_ok():
    ctx = _ctx(settings={"working_days": ["sunday", "monday"]})
    cand = {"day_of_week": "sunday", "period_number": 1}
    assert working_days.validate(ctx, cand) == []


def test_hc07_working_days_violation():
    ctx = _ctx(settings={"working_days": ["sunday", "monday"]})
    cand = {"day_of_week": "friday", "period_number": 1}
    out = working_days.validate(ctx, cand)
    assert len(out) >= 1
    assert out[0].validation_key == "working_days"


# ---------- HC-08 teacher_weekly_load ----------

def test_hc08_teacher_weekly_load_ok():
    ctx = _ctx(
        sessions=[{"teacher_id": "t1"} for _ in range(5)],
        resources={
            "teachers": {"t1": {"weekly_load": 10}},
            "classes": {}, "subjects": {}, "rooms": {}, "teacher_assignments": set(),
        },
    )
    assert teacher_weekly_load.validate(ctx) == []


def test_hc08_teacher_weekly_load_violation():
    ctx = _ctx(
        sessions=[{"teacher_id": "t1"} for _ in range(11)],
        resources={
            "teachers": {"t1": {"weekly_load": 10}},
            "classes": {}, "subjects": {}, "rooms": {}, "teacher_assignments": set(),
        },
    )
    out = teacher_weekly_load.validate(ctx)
    assert len(out) >= 1
    assert out[0].validation_key == "teacher_weekly_load"


# ---------- HC-10 no_consecutive_subject ----------

def test_hc10_no_consecutive_subject_ok():
    ctx = _ctx(sessions=[
        {"class_id": "c1", "subject_id": "math", "day_of_week": "sunday", "period_number": 1},
        {"class_id": "c1", "subject_id": "math", "day_of_week": "sunday", "period_number": 3},
    ])
    cand = {"class_id": "c1", "subject_id": "math", "day_of_week": "sunday", "period_number": 5}
    assert no_consecutive_subject.validate(ctx, cand) == []


def test_hc10_no_consecutive_subject_violation():
    ctx = _ctx(sessions=[
        {"class_id": "c1", "subject_id": "math", "day_of_week": "sunday", "period_number": 1},
        {"class_id": "c1", "subject_id": "math", "day_of_week": "sunday", "period_number": 2},
    ])
    out = no_consecutive_subject.validate(ctx)
    assert len(out) >= 1
    assert out[0].validation_key == "no_consecutive_subject"


# ---------- HC-11 teacher_subject_match ----------

def test_hc11_teacher_subject_match_ok():
    ctx = _ctx(resources={
        "teachers": {"t1": {"qualifications": ["math", "physics"]}},
        "classes": {}, "subjects": {}, "rooms": {}, "teacher_assignments": set(),
    })
    cand = {"teacher_id": "t1", "subject_id": "math"}
    assert teacher_subject_match.validate(ctx, cand) == []


def test_hc11_teacher_subject_match_violation():
    ctx = _ctx(resources={
        "teachers": {"t1": {"qualifications": ["physics"]}},
        "classes": {}, "subjects": {}, "rooms": {}, "teacher_assignments": set(),
    })
    cand = {"teacher_id": "t1", "subject_id": "math"}
    out = teacher_subject_match.validate(ctx, cand)
    assert len(out) >= 1
    assert out[0].validation_key == "teacher_subject_match"


# ---------- HC-12 teacher_class_assignment ----------

def test_hc12_teacher_class_assignment_ok():
    ctx = _ctx(resources={
        "teachers": {}, "classes": {}, "subjects": {}, "rooms": {},
        "teacher_assignments": {("t1", "c1", "math")},
    })
    cand = {"teacher_id": "t1", "class_id": "c1", "subject_id": "math"}
    assert teacher_class_assignment.validate(ctx, cand) == []


def test_hc12_teacher_class_assignment_violation():
    ctx = _ctx(resources={
        "teachers": {}, "classes": {}, "subjects": {}, "rooms": {},
        "teacher_assignments": {("t1", "c1", "physics")},
    })
    cand = {"teacher_id": "t1", "class_id": "c1", "subject_id": "math"}
    out = teacher_class_assignment.validate(ctx, cand)
    assert len(out) >= 1
    assert out[0].validation_key == "teacher_class_assignment"


# ---------- HC-13 resource_single_booking ----------

def test_hc13_resource_single_booking_ok():
    ctx = _ctx(sessions=[
        {"required_resource_id": "lab1", "day_of_week": "sunday", "period_number": 1},
        {"required_resource_id": "lab1", "day_of_week": "sunday", "period_number": 2},
        {"required_resource_id": None, "day_of_week": "sunday", "period_number": 1},
    ])
    assert resource_single_booking.validate(ctx) == []


def test_hc13_resource_single_booking_violation():
    ctx = _ctx(sessions=[
        {"required_resource_id": "lab1", "day_of_week": "sunday", "period_number": 1},
        {"required_resource_id": "lab1", "day_of_week": "sunday", "period_number": 1},
    ])
    out = resource_single_booking.validate(ctx)
    assert len(out) >= 1
    assert out[0].validation_key == "resource_single_booking"


# ---------- HC-14 schedule_completeness ----------

def test_hc14_schedule_completeness_ok():
    ctx = _ctx(
        demands=[{"class_id": "c1", "subject_id": "math", "weekly_periods": 2}],
        sessions=[
            {"class_id": "c1", "subject_id": "math"},
            {"class_id": "c1", "subject_id": "math"},
        ],
    )
    assert schedule_completeness.validate(ctx) == []


def test_hc14_schedule_completeness_violation():
    ctx = _ctx(
        demands=[
            {"class_id": "c1", "subject_id": "math", "weekly_periods": 5},
            {"class_id": "c1", "subject_id": "arabic", "weekly_periods": 4},
        ],
        sessions=[
            {"class_id": "c1", "subject_id": "math"},
            {"class_id": "c1", "subject_id": "math"},
            {"class_id": "c1", "subject_id": "arabic"},
            {"class_id": "c1", "subject_id": "arabic"},
            {"class_id": "c1", "subject_id": "arabic"},
            {"class_id": "c1", "subject_id": "arabic"},
        ],
    )
    out = schedule_completeness.validate(ctx)
    assert len(out) == 1
    assert out[0].validation_key == "schedule_completeness"
    assert out[0].refs["class_id"] == "c1"
    assert any(m["subject_id"] == "math" for m in out[0].refs["missing_subjects"])


# ---------- HC-15 academic_structure_match ----------

def test_hc15_academic_structure_match_ok():
    ctx = _ctx(
        sessions=[{"class_id": "c1", "subject_id": "math"}],
        resources={
            "teachers": {}, "subjects": {}, "rooms": {},
            "classes": {"c1": {"curriculum_subject_ids": {"math", "arabic"}}},
            "teacher_assignments": set(),
        },
    )
    assert academic_structure_match.validate(ctx) == []


def test_hc15_academic_structure_match_violation():
    ctx = _ctx(
        sessions=[{"class_id": "c1", "subject_id": "music"}],
        resources={
            "teachers": {}, "subjects": {}, "rooms": {},
            "classes": {"c1": {"curriculum_subject_ids": {"math", "arabic"}}},
            "teacher_assignments": set(),
        },
    )
    out = academic_structure_match.validate(ctx)
    assert len(out) >= 1
    assert out[0].validation_key == "academic_structure_match"


# ---------- HC-16 entity_integrity ----------

def test_hc16_entity_integrity_ok():
    ctx = _ctx(resources={
        "teachers": {"t1": {}}, "classes": {"c1": {}}, "subjects": {"math": {}},
        "rooms": {"r1": {}}, "teacher_assignments": set(),
    })
    cand = {"teacher_id": "t1", "class_id": "c1", "subject_id": "math", "room_id": "r1"}
    assert entity_integrity.validate(ctx, cand) == []


def test_hc16_entity_integrity_violation():
    ctx = _ctx(resources={
        "teachers": {"t1": {}}, "classes": {"c1": {}}, "subjects": {"math": {}},
        "rooms": {}, "teacher_assignments": set(),
    })
    cand = {"teacher_id": "tX", "class_id": "c1", "subject_id": "math", "room_id": None}
    out = entity_integrity.validate(ctx, cand)
    assert len(out) >= 1
    assert out[0].validation_key == "entity_integrity"


# ---------- HC-17 block_publish_on_conflict ----------

def test_hc17_block_publish_on_conflict_is_noop():
    ctx = _ctx()
    assert block_publish_on_conflict.validate(ctx) == []
