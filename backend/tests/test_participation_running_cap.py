"""
Regression: live-session participation (المشاركة) must be bounded by a
CHRONOLOGICAL RUNNING CLAMP, not summed-then-capped.

Bug: ``compute_session_scores`` accumulated ``participation_points`` as an
unbounded running sum and the column max was applied only at the output
boundary (``_coursework_value`` -> ``min(sum, max)``). A hidden overflow then
absorbed a later negative interaction: ``+5, +5, -2`` with a column max of 5
displayed ``min(8, 5) = 5`` with no visible drop, instead of the bounded
``clamp(clamp(5 + 5) - 2) = 3`` the teacher expects.

Fix: fold the participation deltas in chronological order with a per-step clamp
to ``[0, column_max]`` (``acc = max(0, min(acc + delta, max))``). The same
bounded value must appear in the Follow-up sheet (``build_followup_hydration``),
the committed school grade (``student_grades``), and the persisted
``participation_records`` row — for any configured column max.

The raw ``participation_points`` aggregate is intentionally left UNCHANGED — it
is a tested contract that proves answer-weighting — only the graded / persisted
value is bounded.

All deltas are recorded as ``evaluation`` interactions with explicit ``points``
and explicit ascending timestamps so the scenarios are independent of the score
rules and of any database insertion order.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert
from engines.session_engine import TeacherSessionEngine as SessionEngine, InteractionType


def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session
    return SessionEngine(_DBShim())


async def _mk_class(tenant_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_subject(tenant_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "name": "الرياضيات", "name_ar": "الرياضيات",
    })
    return sid


async def _mk_user(tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x",
    })
    return uid


async def _mk_student(tenant_id: str, class_id: str, name: str = "طالب") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": name, "is_active": True,
    })
    return sid


async def _mk_session(tenant_id: str, class_id: str, subject_id: str,
                      teacher_id: str = None) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": session_id, "school_id": tenant_id, "tenant_id": tenant_id,
        "class_id": class_id, "subject_id": subject_id, "date": "2026-06-15",
        "status": "in_progress", "start_time": now, "attendance_approved": True,
        "created_at": now,
    }
    if teacher_id:
        doc["teacher_id"] = teacher_id
    await gd_insert(db.session, "class_sessions", doc)
    return session_id


async def _mk_part_col(class_id: str, max_grade: int) -> str:
    """Pre-create the participation grade column with an explicit max so the
    engine's auto-create defaults do not run (idempotent only when none exist)."""
    col_id = str(uuid.uuid4())
    await gd_insert(db.session, "grade_columns", {
        "id": col_id, "class_id": class_id, "name": "المشاركة",
        "name_en": "Participation", "column_type": "coursework",
        "max_grade": max_grade, "order": 1, "visible": True,
    })
    return col_id


def _ts(minute: int) -> str:
    return datetime(2026, 6, 15, 10, minute, 0, tzinfo=timezone.utc).isoformat()


async def _eval(session_id: str, student_id: str, recorded_by: str,
                points: int, minute: int) -> str:
    """A side-strip evaluation interaction carrying explicit signed points and a
    controlled timestamp (so the chronological fold order is deterministic)."""
    iid = str(uuid.uuid4())
    ts = _ts(minute)
    await gd_insert(db.session, "session_interactions", {
        "id": iid, "session_id": session_id, "student_id": student_id,
        "type": "evaluation", "interaction_type": InteractionType.EVALUATION.value,
        "points": points, "recorded_by": recorded_by,
        "recorded_at": ts, "timestamp": ts,
    })
    return iid


@pytest.mark.asyncio
async def test_overflow_does_not_absorb_a_later_negative(tenant_a):
    """+5, +5, -2 with column max 5 must surface 3 (clamp), not 5 (sum-then-cap)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    col_id = await _mk_part_col(class_id, 5)
    sid = await _mk_student(tenant_a, class_id)

    await _eval(session_id, sid, teacher_id, 5, 0)
    await _eval(session_id, sid, teacher_id, 5, 1)
    await _eval(session_id, sid, teacher_id, -2, 2)

    eng = _engine()
    hydrated = await eng.build_followup_hydration(session_id, {})
    assert hydrated[sid][col_id] == 3, (
        "the late -2 must reduce the bounded value (clamp), not be absorbed by "
        "the hidden +5 overflow"
    )

    # The raw aggregate stays the unbounded sum (tested contract elsewhere).
    computed = await eng.compute_session_scores(session_id)
    assert computed["students"][sid]["participation_points"] == 8


@pytest.mark.asyncio
async def test_commit_persists_the_bounded_value(tenant_a):
    """Sheet == committed school grade == persisted participation record == 3."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    col_id = await _mk_part_col(class_id, 5)
    sid = await _mk_student(tenant_a, class_id)

    await _eval(session_id, sid, teacher_id, 5, 0)
    await _eval(session_id, sid, teacher_id, 5, 1)
    await _eval(session_id, sid, teacher_id, -2, 2)

    eng = _engine()
    await eng.commit_session_scores(session_id)

    grades = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": sid})
    part_grade = next((g for g in grades if g.get("column_id") == col_id), None) or (
        grades[0] if grades else None
    )
    assert part_grade is not None, "a participation grade should be committed"
    assert int(part_grade["score"]) == 3

    rec = await gd_find_one(db.session, "participation_records",
                            {"session_id": session_id, "student_id": sid})
    assert rec is not None, "a participation record should be persisted"
    assert int(rec["points"]) == 3, "the DB must never persist a value above the max"


@pytest.mark.asyncio
async def test_running_clamp_honors_a_larger_column_max(tenant_a):
    """+5, +5, +5, -2 with column max 10 clamps to 8 (sum-then-cap would give 10)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    col_id = await _mk_part_col(class_id, 10)
    sid = await _mk_student(tenant_a, class_id)

    await _eval(session_id, sid, teacher_id, 5, 0)
    await _eval(session_id, sid, teacher_id, 5, 1)
    await _eval(session_id, sid, teacher_id, 5, 2)
    await _eval(session_id, sid, teacher_id, -2, 3)

    eng = _engine()
    hydrated = await eng.build_followup_hydration(session_id, {})
    assert hydrated[sid][col_id] == 8


@pytest.mark.asyncio
async def test_within_bounds_sequence_is_unchanged(tenant_a):
    """Control: a sequence that never overflows is identical to before (+2, -1 = 1)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    col_id = await _mk_part_col(class_id, 5)
    sid = await _mk_student(tenant_a, class_id)

    await _eval(session_id, sid, teacher_id, 2, 0)
    await _eval(session_id, sid, teacher_id, -1, 1)

    eng = _engine()
    hydrated = await eng.build_followup_hydration(session_id, {})
    assert hydrated[sid][col_id] == 1


@pytest.mark.asyncio
async def test_negative_at_floor_does_not_create_hidden_debt(tenant_a):
    """-2 then +5 (max 5) clamps the floor at 0 then rises to 5, not 3."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    col_id = await _mk_part_col(class_id, 5)
    sid = await _mk_student(tenant_a, class_id)

    await _eval(session_id, sid, teacher_id, -2, 0)
    await _eval(session_id, sid, teacher_id, 5, 1)

    eng = _engine()
    hydrated = await eng.build_followup_hydration(session_id, {})
    assert hydrated[sid][col_id] == 5


@pytest.mark.asyncio
async def test_earned_then_lost_to_floor_surfaces_and_commits_zero(tenant_a):
    """+5, +5, -5 (max 5) lands on the 0 floor: the sheet shows 0 (not blank,
    not stale 5) and the committed grade is 0 — earned-then-lost is a real,
    committable value, distinct from "never participated"."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    col_id = await _mk_part_col(class_id, 5)
    sid = await _mk_student(tenant_a, class_id)

    await _eval(session_id, sid, teacher_id, 5, 0)
    await _eval(session_id, sid, teacher_id, 5, 1)
    await _eval(session_id, sid, teacher_id, -5, 2)

    eng = _engine()
    hydrated = await eng.build_followup_hydration(session_id, {})
    assert hydrated[sid][col_id] == 0, "earned-then-lost must surface 0, not blank/stale"

    await eng.commit_session_scores(session_id)
    grades = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": sid})
    part_grade = next((g for g in grades if g.get("column_id") == col_id), None)
    assert part_grade is not None, "a 0 participation grade must be committed"
    assert int(part_grade["score"]) == 0


@pytest.mark.asyncio
async def test_recommit_clears_a_previously_committed_positive(tenant_a):
    """The reachable stale path via the "حفظ الحصة" save action: commit +5,+5
    (grade 5, record 5), then a later -5 drives the bounded value to 0. The
    re-commit must overwrite the grade to 0 AND clear the stale ledger row, so
    the committed state never lags behind the live sheet."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    col_id = await _mk_part_col(class_id, 5)
    sid = await _mk_student(tenant_a, class_id)

    await _eval(session_id, sid, teacher_id, 5, 0)
    await _eval(session_id, sid, teacher_id, 5, 1)

    eng = _engine()
    await eng.commit_session_scores(session_id)
    grades = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": sid})
    pg = next((g for g in grades if g.get("column_id") == col_id), None)
    assert pg is not None and int(pg["score"]) == 5
    rec = await gd_find_one(db.session, "participation_records",
                            {"session_id": session_id, "student_id": sid})
    assert rec is not None and int(rec["points"]) == 5

    # A later negative drops the bounded value to the 0 floor, then re-save.
    await _eval(session_id, sid, teacher_id, -5, 2)
    await eng.commit_session_scores(session_id)

    grades = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": sid})
    pg = next((g for g in grades if g.get("column_id") == col_id), None)
    assert pg is not None and int(pg["score"]) == 0, "stale 5 must be overwritten to 0"
    rec = await gd_find_one(db.session, "participation_records",
                            {"session_id": session_id, "student_id": sid})
    assert rec is None, "the stale positive participation record must be cleared"


@pytest.mark.asyncio
async def test_never_positive_writes_no_participation_row(tenant_a):
    """A student who only ever lost points (never went positive) must NOT get a
    phantom 0 grade or a 0 participation record — the no-phantom contract that
    distinguishes "earned then lost" (committable 0) from "never participated"."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    col_id = await _mk_part_col(class_id, 5)
    sid = await _mk_student(tenant_a, class_id)

    await _eval(session_id, sid, teacher_id, -1, 0)

    eng = _engine()
    hydrated = await eng.build_followup_hydration(session_id, {})
    assert col_id not in hydrated.get(sid, {}), "never-positive must leave the cell blank"

    await eng.commit_session_scores(session_id)
    grades = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": sid})
    assert not any(g.get("column_id") == col_id for g in grades), "no phantom grade row"
    rec = await gd_find_one(db.session, "participation_records",
                            {"session_id": session_id, "student_id": sid})
    assert rec is None, "no phantom participation record"
