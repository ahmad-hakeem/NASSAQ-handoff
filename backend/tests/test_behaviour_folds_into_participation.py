"""
Regression tests: live-session behaviour (سلوك) must fold into the
participation (المشاركة) coursework column.

Bug: recording a negative behaviour during class (the teacher-facing "سلبي"
popover — عدم التزام / إزعاج / مقاطعة) updated the live daily score and, on
commit, wrote a behaviour_records row, but it never touched any grade column.
compute_session_scores collected positive/negative behaviours into a separate
behaviour_events list that _coursework_value ignored, so the Follow-up Report
(كشف المتابعة) never showed the deduction. This affected both regular teacher
and independent-teacher accounts (same route + engine).

Fix (product decision): behaviour points fold into the participation bucket —
negative lowers it, positive raises it — capped at the column max and never
reported below 0. behaviour_events stays populated so commit still materializes
the individual behaviour_records rows.

Invariants covered:
- A negative behaviour deducts from the participation aggregate.
- A positive behaviour adds to the participation aggregate.
- A negative behaviour reduces the participation column value surfaced by the
  Follow-up hydration (and via the GET route end-to-end).
- A behaviour-only negative produces no phantom coursework grade (<= 0 → blank).
- Commit still writes the behaviour_records row (behaviour_events preserved).
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


async def _participation_col_id(class_id: str) -> str:
    col = await gd_find_one(db.session, "grade_columns",
                            {"class_id": class_id, "name": "المشاركة"})
    assert col, "participation grade column should have been auto-created"
    return col["id"]


@pytest.mark.asyncio
async def test_negative_behaviour_deducts_from_participation(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    # A correct answer (+5) then a negative behaviour disruption (-2) => 3.
    await _interaction(session_id, sid, teacher_id,
                       interaction_type=InteractionType.QUESTION.value,
                       answer_result=AnswerResult.CORRECT.value)
    eng = _engine()
    res = await eng.record_behaviour(
        session_id=session_id, student_id=sid,
        category=BehaviourCategory.NEGATIVE, behaviour_type="disruption",
        details=None, teacher_id=teacher_id,
    )
    assert res["score_change"] == -2

    computed = await eng.compute_session_scores(session_id)
    assert computed["students"][sid]["participation_points"] == 3


@pytest.mark.asyncio
async def test_positive_behaviour_adds_to_participation(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    eng = _engine()
    await eng.record_behaviour(
        session_id=session_id, student_id=sid,
        category=BehaviourCategory.POSITIVE, behaviour_type="respect",
        details=None, teacher_id=teacher_id,
    )
    computed = await eng.compute_session_scores(session_id)
    assert computed["students"][sid]["participation_points"] == 2


@pytest.mark.asyncio
async def test_negative_behaviour_reflects_in_followup_hydration(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    await _interaction(session_id, sid, teacher_id,
                       interaction_type=InteractionType.QUESTION.value,
                       answer_result=AnswerResult.CORRECT.value)
    eng = _engine()
    await eng.record_behaviour(
        session_id=session_id, student_id=sid,
        category=BehaviourCategory.NEGATIVE, behaviour_type="interruption",
        details=None, teacher_id=teacher_id,
    )

    hydrated = await eng.build_followup_hydration(session_id, {})
    part_col = await _participation_col_id(class_id)
    # correct answer (+5) - interruption (-1) = 4, within the column max (5).
    assert hydrated[sid][part_col] == 4


@pytest.mark.asyncio
async def test_behaviour_only_negative_no_phantom_grade(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    eng = _engine()
    await eng.record_behaviour(
        session_id=session_id, student_id=sid,
        category=BehaviourCategory.NEGATIVE, behaviour_type="disruption",
        details=None, teacher_id=teacher_id,
    )
    await eng.commit_session_scores(session_id)
    # participation_points <= 0 → no coursework grade row (never below 0).
    grades = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": sid})
    assert grades == []
    # But the behaviour event is still materialized as a behaviour_records row.
    beh = await gd_find(db.session, "behaviour_records",
                        {"session_id": session_id, "student_id": sid})
    assert beh and beh[0]["category"] == BehaviourCategory.NEGATIVE.value


@pytest.mark.asyncio
async def test_behaviour_route_reflects_in_followup_record(client, tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id, headers = await _mk_teacher_auth(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    # +5 correct answer, then record a negative behaviour through the real route.
    await _interaction(session_id, sid, teacher_id,
                       interaction_type=InteractionType.QUESTION.value,
                       answer_result=AnswerResult.CORRECT.value)
    rec = await client.post(
        f"/session/{session_id}/behaviour",
        json={"student_id": sid, "category": "negative", "behaviour_type": "disruption"},
        headers=headers,
    )
    assert rec.status_code == 200, rec.text
    assert rec.json()["score_change"] == -2

    resp = await client.get(f"/session/{session_id}/followup-record", headers=headers)
    assert resp.status_code == 200, resp.text
    part_col = await _participation_col_id(class_id)
    # 5 (correct) - 2 (disruption) = 3 in the participation column.
    assert resp.json()["data"][sid][part_col] == 3
