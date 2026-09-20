"""HTTP regressions for retired timetable rows in substitution workflows."""

import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_insert


pytestmark = pytest.mark.asyncio
ABSENCE_DATE = "2026-05-03"  # Sunday


async def _insert(collection: str, **fields) -> str:
    row_id = fields.pop("id", str(uuid.uuid4()))
    await gd_insert(db.session, collection, {"id": row_id, **fields})
    return row_id


async def _timetable(school_id: str) -> str:
    return await _insert(
        "timetables",
        school_id=school_id,
        tenant_id=school_id,
        name="Substitution retirement regression",
        status="draft",
        created_at="2026-05-01T00:00:00+00:00",
    )


async def _teacher(school_id: str, name: str, *, weekly_periods: int = 5) -> str:
    return await _insert(
        "teachers",
        school_id=school_id,
        full_name=name,
        is_active=True,
        weekly_periods=weekly_periods,
    )


async def _session(
    school_id: str,
    timetable_id: str,
    teacher_id: str,
    period: int,
    **fields,
) -> str:
    return await _insert(
        "timetable_sessions",
        school_id=school_id,
        tenant_id=school_id,
        timetable_id=timetable_id,
        teacher_id=teacher_id,
        class_id=str(uuid.uuid4()),
        day_of_week="sunday",
        period_number=period,
        **fields,
    )


async def _pin_standby(
    school_id: str, timetable_id: str, teacher_id: str, period: int,
) -> None:
    await _insert(
        "standby_overrides",
        school_id=school_id,
        timetable_id=timetable_id,
        teacher_id=teacher_id,
        day="sunday",
        period=period,
        action="add",
    )


async def test_candidate_scoring_ignores_retired_teacher_occupancy(
    client, school_principal_headers, school_a_id,
):
    timetable_id = await _timetable(school_a_id)
    absent_id = await _teacher(school_a_id, "Absent")
    substitute_id = await _teacher(school_a_id, "Available", weekly_periods=1)
    await _session(school_a_id, timetable_id, absent_id, 1)
    await _session(
        school_a_id, timetable_id, substitute_id, 1, status="cancelled",
    )
    await _pin_standby(school_a_id, timetable_id, substitute_id, 1)

    response = await client.get(
        "/standby/candidates",
        params={
            "school_id": school_a_id,
            "day": "sunday",
            "period": 1,
            "absence_date": ABSENCE_DATE,
            "limit": 10,
        },
        headers=school_principal_headers,
    )

    assert response.status_code == 200, response.text
    candidate = next(
        c for c in response.json()["candidates"]
        if c["teacher_id"] == substitute_id
    )
    assert candidate["today_load"] == 0
    assert candidate["weekly_load"] == 0


async def test_vacant_slot_listing_excludes_retired_history(
    client, school_principal_headers, school_a_id,
):
    timetable_id = await _timetable(school_a_id)
    absent_id = await _teacher(school_a_id, "Absent")
    live_id = await _session(school_a_id, timetable_id, absent_id, 1)
    await _session(
        school_a_id, timetable_id, absent_id, 2, is_active=False,
    )

    response = await client.get(
        "/standby/candidates/bulk",
        params={
            "school_id": school_a_id,
            "absent_teacher_id": absent_id,
            "absence_date": ABSENCE_DATE,
        },
        headers=school_principal_headers,
    )

    assert response.status_code == 200, response.text
    assert [slot["original_session_id"] for slot in response.json()["slots"]] == [
        live_id
    ]


async def test_single_assignment_ignores_retired_conflict(
    client, school_principal_headers, school_a_id,
):
    timetable_id = await _timetable(school_a_id)
    absent_id = await _teacher(school_a_id, "Absent")
    substitute_id = await _teacher(school_a_id, "Available")
    source_id = await _session(school_a_id, timetable_id, absent_id, 1)
    await _session(
        school_a_id, timetable_id, substitute_id, 1, is_active=False,
    )

    response = await client.post(
        "/substitutions",
        params={"school_id": school_a_id},
        json={
            "original_session_id": source_id,
            "substitute_teacher_id": substitute_id,
            "absence_date": ABSENCE_DATE,
        },
        headers=school_principal_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["success"] is True


async def test_bulk_assignment_ignores_retired_conflicts(
    client, school_principal_headers, school_a_id,
):
    timetable_id = await _timetable(school_a_id)
    absent_id = await _teacher(school_a_id, "Absent")
    substitute_id = await _teacher(school_a_id, "Available")
    source_ids = [
        await _session(school_a_id, timetable_id, absent_id, period)
        for period in (1, 2)
    ]
    for period in (1, 2):
        await _session(
            school_a_id,
            timetable_id,
            substitute_id,
            period,
            status="cancelled",
        )

    response = await client.post(
        "/substitutions/bulk",
        params={"school_id": school_a_id},
        json={
            "absence_date": ABSENCE_DATE,
            "items": [
                {
                    "original_session_id": source_id,
                    "substitute_teacher_id": substitute_id,
                }
                for source_id in source_ids
            ],
        },
        headers=school_principal_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["succeeded"] == 2
    assert all(result["success"] for result in response.json()["results"])


@pytest.mark.parametrize(
    "endpoint,payload",
    [
        ("/substitutions", None),
        ("/substitutions/bulk", "bulk"),
    ],
)
async def test_retired_session_cannot_be_assignment_source(
    client, school_principal_headers, school_a_id, endpoint, payload,
):
    timetable_id = await _timetable(school_a_id)
    absent_id = await _teacher(school_a_id, "Absent")
    substitute_id = await _teacher(school_a_id, "Available")
    retired_id = await _session(
        school_a_id, timetable_id, absent_id, 1, is_active=False,
    )
    item = {
        "original_session_id": retired_id,
        "substitute_teacher_id": substitute_id,
    }
    body = (
        {**item, "absence_date": ABSENCE_DATE}
        if payload is None
        else {"items": [item], "absence_date": ABSENCE_DATE}
    )

    response = await client.post(
        endpoint,
        params={"school_id": school_a_id},
        json=body,
        headers=school_principal_headers,
    )

    assert response.status_code in (404, 409), response.text