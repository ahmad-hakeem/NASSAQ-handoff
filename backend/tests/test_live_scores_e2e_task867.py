"""
Task #867 — End-to-end integration tests for the live-session scoring pipeline.

These tests exercise the full HTTP layer (not just the engine in isolation) and
confirm that scores committed by the engine reach every downstream read surface:

  • GET  /session/{id}/followup-record     — hydrated coursework, no clobber
  • POST /session/{id}/commit-scores       — idempotent, owner-verified
  • AssessmentEngine.get_student_grades    — school student-profile read
  • GET  /parent-portal/child/{id}/grades  — parent portal read, access-gated
  • Cross-tenant access is denied on every write and read surface
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    InteractionType,
    AnswerResult,
    ParticipationType,
)
from engines.assessment_engine import AssessmentEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token(user_id: str, role: str, tenant_id: str) -> str:
    return create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})


def _auth(user_id: str, role: str, tenant_id: str) -> dict:
    return {"Authorization": f"Bearer {_token(user_id, role, tenant_id)}"}


async def _mk_user(tenant_id: str, role: str = "teacher") -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "مستخدم",
        "is_active": True, "password_hash": "x",
    })
    return uid


async def _mk_parent(tenant_id: str) -> str:
    """Create a parent user + matching parents row (required by FK students_parent_id_fkey)."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": uid,
        "full_name": f"ولي-{uid[:6]}",
        "email": f"p-{uid}@t.test",
        "school_id": tenant_id,
        "is_active": True,
    })
    await gd_insert(db.session, "users", {
        "id": uid, "role": "parent", "tenant_id": tenant_id,
        "email": f"p-{uid}@t.test", "full_name": f"ولي-{uid[:6]}",
        "is_active": True, "password_hash": "x",
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


async def _mk_student(tenant_id: str, class_id: str, *, parent_id: str | None = None) -> str:
    sid = str(uuid.uuid4())
    doc = {
        "id": sid,
        "tenant_id": tenant_id,
        "school_id": tenant_id,
        "class_id": class_id,
        "full_name": f"طالب-{sid[:6]}",
        "is_active": True,
    }
    if parent_id:
        doc["parent_id"] = parent_id
    await gd_insert(db.session, "students", doc)
    return sid


async def _mk_session(tenant_id: str, class_id: str, subject_id: str,
                      teacher_id: str, *, status: str = "ended") -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "date": "2026-06-11",
        "status": status,
        "start_time": now,
        "attendance_approved": True,
        "created_at": now,
    })
    return session_id


async def _mk_interaction(session_id: str, student_id: str, recorded_by: str, **fields):
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


def _session_engine() -> SessionEngine:
    class _Shim:
        @property
        def session(self):
            return db.session
    return SessionEngine(_Shim())


def _assessment_engine() -> AssessmentEngine:
    class _Shim:
        @property
        def session(self):
            return db.session
    return AssessmentEngine(_Shim())


# ---------------------------------------------------------------------------
# 1. followup-record — hydrated, no clobber
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_followup_record_returns_hydrated_values(client, tenant_a):
    """GET /session/{id}/followup-record returns coursework values derived from
    live session interactions, without requiring a manual pre-existing record."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    student_id = await _mk_student(tenant_a, class_id)

    await _mk_interaction(session_id, student_id, teacher_id,
                          interaction_type=InteractionType.QUESTION.value,
                          answer_result=AnswerResult.CORRECT.value)

    headers = _auth(teacher_id, "teacher", tenant_a)
    resp = await client.get(f"/session/{session_id}/followup-record", headers=headers)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "data" in body
    assert "columns" in body
    # At least one column should have a hydrated numeric value (participation
    # or performance column populated by the CORRECT answer interaction).
    hydrated = body["data"].get(student_id, {})
    assert any(isinstance(v, (int, float)) and v > 0 for v in hydrated.values()), (
        f"Expected at least one positive hydrated value in {hydrated}"
    )


@pytest.mark.asyncio
async def test_followup_record_does_not_clobber_manual_entry(client, tenant_a):
    """GET /session/{id}/followup-record must not overwrite a manual teacher
    entry that was saved before the endpoint is called."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    student_id = await _mk_student(tenant_a, class_id)

    # Derive which column id the engine resolves for participation so we can
    # check the exact cell.
    eng = _session_engine()
    cols = await eng._resolve_coursework_columns(class_id)
    participation_col = cols["participation"]["id"]

    # A live interaction that *would* yield a derived value.
    await _mk_interaction(session_id, student_id, teacher_id,
                          interaction_type=InteractionType.PARTICIPATION.value,
                          participation_type=ParticipationType.ACTIVE.value)

    # Pre-save a followup_record with a manual value of 99 in that column.
    MANUAL_VALUE = 99
    await gd_insert(db.session, "followup_records", {
        "id": str(uuid.uuid4()),
        "class_id": class_id,
        "subject_id": subject_id,
        "session_id": session_id,
        "columns": [{"id": participation_col, "name": "المشاركة", "maxGrade": 10, "type": "grade"}],
        "data": {student_id: {participation_col: MANUAL_VALUE}},
        "absences": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    headers = _auth(teacher_id, "teacher", tenant_a)
    resp = await client.get(f"/session/{session_id}/followup-record", headers=headers)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    student_data = body["data"].get(student_id, {})
    # The manual value must be preserved (not replaced by the derived 2 pts).
    assert student_data.get(participation_col) == MANUAL_VALUE, (
        f"Manual value was clobbered: got {student_data.get(participation_col)}, expected {MANUAL_VALUE}"
    )


@pytest.mark.asyncio
async def test_followup_record_heals_nested_metadata_corruption(client, tenant_a):
    """A legacy follow-up record whose stored ``data`` blob was repeatedly
    re-wrapped (metadata + a nested ``data`` key) must still hydrate to the
    real per-student coursework values instead of reading back as all zeros.

    Reproduces the runtime hop that produced all-zero coursework columns in
    the Follow-up Report: hydration used to throw ValueError on the metadata
    keys and fall back to the corrupted blob.
    """
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _session_engine()
    cols = await eng._resolve_coursework_columns(class_id)
    participation_col = cols["participation"]["id"]

    await _mk_interaction(session_id, student_id, teacher_id,
                          interaction_type=InteractionType.PARTICIPATION.value,
                          participation_type=ParticipationType.ACTIVE.value)

    # The real student map, buried under two layers of metadata-wrapping
    # exactly as the self-perpetuating save loop produced in production.
    real_map = {student_id: {participation_col: 7}}
    inner = {
        "class_id": class_id, "subject_id": subject_id, "session_id": session_id,
        "columns": [], "absences": {}, "data": real_map,
    }
    corrupted = {
        "class_id": class_id, "subject_id": subject_id, "session_id": session_id,
        "columns": [], "absences": {}, "data": inner,
    }
    await gd_insert(db.session, "followup_records", {
        "id": str(uuid.uuid4()),
        "class_id": class_id,
        "subject_id": subject_id,
        "session_id": session_id,
        "columns": [{"id": participation_col, "name": "المشاركة", "maxGrade": 10, "type": "grade"}],
        "data": corrupted,
        "absences": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    headers = _auth(teacher_id, "teacher", tenant_a)
    resp = await client.get(f"/session/{session_id}/followup-record", headers=headers)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # The real student row surfaces, and no metadata key leaked in as a "student".
    assert student_id in body["data"], f"Real student missing from healed data: {list(body['data'])}"
    assert "class_id" not in body["data"] and "columns" not in body["data"]
    student_data = body["data"][student_id]
    # The preserved manual value (7) survives the unwrap, not zeroed out.
    assert student_data.get(participation_col) == 7, (
        f"Healed value lost: got {student_data.get(participation_col)} in {student_data}"
    )


# ---------------------------------------------------------------------------
# 2. commit-scores — idempotent, owner-only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_scores_route_idempotent_no_dupes(client, tenant_a):
    """POST /session/{id}/commit-scores twice must produce the same number of
    rows in both student_grades and grades — no duplicates on repeat calls."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    student_id = await _mk_student(tenant_a, class_id)

    await _mk_interaction(session_id, student_id, teacher_id,
                          interaction_type=InteractionType.QUESTION.value,
                          answer_result=AnswerResult.CORRECT.value)

    headers = _auth(teacher_id, "teacher", tenant_a)

    # First commit.
    r1 = await client.post(f"/session/{session_id}/commit-scores", headers=headers)
    assert r1.status_code == 200, r1.text
    assert r1.json().get("success") is True

    sg_after_1 = await gd_find(db.session, "student_grades",
                               {"session_id": session_id, "student_id": student_id})
    pg_after_1 = await gd_find(db.session, "grades",
                               {"session_id": session_id, "student_id": student_id})
    assert len(sg_after_1) >= 1
    assert len(pg_after_1) >= 1

    # Second commit — counts must not grow.
    r2 = await client.post(f"/session/{session_id}/commit-scores", headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("success") is True

    sg_after_2 = await gd_find(db.session, "student_grades",
                               {"session_id": session_id, "student_id": student_id})
    pg_after_2 = await gd_find(db.session, "grades",
                               {"session_id": session_id, "student_id": student_id})

    assert len(sg_after_2) == len(sg_after_1), (
        f"Duplicate student_grades rows on repeat commit: {len(sg_after_2)} != {len(sg_after_1)}"
    )
    assert len(pg_after_2) == len(pg_after_1), (
        f"Duplicate grades rows on repeat commit: {len(pg_after_2)} != {len(pg_after_1)}"
    )


# ---------------------------------------------------------------------------
# 3. School student-profile read — AssessmentEngine.get_student_grades
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assessment_engine_reads_committed_grades(tenant_a):
    """AssessmentEngine.get_student_grades returns the grade rows committed by
    the session engine, scoped by tenant_id."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    student_id = await _mk_student(tenant_a, class_id)

    await _mk_interaction(session_id, student_id, teacher_id,
                          interaction_type=InteractionType.QUESTION.value,
                          answer_result=AnswerResult.CORRECT.value)

    # Commit via the engine.
    eng = _session_engine()
    result = await eng.commit_session_scores(session_id)
    assert result["grades"] >= 1

    # Verify via AssessmentEngine — this is the path used by the school
    # student-profile page.
    ae = _assessment_engine()
    grades = await ae.get_student_grades(tenant_a, student_id)

    assert len(grades) >= 1, "AssessmentEngine returned no grades after commit"
    for g in grades:
        assert g["tenant_id"] == tenant_a, f"Grade scoped to wrong tenant: {g['tenant_id']}"
        assert g["student_id"] == student_id


@pytest.mark.asyncio
async def test_assessment_engine_no_cross_tenant_grades(tenant_a, tenant_b):
    """AssessmentEngine.get_student_grades must not return rows that belong to
    a different tenant when queried with the correct tenant scope."""
    teacher_a = await _mk_user(tenant_a)
    class_a = await _mk_class(tenant_a)
    subj_a = await _mk_subject(tenant_a)
    session_a = await _mk_session(tenant_a, class_a, subj_a, teacher_a)
    student_a = await _mk_student(tenant_a, class_a)

    await _mk_interaction(session_a, student_a, teacher_a,
                          interaction_type=InteractionType.QUESTION.value,
                          answer_result=AnswerResult.CORRECT.value)

    await _session_engine().commit_session_scores(session_a)

    # Query grades from tenant_b's perspective — must be empty.
    ae = _assessment_engine()
    grades_b = await ae.get_student_grades(tenant_b, student_a)
    assert grades_b == [], (
        f"Cross-tenant grade leak: tenant_b got {len(grades_b)} rows for a tenant_a student"
    )


# ---------------------------------------------------------------------------
# 4. Parent portal — child grades gated by _verify_parent_access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parent_portal_sees_committed_grades(client, tenant_a):
    """GET /parent-portal/child/{id}/grades returns committed grades for a
    parent who is linked to the student via students.parent_id."""
    # Create a parent user + matching parents row (FK requires both).
    parent_id = await _mk_parent(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)

    # Seed the student with parent_id pointing at the parent user — this is
    # what _verify_parent_access checks (students.parent_id == parent user.id).
    student_id = await _mk_student(tenant_a, class_id, parent_id=parent_id)

    await _mk_interaction(session_id, student_id, teacher_id,
                          interaction_type=InteractionType.QUESTION.value,
                          answer_result=AnswerResult.CORRECT.value)

    # Commit via engine so grades reach the parent-facing store.
    await _session_engine().commit_session_scores(session_id)

    parent_headers = _auth(parent_id, "parent", tenant_a)
    resp = await client.get(f"/parent-portal/child/{student_id}/grades",
                            headers=parent_headers)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "subjects" in body
    assert "total_grades" in body
    assert body["total_grades"] >= 1, (
        "Parent portal returned zero grades after commit"
    )
    # Verify the live-session grades appear in at least one subject bucket.
    found_live = any(
        any(g.get("assessment_type") == "coursework" for g in subj["grades"])
        for subj in body["subjects"]
    )
    assert found_live, (
        "No coursework grades from the live session found in parent portal response"
    )


@pytest.mark.asyncio
async def test_parent_portal_denies_unlinked_parent(client, tenant_a):
    """A parent who is NOT linked to a student must receive 403 from the child
    grades endpoint — _verify_parent_access must return None."""
    other_parent_id = await _mk_user(tenant_a, role="parent")
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)

    # Student linked to a *different* parent, not other_parent_id.
    real_parent_id = await _mk_parent(tenant_a)
    student_id = await _mk_student(tenant_a, class_id, parent_id=real_parent_id)

    await _mk_interaction(session_id, student_id, teacher_id,
                          interaction_type=InteractionType.QUESTION.value,
                          answer_result=AnswerResult.CORRECT.value)
    await _session_engine().commit_session_scores(session_id)

    unlinked_headers = _auth(other_parent_id, "parent", tenant_a)
    resp = await client.get(f"/parent-portal/child/{student_id}/grades",
                            headers=unlinked_headers)
    assert resp.status_code == 403, (
        f"Expected 403 for unlinked parent, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# 5. Cross-tenant access denied
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_followup_record_denied(client, tenant_a, tenant_b):
    """A teacher from tenant_b must receive 403 when trying to read the
    followup-record of a session owned by a tenant_a teacher."""
    teacher_a = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_a)

    foreign_teacher_id = await _mk_user(tenant_b)
    foreign_headers = _auth(foreign_teacher_id, "teacher", tenant_b)

    resp = await client.get(f"/session/{session_id}/followup-record",
                            headers=foreign_headers)
    # Canonical cross-tenant contract for /session/{id} routes: 404 (never
    # 403/200) so the API does not confirm the existence of foreign rows.
    assert resp.status_code == 404, (
        f"Expected 404 for cross-tenant followup-record read, got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_cross_tenant_commit_scores_denied(client, tenant_a, tenant_b):
    """A teacher from tenant_b must receive 403 when trying to commit scores
    for a session they do not own (no existence leak beyond the denial)."""
    teacher_a = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_a)

    foreign_teacher_id = await _mk_user(tenant_b)
    foreign_headers = _auth(foreign_teacher_id, "teacher", tenant_b)

    resp = await client.post(f"/session/{session_id}/commit-scores",
                             headers=foreign_headers)
    # Canonical cross-tenant contract for /session/{id} routes: 404 (never
    # 403/200) so the API does not confirm the existence of foreign rows.
    assert resp.status_code == 404, (
        f"Expected 404 for cross-tenant commit-scores, got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_cross_tenant_parent_portal_denied(client, tenant_a, tenant_b):
    """A parent from tenant_b must receive 403 when requesting grades for a
    student scoped to tenant_a — school_id mismatch in _verify_parent_access
    prevents the lookup from resolving."""
    teacher_id = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)

    # Student belongs to tenant_a; a parent_id that exists in tenant_a.
    real_parent_id = await _mk_parent(tenant_a)
    student_id = await _mk_student(tenant_a, class_id, parent_id=real_parent_id)

    await _mk_interaction(session_id, student_id, teacher_id,
                          interaction_type=InteractionType.QUESTION.value,
                          answer_result=AnswerResult.CORRECT.value)
    await _session_engine().commit_session_scores(session_id)

    # The parent token belongs to tenant_b — school_id will not match.
    foreign_parent_id = await _mk_parent(tenant_b)
    foreign_headers = _auth(foreign_parent_id, "parent", tenant_b)

    resp = await client.get(f"/parent-portal/child/{student_id}/grades",
                            headers=foreign_headers)
    assert resp.status_code == 403, (
        f"Expected 403 for cross-tenant parent portal read, got {resp.status_code}"
    )
