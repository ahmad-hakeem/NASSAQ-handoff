"""Focused regressions for operational timetable readers retired last."""

import uuid

from dependencies import db
from engines.sql_utils import gd_insert
from engines.timetable_session_lifecycle import count_live_timetable_sessions
from src.modules.portals.controllers.role_dashboards_mod import (
    _resolve_teacher_sessions,
)
from src.modules.schools.services.constraints_service import ConstraintsService


async def _insert(collection: str, **fields) -> dict:
    row = {"id": str(uuid.uuid4()), **fields}
    await gd_insert(db.session, collection, row)
    return row


async def _school(school_id: str) -> None:
    await _insert(
        "schools",
        id=school_id,
        name=f"Lifecycle readers {school_id[:6]}",
        code=f"LR{school_id[:8]}",
        status="active",
        country="SA",
        language="ar",
    )


async def test_live_count_is_null_safe_and_school_scoped():
    school_id = str(uuid.uuid4())
    other_school_id = str(uuid.uuid4())
    timetable_id = str(uuid.uuid4())

    for school, markers in [
        (school_id, {}),
        (school_id, {"is_active": None, "status": None}),
        (school_id, {"is_active": False}),
        (school_id, {"status": "cancelled"}),
        (other_school_id, {}),
    ]:
        await _insert(
            "timetable_sessions",
            school_id=school,
            timetable_id=timetable_id,
            **markers,
        )

    count = await count_live_timetable_sessions(
        db.session,
        {"school_id": school_id, "timetable_id": timetable_id},
    )

    assert count == 2


async def test_teacher_dashboard_schedule_excludes_retired_placements():
    school_id = str(uuid.uuid4())
    await _school(school_id)
    teacher_id = str(uuid.uuid4())
    class_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    timetable = await _insert(
        "timetables",
        school_id=school_id,
        name="Published operational timetable",
        status="published",
        published_at="2026-01-01T00:00:00+00:00",
    )
    await _insert(
        "classes", school_id=school_id, name="Live class", is_active=True,
        id=class_id,
    )
    await _insert(
        "subjects",
        school_id=school_id,
        name="Live subject",
        name_ar="Live subject",
        id=subject_id,
    )
    live = await _insert(
        "timetable_sessions",
        school_id=school_id,
        timetable_id=timetable["id"],
        teacher_id=teacher_id,
        class_id=class_id,
        subject_id=subject_id,
        day_of_week="sunday",
        period_number=1,
    )
    await _insert(
        "timetable_sessions",
        school_id=school_id,
        timetable_id=timetable["id"],
        teacher_id=teacher_id,
        class_id=class_id,
        subject_id=subject_id,
        day_of_week="monday",
        period_number=2,
        is_active=False,
    )
    await _insert(
        "timetable_sessions",
        school_id=school_id,
        timetable_id=timetable["id"],
        teacher_id=teacher_id,
        class_id=class_id,
        subject_id=subject_id,
        day_of_week="tuesday",
        period_number=3,
        status="cancelled",
    )

    sessions = await _resolve_teacher_sessions(school_id, teacher_id)

    assert [row["id"] for row in sessions] == [live["id"]]


async def test_workload_summary_counts_only_live_placements():
    school_id = str(uuid.uuid4())
    await _school(school_id)
    teacher = await _insert(
        "teachers",
        school_id=school_id,
        full_name="Operational teacher",
        is_active=True,
    )
    timetable = await _insert(
        "timetables",
        school_id=school_id,
        name="Draft operational timetable",
        status="draft",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    common = {
        "school_id": school_id,
        "timetable_id": timetable["id"],
        "teacher_id": teacher["id"],
    }
    await _insert("timetable_sessions", **common)
    await _insert("timetable_sessions", **common, is_active=None, status=None)
    await _insert("timetable_sessions", **common, is_active=False)
    await _insert("timetable_sessions", **common, status="cancelled")

    result = await ConstraintsService.get_workload_summary(
        db.session, {"tenant_id": school_id}
    )

    assert result["total_teachers"] == 1
    assert result["summary"][0]["teaching_periods"] == 2