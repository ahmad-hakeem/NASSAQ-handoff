"""
Regression tests for `get_teacher_classes` (`GET /api/teacher/classes/{id}`)
in `backend/routes/role_dashboards_mod.py`.

Bug: every "My Classes" ("فصولي") card was badged "بدون حصة" (no lesson) even
when the teacher had a full timetable ("جدولي"). Root cause: the handler
computed each class's status/next_session from its OWN inline read of the
legacy ``schedule_sessions`` table, which is empty for schools on the modern
``timetable_sessions`` engine -> every card defaulted to status="no_upcoming".

Fix: the handler now derives status/next_session/weekly_periods from the SAME
resolver the timetable view uses (``_resolve_teacher_sessions``), so a class's
lesson status can never contradict the timetable.

These tests lock in that the card status is driven by the resolver:
  * Resolver returns a session for the class  -> status="active", next_session
    populated, schedule_count/weekly_periods reflect the resolved sessions.
  * Resolver returns nothing                  -> status="no_upcoming" (the only
    truly-valid empty state).
"""
import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_insert
import src.modules.portals.controllers.role_dashboards_mod as rd


async def _seed_class_and_assignment(school_id, teacher_id):
    cid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": school_id,
        "full_name": "أحمد المعلم", "is_active": True,
    })
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "name": "فصل ١", "is_active": True,
    })
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": school_id, "name": "رياضيات", "name_ar": "رياضيات",
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()), "school_id": school_id,
        "teacher_id": teacher_id, "class_id": cid, "subject_id": sid,
        "is_active": True,
    })
    return cid, sid


def _patch_handler_deps(monkeypatch, teacher, sessions):
    """Neutralize identity/tenant guards and one-shot side effects so the test
    exercises only the status-derivation logic, and force the resolver output."""
    async def _resolve_record(_tid):
        return teacher

    async def _assert_identity(*_a, **_k):
        return None

    def _check_tenant(*_a, **_k):
        return None

    async def _noop_reconcile(*_a, **_k):
        return 0

    async def _resolve_sessions(_school_id, _teacher_id):
        return sessions

    monkeypatch.setattr(rd, "_resolve_teacher_record", _resolve_record)
    monkeypatch.setattr(rd, "_assert_teacher_identity", _assert_identity)
    monkeypatch.setattr(rd, "_check_teacher_tenant", _check_tenant)
    monkeypatch.setattr(rd, "_reconcile_teacher_assignments_from_schedule", _noop_reconcile)
    monkeypatch.setattr(rd, "_resolve_teacher_sessions", _resolve_sessions)

    import src.modules.schools.controllers.school_settings_mod as ss

    async def _noop_populate(*_a, **_k):
        return None

    monkeypatch.setattr(ss, "_auto_populate_teacher_class_assignments", _noop_populate)


@pytest.mark.asyncio
async def test_status_active_when_timetable_has_sessions(monkeypatch):
    school_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": school_id, "name": "School", "code": f"S{school_id[:8]}", "status": "active",
    })
    teacher = {"id": teacher_id, "school_id": school_id, "full_name": "أحمد المعلم"}
    cid, sid = await _seed_class_and_assignment(school_id, teacher_id)

    _patch_handler_deps(monkeypatch, teacher, [
        {
            "class_id": cid, "subject_id": sid,
            "day_of_week": "sunday", "period_number": 1, "slot_number": 1,
            "start_time": "08:00", "end_time": "08:45",
            "subject_name": "رياضيات", "room_name": "A1",
        },
        {
            "class_id": cid, "subject_id": sid,
            "day_of_week": "monday", "period_number": 2, "slot_number": 2,
            "start_time": "09:00", "end_time": "09:45",
            "subject_name": "رياضيات", "room_name": "A1",
        },
    ])

    result = await rd.get_teacher_classes(teacher_id, {"role": "teacher", "id": teacher_id})

    assert len(result) == 1
    card = result[0]
    assert card["status"] == "active"
    assert card["next_session"] is not None
    assert card["schedule_count"] == 2
    assert card["weekly_periods"] == 2


@pytest.mark.asyncio
async def test_status_no_upcoming_when_resolver_empty(monkeypatch):
    school_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": school_id, "name": "School", "code": f"S{school_id[:8]}", "status": "active",
    })
    teacher = {"id": teacher_id, "school_id": school_id, "full_name": "أحمد المعلم"}
    cid, sid = await _seed_class_and_assignment(school_id, teacher_id)

    _patch_handler_deps(monkeypatch, teacher, [])

    result = await rd.get_teacher_classes(teacher_id, {"role": "teacher", "id": teacher_id})

    assert len(result) == 1
    card = result[0]
    assert card["status"] == "no_upcoming"
    assert card["next_session"] is None
    assert card["schedule_count"] == 0
