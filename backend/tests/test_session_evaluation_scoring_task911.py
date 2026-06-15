"""
Task #911 — regression tests for routing the live-session side-strip
evaluation items (التقييم) through the canonical scoring pipeline.

Custom teacher-defined evaluation items carry an explicit signed points value
and used to be recorded only as a cosmetic note (note_type='evaluation'), so
their points never reached compute_session_scores / the Follow-up Report / the
committed school + parent ledgers (everything showed zeros).

Invariants covered:
- record_evaluation creates a scoring interaction whose configured signed
  points fold into the participation bucket via compute_session_scores.
- Positive and negative evaluation items combine with standard answers in the
  same participation bucket (sign honored, no phantom from negatives alone).
- The evaluation route scores and is then materialized into both the school
  (student_grades) and parent (grades) stores by the canonical commit.
- Undo reverses an evaluation action: the interaction is excluded and the
  participation aggregate drops back.
- A foreign-tenant teacher cannot post an evaluation (no cross-tenant write).
- A foreign-class student is rejected (400) — class scope comes from the
  session row only.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert
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


async def _mk_subject(tenant_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "name": "الرياضيات", "name_ar": "الرياضيات",
    })
    return sid


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


async def _mk_session(tenant_id: str, class_id: str, subject_id: str,
                      teacher_id: str = None, status: str = "in_progress") -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "date": "2026-06-15",
        "status": status,
        "start_time": now,
        "attendance_approved": True,
        "created_at": now,
    }
    if teacher_id:
        doc["teacher_id"] = teacher_id
    await gd_insert(db.session, "class_sessions", doc)
    return session_id


async def _mk_teacher_auth(tenant_id: str):
    uid = await _mk_user(tenant_id)
    token = create_access_token({"sub": uid, "role": "teacher", "tenant_id": tenant_id})
    return uid, {"Authorization": f"Bearer {token}"}


async def _interaction(session_id: str, student_id: str, recorded_by: str, **fields):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "type": fields.get("interaction_type", "participation"),
        "recorded_by": recorded_by,
        "recorded_at": now,
        "timestamp": now,
    }
    doc.update(fields)
    await gd_insert(db.session, "session_interactions", doc)
    return doc["id"]


@pytest.mark.asyncio
async def test_record_evaluation_folds_into_participation(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    eng = _engine()
    res = await eng.record_evaluation(
        session_id=session_id, student_id=sid,
        item_name="إجابة ممتازة", points=4, teacher_id=teacher_id,
        item_id="custom_eval_1",
    )
    assert res["score_change"] == 4

    computed = await eng.compute_session_scores(session_id)
    assert computed["students"][sid]["participation_points"] == 4


@pytest.mark.asyncio
async def test_evaluation_sign_combines_with_answers(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    # A correct answer (+5) plus a negative evaluation item (-2) => 3.
    await _interaction(session_id, sid, teacher_id,
                       interaction_type=InteractionType.QUESTION.value,
                       answer_result=AnswerResult.CORRECT.value)
    eng = _engine()
    await eng.record_evaluation(
        session_id=session_id, student_id=sid,
        item_name="تشويش", points=-2, teacher_id=teacher_id,
    )
    computed = await eng.compute_session_scores(session_id)
    assert computed["students"][sid]["participation_points"] == 3


@pytest.mark.asyncio
async def test_negative_only_evaluation_no_phantom_grade(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    eng = _engine()
    await eng.record_evaluation(
        session_id=session_id, student_id=sid,
        item_name="عدم انتباه", points=-3, teacher_id=teacher_id,
    )
    await eng.commit_session_scores(session_id)
    # participation_points <= 0 → no coursework grade row.
    grades = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": sid})
    assert grades == []


@pytest.mark.asyncio
async def test_evaluation_route_scores_and_commits(client, tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id, headers = await _mk_teacher_auth(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    resp = await client.post(
        f"/session/{session_id}/evaluation",
        json={"student_id": sid, "name": "إجابة صحيحة", "points": 5, "item_id": "c1"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["score_change"] == 5

    commit = await client.post(f"/session/{session_id}/commit-scores", headers=headers)
    assert commit.status_code == 200, commit.text

    school = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": sid})
    parent = await gd_find(db.session, "grades",
                           {"session_id": session_id, "student_id": sid})
    assert school and all(g["tenant_id"] == tenant_a for g in school)
    assert parent and all(g.get("visible_to_parent") for g in parent)


@pytest.mark.asyncio
async def test_evaluation_undo_reverses_score(client, tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id, headers = await _mk_teacher_auth(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    resp = await client.post(
        f"/session/{session_id}/evaluation",
        json={"student_id": sid, "name": "إجابة صحيحة", "points": 5},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    eng = _engine()
    assert (await eng.compute_session_scores(session_id))["students"][sid]["participation_points"] == 5

    undo = await client.post(f"/session/{session_id}/undo", headers=headers)
    assert undo.status_code == 200, undo.text

    # After undo the evaluation interaction is reversed → no participation signal.
    computed = await eng.compute_session_scores(session_id)
    assert sid not in computed["students"] or computed["students"][sid]["participation_points"] == 0


@pytest.mark.asyncio
async def test_evaluation_route_cross_tenant_denied(client, tenant_a, tenant_b):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    owner_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=owner_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    _, foreign_headers = await _mk_teacher_auth(tenant_b)
    resp = await client.post(
        f"/session/{session_id}/evaluation",
        json={"student_id": sid, "name": "إجابة صحيحة", "points": 5},
        headers=foreign_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_evaluation_foreign_class_student_rejected(client, tenant_a):
    class_id = await _mk_class(tenant_a)
    other_class = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id, headers = await _mk_teacher_auth(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    # Student belongs to a different class and is not in this session's attendance.
    foreign_student = await _mk_student(tenant_a, other_class, "طالب آخر")

    resp = await client.post(
        f"/session/{session_id}/evaluation",
        json={"student_id": foreign_student, "name": "إجابة صحيحة", "points": 5},
        headers=headers,
    )
    assert resp.status_code == 400
