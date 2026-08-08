from engines.scheduling_summary import (
    RejectionCounters,
    TeacherPlacementRecord,
    build_generation_summary,
)


def test_build_generation_summary_basic_shape():
    counters = RejectionCounters()
    counters.teacher_busy = 12
    counters.class_busy = 4
    counters.teacher_unavailable = 3
    counters.max_consecutive_exceeded = 5
    counters.max_per_day_exceeded = 2
    counters.weekly_quota_exceeded = 1
    counters.constraint_registry_rejected = 7
    counters.no_eligible_teacher = 0

    teacher_records = [
        TeacherPlacementRecord(
            teacher_id="t1",
            name="Yousef",
            by_day={"sun": 4, "mon": 3, "tue": 4, "wed": 4, "thu": 3},
            max_consecutive=3,
            gaps=1,
        )
    ]

    unplaced = [
        {"class_id": "c1", "subject_id": "s1", "remaining": 2, "primary_reason": "teacher_unavailable"},
    ]

    result = build_generation_summary(
        required=240,
        placed=235,
        elapsed_ms=1842,
        fairness_score=87,
        constraints_evaluated=[
            "double_booking_teacher",
            "double_booking_class",
            "unavailability",
            "boundary",
            "weekly_quota",
            "max_consecutive_per_day",
            "max_periods_per_day",
        ],
        rejection_counters=counters,
        teacher_records=teacher_records,
        unplaced_demands=unplaced,
    )

    assert result["schema_version"] == 1
    assert result["totals"] == {
        "required": 240,
        "placed": 235,
        "failed": 5,
        "placement_rate": 0.979,
    }
    assert result["elapsed_ms"] == 1842
    assert result["fairness"]["overall_score"] == 87
    assert result["fairness"]["per_teacher"][0]["total_periods"] == 18
    assert result["rejections_by_reason"]["teacher_busy"] == 12
    assert result["rejections_by_reason"]["no_eligible_teacher"] == 0
    assert result["unplaced_demands"] == unplaced


def test_build_generation_summary_zero_required():
    result = build_generation_summary(
        required=0,
        placed=0,
        elapsed_ms=10,
        fairness_score=0,
        constraints_evaluated=[],
        rejection_counters=RejectionCounters(),
        teacher_records=[],
        unplaced_demands=[],
    )
    assert result["totals"]["placement_rate"] is None
    assert result["totals"]["failed"] == 0


def test_rejection_counters_default_to_zero_in_output():
    counters = RejectionCounters()
    result = build_generation_summary(
        required=1, placed=1, elapsed_ms=1, fairness_score=0,
        constraints_evaluated=[], rejection_counters=counters,
        teacher_records=[], unplaced_demands=[],
    )
    for key in [
        "teacher_busy", "class_busy", "teacher_unavailable",
        "max_consecutive_exceeded", "max_per_day_exceeded",
        "weekly_quota_exceeded", "constraint_registry_rejected",
        "no_eligible_teacher",
    ]:
        assert result["rejections_by_reason"][key] == 0
