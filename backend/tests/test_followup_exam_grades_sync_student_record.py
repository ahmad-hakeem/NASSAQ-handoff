"""Regression: exam / custom column grades typed into the follow-up sheet
(كشف المتابعة) during a live session must appear in the class Student Record
(سجل الطلاب) after حفظ الحصة / end-session commit.

Root cause fixed: commit_session_scores only materialized the three DERIVED
coursework buckets (participation / homework / performance) into
student_grades; manual values for exam columns (اختبار قصير, اختبار نهاية
الفترة) and teacher-added custom columns stayed stranded in the
followup_records doc, so GET /class/{id}/student-grades (the record's AVG
aggregation) showed 0 for them.

Contract under test (both school teacher and independent teacher):
  * manual exam value -> commit -> visible in /class/{id}/student-grades
    under the SAME class grade-column id the record table renders;
  * re-commit is idempotent (one doc per class/subject/student/column —
    the record AVG never skews across sessions);
  * editing the value and re-committing updates in place (latest wins);
  * clearing the cell then committing removes the grade (no stale value);
  * a parent-side grades doc is written/removed in lockstep.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_insert
from routes.role_dashboards_mod import session_engine


def _auth(user_id: str, role: str, tenant_id: str) -> dict:
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _setup(school_type: str):
    teacher_id = str(uuid.uuid4())
    role = "independent_teacher" if school_type == "independent_teacher" else "teacher"
    # IT workspace ids are itw_{user_id} — the class-access ownership check
    # reconstructs exactly that, so the fixture must mirror production shape.
    tenant_id = f"itw_{teacher_id}" if role == "independent_teacher" else str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": tenant_id, "name": f"مدرسة-{tenant_id[:6]}", "code": f"S{tenant_id[-8:]}",
        "status": "active", "country": "SA", "language": "ar",
        "school_type": school_type, "tenant_type": school_type,
    })
    await gd_insert(db.session, "users", {
        "id": teacher_id, "role": role, "tenant_id": tenant_id,
        "email": f"t-{teacher_id}@t.test", "full_name": "معلم",
        "is_active": True, "password_hash": "x",
    })
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": tenant_id, "tenant_id": tenant_id,
        "name": "الرياضيات", "name_ar": "الرياضيات",
    })
    student_id = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": student_id, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": "طالب-اختبار", "is_active": True,
    })
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id, "school_id": tenant_id, "tenant_id": tenant_id,
        "class_id": class_id, "subject_id": subject_id, "teacher_id": teacher_id,
        "date": "2026-07-28", "status": "active", "start_time": now, "created_at": now,
    })
    # Canonical class grade columns (same source the record table renders);
    # pick the short-quiz exam column — the exact column from the bug report.
    columns = await session_engine._ensure_grade_columns(class_id)
    quiz = next(c for c in columns if c.get("column_type") == "exams" and c["name"] == "اختبار قصير")
    return {
        "tenant_id": tenant_id, "teacher_id": teacher_id, "class_id": class_id,
        "subject_id": subject_id, "student_id": student_id, "session_id": session_id,
        "quiz_col": quiz, "headers": _auth(teacher_id, role, tenant_id),
    }


async def _save_sheet(client, ctx, cells: dict):
    r = await client.post(
        f"/session/{ctx['session_id']}/followup-record",
        headers=ctx["headers"],
        json={"data": {ctx["student_id"]: cells} if cells else {}, "absences": {}},
    )
    assert r.status_code == 200, r.text


async def _commit(client, ctx):
    r = await client.post(
        f"/session/{ctx['session_id']}/commit-scores", headers=ctx["headers"]
    )
    assert r.status_code == 200, r.text


async def _record_grades(client, ctx):
    r = await client.get(
        f"/class/{ctx['class_id']}/student-grades",
        headers=ctx["headers"],
        params={"subject_id": ctx["subject_id"]},
    )
    assert r.status_code == 200, r.text
    return {
        (g["student_id"], g["column_id"]): g for g in r.json()["grades"]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_exam_grade_flows_to_student_record_and_updates_in_place(
    client, school_type
):
    ctx = await _setup(school_type)
    quiz_id = ctx["quiz_col"]["id"]
    key = (ctx["student_id"], quiz_id)

    # 1. Type a quiz grade during the session, then حفظ الحصة.
    await _save_sheet(client, ctx, {quiz_id: 8})
    await _commit(client, ctx)
    grades = await _record_grades(client, ctx)
    assert key in grades, "exam grade missing from Student Record after commit"
    assert grades[key]["score"] == 8

    # 2. Re-commit (session end re-runs commit) — idempotent, no AVG skew.
    await _commit(client, ctx)
    grades = await _record_grades(client, ctx)
    assert grades[key]["score"] == 8
    assert grades[key]["sessions"] == 1  # exactly one doc per cell

    # 3. Edit the grade in the sheet, commit again — latest value wins.
    await _save_sheet(client, ctx, {quiz_id: 6})
    await _commit(client, ctx)
    grades = await _record_grades(client, ctx)
    assert grades[key]["score"] == 6

    # 4. Parent-side doc mirrors the value.
    parent_rows = await gd_find(db.session, "grades", {
        "student_id": ctx["student_id"], "source": "followup_manual",
    }, limit=10)
    assert len(parent_rows) == 1
    assert parent_rows[0]["score"] == 6

    # 5. Clear the cell, commit — the record must drop the stale grade.
    await _save_sheet(client, ctx, {})
    await _commit(client, ctx)
    grades = await _record_grades(client, ctx)
    assert key not in grades
    parent_rows = await gd_find(db.session, "grades", {
        "student_id": ctx["student_id"], "source": "followup_manual",
    }, limit=10)
    assert parent_rows == []


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_exam_value_clamped_and_student_without_interactions_included(
    client, school_type
):
    """A student with ONLY a manual exam grade (zero live interactions) must
    still get their grade committed — the bucket loop skips such students, so
    the manual sync must iterate the sheet blob, not computed session scores.
    Out-of-range values are clamped to the column max (record contract)."""
    ctx = await _setup(school_type)
    quiz_id = ctx["quiz_col"]["id"]
    max_grade = float(ctx["quiz_col"]["max_grade"])

    await _save_sheet(client, ctx, {quiz_id: max_grade + 90})
    await _commit(client, ctx)
    grades = await _record_grades(client, ctx)
    assert grades[(ctx["student_id"], quiz_id)]["score"] == max_grade


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_teacher_added_custom_column_flows_to_student_record(
    client, school_type
):
    """A custom column the teacher adds (إضافة عمود, e.g. نشاط 1) is a class
    grade_columns row that resolves to none of the derived buckets — its
    manual sheet values must flow to the record exactly like exam columns."""
    ctx = await _setup(school_type)
    custom_id = str(uuid.uuid4())
    await gd_insert(db.session, "grade_columns", {
        "id": custom_id, "class_id": ctx["class_id"], "name": "نشاط 1",
        "name_en": "Activity 1", "column_type": "coursework",
        "max_grade": 10, "order": 6, "visible": True,
    })

    await _save_sheet(client, ctx, {custom_id: 7})
    await _commit(client, ctx)
    grades = await _record_grades(client, ctx)
    assert grades[(ctx["student_id"], custom_id)]["score"] == 7
