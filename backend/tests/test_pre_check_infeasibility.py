"""Task 7 — pre-generation infeasibility report (INF-01..INF-05) and
422 gating on generation endpoints.
"""

import uuid

import pytest

from dependencies import db
from engines.smart_scheduling_engine import SmartSchedulingEngine
from engines.sql_utils import gd_insert, gd_count, gd_delete_many
from engines.infeasibility import InfeasibilityReport, InfeasibilityIssue


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

async def _mk_settings(school_id, working_days, periods_per_day):
    await gd_insert(db.session, "school_settings", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "working_days": working_days,
        "periods_per_day": periods_per_day,
    })


async def _mk_time_slot(school_id, slot_number, *, is_break=False, is_prayer=False):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "time_slots", {
        "id": sid,
        "school_id": school_id,
        "name": f"Period {slot_number}",
        "slot_number": slot_number,
        "start_time": f"{6 + slot_number:02d}:00",
        "end_time": f"{7 + slot_number:02d}:00",
        "duration_minutes": 45,
        "is_break": is_break,
        "is_prayer": is_prayer,
        "is_active": True,
    })
    return sid


async def _mk_class(school_id, grade_id):
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "name": f"C-{cid[:6]}",
        "grade_id": grade_id,
        "is_active": True,
    })
    return cid


async def _mk_subject(school_id, name="Math"):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid,
        "school_id": school_id,
        "name": name,
        "is_active": True,
    })
    return sid


async def _mk_grade_subject(school_id, grade_id, subject_id, weekly_periods):
    gsid = str(uuid.uuid4())
    await gd_insert(db.session, "grade_subjects", {
        "id": gsid,
        "school_id": school_id,
        "grade_id": grade_id,
        "subject_id": subject_id,
        "weekly_periods": weekly_periods,
        "is_active": True,
    })
    return gsid


async def _mk_teacher(school_id, weekly_load=24):
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "school_id": school_id,
        "full_name": f"T-{tid[:6]}",
        "weekly_periods": weekly_load,
        "is_active": True,
    })
    return tid


async def _mk_assignment(school_id, teacher_id, subject_id, class_id):
    aid = str(uuid.uuid4())
    await gd_insert(db.session, "teacher_assignments", {
        "id": aid,
        "school_id": school_id,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "class_id": class_id,
        "weekly_sessions": 4,
        "periods_per_week": 4,
        "is_active": True,
    })
    return aid


# ---------------------------------------------------------------------------
# 1. INF-01 total demand exceeds available teaching slots
# ---------------------------------------------------------------------------

async def test_pre_check_returns_infeasibility_report_when_total_demand_exceeds_slots(
    tenant_a,
):
    grade = "g1"
    await _mk_settings(tenant_a, ["sunday", "monday", "tuesday"], 10)
    # 30 teaching slots total per class (3 days * 10 periods).
    for n in range(1, 11):
        await _mk_time_slot(tenant_a, n, is_break=False)
    await _mk_class(tenant_a, grade)
    subj = await _mk_subject(tenant_a)
    await _mk_grade_subject(tenant_a, grade, subj, weekly_periods=100)

    engine = SmartSchedulingEngine(db)
    report = await engine.build_infeasibility_report(tenant_a)

    assert type(report).__name__ == "InfeasibilityReport"
    assert report.blocks_generation is True
    codes = {i.code for i in report.issues}
    assert "INF-01" in codes


# ---------------------------------------------------------------------------
# 2. INF-02 per-class capacity overrun
# ---------------------------------------------------------------------------

async def test_pre_check_returns_blocker_for_per_class_capacity_overrun(tenant_a):
    grade = "g1"
    await _mk_settings(tenant_a, ["sunday", "monday"], 5)  # cap=10
    for n in range(1, 6):
        await _mk_time_slot(tenant_a, n, is_break=False)
    cls = await _mk_class(tenant_a, grade)
    subj = await _mk_subject(tenant_a)
    await _mk_grade_subject(tenant_a, grade, subj, weekly_periods=50)

    engine = SmartSchedulingEngine(db)
    report = await engine.build_infeasibility_report(tenant_a)

    assert report.blocks_generation is True
    inf02 = [i for i in report.issues if i.code == "INF-02"]
    assert inf02, f"Expected at least one INF-02 issue, got: {[i.code for i in report.issues]}"
    # The per-class issue references the offending class.
    assert any(i.refs.get("class_id") == cls for i in inf02)


# ---------------------------------------------------------------------------
# 3. INF-05 zero time_slots
# ---------------------------------------------------------------------------

async def test_pre_check_returns_blocker_for_no_time_slots(tenant_a):
    await _mk_settings(tenant_a, ["sunday"], 5)
    await _mk_class(tenant_a, "g1")
    # No time_slots inserted at all.

    engine = SmartSchedulingEngine(db)
    report = await engine.build_infeasibility_report(tenant_a)

    assert report.blocks_generation is True
    assert any(i.code == "INF-05" for i in report.issues)


# ---------------------------------------------------------------------------
# 4. POST /smart-scheduling/generate returns 422 when blocker present
# ---------------------------------------------------------------------------

async def test_generate_returns_422_when_blocker_present(
    client, school_principal_headers, tenant_a,
):
    grade = "g1"
    await _mk_settings(tenant_a, ["sunday"], 5)
    for n in range(1, 6):
        await _mk_time_slot(tenant_a, n, is_break=False)
    await _mk_class(tenant_a, grade)
    subj = await _mk_subject(tenant_a)
    await _mk_grade_subject(tenant_a, grade, subj, weekly_periods=200)
    await db.session.commit()

    count_before = await gd_count(db.session, "timetables", {"school_id": tenant_a})

    r = await client.post(
        f"/smart-scheduling/generate/{tenant_a}",
        headers=school_principal_headers,
        json={},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    # The app's HTTPException handler may wrap detail in an envelope.
    text = r.text
    assert "INF-01" in text or "GENERATION_BLOCKED" in text
    assert "GENERATION_BLOCKED" in text

    count_after = await gd_count(db.session, "timetables", {"school_id": tenant_a})
    assert count_after == count_before, (
        f"Expected no new timetable rows, before={count_before} after={count_after}"
    )


# ---------------------------------------------------------------------------
# 5. Clean fixture: no infeasibility issues
# ---------------------------------------------------------------------------

async def test_pre_check_clean_when_capacity_ok(tenant_a):
    grade = "g1"
    await _mk_settings(tenant_a, ["sunday", "monday", "tuesday", "wednesday", "thursday"], 5)
    for n in range(1, 6):
        await _mk_time_slot(tenant_a, n, is_break=False)
    cls = await _mk_class(tenant_a, grade)
    subj = await _mk_subject(tenant_a)
    await _mk_grade_subject(tenant_a, grade, subj, weekly_periods=5)
    teacher = await _mk_teacher(tenant_a, weekly_load=20)
    await _mk_assignment(tenant_a, teacher, subj, cls)

    engine = SmartSchedulingEngine(db)
    report = await engine.build_infeasibility_report(tenant_a)

    assert report.blocks_generation is False
    assert report.issues == []


# ---------------------------------------------------------------------------
# 6. Advisory issues do NOT block generation (HTTP path)
# ---------------------------------------------------------------------------

async def test_advisory_issue_does_not_block_generation(
    client, school_principal_headers, tenant_a,
):
    grade = "g1"
    await _mk_settings(tenant_a, ["sunday", "monday", "tuesday", "wednesday", "thursday"], 5)
    for n in range(1, 6):
        await _mk_time_slot(tenant_a, n, is_break=False)
    cls = await _mk_class(tenant_a, grade)
    subj = await _mk_subject(tenant_a)
    # Demand exactly equals supply: tight but feasible.
    await _mk_grade_subject(tenant_a, grade, subj, weekly_periods=20)
    teacher = await _mk_teacher(tenant_a, weekly_load=20)
    await _mk_assignment(tenant_a, teacher, subj, cls)
    await db.session.commit()

    engine = SmartSchedulingEngine(db)
    report = await engine.build_infeasibility_report(tenant_a)
    assert report.blocks_generation is False
    # Any emitted issues must be advisory, not blockers.
    for issue in report.issues:
        assert issue.severity == "advisory"

    r = await client.post(
        f"/smart-scheduling/generate/{tenant_a}",
        headers=school_principal_headers,
        json={},
    )
    assert r.status_code != 422, (
        f"Generation should not be blocked by advisory; got 422: {r.text}"
    )
