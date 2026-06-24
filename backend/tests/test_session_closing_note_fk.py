"""Regression: ending a lesson WITH a closing note must not fail with the
foreign-key error surfaced as "مرجع غير صالح في البيانات المُرسَلة".

Root cause: ``session_notes.teacher_id`` is an FK to ``teachers.id``, but
``class_sessions`` is a schemaless collection so its ``teacher_id`` (and the
acting ``users.id`` the end-session route passes in) may not be a real
``teachers.id``. The earlier fix copied ``session.teacher_id`` straight into the
FK column, which still violates the constraint for live-started sessions whose
``teacher_id`` is a ``users.id``.

The fix: ``end_session`` resolves a *verified* ``teachers.id`` (session value,
then the acting user's linked teacher), falling back to NULL (the column is
nullable) so the note is always saved against the session.

Only the closing note distinguishes the failing path from the working one
(``confirmEndSession`` adds ``closing_note`` to the POST body only when text is
present), so these tests drive ``end_session`` with and without a note.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert
from engines.session_engine import TeacherSessionEngine as SessionEngine


def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session
    return SessionEngine(_DBShim())


async def _mk_user(tenant_id, *, teacher_link=None) -> str:
    uid = str(uuid.uuid4())
    doc = {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x",
    }
    if teacher_link:
        doc["teacher_id"] = teacher_link
    await gd_insert(db.session, "users", doc)
    return uid


async def _mk_teacher_row(tenant_id) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": tenant_id, "full_name": "معلم", "is_active": True,
    })
    return tid


async def _mk_class(tenant_id) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_session(tenant_id, class_id, teacher_id) -> str:
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "class_id": class_id, "date": "2026-06-24", "status": "in_progress",
        "start_time": now, "teacher_id": teacher_id, "attendance_approved": True,
        "created_at": now,
    })
    return sid


async def _closing_note_row(session_id):
    # The lesson-level closing note is the ``type == "closing"`` row; content
    # lives in the real ``note`` column (NOT the phantom ``text`` key).
    rows = await gd_find(db.session, "session_notes", {"session_id": session_id}, limit=50)
    return next((r for r in rows if r.get("type") == "closing"), None)


async def _session_closing_note(session_id):
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    return (session or {}).get("closing_note")


@pytest.mark.asyncio
async def test_end_session_with_note_when_session_teacher_is_users_id(tenant_a):
    """The exact reported failure: ``session.teacher_id`` holds a ``users.id``
    (no matching ``teachers`` row). Ending with a note must succeed and persist
    the note with a NULL teacher — never raise an FK violation."""
    user_id = await _mk_user(tenant_a)  # users.id only, no teachers row
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id=user_id)

    result = await _engine().end_session(session_id, user_id, closing_note="ملاحظة ختامية")
    assert result is not None

    note = await _closing_note_row(session_id)
    assert note is not None, "closing note row must be persisted"
    assert note["note"] == "ملاحظة ختامية"  # content in the real column
    assert note["teacher_id"] is None  # resolved to NULL — FK-safe

    # Canonical destination: stored against the session record itself.
    assert await _session_closing_note(session_id) == "ملاحظة ختامية"

    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    assert session["status"] == "completed"


@pytest.mark.asyncio
async def test_end_session_with_note_attributes_valid_session_teacher(tenant_a):
    """When ``session.teacher_id`` IS a real ``teachers.id`` the note is
    attributed to it."""
    teacher_row = await _mk_teacher_row(tenant_a)
    user_id = await _mk_user(tenant_a, teacher_link=teacher_row)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id=teacher_row)

    await _engine().end_session(session_id, user_id, closing_note="ختام")
    note = await _closing_note_row(session_id)
    assert note is not None
    assert note["teacher_id"] == teacher_row


@pytest.mark.asyncio
async def test_end_session_with_note_falls_back_to_acting_user_teacher_link(tenant_a):
    """``session.teacher_id`` is a ``users.id``, but the acting user is linked to
    a real ``teachers.id`` — the note is attributed to that linked teacher."""
    teacher_row = await _mk_teacher_row(tenant_a)
    user_id = await _mk_user(tenant_a, teacher_link=teacher_row)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id=user_id)  # users.id

    await _engine().end_session(session_id, user_id, closing_note="note")
    note = await _closing_note_row(session_id)
    assert note is not None
    assert note["teacher_id"] == teacher_row


@pytest.mark.asyncio
async def test_end_session_with_english_note(tenant_a):
    """English note content behaves identically — content is opaque to the FK."""
    user_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id=user_id)

    await _engine().end_session(session_id, user_id, closing_note="Great lesson today")
    note = await _closing_note_row(session_id)
    assert note is not None
    assert note["note"] == "Great lesson today"
    assert note["teacher_id"] is None
    assert await _session_closing_note(session_id) == "Great lesson today"


@pytest.mark.asyncio
async def test_end_session_without_note_writes_no_closing_note(tenant_a):
    """The no-note path (working before) stays unchanged: no closing note row."""
    user_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id=user_id)

    result = await _engine().end_session(session_id, user_id)
    assert result is not None
    assert await _closing_note_row(session_id) is None


# ---------------------------------------------------------------------------
# Visibility: the note must reach its read destinations, not just persist.
# ---------------------------------------------------------------------------

async def _mk_student(tenant_id, class_id) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "class_id": class_id, "full_name": "طالب", "is_active": True,
    })
    return sid


async def _mk_attendance(session_id, student_id, status="present"):
    await gd_insert(db.session, "session_attendance", {
        "id": str(uuid.uuid4()), "session_id": session_id,
        "student_id": student_id, "status": status,
    })


@pytest.mark.asyncio
async def test_export_session_report_surfaces_closing_note(tenant_a):
    """The persisted closing note is visible in the session report export."""
    user_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id=user_id)

    await _engine().end_session(session_id, user_id, closing_note="ملخص الحصة")

    report = await _engine().export_session_report(session_id, user_id)
    closing = [n for n in report["notes"] if n["is_closing"]]
    assert len(closing) == 1
    assert closing[0]["text"] == "ملخص الحصة"


@pytest.mark.asyncio
async def test_parent_lesson_report_surfaces_closing_note(tenant_a):
    """The closing note is delivered to every child's parent lesson report."""
    user_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id=user_id)
    student_id = await _mk_student(tenant_a, class_id)
    await _mk_attendance(session_id, student_id)

    await _engine().end_session(session_id, user_id, closing_note="إلى أولياء الأمور")

    reports = await _engine().build_parent_lesson_reports(session_id)
    assert student_id in reports
    assert reports[student_id]["teacher_note"] == "إلى أولياء الأمور"
