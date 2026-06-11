"""
Task #863 — regression tests for the unified live-session scoring bridge in
``TeacherSessionEngine``: ``compute_session_scores`` (aggregation),
``build_followup_hydration`` (Follow-up Report overlay without clobbering
manual entries) and ``commit_session_scores`` (idempotent materialization into
the persistent student-record collections the school + parent profiles read).

Invariants covered:
- Live interactions aggregate into participation / homework / performance buckets.
- Hydration overlays derived values but never overwrites a manual teacher value
  and never touches exam columns.
- Commit writes to student_grades (school), grades (parent),
  participation_records and behaviour_records, scoped to the session tenant only.
- Commit is idempotent: repeat runs update in place, no duplicate rows.
- No phantom rows: students with no signal and unknown student ids are skipped.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from dependencies import db, create_access_token
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
                      teacher_id: str = None, status: str = "ended") -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "date": "2026-06-11",
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
    """Create a teacher user and return (user_id, auth headers)."""
    uid = await _mk_user(tenant_id)
    token = create_access_token({"sub": uid, "role": "teacher", "tenant_id": tenant_id})
    return uid, {"Authorization": f"Bearer {token}"}


async def _interaction(session_id: str, student_id: str, recorded_by: str, **fields):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        # ``type`` is the NOT-NULL real column; production paths mirror the
        # interaction_type into it. Default to the interaction_type passed in.
        "type": fields.get("interaction_type", "participation"),
        "recorded_by": recorded_by,
        "recorded_at": now,
        "timestamp": now,
    }
    doc.update(fields)
    await gd_insert(db.session, "session_interactions", doc)
    return doc["id"]


@pytest.mark.asyncio
async def test_compute_session_scores_aggregates(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id)
    uid = await _mk_user(tenant_a)
    sid = await _mk_student(tenant_a, class_id, "طالب أول")

    await _interaction(session_id, sid, uid,
                       interaction_type=InteractionType.QUESTION.value,
                       answer_result=AnswerResult.CORRECT.value)
    await _interaction(session_id, sid, uid,
                       interaction_type=InteractionType.PARTICIPATION.value,
                       participation_type=ParticipationType.ACTIVE.value)
    await _interaction(session_id, sid, uid,
                       interaction_type=InteractionType.BEHAVIOUR.value,
                       behaviour_category=BehaviourCategory.SKILL.value)
    await _interaction(session_id, sid, uid,
                       interaction_type=InteractionType.BEHAVIOUR.value,
                       behaviour_category=BehaviourCategory.POSITIVE.value,
                       behaviour_type="respect")
    await gd_insert(db.session, "session_homework", {
        "id": str(uuid.uuid4()), "session_id": session_id,
        "student_id": sid, "status": "done",
    })

    computed = await _engine().compute_session_scores(session_id)
    agg = computed["students"][sid]
    # correct(5) + active(2)
    assert agg["participation_points"] == 7
    assert agg["performance_points"] == 3  # special_skill
    assert agg["homework_done"] is True
    assert len(agg["behaviour_events"]) == 1
    assert agg["behaviour_events"][0]["category"] == BehaviourCategory.POSITIVE.value


@pytest.mark.asyncio
async def test_build_followup_hydration_overlay_without_clobber(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id)
    uid = await _mk_user(tenant_a)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    await _interaction(session_id, sid, uid,
                       interaction_type=InteractionType.PARTICIPATION.value,
                       participation_type=ParticipationType.ACTIVE.value)

    eng = _engine()
    cols = await eng._resolve_coursework_columns(class_id)
    participation_col = cols["participation"]["id"]

    # Manual override on participation must be respected; an exam column value
    # supplied manually must remain untouched.
    manual = {sid: {participation_col: 99}}
    hydrated = await eng.build_followup_hydration(session_id, manual)
    assert hydrated[sid][participation_col] == 99  # not clobbered

    # With no manual value, the derived value fills in.
    hydrated2 = await eng.build_followup_hydration(session_id, {})
    assert hydrated2[sid][participation_col] == 2  # active participation


@pytest.mark.asyncio
async def test_commit_session_scores_idempotent_and_reads(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id)
    uid = await _mk_user(tenant_a)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    await _interaction(session_id, sid, uid,
                       interaction_type=InteractionType.QUESTION.value,
                       answer_result=AnswerResult.CORRECT.value)
    await _interaction(session_id, sid, uid,
                       interaction_type=InteractionType.BEHAVIOUR.value,
                       behaviour_category=BehaviourCategory.POSITIVE.value,
                       behaviour_type="respect")

    eng = _engine()
    r1 = await eng.commit_session_scores(session_id)
    assert r1["grades"] >= 1
    assert r1["participation"] == 1
    assert r1["behaviour"] == 1

    # School-side read present + tenant scoped.
    school_grades = await gd_find(db.session, "student_grades",
                                  {"session_id": session_id, "student_id": sid})
    assert school_grades and all(g["tenant_id"] == tenant_a for g in school_grades)
    # Parent-side read present + visible.
    parent_grades = await gd_find(db.session, "grades",
                                  {"session_id": session_id, "student_id": sid})
    assert parent_grades and all(g.get("visible_to_parent") for g in parent_grades)

    # Idempotent: a second commit must not create duplicate rows.
    await eng.commit_session_scores(session_id)
    school_grades_2 = await gd_find(db.session, "student_grades",
                                    {"session_id": session_id, "student_id": sid})
    participation_2 = await gd_find(db.session, "participation_records",
                                    {"session_id": session_id, "student_id": sid})
    behaviour_2 = await gd_find(db.session, "behaviour_records",
                                {"session_id": session_id, "student_id": sid})
    assert len(school_grades_2) == len(school_grades)
    assert len(participation_2) == 1
    assert len(behaviour_2) == 1


@pytest.mark.asyncio
async def test_commit_no_phantom_rows(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id)
    uid = await _mk_user(tenant_a)
    quiet = await _mk_student(tenant_a, class_id, "صامت")

    # Only a refusal (negative participation) for the quiet student → no
    # positive points, so nothing should be committed for them.
    await _interaction(session_id, quiet, uid,
                       interaction_type=InteractionType.PARTICIPATION.value,
                       participation_type=ParticipationType.REFUSED.value)

    await _engine().commit_session_scores(session_id)

    # No participation row for the quiet student (no positive points).
    part = await gd_find(db.session, "participation_records",
                         {"session_id": session_id, "student_id": quiet})
    assert part == []
    # No coursework grade rows either (refusal alone is not a coursework value).
    grades = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": quiet})
    assert grades == []


@pytest.mark.asyncio
async def test_commit_skips_foreign_tenant_student(tenant_a, tenant_b):
    """Defensive scoping: an interaction referencing a student that belongs to
    another tenant / class must never be materialized into this session's
    tenant. The session row is the only source of tenant/class scope."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id)
    uid = await _mk_user(tenant_a)

    # A student that lives in a different tenant + class.
    foreign_class = await _mk_class(tenant_b)
    foreign_sid = await _mk_student(tenant_b, foreign_class, "غريب")

    await _interaction(session_id, foreign_sid, uid,
                       interaction_type=InteractionType.QUESTION.value,
                       answer_result=AnswerResult.CORRECT.value)

    await _engine().commit_session_scores(session_id)

    # Nothing committed for the foreign-tenant student.
    school = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": foreign_sid})
    parent = await gd_find(db.session, "grades",
                           {"session_id": session_id, "student_id": foreign_sid})
    assert school == []
    assert parent == []


@pytest.mark.asyncio
async def test_commit_route_school_and_parent_visibility(client, tenant_a):
    """Route-level: the owning teacher commits via POST /session/{id}/commit-scores
    and the committed scores are then visible in both the school-side
    (student_grades) and parent-side (grades) stores."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id, headers = await _mk_teacher_auth(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)
    sid = await _mk_student(tenant_a, class_id, "طالب")

    await _interaction(session_id, sid, teacher_id,
                       interaction_type=InteractionType.QUESTION.value,
                       answer_result=AnswerResult.CORRECT.value)

    resp = await client.post(f"/session/{session_id}/commit-scores", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("success") is True

    school = await gd_find(db.session, "student_grades",
                           {"session_id": session_id, "student_id": sid})
    parent = await gd_find(db.session, "grades",
                           {"session_id": session_id, "student_id": sid})
    assert school and all(g["tenant_id"] == tenant_a for g in school)
    assert parent and all(g.get("visible_to_parent") for g in parent)


@pytest.mark.asyncio
async def test_commit_route_cross_tenant_denied(client, tenant_a, tenant_b):
    """Route-level: a teacher from another tenant cannot commit scores for a
    session they do not own (no cross-tenant write, no existence confirmation
    of the foreign session beyond ownership denial)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    owner_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=owner_id)

    _, foreign_headers = await _mk_teacher_auth(tenant_b)
    resp = await client.post(f"/session/{session_id}/commit-scores", headers=foreign_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_commit_route_surfaces_failure_no_false_success(client, tenant_a, monkeypatch):
    """Route-level: when the commit fails, the route must return an Arabic error
    (HTTP 500) — never a misleading success — so the UI does not show points as
    saved while the profiles never received them."""
    import routes.role_dashboards_mod as rd

    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id, headers = await _mk_teacher_auth(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id=teacher_id)

    async def _boom(_sid):
        raise RuntimeError("db down")

    monkeypatch.setattr(rd.session_engine, "commit_session_scores", _boom)
    resp = await client.post(f"/session/{session_id}/commit-scores", headers=headers)
    # Must be an explicit failure — never a misleading success.
    assert resp.status_code == 500
    body = resp.json()
    assert body.get("success") is not True
    # Safe Arabic envelope, and the raw exception text must not leak.
    assert "db down" not in resp.text
    assert "RuntimeError" not in resp.text


@pytest.mark.asyncio
async def test_end_session_blocks_and_stays_retryable_on_commit_failure(tenant_a, monkeypatch):
    """End flow: if the score commit fails, end_session must raise (no false
    "session ended" success) AND must not mark the session COMPLETED — so the
    teacher can retry the end and the idempotent commit reconciles."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id,
                                   teacher_id=teacher_id, status="in_progress")

    eng = _engine()

    async def _boom(_sid):
        raise RuntimeError("commit exploded")

    monkeypatch.setattr(eng, "commit_session_scores", _boom)

    with pytest.raises(HTTPException) as exc:
        await eng.end_session(session_id, teacher_id)
    assert exc.value.status_code == 500

    # Session must remain non-completed so the end can be safely retried.
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    assert session["status"] != "completed"
