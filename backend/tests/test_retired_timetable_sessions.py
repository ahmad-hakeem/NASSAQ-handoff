"""Regression coverage for retained, non-operational timetable history."""

import uuid

import pytest

from dependencies import db
from engines.smart_scheduling_engine import (
    AcademicDemand,
    ResourceAvailability,
    SmartSchedulingEngine,
)
from engines.timetable_session_lifecycle import find_live_timetable_sessions
from engines.sql_utils import (
    gd_find,
    gd_find_one,
    gd_insert,
    gd_update_many,
    gd_update_one,
)
from services.teacher_permanent_deletion import permanently_delete_teacher
from tests.test_teacher_restore_create_contract import (
    _deleted_teacher,
    _headers,
    _principal,
)


async def _timetable(school_id: str, *, status: str = "draft") -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": "Lifecycle regression",
        "academic_year": "2026-2027",
        "semester": 1,
        "status": status,
        "is_published": status == "published",
        "version": 1,
        "total_sessions": 0,
    }
    await gd_insert(db.session, "timetables", row)
    return row


async def _session(school_id: str, timetable_id: str, **fields) -> str:
    session_id = fields.pop("id", str(uuid.uuid4()))
    row = {
        "id": session_id,
        "school_id": school_id,
        "timetable_id": timetable_id,
        "day_of_week": "sunday",
        "period_number": 1,
    }
    row.update(fields)
    await gd_insert(db.session, "timetable_sessions", row)
    return session_id


async def _active_teacher(school_id: str) -> str:
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": school_id,
        "full_name": "Lifecycle Teacher",
        "is_active": True,
    })
    return teacher_id


async def _active_class(school_id: str) -> str:
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id,
        "school_id": school_id,
        "name": "Lifecycle Class",
        "is_active": True,
    })
    return class_id


async def _only_entity_integrity_constraint() -> None:
    await gd_update_many(
        db.session, "timetable_hard_constraints", {}, {"is_active": False}
    )
    existing = await gd_find_one(
        db.session,
        "timetable_hard_constraints",
        {"validation_key": "entity_integrity"},
    )
    if existing:
        await gd_update_one(
            db.session,
            "timetable_hard_constraints",
            {"id": existing["id"]},
            {"is_active": True, "severity": "critical"},
        )
        return
    await gd_insert(db.session, "timetable_hard_constraints", {
        "id": str(uuid.uuid4()),
        "code": "HC-16",
        "name_ar": "HC-16",
        "name_en": "HC-16",
        "description_ar": "",
        "description_en": "",
        "category": "test",
        "severity": "critical",
        "is_system": True,
        "is_active": True,
        "can_disable": False,
        "validation_key": "entity_integrity",
    })


def _minimal_hc16_resources(
    engine: SmartSchedulingEngine,
    *,
    class_id: str,
    subject_id: str,
    teacher_id: str,
) -> None:
    async def demands(*_args, **_kwargs):
        return [
            AcademicDemand(
                class_id=class_id,
                class_name="1A",
                grade_id=str(uuid.uuid4()),
                subjects=[{
                    "subject_id": subject_id,
                    "weekly_periods": 1,
                    "suitable_teachers": [teacher_id],
                }],
                total_periods_required=1,
            )
        ]

    async def resources(*_args, **_kwargs):
        return [
            ResourceAvailability(
                teacher_id=teacher_id,
                teacher_name="Live teacher",
                subject_ids=[subject_id],
                weekly_load=24,
                availability={"sunday": [1]},
            )
        ]

    engine.build_academic_demand = demands
    engine.build_resource_availability = resources


async def _publish_fixture(school_id: str):
    await _only_entity_integrity_constraint()
    timetable = await _timetable(school_id)
    class_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "school_id": school_id,
        "name": "Subject",
        "is_active": True,
    })
    engine = SmartSchedulingEngine(db)
    _minimal_hc16_resources(
        engine,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
    )
    return engine, timetable["id"], class_id, subject_id, teacher_id


@pytest.mark.parametrize(
    "retirement",
    [{"is_active": False}, {"status": "cancelled"}],
)
async def test_publish_ignores_retired_teacher_tombstone_and_missing_class_rows(
    school_a_id,
    retirement,
):
    engine, timetable_id, class_id, subject_id, teacher_id = (
        await _publish_fixture(school_a_id)
    )
    await _session(
        school_a_id,
        timetable_id,
        teacher_id=f"deleted-teacher:{school_a_id}",
        class_id=class_id,
        subject_id=subject_id,
        **retirement,
    )
    await _session(
        school_a_id,
        timetable_id,
        teacher_id=teacher_id,
        class_id=str(uuid.uuid4()),
        subject_id=subject_id,
        period_number=2,
        **retirement,
    )

    result = await engine.validate_before_publish(
        school_id=school_a_id, timetable_id=timetable_id
    )

    assert result["is_publishable"] is True
    assert result["violations"] == []


@pytest.mark.parametrize("missing_field", ["teacher_id", "class_id"])
@pytest.mark.parametrize(
    "lifecycle_fields",
    [{}, {"is_active": None}, {"status": None}, {"is_active": None, "status": None}],
)
async def test_publish_still_blocks_live_or_legacy_missing_references(
    school_a_id,
    missing_field,
    lifecycle_fields,
):
    engine, timetable_id, class_id, subject_id, teacher_id = (
        await _publish_fixture(school_a_id)
    )
    fields = {
        "teacher_id": teacher_id,
        "class_id": class_id,
        "subject_id": subject_id,
        **lifecycle_fields,
    }
    fields[missing_field] = str(uuid.uuid4())
    await _session(school_a_id, timetable_id, **fields)

    result = await engine.validate_before_publish(
        school_id=school_a_id, timetable_id=timetable_id
    )

    assert result["is_publishable"] is False
    assert any(
        violation["validation_key"] == "entity_integrity"
        and violation["refs"].get("field") == missing_field
        for violation in result["violations"]
    )


@pytest.mark.parametrize("missing_field", ["teacher_id", "class_id"])
async def test_http_publish_returns_409_for_active_missing_reference(
    client,
    school_principal_headers,
    school_a_id,
    missing_field,
):
    await _only_entity_integrity_constraint()
    timetable = await _timetable(school_a_id)
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "school_id": school_a_id,
        "name": "Publish integrity subject",
        "is_active": True,
    })
    fields = {
        "teacher_id": await _active_teacher(school_a_id),
        "class_id": await _active_class(school_a_id),
        "subject_id": subject_id,
        "is_active": True,
        "status": "active",
    }
    fields[missing_field] = str(uuid.uuid4())
    await _session(school_a_id, timetable["id"], **fields)

    response = await client.post(
        f"/smart-scheduling/timetable/{timetable['id']}/publish",
        headers=school_principal_headers,
    )

    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "PUBLISH_BLOCKED"
    detail = error["detail"]
    assert any(
        violation["validation_key"] == "entity_integrity"
        and violation["refs"].get("field") == missing_field
        for violation in detail["violations"]
    )
    unchanged = await gd_find_one(
        db.session, "timetables", {"id": timetable["id"]}
    )
    assert unchanged["status"] == "draft"


@pytest.mark.parametrize(
    "live_markers",
    [
        pytest.param({}, id="missing-json-markers"),
        pytest.param(
            {"is_active": None, "status": None},
            id="json-null-markers",
        ),
    ],
)
async def test_find_live_sessions_filters_before_limit(
    school_a_id,
    live_markers,
):
    timetable = await _timetable(school_a_id)
    timetable_id = timetable["id"]
    common = {
        "teacher_id": str(uuid.uuid4()),
        "class_id": str(uuid.uuid4()),
        "subject_id": str(uuid.uuid4()),
    }
    # Explicit IDs make all three retired rows sort before the live row. A
    # post-LIMIT Python filter would therefore return no row for limit=1.
    await _session(
        school_a_id,
        timetable_id,
        id=f"000-inactive-{timetable_id}",
        **common,
        is_active=False,
    )
    await _session(
        school_a_id,
        timetable_id,
        id=f"001-cancelled-{timetable_id}",
        **common,
        status="cancelled",
    )
    await _session(
        school_a_id,
        timetable_id,
        id=f"002-both-{timetable_id}",
        **common,
        is_active=False,
        status="cancelled",
    )
    live_id = await _session(
        school_a_id,
        timetable_id,
        id=f"fff-live-{timetable_id}",
        **common,
        **live_markers,
    )

    sessions = await find_live_timetable_sessions(
        db.session, {"timetable_id": timetable_id}, limit=1
    )

    assert [row["id"] for row in sessions] == [live_id]


async def test_get_timetable_sessions_excludes_only_explicitly_retired_rows(
    school_a_id,
):
    timetable = await _timetable(school_a_id)
    common = {
        "teacher_id": str(uuid.uuid4()),
        "class_id": str(uuid.uuid4()),
        "subject_id": str(uuid.uuid4()),
    }
    inactive_id = await _session(
        school_a_id, timetable["id"], **common, is_active=False
    )
    cancelled_id = await _session(
        school_a_id, timetable["id"], **common, period_number=2,
        status="cancelled",
    )
    legacy_id = await _session(
        school_a_id, timetable["id"], **common, period_number=3
    )
    null_id = await _session(
        school_a_id, timetable["id"], **common, period_number=4,
        is_active=None, status=None,
    )

    sessions = await SmartSchedulingEngine(db).get_timetable_sessions(
        timetable["id"]
    )
    returned_ids = {session["id"] for session in sessions}

    assert returned_ids == {legacy_id, null_id}
    assert inactive_id not in returned_ids
    assert cancelled_id not in returned_ids


async def test_clone_omits_retired_rows_without_deleting_source_history(
    school_a_id,
):
    source = await _timetable(school_a_id, status="published")
    common = {
        "teacher_id": str(uuid.uuid4()),
        "class_id": str(uuid.uuid4()),
        "subject_id": str(uuid.uuid4()),
    }
    live_id = await _session(school_a_id, source["id"], **common)
    null_id = await _session(
        school_a_id, source["id"], **common, period_number=2,
        is_active=None, status=None,
    )
    inactive_id = await _session(
        school_a_id, source["id"], **common, period_number=3, is_active=False
    )
    cancelled_id = await _session(
        school_a_id, source["id"], **common, period_number=4,
        status="cancelled",
    )

    clone_id = await SmartSchedulingEngine(db)._clone_timetable_as_draft(
        source, str(uuid.uuid4())
    )

    source_rows = await gd_find(
        db.session, "timetable_sessions", {"timetable_id": source["id"]},
        limit=20,
    )
    cloned_rows = await gd_find(
        db.session, "timetable_sessions", {"timetable_id": clone_id}, limit=20
    )
    assert {row["id"] for row in source_rows} == {
        live_id, null_id, inactive_id, cancelled_id
    }
    assert len(cloned_rows) == 2
    assert {row["period_number"] for row in cloned_rows} == {1, 2}
    cloned_timetable = await gd_find_one(
        db.session, "timetables", {"id": clone_id}
    )
    assert cloned_timetable["total_sessions"] == 2


async def test_permanently_deleted_teacher_history_does_not_block_http_publish(
    client,
    school_a_id,
):
    """Exercise the producer of teacher tombstones, not only hand-built rows."""
    actor = await _principal(school_a_id)
    teacher, user = await _deleted_teacher(school_a_id)
    await gd_update_one(
        db.session,
        "teachers",
        {"id": teacher["id"]},
        {"is_active": True, "deleted_at": None},
    )
    await gd_update_one(
        db.session, "users", {"id": user["id"]}, {"is_active": True}
    )
    timetable = await _timetable(school_a_id)
    session_id = await _session(
        school_a_id,
        timetable["id"],
        teacher_id=teacher["id"],
        class_id=str(uuid.uuid4()),
        subject_id=str(uuid.uuid4()),
    )

    await permanently_delete_teacher(
        db.session, teacher["id"], actor
    )
    retired = await gd_find_one(
        db.session, "timetable_sessions", {"id": session_id}
    )
    assert retired is not None
    assert retired["teacher_id"] == f"deleted-teacher:{school_a_id}"
    assert retired["is_active"] is False

    await _only_entity_integrity_constraint()
    response = await client.post(
        f"/smart-scheduling/timetable/{timetable['id']}/publish",
        headers=_headers(actor["id"], school_a_id),
    )

    assert response.status_code == 200, response.text


async def test_active_sessions_http_route_excludes_retired_rows(
    client,
    school_principal_headers,
    school_a_id,
):
    timetable = await _timetable(school_a_id, status="published")
    common = {
        "teacher_id": await _active_teacher(school_a_id),
        "class_id": await _active_class(school_a_id),
        "subject_id": str(uuid.uuid4()),
    }
    inactive_id = await _session(
        school_a_id, timetable["id"], **common, is_active=False
    )
    cancelled_id = await _session(
        school_a_id, timetable["id"], **common, period_number=2,
        status="cancelled",
    )
    live_id = await _session(
        school_a_id, timetable["id"], **common, period_number=3
    )
    null_id = await _session(
        school_a_id, timetable["id"], **common, period_number=4,
        is_active=None, status=None,
    )

    response = await client.get(
        "/smart-scheduling/timetable/active/sessions",
        headers=school_principal_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    returned_ids = {row["id"] for row in body["sessions"]}
    assert body["timetable_id"] == timetable["id"]
    assert body["total"] == 2
    assert returned_ids == {live_id, null_id}
    assert inactive_id not in returned_ids
    assert cancelled_id not in returned_ids


async def test_master_grid_keeps_active_teacher_but_hides_retired_class_slot(
    client,
    school_principal_headers,
    school_a_id,
):
    timetable = await _timetable(school_a_id, status="published")
    teacher_id = await _active_teacher(school_a_id)
    class_id = await _active_class(school_a_id)
    retired_id = await _session(
        school_a_id,
        timetable["id"],
        teacher_id=teacher_id,
        class_id=class_id,
        subject_id=str(uuid.uuid4()),
        is_active=False,
    )

    response = await client.get(
        f"/schedule/master-grid?school_id={school_a_id}&view=published",
        headers=school_principal_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert teacher_id in {teacher["id"] for teacher in body["teachers"]}
    assert teacher_id not in body["cells"] or not body["cells"][teacher_id]
    assert retired_id not in response.text


async def test_actual_class_deletion_retires_slot_and_allows_http_publish(
    client,
    school_principal_headers,
    school_a_id,
):
    timetable = await _timetable(school_a_id)
    class_id = await _active_class(school_a_id)
    session_id = await _session(
        school_a_id,
        timetable["id"],
        teacher_id=await _active_teacher(school_a_id),
        class_id=class_id,
        subject_id=str(uuid.uuid4()),
    )

    deleted = await client.delete(
        f"/classes/{class_id}?force=true",
        headers=school_principal_headers,
    )
    assert deleted.status_code == 200, deleted.text
    retired = await gd_find_one(
        db.session, "timetable_sessions", {"id": session_id}
    )
    assert retired is not None
    assert retired["class_id"] == class_id
    assert retired["is_active"] is False

    await _only_entity_integrity_constraint()
    published = await client.post(
        f"/smart-scheduling/timetable/{timetable['id']}/publish",
        headers=school_principal_headers,
    )

    assert published.status_code == 200, published.text