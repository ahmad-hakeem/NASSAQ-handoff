"""
Regression: the post-lesson summary pages (review preview + end-session
summary) showed مشاركات = 0 and معدل المشاركة = 0% even when students actively
participated during the lesson.

Root cause: ``get_review_preview`` and ``end_session`` classified
"participation" as ONLY ``interaction_type == 'participation'`` rows, but the
primary teaching flow records engagement as ``question`` answers (صحيح/خطأ),
``evaluation`` and ``recitation`` interactions. The canonical participatory
predicate already existed (``_interaction_is_participatory`` in
``role_dashboards_mod``) and is used by student analytics — the session engine
must use the same classification.

Participatory (counts toward مشاركات / طلاب شاركوا / معدل المشاركة):
- question with answer_result correct or wrong (the student engaged),
- participation with type active / initiative,
- evaluation, recitation.

NOT participatory:
- question with answer_result no_answer,
- participation with type inactive / refused,
- behaviour rows,
- reversed (undone) interactions.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    InteractionType,
    interaction_is_participatory,
)


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


async def _mk_teacher_user(tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x",
    })
    return uid


async def _mk_student(tenant_id: str, class_id: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": name, "is_active": True,
    })
    return sid


async def _mk_session(tenant_id: str, class_id: str, subject_id: str,
                      teacher_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id, "school_id": tenant_id, "tenant_id": tenant_id,
        "class_id": class_id, "subject_id": subject_id, "date": now[:10],
        "status": "in_progress", "start_time": now, "attendance_approved": True,
        "created_at": now, "teacher_id": teacher_id,
    })
    return session_id


async def _mk_present(session_id: str, student_id: str, status: str = "present"):
    await gd_insert(db.session, "session_attendance", {
        "id": str(uuid.uuid4()), "session_id": session_id,
        "student_id": student_id, "status": status,
    })


def _ts(minute: int) -> str:
    return datetime(2026, 6, 15, 10, minute, 0, tzinfo=timezone.utc).isoformat()


async def _interaction(session_id: str, student_id: str, recorded_by: str,
                       minute: int, **fields) -> str:
    iid = str(uuid.uuid4())
    ts = _ts(minute)
    doc = {
        "id": iid, "session_id": session_id, "student_id": student_id,
        "recorded_by": recorded_by, "recorded_at": ts, "timestamp": ts,
    }
    doc.update(fields)
    await gd_insert(db.session, "session_interactions", doc)
    return iid


async def _answer(session_id, student_id, recorded_by, minute, result):
    return await _interaction(
        session_id, student_id, recorded_by, minute,
        type="question", interaction_type=InteractionType.QUESTION.value,
        answer_result=result, points=5 if result == "correct" else 0,
    )


async def _participation(session_id, student_id, recorded_by, minute, ptype):
    return await _interaction(
        session_id, student_id, recorded_by, minute,
        type="participation",
        interaction_type=InteractionType.PARTICIPATION.value,
        participation_type=ptype,
    )


async def _seed(tenant_id: str, n_students: int = 2):
    class_id = await _mk_class(tenant_id)
    subject_id = await _mk_subject(tenant_id)
    teacher_id = await _mk_teacher_user(tenant_id)
    session_id = await _mk_session(tenant_id, class_id, subject_id, teacher_id)
    students = []
    for i in range(n_students):
        sid = await _mk_student(tenant_id, class_id, f"طالب {i + 1}")
        await _mk_present(session_id, sid)
        students.append(sid)
    return session_id, teacher_id, students


# ---------- the canonical predicate itself ----------

def test_predicate_classification_matrix():
    assert interaction_is_participatory(
        {"interaction_type": "question", "answer_result": "correct"})
    assert interaction_is_participatory(
        {"interaction_type": "question", "answer_result": "wrong"})
    assert not interaction_is_participatory(
        {"interaction_type": "question", "answer_result": "no_answer"})
    assert interaction_is_participatory(
        {"interaction_type": "participation", "participation_type": "active"})
    assert interaction_is_participatory(
        {"interaction_type": "participation", "participation_type": "initiative"})
    assert not interaction_is_participatory(
        {"interaction_type": "participation", "participation_type": "inactive"})
    assert not interaction_is_participatory(
        {"interaction_type": "participation", "participation_type": "refused"})
    assert interaction_is_participatory({"interaction_type": "evaluation"})
    assert interaction_is_participatory({"interaction_type": "recitation"})
    assert not interaction_is_participatory({"interaction_type": "behaviour"})
    # ``type`` column fallback (rows read outside gd_* flattening)
    assert interaction_is_participatory(
        {"type": "question", "answer_result": "correct"})


def test_role_dashboards_predicate_is_the_same_function():
    # Single source of truth — analytics and the session summary must never
    # drift apart again.
    from routes.role_dashboards_mod import _interaction_is_participatory
    assert _interaction_is_participatory is interaction_is_participatory


# ---------- review preview (first post-lesson page) ----------

@pytest.mark.asyncio
async def test_review_preview_counts_answers_as_participation(tenant_a):
    """The bug scenario: teacher records only answers (صحيح/خطأ), no explicit
    participation rows. مشاركات must NOT be 0."""
    session_id, teacher_id, (s1, s2) = await _seed(tenant_a, 2)

    await _answer(session_id, s1, teacher_id, 0, "correct")
    await _answer(session_id, s1, teacher_id, 1, "correct")
    await _answer(session_id, s2, teacher_id, 2, "wrong")

    preview = await _engine().get_review_preview(session_id, teacher_id)

    assert preview.interactions["total_participations"] == 3
    assert preview.interactions["participating_students"] == 2
    assert preview.interactions["participation_rate"] == 100.0
    # Question counters stay independent and correct.
    assert preview.interactions["questions_asked"] == 3
    assert preview.interactions["correct_answers"] == 2
    assert preview.interactions["wrong_answers"] == 1
    # With real participation present, the "no participation" warning must go.
    assert "لا توجد مشاركات مسجلة" not in preview.warnings


@pytest.mark.asyncio
async def test_review_preview_negative_engagement_does_not_count(tenant_a):
    """no_answer questions and inactive/refused participation are NOT
    participation — the zero must stay a truthful zero."""
    session_id, teacher_id, (s1, s2) = await _seed(tenant_a, 2)

    await _answer(session_id, s1, teacher_id, 0, "no_answer")
    await _participation(session_id, s2, teacher_id, 1, "inactive")
    await _participation(session_id, s2, teacher_id, 2, "refused")

    preview = await _engine().get_review_preview(session_id, teacher_id)

    assert preview.interactions["total_participations"] == 0
    assert preview.interactions["participating_students"] == 0
    assert preview.interactions["participation_rate"] == 0
    assert "لا توجد مشاركات مسجلة" in preview.warnings


@pytest.mark.asyncio
async def test_review_preview_explicit_participation_still_counts(tenant_a):
    session_id, teacher_id, (s1, _) = await _seed(tenant_a, 2)

    await _participation(session_id, s1, teacher_id, 0, "active")
    await _participation(session_id, s1, teacher_id, 1, "initiative")

    preview = await _engine().get_review_preview(session_id, teacher_id)

    assert preview.interactions["total_participations"] == 2
    assert preview.interactions["participating_students"] == 1
    assert preview.interactions["participation_rate"] == 50.0


@pytest.mark.asyncio
async def test_review_preview_reversed_rows_are_excluded(tenant_a):
    session_id, teacher_id, (s1, _) = await _seed(tenant_a, 2)

    await _answer(session_id, s1, teacher_id, 0, "correct")
    await _interaction(
        session_id, s1, teacher_id, 1,
        type="question", interaction_type="question",
        answer_result="correct", reversed=True,
    )

    preview = await _engine().get_review_preview(session_id, teacher_id)

    assert preview.interactions["total_participations"] == 1
    assert preview.interactions["participating_students"] == 1


@pytest.mark.asyncio
async def test_review_preview_top_participants_score_not_double_counted(tenant_a):
    """A correct answer already scores 2 — it must not ALSO add 1 as a
    participation, or the displayed per-student participation count lies."""
    session_id, teacher_id, (s1, s2) = await _seed(tenant_a, 2)

    await _answer(session_id, s1, teacher_id, 0, "correct")
    await _participation(session_id, s2, teacher_id, 1, "active")

    preview = await _engine().get_review_preview(session_id, teacher_id)

    tp = {t["student_id"]: t for t in preview.top_participants}
    assert tp[s1]["correct_answers"] == 1
    assert tp[s1]["participations"] == 0  # the correct answer is the "correct" stat
    assert tp[s2]["correct_answers"] == 0
    assert tp[s2]["participations"] == 1
    # correct (2) outranks a lone participation (1)
    assert preview.top_participants[0]["student_id"] == s1


# ---------- end session (second post-lesson page + stored summary) ----------

@pytest.mark.asyncio
async def test_end_session_summary_reflects_answer_participation(tenant_a):
    session_id, teacher_id, (s1, s2) = await _seed(tenant_a, 2)

    await _answer(session_id, s1, teacher_id, 0, "correct")
    await _answer(session_id, s2, teacher_id, 1, "wrong")

    summary = await _engine().end_session(session_id=session_id, teacher_id=teacher_id)

    assert summary.participation_rate == 100.0

    stored = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    assert stored["summary"]["participation_rate"] == 100.0
    # Both students engaged — nobody should be flagged "لم يشارك في الحصة".
    assert stored["summary"]["needs_attention"] == []


@pytest.mark.asyncio
async def test_end_session_zero_engagement_stays_zero(tenant_a):
    session_id, teacher_id, (s1, _) = await _seed(tenant_a, 2)

    await _answer(session_id, s1, teacher_id, 0, "no_answer")

    summary = await _engine().end_session(session_id=session_id, teacher_id=teacher_id)

    assert summary.participation_rate == 0


@pytest.mark.asyncio
async def test_needs_attention_flags_non_participatory_students(tenant_a):
    """A present student whose only rows are no_answer / refused must be
    flagged "لم يشارك في الحصة" — those rows are interactions but NOT
    participation."""
    session_id, teacher_id, (s1, s2) = await _seed(tenant_a, 2)

    await _answer(session_id, s1, teacher_id, 0, "correct")
    await _answer(session_id, s2, teacher_id, 1, "no_answer")
    await _participation(session_id, s2, teacher_id, 2, "refused")

    preview = await _engine().get_review_preview(session_id, teacher_id)
    flagged = {n["student_id"] for n in preview.needs_attention
               if n["reason"] == "لم يشارك في الحصة"}
    assert flagged == {s2}

    summary = await _engine().end_session(session_id=session_id, teacher_id=teacher_id)
    flagged_end = {n["student_id"] for n in summary.needs_attention
                   if n["reason"] == "لم يشارك في الحصة"}
    assert flagged_end == {s2}


@pytest.mark.asyncio
async def test_repeat_end_returns_same_participation_numbers(tenant_a):
    """A second POST /end takes the completed-session cache path — it must
    report the same participation numbers as the first end (predicate +
    reversed-row exclusion in lockstep)."""
    session_id, teacher_id, (s1, s2) = await _seed(tenant_a, 2)

    await _answer(session_id, s1, teacher_id, 0, "correct")
    await _answer(session_id, s2, teacher_id, 1, "wrong")
    await _interaction(  # recitation counts as participation
        session_id, s1, teacher_id, 2,
        type="recitation", interaction_type="recitation",
    )
    await _interaction(  # reversed row must stay excluded on the repeat path
        session_id, s2, teacher_id, 3,
        type="question", interaction_type="question",
        answer_result="correct", reversed=True,
    )

    eng = _engine()
    first = await eng.end_session(session_id=session_id, teacher_id=teacher_id)
    second = await eng.end_session(session_id=session_id, teacher_id=teacher_id)

    assert first.participation_rate == 100.0
    assert second.participation_rate == first.participation_rate
    assert second.correct_answers == first.correct_answers == 1
    assert second.needs_attention == []
    # Repeat path must not double-count the correct answer as a participation.
    tp = {t["student_id"]: t for t in second.top_participants}
    assert tp[s1]["correct_answers"] == 1
    assert tp[s1]["participations"] == 1  # the recitation only


@pytest.mark.asyncio
async def test_live_metrics_match_summary_participation(tenant_a):
    """The in-lesson live counters must agree with the post-lesson summary:
    answered questions count as participation, negative engagement doesn't."""
    session_id, teacher_id, (s1, s2) = await _seed(tenant_a, 2)

    await _answer(session_id, s1, teacher_id, 0, "correct")
    await _answer(session_id, s2, teacher_id, 1, "no_answer")

    metrics = await _engine().get_live_metrics(session_id)

    assert metrics["interaction"]["total_participations"] == 1
    assert metrics["interaction"]["unique_participants"] == 1
    assert metrics["interaction"]["participation_rate"] == 50.0
    # "not yet engaged" stays ANY-interaction based (both students were reached).
    assert metrics["interaction"]["not_interacted"] == 0
