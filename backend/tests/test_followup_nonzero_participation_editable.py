"""Regression: a teacher reopening كشف المتابعة must be able to raise OR lower a
student's *non-zero* participation score, not only fill in students sitting at 0.

The reported defect: after a lesson ends and is reopened, students who already
carry a non-zero (session-derived) participation value could not have that value
changed, while students at 0 still accepted new points. The asymmetry came from
``build_followup_hydration`` re-overlaying the live session-derived value on top
of the teacher's stored manual edit for every student that appears in
``compute_session_scores`` (i.e. every student WITH an interaction = non-zero),
while students with no interactions were skipped and kept their manual value.

The participation/performance buckets must honor the teacher's stored manual
override (raise or lower) and only fall back to the derived value when there is
no override. Homework is intentionally excluded — it stays toggle-authoritative
(covered by ``test_homework_not_done_grade_sync_followup``) — so this test pins
participation only.

Covers BOTH a normal school tenant and an independent-teacher workspace, since
the follow-up sheet is a shared surface.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_insert
from engines.session_engine import TeacherSessionEngine, ParticipationType


def _session_engine() -> TeacherSessionEngine:
    class _Shim:
        @property
        def session(self):
            return db.session
    return TeacherSessionEngine(_Shim())


async def _mk_school(school_id: str, school_type: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id, "name": f"مدرسة-{school_id[:6]}", "code": f"S{school_id[:8]}",
        "status": "active", "country": "SA", "language": "ar",
        "school_type": school_type, "tenant_type": school_type,
    })


async def _mk_teacher(tenant_id: str) -> dict:
    tid = str(uuid.uuid4()); uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "email": f"t-{uid}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x", "teacher_id": tid,
    })
    await gd_insert(db.session, "teachers", {
        "id": tid, "user_id": uid, "school_id": tenant_id,
        "full_name": "معلم", "email": f"t-{uid}@t.test",
    })
    return {"teacher_id": tid, "user_id": uid}


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


async def _mk_session_settings(teacher_id, subject_id, class_id, tenant_id) -> None:
    await gd_insert(db.session, "session_settings", {
        "id": str(uuid.uuid4()), "teacher_id": teacher_id, "subject_id": subject_id,
        "class_id": class_id, "tenant_id": tenant_id,
        "homework_enabled": True, "homework_mode": "submitted",
        "participation_enabled": True, "recitation_enabled": False,
        "recitation_attempts": 1, "skills_enabled": False, "custom_skills": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


async def _setup(school_type: str):
    tenant = str(uuid.uuid4())
    await _mk_school(tenant, school_type)
    teacher = await _mk_teacher(tenant)
    teacher_id = teacher["teacher_id"]
    user_id = teacher["user_id"]
    class_id = await _mk_class(tenant)
    subject_id = await _mk_subject(tenant)
    s_nonzero = await _mk_student(tenant, class_id)   # will receive participation
    s_zero = await _mk_student(tenant, class_id)       # stays at 0
    await _mk_session_settings(teacher_id, subject_id, class_id, tenant)

    engine = _session_engine()
    result = await engine.start_session(
        teacher_id=teacher_id, schedule_session_id=str(uuid.uuid4()),
        class_id=class_id, subject_id=subject_id,
    )
    session_id = result["session_record_id"]

    columns = await engine._resolve_coursework_columns(class_id)
    part_col = columns[TeacherSessionEngine._CW_PARTICIPATION]
    part_col_id = part_col["id"]
    part_max = float(part_col["max_grade"])
    assert part_max >= 4, "default participation column should allow values up to its max"

    # The non-zero student earns a live participation point -> appears in
    # compute_session_scores (the exact branch that used to re-overlay).
    await engine.record_participation(
        session_id=session_id, student_id=s_nonzero,
        participation_type=ParticipationType.ACTIVE, teacher_id=user_id,
    )

    return {
        "engine": engine, "tenant": tenant, "session_id": session_id,
        "s_nonzero": s_nonzero, "s_zero": s_zero,
        "part_col_id": part_col_id, "part_max": part_max,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_nonzero_participation_derived_baseline(school_type):
    """With no manual edit, the non-zero student shows the derived value and the
    zero student is absent (no phantom value)."""
    ctx = await _setup(school_type)
    hydrated = await ctx["engine"].build_followup_hydration(ctx["session_id"], {})
    derived = hydrated[ctx["s_nonzero"]][ctx["part_col_id"]]
    assert derived > 0, "non-zero student should carry the derived participation value"
    assert ctx["part_col_id"] not in hydrated.get(ctx["s_zero"], {})


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_nonzero_participation_can_be_raised(school_type):
    """The reported bug: raising an already non-zero participation score must
    stick, not snap back to the derived value."""
    ctx = await _setup(school_type)
    engine, sid, col = ctx["engine"], ctx["s_nonzero"], ctx["part_col_id"]
    derived = (await engine.build_followup_hydration(ctx["session_id"], {}))[sid][col]
    raised = min(derived + 2, ctx["part_max"])
    assert raised > derived

    manual = {sid: {col: raised}}
    hydrated = await engine.build_followup_hydration(ctx["session_id"], manual)
    assert hydrated[sid][col] == raised, (
        "raising a non-zero participation score must persist through hydration"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_nonzero_participation_can_be_lowered(school_type):
    """Lowering an already non-zero participation score (including back to 0)
    must also stick."""
    ctx = await _setup(school_type)
    engine, sid, col = ctx["engine"], ctx["s_nonzero"], ctx["part_col_id"]

    manual_low = {sid: {col: 1}}
    hydrated = await engine.build_followup_hydration(ctx["session_id"], manual_low)
    assert hydrated[sid][col] == 1, "lowering a non-zero participation score must persist"


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_zero_participation_accepts_points(school_type):
    """Control: the zero-score student still accepts new points (the path that
    always worked)."""
    ctx = await _setup(school_type)
    engine, sid, col = ctx["engine"], ctx["s_zero"], ctx["part_col_id"]
    manual = {sid: {col: 3}}
    hydrated = await engine.build_followup_hydration(ctx["session_id"], manual)
    assert hydrated[sid][col] == 3
