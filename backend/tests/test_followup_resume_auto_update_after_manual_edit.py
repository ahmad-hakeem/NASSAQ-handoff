"""Regression: after a teacher MANUALLY edits a student's المشاركة value in
كشف المتابعة, later side-panel interactions for that SAME student must resume
updating the cell (latest-action-wins), while a manual edit that is still the
most recent action keeps sticking.

The reported defect: ``build_followup_hydration`` treated ANY stored manual
value as authoritative forever, so once a student's participation was edited by
hand, new side-panel interactions kept raising the backend-derived value but
never surfaced in the sheet for that student.

Desired behaviour (user-chosen "latest action wins"):
  * A manual override is respected only while it is at least as new as the
    student's most recent contributing interaction.
  * Once a NEWER interaction lands, the live derived value resumes.
  * With no timestamp at all (legacy records, no fallback), the manual value is
    kept (conservative — preserves the existing manual-authoritative tests).

Covers BOTH a normal school tenant and an independent-teacher workspace, since
the follow-up sheet is a shared surface.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_insert, gd_find
from engines.session_engine import (
    TeacherSessionEngine,
    ParticipationType,
    InteractionType,
)

# Fixed, strictly-ordered timestamps: T1 < T2 < T3 < T4.
T1 = "2026-06-22T10:00:00+00:00"
T2 = "2026-06-22T11:00:00+00:00"
T3 = "2026-06-22T12:00:00+00:00"
T4 = "2026-06-22T13:00:00+00:00"


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


async def _add_participation(
    session_id: str,
    student_id: str,
    recorded_at: str,
    ptype: str = ParticipationType.ACTIVE.value,
) -> None:
    """Insert a scoring participation interaction at an explicit timestamp."""
    await gd_insert(db.session, "session_interactions", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "type": InteractionType.PARTICIPATION.value,
        "interaction_type": InteractionType.PARTICIPATION.value,
        "participation_type": ptype,
        "recorded_at": recorded_at,
        "timestamp": recorded_at,
    })


async def _setup(school_type: str):
    tenant = str(uuid.uuid4())
    await _mk_school(tenant, school_type)
    teacher = await _mk_teacher(tenant)
    class_id = await _mk_class(tenant)
    subject_id = await _mk_subject(tenant)
    student = await _mk_student(tenant, class_id)
    await _mk_session_settings(teacher["teacher_id"], subject_id, class_id, tenant)

    engine = _session_engine()
    result = await engine.start_session(
        teacher_id=teacher["teacher_id"], schedule_session_id=str(uuid.uuid4()),
        class_id=class_id, subject_id=subject_id,
    )
    session_id = result["session_record_id"]

    columns = await engine._resolve_coursework_columns(class_id)
    part_col = columns[TeacherSessionEngine._CW_PARTICIPATION]
    col = part_col["id"]
    part_max = int(float(part_col["max_grade"]))

    # Two scoring interactions: one early (T1), one late (T3).
    await _add_participation(session_id, student, T1)
    derived1 = (await engine.build_followup_hydration(session_id, {}))[student][col]
    await _add_participation(session_id, student, T3)
    derived2 = (await engine.build_followup_hydration(session_id, {}))[student][col]
    assert derived1 > 0 and derived2 > 0

    # A manual value distinct from BOTH derived values, within [0, max].
    candidates = [v for v in range(0, part_max + 1) if v not in (derived1, derived2)]
    manual_val = candidates[-1]

    return {
        "engine": engine, "session_id": session_id, "student": student,
        "col": col, "manual_val": manual_val,
        "derived1": derived1, "derived2": derived2,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_interaction_after_manual_edit_resumes_derived(school_type):
    """THE BUG: a manual edit (at T2) older than the latest interaction (T3)
    must give way to the live derived value."""
    ctx = await _setup(school_type)
    engine, sid, col = ctx["engine"], ctx["student"], ctx["col"]
    manual = {sid: {col: ctx["manual_val"]}}
    ts = {sid: {col: T2}}  # manual edited BEFORE the T3 interaction
    hydrated = await engine.build_followup_hydration(
        ctx["session_id"], manual, manual_ts=ts,
    )
    assert hydrated[sid][col] == ctx["derived2"], (
        "a newer side-panel interaction must resume the live derived value"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_manual_edit_newer_than_interactions_sticks(school_type):
    """A manual edit (at T4) that is the most recent action must be kept."""
    ctx = await _setup(school_type)
    engine, sid, col = ctx["engine"], ctx["student"], ctx["col"]
    manual = {sid: {col: ctx["manual_val"]}}
    ts = {sid: {col: T4}}  # manual edited AFTER the T3 interaction
    hydrated = await engine.build_followup_hydration(
        ctx["session_id"], manual, manual_ts=ts,
    )
    assert hydrated[sid][col] == ctx["manual_val"], (
        "a manual edit that is the latest action must persist"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_legacy_fallback_ts_older_resumes_derived(school_type):
    """Legacy records carry no per-cell timestamp; the record's updated_at is
    used as a fallback. An older fallback (T2) must let a newer interaction win."""
    ctx = await _setup(school_type)
    engine, sid, col = ctx["engine"], ctx["student"], ctx["col"]
    manual = {sid: {col: ctx["manual_val"]}}
    hydrated = await engine.build_followup_hydration(
        ctx["session_id"], manual, manual_ts=None, fallback_ts=T2,
    )
    assert hydrated[sid][col] == ctx["derived2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_no_timestamp_keeps_manual(school_type):
    """Conservative back-compat: with no per-cell ts and no fallback, the manual
    value is kept (this is what the existing 2-arg hydration tests rely on)."""
    ctx = await _setup(school_type)
    engine, sid, col = ctx["engine"], ctx["student"], ctx["col"]
    manual = {sid: {col: ctx["manual_val"]}}
    hydrated = await engine.build_followup_hydration(ctx["session_id"], manual)
    assert hydrated[sid][col] == ctx["manual_val"]


@pytest.mark.asyncio
async def test_stamp_manual_ts_keeps_unchanged_cells_and_stamps_changed():
    """The save path must keep a cell's timestamp when its value is unchanged and
    re-stamp only new/changed cells (so editing student B never resurrects a
    superseded pin on student A)."""
    eng = _session_engine()
    a, b, col = "stu-A", "stu-B", "col-1"
    existing_manual = {a: {col: 3}}
    existing_ts = {a: {col: T1}}
    # Re-save: A unchanged (3), B newly added (7).
    new_manual = {a: {col: 3}, b: {col: 7}}
    out = eng._stamp_manual_ts(new_manual, existing_manual, existing_ts, T4)
    assert out[a][col] == T1, "unchanged cell keeps its original edit timestamp"
    assert out[b][col] == T4, "new cell is stamped at save time"
    # Now change A's value -> it must be re-stamped.
    out2 = eng._stamp_manual_ts({a: {col: 5}}, existing_manual, existing_ts, T4)
    assert out2[a][col] == T4, "changed cell is re-stamped at save time"


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_none_derived_keeps_manual_on_read_and_commit(school_type):
    """Read/commit symmetry: when a NEWER interaction drives the bucket to a
    non-positive (derived None) value, the manual edit is kept on BOTH the
    displayed sheet (hydration) AND committed grades — they must never diverge.

    Without this, hydration keeps the manual value (it only overwrites when the
    derived value is not None) while commit would drop it (value=derived=None ->
    skipped), so the sheet and the gradebook would disagree.
    """
    tenant = str(uuid.uuid4())
    await _mk_school(tenant, school_type)
    teacher = await _mk_teacher(tenant)
    class_id = await _mk_class(tenant)
    subject_id = await _mk_subject(tenant)
    student = await _mk_student(tenant, class_id)
    await _mk_session_settings(teacher["teacher_id"], subject_id, class_id, tenant)

    engine = _session_engine()
    result = await engine.start_session(
        teacher_id=teacher["teacher_id"], schedule_session_id=str(uuid.uuid4()),
        class_id=class_id, subject_id=subject_id,
    )
    session_id = result["session_record_id"]

    columns = await engine._resolve_coursework_columns(class_id)
    part_col = columns[TeacherSessionEngine._CW_PARTICIPATION]
    col = part_col["id"]
    part_max = int(float(part_col["max_grade"]))
    manual_val = max(1, part_max - 1)

    # A single REFUSED interaction (T3) -> non-positive points -> derived None,
    # and it is NEWER than the manual edit (T2), so the override is superseded.
    await _add_participation(session_id, student, T3, ParticipationType.REFUSED.value)
    live = await engine.build_followup_hydration(session_id, {})
    assert live.get(student, {}).get(col) is None, (
        "precondition: a lone refusal yields no positive derived value"
    )

    manual = {student: {col: manual_val}}
    ts = {student: {col: T2}}

    # READ: manual is kept (there is no derived value to resume to).
    hydrated = await engine.build_followup_hydration(session_id, manual, manual_ts=ts)
    assert hydrated[student][col] == manual_val, (
        "hydration must keep the manual value when the newer interaction zeroes "
        "the bucket (no derived value to show)"
    )

    # COMMIT must mirror READ: persist the manual override + its per-cell ts, then
    # commit, and assert the manual value is written (NOT skipped).
    await gd_insert(db.session, "followup_records", {
        "id": str(uuid.uuid4()),
        "class_id": class_id, "subject_id": subject_id, "session_id": session_id,
        "school_id": tenant,
        # Mirror the exact stored shape from save_followup_record: the document's
        # ``data`` column holds the record blob (class_id/subject_id siblings),
        # with the student map nested under ``data`` and the per-cell ``manual_ts``
        # / record ``updated_at`` alongside it.
        "data": {
            "class_id": class_id, "subject_id": subject_id, "session_id": session_id,
            "data": manual, "manual_ts": ts, "updated_at": T2,
        },
    })
    await engine.commit_session_scores(session_id)
    grades = await gd_find(
        db.session, "student_grades", {"student_id": student, "column_id": col},
    )
    assert grades, (
        "commit must write the manual participation grade (read/commit symmetry); "
        "it must not be dropped just because the derived value is None"
    )
    assert float(grades[0]["score"]) == float(manual_val), (
        "committed grade must equal the kept manual value shown on the sheet"
    )
