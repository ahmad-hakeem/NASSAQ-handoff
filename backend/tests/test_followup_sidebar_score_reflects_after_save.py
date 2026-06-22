"""Regression: a live participation score recorded from the session sidebar must
keep flowing into كشف المتابعة *after* the sheet has been opened once and the
lesson has been saved.

Realistic cycle this exercises (the exact app flow):
  1. Teacher records a sidebar participation point  -> session-derived value D1.
  2. Teacher OPENS كشف المتابعة (GET /followup-record) -> the row hydrates with
     the derived D1 and the frontend holds that whole blob in ``followupData``.
  3. Teacher saves the lesson / changes settings -> the frontend flushes the
     ENTIRE ``followupData`` blob back (POST /followup-record). Before the fix
     this persisted the *derived* D1 into ``followup_records.data`` as if it were
     a manual edit; ``strip_derived_followup_echoes`` now drops that echo.
  4. Teacher records ANOTHER sidebar participation point -> derived value D2 > D1.
  5. Teacher REOPENS the sheet (GET /followup-record).

Expected: the sheet shows the live derived value D2 (the new sidebar point is
reflected). The pre-fix bug: the keep-manual guard in ``build_followup_hydration``
treated the persisted-derived D1 as an immutable manual override, so the sheet
froze at D1 and the second sidebar point never appeared.

This is NOT about a genuine manual edit (that must still win — see
``test_followup_nonzero_participation_editable``). Here the teacher never typed a
value; only the sidebar drove the score, yet the sheet stopped tracking it.

Runs against both a normal school tenant and an independent-teacher workspace,
since the follow-up sheet is a shared surface.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert
from engines.session_engine import TeacherSessionEngine, ParticipationType


def _session_engine() -> TeacherSessionEngine:
    class _Shim:
        @property
        def session(self):
            return db.session
    return TeacherSessionEngine(_Shim())


def _auth(user_id: str, tenant_id: str) -> dict:
    token = create_access_token({"sub": user_id, "role": "teacher", "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


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
    student_id = await _mk_student(tenant, class_id)
    await _mk_session_settings(teacher_id, subject_id, class_id, tenant)

    engine = _session_engine()
    result = await engine.start_session(
        teacher_id=teacher_id, schedule_session_id=str(uuid.uuid4()),
        class_id=class_id, subject_id=subject_id,
    )
    session_id = result["session_record_id"]

    columns = await engine._resolve_coursework_columns(class_id)
    part_col_id = columns[TeacherSessionEngine._CW_PARTICIPATION]["id"]

    return {
        "engine": engine, "tenant": tenant, "session_id": session_id,
        "student_id": student_id, "part_col_id": part_col_id,
        "user_id": user_id,
    }


async def _record_active(engine, session_id, student_id, user_id):
    await engine.record_participation(
        session_id=session_id, student_id=student_id,
        participation_type=ParticipationType.ACTIVE, teacher_id=user_id,
    )


async def _live_derived(engine, session_id, student_id, col):
    """Ground-truth live derived value, straight from the interactions."""
    hydrated = await engine.build_followup_hydration(session_id, {})
    return hydrated.get(student_id, {}).get(col)


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_sidebar_score_reflects_after_sheet_opened_and_saved(client, school_type):
    ctx = await _setup(school_type)
    engine = ctx["engine"]
    sid = ctx["session_id"]
    student = ctx["student_id"]
    col = ctx["part_col_id"]
    headers = _auth(ctx["user_id"], ctx["tenant"])

    # 1. First sidebar participation point -> derived D1.
    await _record_active(engine, sid, student, ctx["user_id"])
    d1 = await _live_derived(engine, sid, student, col)
    assert d1 and d1 > 0, "first sidebar point should produce a derived value"

    # 2. Teacher opens the sheet (hydrates with the derived value).
    r_open = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert r_open.status_code == 200, r_open.text
    opened = r_open.json()["data"]
    assert opened.get(student, {}).get(col) == d1

    # 3. Teacher saves the lesson -> frontend flushes the WHOLE hydrated blob.
    r_save = await client.post(
        f"/session/{sid}/followup-record", headers=headers,
        json={"data": opened, "absences": r_open.json().get("absences", {})},
    )
    assert r_save.status_code == 200, r_save.text

    # 4. Another sidebar participation point -> derived D2 > D1.
    await _record_active(engine, sid, student, ctx["user_id"])
    d2 = await _live_derived(engine, sid, student, col)
    assert d2 and d2 > d1, "second sidebar point must raise the live derived value"

    # 5. Teacher reopens the sheet. It MUST reflect the new live derived value.
    r_reopen = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert r_reopen.status_code == 200, r_reopen.text
    shown = r_reopen.json()["data"].get(student, {}).get(col)

    assert shown == d2, (
        f"follow-up sheet froze at the persisted-derived value {shown!r}; "
        f"the live sidebar-driven score is now {d2!r}. The second participation "
        f"point recorded from the sidebar never reached the sheet."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_genuine_manual_edit_still_wins_after_save(client, school_type):
    """Guard the fix's other half: a value the teacher actually TYPED (one that
    deviates from the derived value) must still be stored and survive a reopen —
    the echo-drop must only discard derived echoes, never real manual edits."""
    ctx = await _setup(school_type)
    engine = ctx["engine"]
    sid = ctx["session_id"]
    student = ctx["student_id"]
    col = ctx["part_col_id"]
    headers = _auth(ctx["user_id"], ctx["tenant"])

    await _record_active(engine, sid, student, ctx["user_id"])
    d1 = await _live_derived(engine, sid, student, col)
    assert d1 and d1 > 0

    # Teacher types a value that deviates from the derived one.
    typed = d1 + 3
    r_save = await client.post(
        f"/session/{sid}/followup-record", headers=headers,
        json={"data": {student: {col: typed}}, "absences": {}},
    )
    assert r_save.status_code == 200, r_save.text

    r_reopen = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert r_reopen.status_code == 200, r_reopen.text
    shown = r_reopen.json()["data"].get(student, {}).get(col)
    assert shown == typed, (
        f"a genuine manual edit ({typed}) must survive the save/reopen cycle, "
        f"got {shown!r}"
    )
