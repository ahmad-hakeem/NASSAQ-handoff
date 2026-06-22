"""Regression: a live participation score recorded from the session sidebar must
keep flowing into كشف المتابعة *after* the sheet has been opened once and the
lesson has been saved — and a value the teacher actually TYPED must win and
survive, even when it happens to equal the current derived value.

This locks in the "Option B" contract for the follow-up sheet:

  * The frontend persists ONLY the cells the teacher took manual ownership of.
    A session-derived value the teacher never edited is never POSTed, so it is
    never stored as an override and always re-hydrates to the live score.
  * GET exposes ``manual_keys`` (``"<student_id>:<column_id>"`` for each non-empty
    stored override) so the frontend can seed its manual-ownership set.
  * A stored manual cell wins over the live derived value on reopen — including a
    manual value EQUAL to the derived one (the old value-equality echo-strip
    would have wrongly dropped that and let the cell drift).
  * An empty cell means "revert to derived": the backend prunes it, and a full
    replace that omits a previously-stored cell drops that override.

The pre-fix bug: the keep-manual guard in ``build_followup_hydration`` treated a
persisted-derived value as an immutable manual override, so the sheet froze at the
first derived value and later sidebar points never appeared.

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


# ---------------------------------------------------------------------------
# Anti-freeze: a derived cell the teacher never edited is never persisted, so it
# always tracks the live sidebar score — even after the sheet is opened + saved.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_unsent_derived_cell_keeps_tracking_live_score(client, school_type):
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

    # 2. Teacher opens the sheet. It hydrates with D1, and because nothing was
    #    manually edited there are no manual overrides to advertise.
    r_open = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert r_open.status_code == 200, r_open.text
    assert r_open.json()["data"].get(student, {}).get(col) == d1
    assert r_open.json().get("manual_keys") == []

    # 3. Teacher saves the lesson WITHOUT having edited the participation cell.
    #    The frontend filters to manual cells only, so the derived value is never
    #    POSTed (here: an empty data map).
    r_save = await client.post(
        f"/session/{sid}/followup-record", headers=headers,
        json={"data": {}, "absences": {}},
    )
    assert r_save.status_code == 200, r_save.text

    # 4. Another sidebar participation point -> derived D2 > D1.
    await _record_active(engine, sid, student, ctx["user_id"])
    d2 = await _live_derived(engine, sid, student, col)
    assert d2 and d2 > d1, "second sidebar point must raise the live derived value"

    # 5. Reopen: the sheet MUST reflect the new live derived value (never frozen),
    #    and there is still no stored override.
    r_reopen = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert r_reopen.status_code == 200, r_reopen.text
    shown = r_reopen.json()["data"].get(student, {}).get(col)
    assert shown == d2, (
        f"follow-up sheet froze at {shown!r}; the live sidebar-driven score is "
        f"now {d2!r}. A derived cell the teacher never edited must never be "
        f"persisted as a manual override."
    )
    assert r_reopen.json().get("manual_keys") == []


# ---------------------------------------------------------------------------
# A genuine manual edit is stored, advertised via manual_keys, and wins on reopen.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_manual_edit_stored_advertised_and_wins(client, school_type):
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

    # GET advertises the manual cell so the frontend can keep sending it.
    r_reopen = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert r_reopen.status_code == 200, r_reopen.text
    assert f"{student}:{col}" in r_reopen.json().get("manual_keys", [])
    assert r_reopen.json()["data"].get(student, {}).get(col) == typed

    # Even after more sidebar scoring, the manual edit wins (it was explicitly set).
    await _record_active(engine, sid, student, ctx["user_id"])
    r_after = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert r_after.json()["data"].get(student, {}).get(col) == typed, (
        "a genuine manual edit must survive later sidebar scoring"
    )


# ---------------------------------------------------------------------------
# The edge the old echo-strip broke: a manual value EQUAL to the current derived
# value is a real override and must be pinned (it must NOT drift with later
# sidebar scoring).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_manual_value_equal_to_derived_is_pinned(client, school_type):
    ctx = await _setup(school_type)
    engine = ctx["engine"]
    sid = ctx["session_id"]
    student = ctx["student_id"]
    col = ctx["part_col_id"]
    headers = _auth(ctx["user_id"], ctx["tenant"])

    await _record_active(engine, sid, student, ctx["user_id"])
    d1 = await _live_derived(engine, sid, student, col)
    assert d1 and d1 > 0

    # Teacher deliberately types the SAME value the sidebar currently derives.
    r_save = await client.post(
        f"/session/{sid}/followup-record", headers=headers,
        json={"data": {student: {col: d1}}, "absences": {}},
    )
    assert r_save.status_code == 200, r_save.text
    # It is a genuine override and is advertised as such.
    r_check = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert f"{student}:{col}" in r_check.json().get("manual_keys", [])

    # More sidebar scoring would raise the derived value...
    await _record_active(engine, sid, student, ctx["user_id"])
    d2 = await _live_derived(engine, sid, student, col)
    assert d2 and d2 > d1

    # ...but the manual pin holds at d1 (the old value-equality strip would have
    # dropped it and let the cell drift to d2).
    r_reopen = await client.get(f"/session/{sid}/followup-record", headers=headers)
    shown = r_reopen.json()["data"].get(student, {}).get(col)
    assert shown == d1, (
        f"a manual value equal to the derived one must be pinned ({d1!r}); it "
        f"must not drift to the later derived value {d2!r}."
    )


# ---------------------------------------------------------------------------
# Clearing a cell removes the override and reverts to the live derived value.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_empty_cell_prunes_override_and_reverts_to_derived(client, school_type):
    ctx = await _setup(school_type)
    engine = ctx["engine"]
    sid = ctx["session_id"]
    student = ctx["student_id"]
    col = ctx["part_col_id"]
    headers = _auth(ctx["user_id"], ctx["tenant"])

    await _record_active(engine, sid, student, ctx["user_id"])
    d1 = await _live_derived(engine, sid, student, col)
    assert d1 and d1 > 0

    # Store a manual override, then clear it by sending an empty value.
    assert (await client.post(
        f"/session/{sid}/followup-record", headers=headers,
        json={"data": {student: {col: d1 + 5}}, "absences": {}},
    )).status_code == 200
    assert (await client.post(
        f"/session/{sid}/followup-record", headers=headers,
        json={"data": {student: {col: ""}}, "absences": {}},
    )).status_code == 200

    r_reopen = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert r_reopen.json().get("manual_keys") == [], (
        "an emptied cell must be pruned, leaving no stored override"
    )
    assert r_reopen.json()["data"].get(student, {}).get(col) == d1, (
        "after clearing the override the cell must revert to the live derived value"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_replace_omitting_cell_drops_its_override(client, school_type):
    """A full-replace save that no longer includes a previously-stored cell drops
    that override (the frontend stops sending a cell the teacher cleared)."""
    ctx = await _setup(school_type)
    engine = ctx["engine"]
    sid = ctx["session_id"]
    student = ctx["student_id"]
    col = ctx["part_col_id"]
    headers = _auth(ctx["user_id"], ctx["tenant"])

    await _record_active(engine, sid, student, ctx["user_id"])
    d1 = await _live_derived(engine, sid, student, col)
    assert d1 and d1 > 0

    assert (await client.post(
        f"/session/{sid}/followup-record", headers=headers,
        json={"data": {student: {col: d1 + 5}}, "absences": {}},
    )).status_code == 200
    # Replace with an empty manual set (the cleared cell is simply omitted).
    assert (await client.post(
        f"/session/{sid}/followup-record", headers=headers,
        json={"data": {}, "absences": {}},
    )).status_code == 200

    r_reopen = await client.get(f"/session/{sid}/followup-record", headers=headers)
    assert r_reopen.json().get("manual_keys") == []
    assert r_reopen.json()["data"].get(student, {}).get(col) == d1
