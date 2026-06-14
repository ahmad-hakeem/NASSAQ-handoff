"""Task #900 — regression coverage for authoritative per-student in-session
totals on ``get_session_students`` and undo consistency.

The live-session bug: pressing "undo last action" visually wiped *every*
student's roster badge because the badges were optimistic-only frontend state
and ``get_session_students`` returned no per-student score totals — so the
post-undo refresh replaced every counter with 0.

These tests assert the backend is now the source of truth:
- ``get_session_students`` returns per-student aggregates derived from
  ``session_interactions`` (correct/wrong/participation/behaviour counts and a
  total ``interaction_count``).
- Reversed interactions (``data.reversed``) are excluded from those totals.
- A real undo reverses exactly the last event and leaves every other student's
  totals untouched, both at the interaction level and as surfaced by
  ``get_session_students``.
- Repeat undo walks back one event at a time without ever zeroing unrelated
  students.
- ``compute_session_scores`` (the end/commit path) also honors the reversed
  flag so persisted scores match the live roster.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    InteractionType,
    AnswerResult,
    ParticipationType,
    BehaviourCategory,
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
async def test_get_session_students_multi_student_accumulation(tenant_a):
    """Each student's badge totals reflect their OWN interactions only."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    s2 = await _mk_student(tenant_a, class_id, "بدر")
    for s in (s1, s2):
        await _present(session_id, s)

    eng = _engine()
    # s1: 2 correct answers + 1 participation
    await eng.record_answer(session_id, s1, AnswerResult.CORRECT, teacher_id)
    await eng.record_answer(session_id, s1, AnswerResult.CORRECT, teacher_id)
    await eng.record_participation(session_id, s1, ParticipationType.ACTIVE, teacher_id)
    # s2: 1 wrong answer + 1 positive behaviour
    await eng.record_answer(session_id, s2, AnswerResult.WRONG, teacher_id)
    await eng.record_behaviour(session_id, s2, BehaviourCategory.POSITIVE, "respect", None, teacher_id)

    students = await eng.get_session_students(session_id)
    a1 = _by_id(students, s1)
    a2 = _by_id(students, s2)

    assert a1["correct_answers"] == 2
    assert a1["participation_count"] == 1
    assert a1["wrong_answers"] == 0
    assert a1["interaction_count"] == 3

    assert a2["correct_answers"] == 0
    assert a2["wrong_answers"] == 1
    assert a2["positive_behaviour"] == 1
    assert a2["interaction_count"] == 2


@pytest.mark.asyncio
async def test_get_session_students_excludes_reversed(tenant_a):
    """Interactions flagged data.reversed must not count toward totals."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")
    await _present(session_id, sid)

    now = datetime.now(timezone.utc).isoformat()
    # One live correct answer.
    await gd_insert(db.session, "session_interactions", {
        "id": str(uuid.uuid4()), "session_id": session_id, "student_id": sid,
        "type": InteractionType.QUESTION.value,
        "interaction_type": InteractionType.QUESTION.value,
        "answer_result": AnswerResult.CORRECT.value,
        "recorded_at": now, "timestamp": now,
    })
    # One reversed correct answer — must be ignored.
    await gd_insert(db.session, "session_interactions", {
        "id": str(uuid.uuid4()), "session_id": session_id, "student_id": sid,
        "type": InteractionType.QUESTION.value,
        "interaction_type": InteractionType.QUESTION.value,
        "answer_result": AnswerResult.CORRECT.value,
        "data": {"reversed": True},
        "recorded_at": now, "timestamp": now,
    })

    students = await _engine().get_session_students(session_id)
    agg = _by_id(students, sid)
    assert agg["correct_answers"] == 1
    assert agg["interaction_count"] == 1


@pytest.mark.asyncio
async def test_undo_reverses_only_last_student(tenant_a):
    """A real undo reverses exactly the last event; other students keep totals."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    s2 = await _mk_student(tenant_a, class_id, "بدر")
    for s in (s1, s2):
        await _present(session_id, s)

    eng = _engine()
    await eng.record_answer(session_id, s1, AnswerResult.CORRECT, teacher_id)
    await eng.record_participation(session_id, s1, ParticipationType.ACTIVE, teacher_id)
    # s2's correct answer is the most-recent action.
    await eng.record_answer(session_id, s2, AnswerResult.CORRECT, teacher_id)

    before = await eng.get_session_students(session_id)
    assert _by_id(before, s1)["interaction_count"] == 2
    assert _by_id(before, s2)["correct_answers"] == 1

    await eng.undo_last_action(session_id, teacher_id)

    after = await eng.get_session_students(session_id)
    # s1 untouched.
    assert _by_id(after, s1)["correct_answers"] == 1
    assert _by_id(after, s1)["participation_count"] == 1
    assert _by_id(after, s1)["interaction_count"] == 2
    # only s2's last action reversed.
    assert _by_id(after, s2)["correct_answers"] == 0
    assert _by_id(after, s2)["interaction_count"] == 0


@pytest.mark.asyncio
async def test_repeated_undo_walks_back_one_at_a_time(tenant_a):
    """Each undo steps back exactly one event with no cross-student zeroing."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    s1 = await _mk_student(tenant_a, class_id, "أحمد")
    s2 = await _mk_student(tenant_a, class_id, "بدر")
    for s in (s1, s2):
        await _present(session_id, s)

    eng = _engine()
    await eng.record_answer(session_id, s1, AnswerResult.CORRECT, teacher_id)   # 1
    await eng.record_answer(session_id, s2, AnswerResult.CORRECT, teacher_id)   # 2
    await eng.record_participation(session_id, s1, ParticipationType.ACTIVE, teacher_id)  # 3 (latest)

    # Undo #1 → s1 participation reverses; counts otherwise intact.
    await eng.undo_last_action(session_id, teacher_id)
    st = await eng.get_session_students(session_id)
    assert _by_id(st, s1)["participation_count"] == 0
    assert _by_id(st, s1)["correct_answers"] == 1
    assert _by_id(st, s2)["correct_answers"] == 1

    # Undo #2 → s2 correct answer reverses; s1's answer survives.
    await eng.undo_last_action(session_id, teacher_id)
    st = await eng.get_session_students(session_id)
    assert _by_id(st, s2)["correct_answers"] == 0
    assert _by_id(st, s1)["correct_answers"] == 1

    # Undo #3 → s1 answer reverses; everyone at zero now.
    await eng.undo_last_action(session_id, teacher_id)
    st = await eng.get_session_students(session_id)
    assert _by_id(st, s1)["interaction_count"] == 0
    assert _by_id(st, s2)["interaction_count"] == 0

    # Nothing left to undo.
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await eng.undo_last_action(session_id, teacher_id)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_compute_session_scores_excludes_reversed(tenant_a):
    """The end/commit aggregation honors the reversed flag like the roster."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")
    await _present(session_id, sid)

    eng = _engine()
    await eng.record_answer(session_id, sid, AnswerResult.CORRECT, teacher_id)
    await eng.record_answer(session_id, sid, AnswerResult.CORRECT, teacher_id)

    full = await eng.compute_session_scores(session_id)
    points_before = full["students"][sid]["participation_points"]

    # Reverse the latest correct answer.
    await eng.undo_last_action(session_id, teacher_id)

    reduced = await eng.compute_session_scores(session_id)
    points_after = reduced["students"][sid]["participation_points"]

    assert points_after < points_before
    # Exactly one correct answer (5 pts) should remain.
    assert points_after == 5
