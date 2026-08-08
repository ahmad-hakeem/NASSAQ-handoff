"""Task — full audit of teacher-entered notes across the live-lesson flow.

Root cause of the reported bug: ``session_notes`` is a REAL table whose
content columns are ``note`` / ``type``, but ``add_note`` (used by the quick
note, per-student note, parent broadcast and non-scoring evaluation paths)
inserted phantom ``text`` / ``note_type`` / ``student_ids`` keys. The generic
writer silently drops non-column keys, so every in-session note was persisted
as an EMPTY row — the UI could only ever show a count ("الملاحظات (2)") with
blank content. Only the closing-note path had been fixed earlier.

These tests cover, for both a real school and an independent-teacher
workspace:
  * add_note persists real content + type + student linkage + FK-safe teacher;
  * a parent broadcast fans out to one row per student;
  * get_session_notes returns the canonical text/note_type shape and hides
    unrecoverable legacy empty rows;
  * delete_note works against the resolved rows;
  * get_session_report merges ALL note sources (session notes, closing note,
    recitation note, behaviour details, skill note) with student names;
  * the management end-of-session summary embeds the closing note text.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_count, gd_find, gd_find_one, gd_insert
from engines.session_engine import TeacherSessionEngine as SessionEngine
from engines.session_engine import BehaviourCategory


def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session
    return SessionEngine(_DBShim())


async def _mk_tenant(kind: str, owner_user_id: str = None) -> str:
    if kind == "independent_teacher":
        tid = f"itw_{owner_user_id}"
    else:
        tid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": tid, "name": f"مدرسة-{tid[-6:]}", "code": f"S{tid[-8:]}",
        "status": "active", "country": "SA", "language": "ar",
        "school_type": kind if kind == "independent_teacher" else "public",
        "tenant_type": kind if kind == "independent_teacher" else "school",
    })
    return tid


async def _mk_ctx(kind: str):
    """Seed tenant + teacher(user/teachers rows) + class + student + session."""
    user_id = str(uuid.uuid4())
    tenant_id = await _mk_tenant(kind, owner_user_id=user_id)
    teacher_row = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_row, "school_id": tenant_id, "full_name": "معلم الاختبار",
        "is_active": True,
    })
    role = "independent_teacher" if kind == "independent_teacher" else "teacher"
    await gd_insert(db.session, "users", {
        "id": user_id, "role": role, "tenant_id": tenant_id,
        "email": f"u-{user_id}@t.test", "full_name": "معلم الاختبار",
        "is_active": True, "password_hash": "x", "teacher_id": teacher_row,
    })
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    students = []
    for n in ("طالب أول", "طالب ثاني"):
        sid = str(uuid.uuid4())
        await gd_insert(db.session, "students", {
            "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
            "class_id": class_id, "full_name": n, "is_active": True,
        })
        students.append(sid)
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id, "school_id": tenant_id, "tenant_id": tenant_id,
        "class_id": class_id, "date": now[:10], "status": "in_progress",
        "start_time": now, "teacher_id": teacher_row, "attendance_approved": True,
        "created_at": now,
    })
    for sid in students:
        await gd_insert(db.session, "session_attendance", {
            "id": str(uuid.uuid4()), "session_id": session_id,
            "student_id": sid, "status": "present",
        })
    return {
        "tenant_id": tenant_id, "user_id": user_id, "teacher_row": teacher_row,
        "class_id": class_id, "students": students, "session_id": session_id,
    }


ROLES = ["real", "independent_teacher"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ROLES)
async def test_add_note_persists_content_in_real_columns(kind):
    ctx = await _mk_ctx(kind)
    eng = _engine()
    res = await eng.add_note(
        ctx["session_id"], ctx["user_id"], "ملاحظة عن الطالب",
        note_type="student", student_id=ctx["students"][0],
    )
    assert res["note"]["text"] == "ملاحظة عن الطالب"

    rows = await gd_find(db.session, "session_notes", {"session_id": ctx["session_id"]})
    assert len(rows) == 1
    row = rows[0]
    # Content lives in the REAL columns — not phantom keys the writer drops.
    assert row["note"] == "ملاحظة عن الطالب"
    assert row["type"] == "student"
    assert row["student_id"] == ctx["students"][0]
    # FK-safe attribution: a verified teachers.id (the user carries the link).
    assert row["teacher_id"] == ctx["teacher_row"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ROLES)
async def test_parent_broadcast_fans_out_one_row_per_student(kind):
    ctx = await _mk_ctx(kind)
    eng = _engine()
    await eng.add_note(
        ctx["session_id"], ctx["user_id"], "ملاحظة لأولياء الأمور",
        note_type="parent", student_ids=ctx["students"],
    )
    rows = await gd_find(db.session, "session_notes", {"session_id": ctx["session_id"]})
    assert len(rows) == 2
    assert {r["student_id"] for r in rows} == set(ctx["students"])
    assert all(r["note"] == "ملاحظة لأولياء الأمور" and r["type"] == "parent" for r in rows)
    # The "sent to parents" counter must filter on the real ``type`` column.
    assert await gd_count(db.session, "session_notes", {
        "session_id": ctx["session_id"], "type": "parent",
    }) == 2


@pytest.mark.asyncio
async def test_get_session_notes_canonical_shape_and_legacy_rows_hidden():
    ctx = await _mk_ctx("real")
    eng = _engine()
    # A legacy pre-fix row: content was dropped, only the skeleton persisted.
    await gd_insert(db.session, "session_notes", {
        "id": str(uuid.uuid4()), "session_id": ctx["session_id"],
        "type": "general", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await eng.add_note(
        ctx["session_id"], ctx["user_id"], "ملاحظة حقيقية",
        note_type="evaluation", student_id=ctx["students"][1],
    )
    notes = await eng.get_session_notes(ctx["session_id"])
    # Legacy empty row is unrecoverable — hidden, not rendered as a blank line.
    assert len(notes) == 1
    n = notes[0]
    assert n["text"] == "ملاحظة حقيقية"
    assert n["note_type"] == "evaluation"
    assert n["student_name"] == "طالب ثاني"

    # Deletion is scoped by session (route already verified ownership).
    await eng.delete_note(n["id"], ctx["session_id"])
    assert await eng.get_session_notes(ctx["session_id"]) == []


@pytest.mark.asyncio
async def test_add_note_rejects_empty_text():
    ctx = await _mk_ctx("real")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        await _engine().add_note(ctx["session_id"], ctx["user_id"], "   ")
    assert ei.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ROLES)
async def test_session_report_merges_all_note_sources(kind):
    ctx = await _mk_ctx(kind)
    eng = _engine()
    s1, s2 = ctx["students"]

    await eng.add_note(ctx["session_id"], ctx["user_id"], "ملاحظة سريعة", note_type="parent", student_ids=[s1])
    await eng.record_recitation(ctx["session_id"], s1, True, ctx["user_id"], attempts=2, note="تسميع ممتاز")
    await eng.record_behaviour(
        ctx["session_id"], s2, BehaviourCategory.POSITIVE, "احترام",
        details="ساعد زميله", teacher_id=ctx["user_id"],
    )
    await eng.record_skill(
        ctx["session_id"], s2, "custom", ctx["user_id"],
        notes="مهارة قيادية", custom_name="قيادة",
    )
    await eng.end_session(ctx["session_id"], ctx["user_id"], closing_note="درس موفق")

    report = await eng.get_session_report(ctx["session_id"])
    notes = report["notes"]
    by_type = {}
    for n in notes:
        by_type.setdefault(n["note_type"], []).append(n)

    assert by_type["closing"][0]["text"] == "درس موفق"
    assert by_type["parent"][0]["text"] == "ملاحظة سريعة"
    assert by_type["parent"][0]["student_name"] == "طالب أول"
    assert by_type["recitation"][0]["text"] == "تسميع ممتاز"
    assert by_type["recitation"][0]["student_name"] == "طالب أول"
    assert by_type["behaviour"][0]["text"] == "ساعد زميله"
    assert by_type["behaviour"][0]["student_name"] == "طالب ثاني"
    assert by_type["skill"][0]["text"] == "مهارة قيادية"
    assert by_type["skill"][0]["student_name"] == "طالب ثاني"
    # Every rendered note carries real content — no blank lines.
    assert all((n["text"] or "").strip() for n in notes)
    # Closing note is ordered first for the report reader.
    assert notes[0]["is_closing"] is True


@pytest.mark.asyncio
async def test_reversed_interaction_note_hidden_from_report():
    """An undone recitation (data.reversed — the engine's canonical undo
    marker) must not leak its note into the session report."""
    ctx = await _mk_ctx("real")
    eng = _engine()
    await eng.record_recitation(
        ctx["session_id"], ctx["students"][0], True, ctx["user_id"], note="سيُتراجع عنه",
    )
    from engines.sql_utils import gd_update_one
    inter = await gd_find_one(db.session, "session_interactions", {"session_id": ctx["session_id"]})
    await gd_update_one(
        db.session, "session_interactions", {"id": inter["id"]},
        {"data": {**(inter.get("data") or {}), "reversed": True}},
    )
    report = await eng.get_session_report(ctx["session_id"])
    assert all(n["note_type"] != "recitation" for n in report["notes"])


@pytest.mark.asyncio
async def test_management_summary_embeds_closing_note():
    ctx = await _mk_ctx("real")
    principal_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": principal_id, "role": "school_principal", "tenant_id": ctx["tenant_id"],
        "email": f"p-{principal_id}@t.test", "full_name": "مدير", "is_active": True,
        "password_hash": "x",
    })
    await _engine().end_session(ctx["session_id"], ctx["user_id"], closing_note="أنهينا الوحدة الثالثة")

    notif = await gd_find_one(db.session, "notifications", {
        "user_id": principal_id, "entity_id": ctx["session_id"],
    })
    assert notif is not None, "management summary notification must exist"
    assert "ملاحظة المعلم: أنهينا الوحدة الثالثة" in notif["message"]


@pytest.mark.asyncio
async def test_summary_no_closing_note_message_unchanged():
    ctx = await _mk_ctx("real")
    principal_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": principal_id, "role": "school_principal", "tenant_id": ctx["tenant_id"],
        "email": f"p2-{principal_id}@t.test", "full_name": "مدير", "is_active": True,
        "password_hash": "x",
    })
    await _engine().end_session(ctx["session_id"], ctx["user_id"])
    notif = await gd_find_one(db.session, "notifications", {
        "user_id": principal_id, "entity_id": ctx["session_id"],
    })
    assert notif is not None
    assert "ملاحظة المعلم" not in notif["message"]
