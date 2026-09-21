import uuid

import pytest
from sqlalchemy import text

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert
from engines.smart_scheduling_engine import SmartSchedulingEngine
from src.modules.scheduling.controllers.schedule_master_grid_routes import (
    _resolve_period_times,
)


async def _seed_settings(school_id, *, break_duration=20):
    await gd_insert(db.session, "school_settings", {
        "id": f"settings-{school_id}",
        "school_id": school_id,
        "working_days": {
            "sunday": True, "monday": True, "tuesday": True,
            "wednesday": True, "thursday": True,
            "friday": False, "saturday": False,
        },
        "periods_per_day": 7,
        "period_duration": 45,
        "break_duration": break_duration,
        "start_time": "07:00",
        "end_time": "14:00",
        # Deliberately stale legacy values: ORM columns must win.
        "custom_settings": {
            "breakDuration": 999,
            "break_duration_minutes": 999,
            "settings_version": 0,
        },
    })


@pytest.mark.asyncio
async def test_break_duration_camel_alias_persists_and_regenerates_null_base_break(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)

    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "breakDuration": 25,
            "breaks": [{
                "id": "break-1", "name": "استراحة",
                "afterPeriod": 3, "duration": None, "type": "break",
            }],
            "expected_version": 0,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["settings"]["break_duration"] == 25
    assert body["settings"]["breakDuration"] == 25
    assert body["settings"]["settings_version"] == 1

    refreshed = await client.get(
        "/school/settings", headers=school_principal_headers
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["breakDuration"] == 25
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert row["break_duration"] == 25
    assert "breakDuration" not in row["custom_settings"]
    assert row["custom_settings"]["breaks"][0]["duration"] is None
    slots = await gd_find(
        db.session, "time_slots", {"school_id": tenant_a},
        order_by="slot_number", desc_order=False,
    )
    break_slots = [slot for slot in slots if slot.get("is_break")]
    assert break_slots and break_slots[0]["duration_minutes"] == 25

    # The stored null must remain an inheritance marker.  A subsequent BASE
    # edit without resending the break list must update the actual slot again.
    second = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"breakDuration": 30, "expected_version": 1},
    )
    assert second.status_code == 200, second.text
    assert second.json()["settings"]["breakDuration"] == 30
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert row["custom_settings"]["breaks"][0]["duration"] is None
    slots = await gd_find(
        db.session, "time_slots", {"school_id": tenant_a},
        order_by="slot_number", desc_order=False,
    )
    break_slots = [slot for slot in slots if slot.get("is_break")]
    assert break_slots and break_slots[0]["duration_minutes"] == 30


@pytest.mark.asyncio
async def test_multi_field_aliases_zero_break_and_school_isolation(
    client, tenant_a, tenant_b, school_principal_headers,
):
    await _seed_settings(tenant_a)
    await _seed_settings(tenant_b, break_duration=33)

    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "dayStart": "08:00",
            "dayEnd": "13:00",
            "periodsPerDay": 5,
            "lessonDuration": 40,
            "baseBreakDuration": 0,
            "breaks": [],
            "activeWeekdays": ["sunday", "monday", "tuesday"],
            "expectedVersion": 0,
        },
    )
    assert response.status_code == 200, response.text
    saved = response.json()["settings"]
    assert (
        saved["dayStart"], saved["dayEnd"], saved["periodsPerDay"],
        saved["periodDuration"], saved["breakDuration"],
    ) == ("08:00", "13:00", 5, 40, 0)
    assert saved["working_days"]["wednesday"] is False

    other = await gd_find_one(db.session, "school_settings", {"school_id": tenant_b})
    assert other["break_duration"] == 33
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert row["break_duration"] == 0
    assert row["custom_settings"]["breaks"] == []
    slots = await gd_find(db.session, "time_slots", {"school_id": tenant_a})
    assert not [slot for slot in slots if slot.get("is_break")]


@pytest.mark.asyncio
async def test_legacy_camel_only_row_partial_update_uses_same_load_and_validation_values(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    await db.session.execute(
        text(
            "UPDATE school_settings "
            "SET start_time = NULL, end_time = NULL, periods_per_day = NULL, "
            "period_duration = NULL, break_duration = NULL, "
            "custom_settings = CAST(:settings AS jsonb) "
            "WHERE school_id = :school_id"
        ),
        {
            "school_id": tenant_a,
            "settings": (
                '{"dayStart":"08:10","dayEnd":"13:30","periodsPerDay":5,'
                '"periodDuration":40,"breakDuration":10,"settings_version":0}'
            ),
        },
    )
    await db.session.flush()

    before = await client.get("/school/settings", headers=school_principal_headers)
    assert before.status_code == 200
    assert before.json()["dayStart"] == "08:10"
    assert before.json()["periodDuration"] == 40

    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"academicYear": "1447", "expected_version": 0},
    )
    assert response.status_code == 200, response.text
    saved = response.json()["settings"]
    assert saved["dayStart"] == "08:10"
    assert saved["dayEnd"] == "13:30"
    assert saved["periodsPerDay"] == 5
    assert saved["periodDuration"] == 40
    assert saved["breakDuration"] == 10


@pytest.mark.asyncio
async def test_invalid_update_rolls_back_all_fields_and_version(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "periodDuration": 60,
            "periodsPerDay": 8,
            "dayStart": "12:00",
            "dayEnd": "12:30",
            "breakDuration": -1,
            "expected_version": 0,
        },
    )
    assert response.status_code == 422
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert row["period_duration"] == 45
    assert row["periods_per_day"] == 7
    assert row["break_duration"] == 20
    assert row["custom_settings"]["settings_version"] == 0


@pytest.mark.asyncio
async def test_feasibility_accounts_for_generator_passing_minutes(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "dayStart": "07:00",
            "dayEnd": "07:40",
            "periodsPerDay": 2,
            "periodDuration": 20,
            "breaks": [],
            "expected_version": 0,
        },
    )
    # Lessons consume 40 minutes, but the generator also emits 5 passing
    # minutes after each of the two no-break periods.
    assert response.status_code == 422
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert row["periods_per_day"] == 7
    assert row["custom_settings"]["settings_version"] == 0


@pytest.mark.asyncio
async def test_expected_version_rejects_stale_writer_without_overwrite(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    first = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"breakDuration": 25, "expected_version": 0},
    )
    assert first.status_code == 200, first.text

    stale = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"breakDuration": 30, "expected_version": 0},
    )
    assert stale.status_code == 409
    assert "settings_version_conflict" in stale.text
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert row["break_duration"] == 25


@pytest.mark.asyncio
async def test_split_timing_endpoint_uses_same_occ_and_response_contract(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    response = await client.put(
        "/school/settings/periods-per-day?expected_version=0",
        headers=school_principal_headers,
        json={"periods_per_day": 6},
    )
    assert response.status_code == 200, response.text
    assert response.json()["settings"]["periods_per_day"] == 6
    assert response.json()["settings"]["settings_version"] == 1

    stale = await client.put(
        "/school/settings/periods-per-day?expected_version=0",
        headers=school_principal_headers,
        json={"periods_per_day": 8},
    )
    assert stale.status_code == 409
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert row["periods_per_day"] == 6


@pytest.mark.asyncio
async def test_timing_edit_rejected_while_timetable_is_published(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    await gd_insert(db.session, "timetables", {
        "id": str(uuid.uuid4()),
        "school_id": tenant_a,
        "name": "Published",
        "status": "published",
        "is_published": True,
    })
    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"breakDuration": 25, "expected_version": 0},
    )
    assert response.status_code == 409
    assert "published_timetable_requires_unpublish" in response.text
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert row["break_duration"] == 20


@pytest.mark.asyncio
async def test_zero_custom_break_uses_canonical_base_and_consumers_match_slots(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "dayStart": "08:00",
            "dayEnd": "12:00",
            "periodsPerDay": 4,
            "periodDuration": 25,
            "breakDuration": 25,
            "breaks": [{
                "name": "عبور",
                "afterPeriod": 2,
                "duration": 0,
                "type": "break",
            }],
            "expectedVersion": 0,
        },
    )
    assert response.status_code == 200, response.text

    slots = await gd_find(
        db.session, "time_slots", {"school_id": tenant_a},
        order_by="slot_number", desc_order=False,
    )
    teaching = [slot for slot in slots if not slot.get("is_break")]
    breaks = [slot for slot in slots if slot.get("is_break")]
    assert [(slot["start_time"], slot["end_time"]) for slot in teaching] == [
        ("08:00", "08:25"),
        ("08:30", "08:55"),
        ("08:55", "09:20"),
        ("09:25", "09:50"),
    ]
    assert len(breaks) == 1
    assert breaks[0]["duration_minutes"] == 0

    master_times = await _resolve_period_times(tenant_a, [1, 2, 3, 4])
    assert [
        (master_times[str(period)]["start"], master_times[str(period)]["end"])
        for period in range(1, 5)
    ] == [(slot["start_time"], slot["end_time"]) for slot in teaching]

    generator_settings = await SmartSchedulingEngine(db).load_school_settings(tenant_a)
    generator_teaching = [
        slot for slot in generator_settings["time_slots"]
        if slot["type"] in ("class", "period")
    ]
    assert [
        (slot["start_time"], slot["end_time"]) for slot in generator_teaching
    ] == [(slot["start_time"], slot["end_time"]) for slot in teaching]


@pytest.mark.asyncio
async def test_timing_regeneration_retargets_draft_session_but_not_archived_history(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    initial = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "periodsPerDay": 5,
            "breaks": [],
            "expectedVersion": 0,
        },
    )
    assert initial.status_code == 200, initial.text
    old_slots = await gd_find(
        db.session, "time_slots", {"school_id": tenant_a},
        order_by="slot_number", desc_order=False,
    )
    assert not [slot for slot in old_slots if slot.get("is_break")]
    old_fourth = [slot for slot in old_slots if not slot.get("is_break")][3]

    draft_id = str(uuid.uuid4())
    archived_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": draft_id, "school_id": tenant_a, "name": "Editable",
        "status": "draft", "is_published": False,
    })
    await gd_insert(db.session, "timetables", {
        "id": archived_id, "school_id": tenant_a, "name": "History",
        "status": "archived", "is_published": False,
    })
    for timetable_id, session_id in ((draft_id, "draft-session"), (archived_id, "history-session")):
        await gd_insert(db.session, "timetable_sessions", {
            "id": session_id,
            "school_id": tenant_a,
            "timetable_id": timetable_id,
            "day_of_week": "sunday",
            "period_number": 4,
            # Exercise manual/raw-slot mapping through the old slot id.
            "slot_number": old_fourth["slot_number"],
            "time_slot_id": old_fourth["id"],
            "start_time": old_fourth["start_time"],
            "end_time": old_fourth["end_time"],
        })

    changed = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "dayStart": "08:00",
            "periodDuration": 25,
            "breakDuration": 25,
            "breaks": [{"afterPeriod": 2, "duration": 0, "type": "break"}],
            "expectedVersion": 1,
        },
    )
    assert changed.status_code == 200, changed.text

    new_slots = await gd_find(
        db.session, "time_slots", {"school_id": tenant_a},
        order_by="slot_number", desc_order=False,
    )
    new_fourth = [slot for slot in new_slots if not slot.get("is_break")][3]
    draft_session = await gd_find_one(
        db.session, "timetable_sessions", {"id": "draft-session"},
    )
    assert (
        draft_session["time_slot_id"],
        draft_session["start_time"],
        draft_session["end_time"],
    ) == (new_fourth["id"], new_fourth["start_time"], new_fourth["end_time"])

    history = await gd_find_one(
        db.session, "timetable_sessions", {"id": "history-session"},
    )
    assert (
        history["time_slot_id"], history["start_time"], history["end_time"],
    ) == (old_fourth["id"], old_fourth["start_time"], old_fourth["end_time"])

    rejected = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"periodsPerDay": 3, "expectedVersion": 2},
    )
    assert rejected.status_code == 422
    assert "draft_sessions_use_removed_periods" in rejected.text
    persisted = await gd_find_one(
        db.session, "school_settings", {"school_id": tenant_a},
    )
    assert persisted["periods_per_day"] == 5