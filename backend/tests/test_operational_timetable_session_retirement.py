"""Retired timetable history must not act as live operational occupancy."""

import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_insert


async def _timetable(school_id: str) -> str:
    timetable_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": timetable_id,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": "Operational retirement regression",
        "academic_year": "2026-2027",
        "semester": 1,
        "status": "draft",
        "version": 1,
    })
    return timetable_id


async def _session(school_id: str, timetable_id: str, **fields) -> str:
    session_id = str(uuid.uuid4())
    row = {
        "id": session_id,
        "school_id": school_id,
        "tenant_id": school_id,
        "timetable_id": timetable_id,
        "teacher_id": str(uuid.uuid4()),
        "class_id": str(uuid.uuid4()),
        "day_of_week": "sunday",
        "period_number": 1,
    }
    row.update(fields)
    await gd_insert(db.session, "timetable_sessions", row)
    return session_id


@pytest.mark.parametrize(
    "retirement",
    [{"is_active": False}, {"status": "cancelled"}],
)
async def test_slot_candidates_ignores_retired_occupancy(
    client,
    school_principal_headers,
    school_a_id,
    retirement,
):
    timetable_id = await _timetable(school_a_id)
    class_id = str(uuid.uuid4())
    await _session(
        school_a_id,
        timetable_id,
        class_id=class_id,
        **retirement,
    )
    slot_id = f"{timetable_id}__{class_id}__sunday__1"

    response = await client.get(
        f"/schedule/slots/{slot_id}/candidates",
        headers=school_principal_headers,
    )

    assert response.status_code == 200, response.text


async def test_slot_candidates_keeps_live_orphan_as_occupancy(
    client,
    school_principal_headers,
    school_a_id,
):
    timetable_id = await _timetable(school_a_id)
    missing_class_id = str(uuid.uuid4())
    await _session(
        school_a_id,
        timetable_id,
        class_id=missing_class_id,
        teacher_id=str(uuid.uuid4()),
    )
    slot_id = f"{timetable_id}__{missing_class_id}__sunday__1"

    response = await client.get(
        f"/schedule/slots/{slot_id}/candidates",
        headers=school_principal_headers,
    )

    assert response.status_code == 409, response.text


@pytest.mark.parametrize(
    "retirement",
    [{"is_active": False}, {"status": "cancelled"}],
)
async def test_smart_move_conflicts_ignore_retired_occupancy(
    client,
    school_principal_headers,
    school_a_id,
    retirement,
):
    timetable_id = await _timetable(school_a_id)
    teacher_id = str(uuid.uuid4())
    class_id = str(uuid.uuid4())
    moving_id = await _session(
        school_a_id,
        timetable_id,
        teacher_id=teacher_id,
        class_id=class_id,
        day_of_week="sunday",
        period_number=1,
    )
    await _session(
        school_a_id,
        timetable_id,
        teacher_id=teacher_id,
        class_id=class_id,
        day_of_week="monday",
        period_number=2,
        **retirement,
    )

    response = await client.put(
        f"/smart-scheduling/session/{moving_id}",
        json={"day_of_week": "monday", "period_number": 2},
        headers=school_principal_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


async def test_standby_generation_guard_rejects_retired_history_only(
    client,
    school_principal_headers,
    school_a_id,
):
    timetable_id = await _timetable(school_a_id)
    await _session(
        school_a_id,
        timetable_id,
        is_active=False,
    )

    response = await client.get(
        f"/standby/roster?school_id={school_a_id}",
        headers=school_principal_headers,
    )

    assert response.status_code == 409, response.text