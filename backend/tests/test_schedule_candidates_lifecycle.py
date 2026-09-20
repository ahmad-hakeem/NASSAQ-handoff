"""Real-DB regressions for candidate-picker timetable lifecycle handling."""

import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_insert


def _id() -> str:
    return str(uuid.uuid4())


async def _seed_timetable(school_id: str) -> str:
    timetable_id = _id()
    await gd_insert(db.session, "timetables", {
        "id": timetable_id,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": "Candidate lifecycle regression",
        "academic_year": "2026-2027",
        "semester": 1,
        "status": "draft",
    })
    return timetable_id


async def _seed_teacher(school_id: str, name: str) -> str:
    teacher_id = _id()
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": school_id,
        "tenant_id": school_id,
        "full_name": name,
        "weekly_periods": 4,
        "is_active": True,
    })
    return teacher_id


async def _seed_class(school_id: str, name: str) -> str:
    class_id = _id()
    await gd_insert(db.session, "classes", {
        "id": class_id,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": name,
        "grade_id": _id(),
        "is_active": True,
    })
    return class_id


async def _seed_session(
    school_id: str,
    timetable_id: str,
    teacher_id: str,
    class_id: str,
    day: str,
    period: int,
    **lifecycle,
) -> str:
    session_id = _id()
    row = {
        "id": session_id,
        "school_id": school_id,
        "tenant_id": school_id,
        "timetable_id": timetable_id,
        "teacher_id": teacher_id,
        "class_id": class_id,
        "day_of_week": day,
        "period_number": period,
    }
    row.update(lifecycle)
    await gd_insert(db.session, "timetable_sessions", row)
    return session_id


async def test_candidates_exclude_retired_from_availability_and_load_but_keep_legacy_live(
    client,
    school_principal_headers,
    school_a_id,
):
    timetable_id = await _seed_timetable(school_a_id)
    target_class_id = await _seed_class(school_a_id, "Target")
    retired_teacher = await _seed_teacher(school_a_id, "Retired occupancy")
    legacy_teacher = await _seed_teacher(school_a_id, "Legacy occupancy")

    # Neither explicitly retired row contributes load or target-slot occupancy.
    await _seed_session(
        school_a_id, timetable_id, retired_teacher, _id(), "sunday", 1,
        is_active=False,
    )
    await _seed_session(
        school_a_id, timetable_id, retired_teacher, _id(), "monday", 2,
        status="cancelled",
    )

    # Missing lifecycle fields and explicit nulls remain operational.
    await _seed_session(
        school_a_id, timetable_id, legacy_teacher, _id(), "sunday", 1,
    )
    await _seed_session(
        school_a_id, timetable_id, legacy_teacher, _id(), "monday", 2,
        is_active=None,
        status=None,
    )

    slot_id = f"{timetable_id}__{target_class_id}__sunday__1"
    response = await client.get(
        f"/schedule/slots/{slot_id}/candidates?limit=10",
        headers=school_principal_headers,
    )

    assert response.status_code == 200, response.text
    candidates = {
        candidate["teacher_id"]: candidate
        for candidate in response.json()["candidates"]
    }
    assert candidates[retired_teacher]["available"] is True
    assert candidates[retired_teacher]["weekly_load"] == 0
    assert candidates[legacy_teacher]["available"] is False
    assert candidates[legacy_teacher]["weekly_load"] == 2


async def test_assignment_succeeds_over_retired_teacher_and_class_occupancy(
    client,
    school_principal_headers,
    school_a_id,
):
    timetable_id = await _seed_timetable(school_a_id)
    teacher_id = await _seed_teacher(school_a_id, "Assignable")
    class_id = await _seed_class(school_a_id, "Assignable class")

    await _seed_session(
        school_a_id, timetable_id, teacher_id, class_id, "sunday", 1,
        is_active=False,
    )
    await _seed_session(
        school_a_id, timetable_id, teacher_id, class_id, "sunday", 1,
        status="cancelled",
    )
    slot_id = f"{timetable_id}__{class_id}__sunday__1"

    response = await client.post(
        f"/schedule/slots/{slot_id}/assign",
        json={"teacher_id": teacher_id},
        headers=school_principal_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    inserted = await gd_find_one(
        db.session,
        "timetable_sessions",
        {"id": body["session_id"]},
    )
    assert inserted is not None
    assert inserted["teacher_id"] == teacher_id
    assert inserted["class_id"] == class_id


@pytest.mark.parametrize(
    "lifecycle",
    [
        pytest.param({"is_active": True, "status": "scheduled"}, id="explicit-live"),
        pytest.param({}, id="legacy-missing"),
        pytest.param({"is_active": None, "status": None}, id="legacy-null"),
    ],
)
async def test_assignment_rejects_explicit_and_legacy_live_teacher_conflicts(
    client,
    school_principal_headers,
    school_a_id,
    lifecycle,
):
    timetable_id = await _seed_timetable(school_a_id)
    teacher_id = await _seed_teacher(school_a_id, "Busy")
    target_class_id = await _seed_class(school_a_id, "Target class")
    await _seed_session(
        school_a_id, timetable_id, teacher_id, _id(), "sunday", 1,
        **lifecycle,
    )
    slot_id = f"{timetable_id}__{target_class_id}__sunday__1"

    response = await client.post(
        f"/schedule/slots/{slot_id}/assign",
        json={"teacher_id": teacher_id},
        headers=school_principal_headers,
    )

    assert response.status_code == 409, response.text
    assert "المعلم لديه حصة أخرى" in response.json()["error"]["message"]


async def test_assignment_still_rejects_live_class_conflict(
    client,
    school_principal_headers,
    school_a_id,
):
    timetable_id = await _seed_timetable(school_a_id)
    teacher_id = await _seed_teacher(school_a_id, "Free teacher")
    class_id = await _seed_class(school_a_id, "Busy class")
    await _seed_session(
        school_a_id, timetable_id, _id(), class_id, "sunday", 1,
        is_active=True,
        status="scheduled",
    )
    slot_id = f"{timetable_id}__{class_id}__sunday__1"

    response = await client.post(
        f"/schedule/slots/{slot_id}/assign",
        json={"teacher_id": teacher_id},
        headers=school_principal_headers,
    )

    assert response.status_code == 409, response.text
    assert "الفصل لديه حصة أخرى" in response.json()["error"]["message"]