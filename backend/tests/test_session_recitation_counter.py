"""Regression coverage for recitation (التسميع) in the live-session per-student
counter.

The bug: recitation was stored as a ``session_notes`` row, but the live
per-student "X/Y" counter on ``get_session_students`` aggregates ONLY
``session_interactions``. So recitation never counted server-side — the
frontend bumped the badge optimistically and pressing "تحديث" (refresh) wiped
it.

The fix: recitation is a dedicated grade-NEUTRAL ``InteractionType.RECITATION``
interaction that moves the counter (denominator always; numerator when
mastered) but is deliberately absent from every scoring branch, so it never
touches grades / the follow-up sheet / committed ledgers. It is reversible.

These tests assert:
- A mastered recitation is 1 denominator + 1 numerator; not-mastered is
  denominator only.
- Recitation stacks with question answers on the same counter.
- Recitation is grade-NEUTRAL: ``compute_session_scores`` is unchanged by it.
- Reversed recitation rows are excluded from the counter.
- A real undo reverses exactly the recitation and leaves prior actions intact.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_insert
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    InteractionType,
    AnswerResult,
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


async def _mk_session(tenant_id: str, class_id: str, teacher_id: str,
                      status: str = "in_progress") -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "teacher_id": teacher_id,
        "date": "2026-06-14",
        "status": status,
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


async def _present(session_id: str, student_id: str):
    await gd_insert(db.session, "session_attendance", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "status": "present",
    })


def _by_id(students, sid):
    return next(s for s in students if s["id"] == sid)


@pytest.mark.asyncio
async def test_mastered_recitation_moves_numerator_and_denominator(tenant_a):
    """متقن → question_count += 1 AND eval_positive_count += 1."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id, "أحمد")
    await _present(session_id, sid)

    eng = _engine()
    await eng.record_recitation(session_id, sid, mastered=True, teacher_id=teacher_id, attempts=1)

    agg = _by_id(await eng.get_session_students(session_id), sid)
    assert agg["question_count"] == 1
    assert agg["eval_positive_count"] == 1
    assert agg["interaction_count"] == 1
    # Grade-neutral markers: recitation must not touch answer/participation buckets.
    assert agg["correct_answers"] == 0
    assert agg["participation_count"] == 0


@pytest.mark.asyncio
async def test_not_mastered_recitation_moves_only_denominator(tenant_a):
    """لم يتقن → question_count += 1, numerator unchanged."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id, "بدر")
    await _present(session_id, sid)

    eng = _engine()
    await eng.record_recitation(session_id, sid, mastered=False, teacher_id=teacher_id, attempts=2)

    agg = _by_id(await eng.get_session_students(session_id), sid)
    assert agg["question_count"] == 1
    assert agg["eval_positive_count"] == 0
    assert agg["interaction_count"] == 1


@pytest.mark.asyncio
async def test_recitation_stacks_with_question_answer(tenant_a):
    """A correct answer + a mastered recitation → 2/2 on the same counter."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id, "أحمد")
    await _present(session_id, sid)

    eng = _engine()
    await eng.record_answer(session_id, sid, AnswerResult.CORRECT, teacher_id)
    await eng.record_recitation(session_id, sid, mastered=True, teacher_id=teacher_id)

    agg = _by_id(await eng.get_session_students(session_id), sid)
    assert agg["question_count"] == 2
    assert agg["eval_positive_count"] == 2
    assert agg["correct_answers"] == 1
    assert agg["interaction_count"] == 2


@pytest.mark.asyncio
async def test_recitation_is_grade_neutral(tenant_a):
    """compute_session_scores (grades/ledger path) must ignore recitation."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")
    await _present(session_id, sid)

    eng = _engine()
    await eng.record_answer(session_id, sid, AnswerResult.CORRECT, teacher_id)
    before = (await eng.compute_session_scores(session_id))["students"][sid]["participation_points"]

    # Two recitations (mastered + not) must not change the graded points.
    await eng.record_recitation(session_id, sid, mastered=True, teacher_id=teacher_id)
    await eng.record_recitation(session_id, sid, mastered=False, teacher_id=teacher_id)

    after = (await eng.compute_session_scores(session_id))["students"][sid]["participation_points"]
    assert after == before


@pytest.mark.asyncio
async def test_reversed_recitation_excluded_from_counter(tenant_a):
    """A recitation row flagged data.reversed must not count."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")
    await _present(session_id, sid)

    now = datetime.now(timezone.utc).isoformat()
    # One live mastered recitation.
    await gd_insert(db.session, "session_interactions", {
        "id": str(uuid.uuid4()), "session_id": session_id, "student_id": sid,
        "type": InteractionType.RECITATION.value,
        "interaction_type": InteractionType.RECITATION.value,
        "recitation_mastered": True,
        "recorded_at": now, "timestamp": now,
    })
    # One reversed mastered recitation — must be ignored.
    await gd_insert(db.session, "session_interactions", {
        "id": str(uuid.uuid4()), "session_id": session_id, "student_id": sid,
        "type": InteractionType.RECITATION.value,
        "interaction_type": InteractionType.RECITATION.value,
        "recitation_mastered": True,
        "data": {"reversed": True},
        "recorded_at": now, "timestamp": now,
    })

    agg = _by_id(await _engine().get_session_students(session_id), sid)
    assert agg["question_count"] == 1
    assert agg["eval_positive_count"] == 1


@pytest.mark.asyncio
async def test_undo_reverses_recitation_only(tenant_a):
    """Undo after a correct answer + recitation reverses just the recitation."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id, "أحمد")
    await _present(session_id, sid)

    eng = _engine()
    await eng.record_answer(session_id, sid, AnswerResult.CORRECT, teacher_id)
    await eng.record_recitation(session_id, sid, mastered=True, teacher_id=teacher_id)

    before = _by_id(await eng.get_session_students(session_id), sid)
    assert before["question_count"] == 2
    assert before["eval_positive_count"] == 2

    await eng.undo_last_action(session_id, teacher_id)

    after = _by_id(await eng.get_session_students(session_id), sid)
    # Recitation reversed; the correct answer survives.
    assert after["question_count"] == 1
    assert after["eval_positive_count"] == 1
    assert after["correct_answers"] == 1
    assert after["interaction_count"] == 1
