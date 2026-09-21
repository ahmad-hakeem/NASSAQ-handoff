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
async def test_exact_boundary_uses_only_lessons_and_submitted_breaks(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "dayStart": "٠٧:٠٠",
            "dayEnd": "۰۷:۴۰",
            "periodsPerDay": 2,
            "periodDuration": 20,
            "breaks": [],
            "expected_version": 0,
        },
    )
    assert response.status_code == 200, response.text
    refreshed = await client.get(
        "/school/settings", headers=school_principal_headers,
    )
    assert (refreshed.json()["dayStart"], refreshed.json()["dayEnd"]) == (
        "07:00", "07:40",
    )
    assert refreshed.json()["breaks"] == []
    slots = await gd_find(
        db.session, "time_slots", {"school_id": tenant_a},
        order_by="slot_number", desc_order=False,
    )
    assert [(slot["start_time"], slot["end_time"]) for slot in slots] == [
        ("07:00", "07:20"),
        ("07:20", "07:40"),
    ]
    assert response.json()["time_slots_regenerated"]["day_end"] == "07:40"


@pytest.mark.asyncio
async def test_short_day_returns_structured_duration_metadata_without_mutation(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "dayStart": "٠٧:٠٠",
            "dayEnd": "۰۸:۰۰",
            "periodsPerDay": 2,
            "periodDuration": 25,
            "breakDuration": 10,
            "breaks": [
                {"afterPeriod": 1, "duration": None, "day": "all"},
                {"afterPeriod": 2, "duration": 5, "day": "all"},
            ],
            "expected_version": 0,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["detail"] == {
        "code": "TIMING_VALIDATION_ERROR",
        "reason": "school_day_too_short",
        "field": "end_time",
        "available_minutes": 60,
        "lesson_minutes": 50,
        "break_minutes": 15,
        "required_minutes": 65,
        "shortage_minutes": 5,
        "message": "School day is too short for the configured lessons and breaks.",
    }
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert row["start_time"] == "07:00"
    assert row["custom_settings"]["settings_version"] == 0


@pytest.mark.asyncio
async def test_day_specific_break_is_structured_rejection_and_preserves_existing_settings(
    client, tenant_a, school_principal_headers,
):
    await _seed_settings(tenant_a)
    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "breaks": [{
                "afterPeriod": 2, "duration": 10, "day": "sunday",
            }],
            "expected_version": 0,
        },
    )
    assert response.status_code == 422
    detail = response.json()["error"]["detail"]
    assert detail["code"] == "TIMING_VALIDATION_ERROR"
    assert detail["reason"] == "unsupported_break_day"
    assert detail["field"] == "breaks[0].day"
    assert detail["day"] == "sunday"
    row = await gd_find_one(db.session, "school_settings", {"school_id": tenant_a})
    assert "breaks" not in row["custom_settings"]
    assert row["custom_settings"]["settings_version"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "reason", "field"),
    [
        ({"periodsPerDay": 1.5}, "invalid_integer", "periods_per_day"),
        ({"periodDuration": 19}, "out_of_range", "period_duration"),
        ({"dayStart": "7:00"}, "invalid_time_format", "start_time"),
        ({"dayStart": "00:00"}, "midnight_not_allowed", "start_time"),
        ({"dayStart": "12:00", "dayEnd": "11:00"}, "invalid_time_order", "end_time"),
        ({"activeWeekdays": ["noday"]}, "invalid_weekday", "working_days"),
        ({"activeWeekdays": []}, "no_working_days", "working_days"),
        ({"breaks": "bad"}, "invalid_breaks", "breaks"),
        ({"breaks": [{}]}, "missing_break_position", "breaks[0].afterPeriod"),
        (
            {"breaks": [{"afterPeriod": 2}, {"afterPeriod": 2}]},
            "duplicate_break_position",
            "breaks[1].afterPeriod",
        ),
    ],
)
async def test_timing_validation_family_has_stable_structured_details(
    client, tenant_a, school_principal_headers, payload, reason, field,
):
    await _seed_settings(tenant_a)
    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={**payload, "expected_version": 0},
    )
    assert response.status_code == 422
    detail = response.json()["error"]["detail"]
    assert detail["code"] == "TIMING_VALIDATION_ERROR"
    assert detail["reason"] == reason
    assert detail["field"] == field
    assert isinstance(detail["message"], str) and detail["message"]


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
        ("08:25", "08:50"),
        ("08:50", "09:15"),
        ("09:15", "09:40"),
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

    reconciled = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"periodsPerDay": 3, "expectedVersion": 2},
    )
    assert reconciled.status_code == 200, reconciled.text
    summary = reconciled.json()["draft_reconciliation"]
    assert summary == {
        "remapped_sessions": 0,
        "archived_drafts": 1,
        "excluded_sessions": 1,
        "editable_draft_id": summary["editable_draft_id"],
    }
    assert summary["editable_draft_id"]
    old_draft = await gd_find_one(db.session, "timetables", {"id": draft_id})
    assert old_draft["status"] == "archived"
    assert await gd_find_one(
        db.session, "timetable_sessions", {"id": "draft-session"}
    )
    clean_draft = await gd_find_one(
        db.session, "timetables", {"id": summary["editable_draft_id"]}
    )
    assert clean_draft["status"] == "draft"
    assert not await gd_find(
        db.session, "timetable_sessions",
        {"timetable_id": summary["editable_draft_id"]},
    )
    persisted = await gd_find_one(
        db.session, "school_settings", {"school_id": tenant_a},
    )
    assert persisted["periods_per_day"] == 3


@pytest.mark.asyncio
async def test_structural_reconciliation_archives_mixed_draft_and_clones_only_compatible(
    client, tenant_a, tenant_b, school_principal_headers,
):
    await _seed_settings(tenant_a)
    await _seed_settings(tenant_b)
    seeded = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"dayStart": "07:05", "breaks": [], "expectedVersion": 0},
    )
    assert seeded.status_code == 200, seeded.text
    old_slots = await gd_find(
        db.session, "time_slots", {"school_id": tenant_a},
        order_by="slot_number", desc_order=False,
    )
    teaching = [slot for slot in old_slots if not slot.get("is_break")]

    draft_id = str(uuid.uuid4())
    history_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": draft_id, "school_id": tenant_a, "name": "Mixed",
        "status": "draft", "is_published": False,
    })
    await gd_insert(db.session, "timetables", {
        "id": history_id, "school_id": tenant_a, "name": "Prior history",
        "status": "archived", "is_published": False,
    })
    await gd_insert(db.session, "timetables", {
        "id": other_id, "school_id": tenant_b, "name": "Other school",
        "status": "draft", "is_published": False,
    })

    rows = [
        {
            "id": "compatible-raw", "day_of_week": "sunday",
            "slot_number": teaching[1]["slot_number"],
            "teacher_id": "teacher-preserved", "class_id": "class-preserved",
            "subject_id": "subject-preserved",
        },
        {
            "id": "compatible-times-only", "day_of_week": "sunday",
            "start_time": teaching[2]["start_time"],
            "end_time": teaching[2]["end_time"],
        },
        {"id": "removed-period", "day_of_week": "sunday", "period_number": 7},
        {"id": "removed-day", "day_of_week": "monday", "period_number": 1},
        {
            "id": "inactive-removed", "day_of_week": "sunday",
            "period_number": 7, "is_active": False,
        },
    ]
    for row in rows:
        await gd_insert(db.session, "timetable_sessions", {
            "school_id": tenant_a, "timetable_id": draft_id, **row,
        })
    await gd_insert(db.session, "timetable_sessions", {
        "id": "history-row", "school_id": tenant_a,
        "timetable_id": history_id, "day_of_week": "sunday",
        "period_number": 7, "teacher_id": "history-teacher",
    })
    await gd_insert(db.session, "timetable_sessions", {
        "id": "other-row", "school_id": tenant_b,
        "timetable_id": other_id, "day_of_week": "sunday",
        "period_number": 7,
    })

    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={
            "periodsPerDay": 5,
            "activeWeekdays": ["sunday"],
            "expectedVersion": 1,
        },
    )
    assert response.status_code == 200, response.text
    summary = response.json()["draft_reconciliation"]
    assert summary["remapped_sessions"] == 2
    assert summary["archived_drafts"] == 1
    assert summary["excluded_sessions"] == 2
    assert summary["editable_draft_id"]

    clones = await gd_find(
        db.session, "timetable_sessions",
        {"timetable_id": summary["editable_draft_id"]},
    )
    assert len(clones) == 2
    preserved = next(row for row in clones if row.get("teacher_id") == "teacher-preserved")
    assert (
        preserved["class_id"], preserved["subject_id"], preserved["period_number"]
    ) == ("class-preserved", "subject-preserved", 2)
    assert sorted(row["period_number"] for row in clones) == [2, 3]

    # Prior history, the archived source snapshot (including inactive rows),
    # and another school's editable draft are not rewritten.
    assert (await gd_find_one(
        db.session, "timetable_sessions", {"id": "history-row"}
    ))["teacher_id"] == "history-teacher"
    assert (await gd_find_one(
        db.session, "timetable_sessions", {"id": "inactive-removed"}
    ))["is_active"] is False
    assert (await gd_find_one(
        db.session, "timetables", {"id": other_id}
    ))["status"] == "draft"
    assert (await gd_find_one(
        db.session, "timetable_sessions", {"id": "other-row"}
    ))["period_number"] == 7


@pytest.mark.asyncio
async def test_reconciliation_failure_rolls_back_settings_slots_and_draft(
    client, tenant_a, school_principal_headers, monkeypatch,
):
    from src.modules.schools.services.time_slots_service import TimeSlotsService

    await _seed_settings(tenant_a)
    draft_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": draft_id, "school_id": tenant_a, "name": "Rollback draft",
        "status": "draft", "is_published": False,
    })
    run_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetable_runs", {
        "id": run_id, "school_id": tenant_a, "status": "generating",
    })

    async def fail_after_settings_write(_session, _school_id):
        raise RuntimeError("injected reconciliation failure")

    monkeypatch.setattr(TimeSlotsService, "regenerate_time_slots", fail_after_settings_write)
    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"periodsPerDay": 5, "expectedVersion": 0},
    )
    assert response.status_code == 500
    persisted = await gd_find_one(
        db.session, "school_settings", {"school_id": tenant_a},
    )
    assert persisted["periods_per_day"] == 7
    assert persisted["custom_settings"]["settings_version"] == 0
    assert (await gd_find_one(
        db.session, "timetables", {"id": draft_id}
    ))["status"] == "draft"
    assert (await gd_find_one(
        db.session, "timetable_runs", {"id": run_id}
    ))["status"] == "generating"


@pytest.mark.asyncio
async def test_structural_change_cancels_only_own_active_generation_runs(
    client, tenant_a, tenant_b, school_principal_headers,
):
    await _seed_settings(tenant_a)
    await _seed_settings(tenant_b)
    own_active = str(uuid.uuid4())
    own_finished = str(uuid.uuid4())
    other_active = str(uuid.uuid4())
    for run_id, school_id, status in (
        (own_active, tenant_a, "optimizing"),
        (own_finished, tenant_a, "completed"),
        (other_active, tenant_b, "generating"),
    ):
        await gd_insert(db.session, "timetable_runs", {
            "id": run_id, "school_id": school_id, "status": status,
        })

    response = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json={"periodDuration": 40, "expectedVersion": 0},
    )
    assert response.status_code == 200, response.text
    assert response.json()["cancelled_generation_runs"] == 1
    cancelled = await gd_find_one(
        db.session, "timetable_runs", {"id": own_active},
    )
    assert cancelled["status"] == "failed"
    assert cancelled["error_code"] == "GENERATION_SETTINGS_CHANGED"
    assert (await gd_find_one(
        db.session, "timetable_runs", {"id": own_finished}
    ))["status"] == "completed"
    assert (await gd_find_one(
        db.session, "timetable_runs", {"id": other_active}
    ))["status"] == "generating"