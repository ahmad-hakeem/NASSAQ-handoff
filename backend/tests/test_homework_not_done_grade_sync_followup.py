"""End-to-end regression: marking homework "لم يُنجز الواجب" (not_done) must
zero the homework grade everywhere — كشف المتابعة (follow-up hydration), the
school student_grades store, and the parent grades store — even when a stale
full-marks value is already present from the session-start auto-submission.

This reproduces the original defect, where:
  * session start auto-submitted homework as full marks and the frontend
    persisted that value back into followup_records, and
  * build_followup_hydration / commit_session_scores treated that stored value
    as a manual override, so flipping the student to not_done left the homework
    column at max instead of 0.

The homework toggle is now the single source of truth for the homework column
(done -> full marks, not_done -> 0). These tests assert that contract for BOTH
a normal school tenant and an independent-teacher (freelance) workspace.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_insert
from engines.session_engine import TeacherSessionEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_engine() -> TeacherSessionEngine:
    class _Shim:
        @property
        def session(self):
            return db.session
    return TeacherSessionEngine(_Shim())


async def _mk_school(school_id: str, school_type: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"مدرسة-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": school_type,
        "tenant_type": school_type,
    })


async def _mk_teacher(tenant_id: str) -> str:
    tid = str(uuid.uuid4())
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "email": f"t-{uid}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x", "teacher_id": tid,
    })
    await gd_insert(db.session, "teachers", {
        "id": tid, "user_id": uid, "school_id": tenant_id,
        "full_name": "معلم", "email": f"t-{uid}@t.test",
    })
    return tid


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


async def _mk_student(tenant_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": f"طالب-{sid[:6]}", "is_active": True,
    })
    return sid


async def _mk_session_settings(teacher_id: str, subject_id: str, class_id: str, tenant_id: str) -> None:
    await gd_insert(db.session, "session_settings", {
        "id": str(uuid.uuid4()),
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "class_id": class_id,
        "tenant_id": tenant_id,
        "homework_enabled": True,
        "homework_mode": "submitted",
        "participation_enabled": True,
        "recitation_enabled": False,
        "recitation_attempts": 1,
        "skills_enabled": False,
        "custom_skills": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


async def _setup(school_type: str):
    """Provision a tenant + started (homework=submitted) session and return the
    handles the regression assertions need."""
    tenant = str(uuid.uuid4())
    await _mk_school(tenant, school_type)
    teacher_id = await _mk_teacher(tenant)
    class_id = await _mk_class(tenant)
    subject_id = await _mk_subject(tenant)
    s1 = await _mk_student(tenant, class_id)
    s2 = await _mk_student(tenant, class_id)
    await _mk_session_settings(teacher_id, subject_id, class_id, tenant)

    engine = _session_engine()
    result = await engine.start_session(
        teacher_id=teacher_id,
        schedule_session_id=str(uuid.uuid4()),
        class_id=class_id,
        subject_id=subject_id,
    )
    session_id = result["session_record_id"]

    columns = await engine._resolve_coursework_columns(class_id)
    hw_col = columns[TeacherSessionEngine._CW_HOMEWORK]
    hw_col_id = hw_col["id"]
    hw_max = float(hw_col["max_grade"])
    assert hw_max > 0

    return {
        "engine": engine, "tenant": tenant, "teacher_id": teacher_id,
        "class_id": class_id, "subject_id": subject_id, "s1": s1, "s2": s2,
        "session_id": session_id, "hw_col_id": hw_col_id, "hw_max": hw_max,
    }


async def _seed_stale_followup_override(ctx: dict) -> None:
    """Mimic the FE persisting the auto-submitted full-marks value back into the
    follow-up record — the stale override that used to shadow the live 0."""
    await gd_insert(db.session, "followup_records", {
        "id": str(uuid.uuid4()),
        "class_id": ctx["class_id"],
        "subject_id": ctx["subject_id"],
        "tenant_id": ctx["tenant"],
        "data": {ctx["s1"]: {ctx["hw_col_id"]: ctx["hw_max"]}},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Follow-up hydration (كشف المتابعة) — derived 0 must beat the stale max
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_not_done_zeroes_homework_in_followup_hydration(school_type):
    ctx = await _setup(school_type)
    engine, s1, hw_col_id, hw_max = ctx["engine"], ctx["s1"], ctx["hw_col_id"], ctx["hw_max"]

    await engine.record_homework(
        session_id=ctx["session_id"], student_id=s1,
        status="not_done", teacher_id=ctx["teacher_id"],
    )

    # The stored follow-up value (stale full marks) is passed in as the manual
    # data map — exactly what the report carries after the auto-submit save.
    stale = {s1: {hw_col_id: hw_max}}
    hydrated = await engine.build_followup_hydration(ctx["session_id"], stale)

    assert hydrated[s1][hw_col_id] == 0, (
        "not_done homework must hydrate to 0 in كشف المتابعة, "
        "not the stale full-marks override"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_done_keeps_full_marks_in_followup_hydration(school_type):
    ctx = await _setup(school_type)
    engine, s1, hw_col_id, hw_max = ctx["engine"], ctx["s1"], ctx["hw_col_id"], ctx["hw_max"]

    # not_done then back to done — the toggle must round-trip to full marks.
    await engine.record_homework(
        session_id=ctx["session_id"], student_id=s1,
        status="not_done", teacher_id=ctx["teacher_id"],
    )
    await engine.record_homework(
        session_id=ctx["session_id"], student_id=s1,
        status="done", teacher_id=ctx["teacher_id"],
    )

    hydrated = await engine.build_followup_hydration(ctx["session_id"], {})
    assert hydrated[s1][hw_col_id] == hw_max


# ---------------------------------------------------------------------------
# Commit -> student_grades (school) + grades (parent) must persist 0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_not_done_commits_zero_to_school_and_parent_grades(school_type):
    ctx = await _setup(school_type)
    engine, s1, session_id = ctx["engine"], ctx["s1"], ctx["session_id"]

    # Stale full-marks override stored in followup_records (the shadowing bug).
    await _seed_stale_followup_override(ctx)

    await engine.record_homework(
        session_id=session_id, student_id=s1,
        status="not_done", teacher_id=ctx["teacher_id"],
    )

    await engine.commit_session_scores(session_id)

    sg = await gd_find_one(db.session, "student_grades", {"id": f"sess:{session_id}:{s1}:homework:sg"})
    pg = await gd_find_one(db.session, "grades", {"id": f"sess:{session_id}:{s1}:homework:pg"})
    assert sg is not None and sg["score"] == 0, "school grade must commit as 0"
    assert pg is not None and pg["score"] == 0, "parent grade must commit as 0"


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_done_commits_full_marks_to_school_and_parent_grades(school_type):
    ctx = await _setup(school_type)
    engine, s1, session_id, hw_max = ctx["engine"], ctx["s1"], ctx["session_id"], ctx["hw_max"]

    # Round-trip not_done -> done, then commit must persist full marks.
    await engine.record_homework(
        session_id=session_id, student_id=s1,
        status="not_done", teacher_id=ctx["teacher_id"],
    )
    await engine.record_homework(
        session_id=session_id, student_id=s1,
        status="done", teacher_id=ctx["teacher_id"],
    )

    await engine.commit_session_scores(session_id)

    sg = await gd_find_one(db.session, "student_grades", {"id": f"sess:{session_id}:{s1}:homework:sg"})
    pg = await gd_find_one(db.session, "grades", {"id": f"sess:{session_id}:{s1}:homework:pg"})
    assert sg is not None and sg["score"] == hw_max, "school grade must commit as full marks"
    assert pg is not None and pg["score"] == hw_max, "parent grade must commit as full marks"
