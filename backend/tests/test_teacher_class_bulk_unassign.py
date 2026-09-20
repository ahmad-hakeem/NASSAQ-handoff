"""Backend contract tests for approved bulk teacher/class unassignment."""
from __future__ import annotations

import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert
import src.modules.schools.services.teacher_assignments_service as assignment_service_module
from src.common.utils.teacher_assignment_sync import load_tombstones
from src.modules.schools.services.teacher_assignments_service import (
    TeacherAssignmentsService,
)


async def _teacher(school_id: str) -> str:
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": school_id,
        "full_name": f"T-{teacher_id[:6]}",
        "is_active": True,
    })
    return teacher_id


async def _class(school_id: str) -> str:
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id,
        "school_id": school_id,
        "name": f"C-{class_id[:6]}",
        "is_active": True,
    })
    return class_id


async def _assignment(
    school_id: str, teacher_id: str, class_id: str, academic_year_id: str
) -> str:
    assignment_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "school_id": school_id,
        "name": f"S-{subject_id[:6]}",
        "is_active": True,
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": assignment_id,
        "school_id": school_id,
        "teacher_id": teacher_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "academic_year_id": academic_year_id,
        "is_active": True,
    })
    return assignment_id


@pytest.mark.asyncio
async def test_unassign_teacher_all_years_preserves_entities_and_history(
    client, tenant_a, school_principal_headers
):
    teacher_id = await _teacher(tenant_a)
    other_teacher = await _teacher(tenant_a)
    class_a, class_b = await _class(tenant_a), await _class(tenant_a)
    assignment_a = await _assignment(tenant_a, teacher_id, class_a, "old-year")
    assignment_b = await _assignment(tenant_a, teacher_id, class_b, "new-year")
    other_assignment = await _assignment(
        tenant_a, other_teacher, class_a, "new-year"
    )
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": tenant_a,
        "teacher_id": teacher_id,
        "class_id": class_a,
    })
    inactive_legacy_id = str(uuid.uuid4())
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": inactive_legacy_id,
        "school_id": tenant_a,
        "teacher_id": teacher_id,
        "class_id": class_b,
        "is_active": False,
    })
    timetable_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": timetable_id,
        "school_id": tenant_a,
        "name": "published",
        "status": "published",
    })
    affected_session = str(uuid.uuid4())
    unaffected_session = str(uuid.uuid4())
    for session_id, tid, cid in (
        (affected_session, teacher_id, class_a),
        (unaffected_session, other_teacher, class_a),
    ):
        await gd_insert(db.session, "timetable_sessions", {
            "id": session_id,
            "school_id": tenant_a,
            "timetable_id": timetable_id,
            "teacher_id": tid,
            "class_id": cid,
        })

    response = await client.post(
        "/teacher-class-assignments/unassign-teacher",
        json={"teacher_id": teacher_id},
        headers=school_principal_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["unassigned_count"] == 2
    assert body["teachers_affected"] == 1
    assert body["classes_affected"] == 2
    assert body["flagged_sessions"] == 1

    for assignment_id in (assignment_a, assignment_b):
        row = await gd_find_one(
            db.session, "teacher_assignments", {"id": assignment_id}
        )
        assert row["is_active"] is False
    assert (await gd_find_one(
        db.session, "teacher_assignments", {"id": other_assignment}
    ))["is_active"] is True
    assert await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert await gd_find_one(db.session, "classes", {"id": class_a})
    assert await gd_find(
        db.session, "teacher_class_assignments",
        {
            "school_id": tenant_a,
            "teacher_id": teacher_id,
            "is_active": True,
        },
        limit=10,
    ) == []
    assert await gd_find_one(
        db.session, "teacher_class_assignments", {"id": inactive_legacy_id}
    )
    tombstones = await load_tombstones(db.session, tenant_a, teacher_id)
    assert {row["class_id"] for row in tombstones} == {class_a, class_b}
    assert (await gd_find_one(
        db.session, "timetable_sessions", {"id": affected_session}
    ))["needs_review"] is True
    assert (await gd_find_one(
        db.session, "timetable_sessions", {"id": unaffected_session}
    )).get("needs_review") is not True


@pytest.mark.asyncio
async def test_unassign_all_is_tenant_scoped_and_sub_admin_allowed(
    client, tenant_a, tenant_b, school_sub_admin_headers
):
    teacher_a, teacher_b = await _teacher(tenant_a), await _teacher(tenant_b)
    class_a, class_b = await _class(tenant_a), await _class(tenant_b)
    assignment_a = await _assignment(tenant_a, teacher_a, class_a, "y1")
    assignment_b = await _assignment(tenant_b, teacher_b, class_b, "y1")

    response = await client.post(
        "/teacher-class-assignments/unassign-all",
        json={},
        headers=school_sub_admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["unassigned_count"] == 1
    assert (await gd_find_one(
        db.session, "teacher_assignments", {"id": assignment_a}
    ))["is_active"] is False
    assert (await gd_find_one(
        db.session, "teacher_assignments", {"id": assignment_b}
    ))["is_active"] is True


@pytest.mark.asyncio
async def test_unassign_teacher_rejects_cross_school_identifier(
    client, tenant_a, tenant_b, school_principal_headers
):
    foreign_teacher = await _teacher(tenant_b)
    response = await client.post(
        "/teacher-class-assignments/unassign-teacher",
        json={"teacher_id": foreign_teacher},
        headers=school_principal_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_bulk_unassign_rejects_non_leadership(
    client, teacher_headers, parent_headers
):
    for headers in (teacher_headers, parent_headers):
        response = await client.post(
            "/teacher-class-assignments/unassign-all",
            json={},
            headers=headers,
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_bulk_unassign_rolls_back_all_writes_when_tombstones_fail(
    tenant_a, monkeypatch
):
    teacher_id = await _teacher(tenant_a)
    class_id = await _class(tenant_a)
    assignment_id = await _assignment(tenant_a, teacher_id, class_id, "y1")

    async def _fail(*args, **kwargs):
        raise RuntimeError("forced tombstone failure")

    monkeypatch.setattr(
        "src.modules.schools.services.teacher_assignments_service.add_class_tombstones",
        _fail,
    )
    with pytest.raises(RuntimeError, match="forced tombstone failure"):
        await TeacherAssignmentsService.bulk_unassign_class_assignments(
            db.session,
            {"id": "principal", "tenant_id": tenant_a, "role": "school_principal"},
            teacher_id=teacher_id,
        )

    row = await gd_find_one(
        db.session, "teacher_assignments", {"id": assignment_id}
    )
    assert row["is_active"] is True


@pytest.mark.asyncio
async def test_bulk_unassign_rejects_pair_overflow_before_writes(
    tenant_a, monkeypatch
):
    teacher_id = await _teacher(tenant_a)
    class_a, class_b = await _class(tenant_a), await _class(tenant_a)
    assignment_a = await _assignment(tenant_a, teacher_id, class_a, "y1")
    assignment_b = await _assignment(tenant_a, teacher_id, class_b, "y1")
    monkeypatch.setattr(
        "src.modules.schools.services.teacher_assignments_service.BULK_UNASSIGN_PAIR_LIMIT",
        1,
    )

    with pytest.raises(Exception) as exc:
        await TeacherAssignmentsService.bulk_unassign_class_assignments(
            db.session,
            {"id": "principal", "tenant_id": tenant_a, "role": "school_principal"},
            teacher_id=teacher_id,
        )
    assert getattr(exc.value, "status_code", None) == 409
    assert exc.value.detail["code"] == "bulk_unassign_limit_exceeded"
    for assignment_id in (assignment_a, assignment_b):
        assert (await gd_find_one(
            db.session, "teacher_assignments", {"id": assignment_id}
        ))["is_active"] is True


@pytest.mark.asyncio
async def test_bulk_unassign_rejects_published_timetable_overflow_before_writes(
    tenant_a, monkeypatch
):
    teacher_id = await _teacher(tenant_a)
    class_id = await _class(tenant_a)
    assignment_id = await _assignment(tenant_a, teacher_id, class_id, "y1")
    for index in range(2):
        await gd_insert(db.session, "timetables", {
            "id": str(uuid.uuid4()),
            "school_id": tenant_a,
            "name": f"published-{index}",
            "status": "published",
        })
    monkeypatch.setattr(
        "src.modules.schools.services.teacher_assignments_service.BULK_UNASSIGN_TIMETABLE_LIMIT",
        1,
    )

    with pytest.raises(Exception) as exc:
        await TeacherAssignmentsService.bulk_unassign_class_assignments(
            db.session,
            {"id": "principal", "tenant_id": tenant_a, "role": "school_principal"},
            teacher_id=teacher_id,
        )
    assert getattr(exc.value, "status_code", None) == 409
    assert exc.value.detail["code"] == "bulk_unassign_timetable_limit_exceeded"
    assert (await gd_find_one(
        db.session, "teacher_assignments", {"id": assignment_id}
    ))["is_active"] is True


@pytest.mark.asyncio
async def test_load_tombstones_propagates_read_failure(tenant_a, monkeypatch):
    async def _fail(*args, **kwargs):
        raise RuntimeError("tombstone storage unavailable")

    monkeypatch.setattr(
        "src.common.utils.teacher_assignment_sync.gd_find",
        _fail,
    )
    with pytest.raises(RuntimeError, match="tombstone storage unavailable"):
        await load_tombstones(db.session, tenant_a)


@pytest.mark.asyncio
async def test_published_session_review_updates_are_chunked(
    tenant_a, monkeypatch
):
    teacher_id = await _teacher(tenant_a)
    class_a, class_b = await _class(tenant_a), await _class(tenant_a)
    await _assignment(tenant_a, teacher_id, class_a, "y1")
    await _assignment(tenant_a, teacher_id, class_b, "y1")
    timetable_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": timetable_id,
        "school_id": tenant_a,
        "name": "published",
        "status": "published",
    })
    for class_id in (class_a, class_b):
        await gd_insert(db.session, "timetable_sessions", {
            "id": str(uuid.uuid4()),
            "school_id": tenant_a,
            "timetable_id": timetable_id,
            "teacher_id": teacher_id,
            "class_id": class_id,
        })

    original_update_many = assignment_service_module.gd_update_many
    review_chunk_sizes = []

    async def _track_update(session, collection, filters, updates):
        if collection == "timetable_sessions":
            review_chunk_sizes.append(len(filters["$or"]))
        return await original_update_many(
            session, collection, filters, updates
        )

    monkeypatch.setattr(assignment_service_module, "gd_update_many", _track_update)
    monkeypatch.setattr(assignment_service_module, "BULK_REVIEW_CHUNK_SIZE", 1)
    result = await TeacherAssignmentsService.bulk_unassign_class_assignments(
        db.session,
        {"id": "principal", "tenant_id": tenant_a, "role": "school_principal"},
        teacher_id=teacher_id,
    )
    assert result["flagged_sessions"] == 2
    assert review_chunk_sizes == [1, 1]