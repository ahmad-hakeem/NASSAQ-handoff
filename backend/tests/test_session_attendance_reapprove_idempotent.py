"""Task #928 — regression coverage for idempotent attendance-score application
on ``approve_attendance``.

The live-session bug: the in-session attendance register wrote only to the
school-wide daily ``attendance`` table, so the session summary/report (which
read from ``session_attendance``) showed everyone present. The fix routes the
live register through the canonical session endpoints and re-finalizes (approve)
on close. Because the drafts are already approved once at session start, approve
can now run more than once for the same session.

These tests assert that re-approval applies only the *net* score delta between a
record's previously-applied status and its current status, so editing attendance
mid-session never double-counts a student's attendance score. Default rules:
present=+1, absent_no_excuse=-3, late=-1, excused=0.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find, gd_insert
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    AttendanceStatus,
)


def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session

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
        "date": "2026-06-14",
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


async def _score_total(student_id: str) -> int:
    rows = await gd_find(db.session, "student_score_ledger", {"student_id": student_id}, limit=200)
    attendance_rows = [r for r in rows if r.get("category") == "attendance"]
    return sum(r.get("score_change", 0) for r in attendance_rows)


@pytest.mark.asyncio
async def test_reapprove_after_edit_applies_only_net_delta(tenant_a):
    """Editing one student to absent and re-approving applies only the delta;
    unchanged students get no extra score."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    s2 = await _mk_student(tenant_a, class_id, "بدر")
    for s in (s1, s2):
        await _draft_present(session_id, s)

    eng = _engine()

    # First approval (session start): both present → +1 each.
    await eng.approve_attendance(session_id, teacher_id)
    assert await _score_total(s1) == 1
    assert await _score_total(s2) == 1

    # Teacher edits s1 to absent from the live register, then re-finalizes.
    await eng.update_attendance(session_id, s1, AttendanceStatus.ABSENT, teacher_id)
    await eng.approve_attendance(session_id, teacher_id)

    # s1: net should equal a single absent (-3), not present+absent double-count.
    assert await _score_total(s1) == -3
    # s2: unchanged status → no extra score applied on re-approval.
    assert await _score_total(s2) == 1


@pytest.mark.asyncio
async def test_reapprove_without_change_is_noop_for_scores(tenant_a):
    """Re-approving with no status changes does not alter any score."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    await _draft_present(session_id, s1)

    eng = _engine()
    await eng.approve_attendance(session_id, teacher_id)
    assert await _score_total(s1) == 1

    # Re-approve repeatedly with no edits — score must stay put.
    await eng.approve_attendance(session_id, teacher_id)
    await eng.approve_attendance(session_id, teacher_id)
    assert await _score_total(s1) == 1
