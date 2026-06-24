"""Task #1087 — cross-page consistency between the live-session attendance
register and the canonical daily ``attendance`` table.

Product decision: the canonical daily ``attendance`` table is the single source
of truth. A status change made in the live-session register must update that one
record immediately (no approval step), and the session roster must reflect a
status that was set on the daily attendance page. No duplicate rows may be
created for the same class/date/student regardless of how many times (or from
which entry point) the teacher saves.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find, gd_insert
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    AttendanceStatus,
    _coerce_attendance_date,
)

SESSION_DATE = "2026-06-14"


class _DBShim:
    @property
    def session(self):
        return db.session


def _engine():
    return SessionEngine(_DBShim())


async def _mk_user(tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x",
    })
    return uid


async def _mk_class(tenant_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_session(tenant_id: str, class_id: str, teacher_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "teacher_id": teacher_id,
        "date": SESSION_DATE,
        "status": "in_progress",
        "start_time": now,
        "created_at": now,
    })
    return session_id


async def _mk_student(tenant_id: str, class_id: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "tenant_id": tenant_id,
        "school_id": tenant_id,
        "class_id": class_id,
        "full_name": name,
        "is_active": True,
    })
    return sid


async def _draft_present(session_id: str, student_id: str):
    await gd_insert(db.session, "session_attendance", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "status": AttendanceStatus.PRESENT.value,
        "is_draft": True,
    })


async def _canonical_rows(class_id: str, student_id: str):
    """All canonical daily-attendance rows for the class/date/student."""
    att_date = _coerce_attendance_date(SESSION_DATE)
    return await gd_find(
        db.session, "attendance",
        {"class_id": class_id, "student_id": student_id, "date": att_date},
        limit=50,
    )


async def _daily_mark(tenant_id: str, class_id: str, student_id: str, status: str, recorded_by: str):
    """Emulate the daily attendance page writing to the canonical table."""
    from engines.attendance_engine import AttendanceEngine
    att = AttendanceEngine(_DBShim())
    await att.record_bulk_attendance(
        tenant_id=tenant_id,
        section_id=class_id,
        attendance_date=_coerce_attendance_date(SESSION_DATE),
        attendance_records=[{"student_id": student_id, "status": status}],
        recorded_by=recorded_by,
    )


def _by_id(students, sid):
    return next(s for s in students if s["id"] == sid)


@pytest.mark.asyncio
async def test_live_toggle_writes_through_to_canonical_immediately(tenant_a):
    """A single live-session toggle is readable on the canonical daily table
    with no approval step."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    await _draft_present(session_id, s1)

    await _engine().update_attendance(session_id, s1, AttendanceStatus.ABSENT, teacher_id)

    rows = await _canonical_rows(class_id, s1)
    assert len(rows) == 1
    assert rows[0]["status"] == "absent"


@pytest.mark.asyncio
async def test_repeated_live_toggles_never_duplicate_rows(tenant_a):
    """Toggling the same student multiple times keeps exactly one canonical row
    holding the latest status."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    await _draft_present(session_id, s1)

    eng = _engine()
    await eng.update_attendance(session_id, s1, AttendanceStatus.ABSENT, teacher_id)
    await eng.update_attendance(session_id, s1, AttendanceStatus.PRESENT, teacher_id)
    await eng.update_attendance(session_id, s1, AttendanceStatus.LATE, teacher_id)

    rows = await _canonical_rows(class_id, s1)
    assert len(rows) == 1
    assert rows[0]["status"] == "late"


@pytest.mark.asyncio
async def test_approve_after_live_toggle_keeps_single_canonical_row(tenant_a):
    """Approving after a live toggle re-runs the idempotent upsert — still one
    canonical row, holding the toggled status."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    await _draft_present(session_id, s1)

    eng = _engine()
    await eng.update_attendance(session_id, s1, AttendanceStatus.ABSENT, teacher_id)
    await eng.approve_attendance(session_id, teacher_id)
    await eng.approve_attendance(session_id, teacher_id)

    rows = await _canonical_rows(class_id, s1)
    assert len(rows) == 1
    assert rows[0]["status"] == "absent"


@pytest.mark.asyncio
async def test_session_roster_reflects_status_set_on_daily_page(tenant_a):
    """A status written through the daily-page path shows up in the live-session
    roster instead of defaulting to present."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    s2 = await _mk_student(tenant_a, class_id, "بدر")
    for s in (s1, s2):
        await _draft_present(session_id, s)

    # Daily page marks s1 absent in the canonical table.
    await _daily_mark(tenant_a, class_id, s1, "absent", teacher_id)

    students = await _engine().get_session_students(session_id)
    assert _by_id(students, s1)["attendance_status"] == "absent"
    # s2 has no canonical row yet → falls back to the session draft (present).
    assert _by_id(students, s2)["attendance_status"] == "present"


@pytest.mark.asyncio
async def test_session_roster_falls_back_to_draft_without_canonical(tenant_a):
    """With no canonical record, the roster still shows the draft/default."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    await _draft_present(session_id, s1)

    students = await _engine().get_session_students(session_id)
    assert _by_id(students, s1)["attendance_status"] == "present"


@pytest.mark.asyncio
async def test_live_toggle_then_roster_round_trips(tenant_a):
    """End-to-end: toggle in the register → canonical updated → roster reads the
    same status back (no stale present default)."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    await _draft_present(session_id, s1)

    eng = _engine()
    await eng.update_attendance(session_id, s1, AttendanceStatus.ABSENT, teacher_id)

    students = await eng.get_session_students(session_id)
    assert _by_id(students, s1)["attendance_status"] == "absent"
