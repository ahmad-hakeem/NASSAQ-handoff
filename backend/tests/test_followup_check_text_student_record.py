"""Regression: check (تحقق) and text (نص) column values entered in the
follow-up sheet (كشف المتابعة) during a live session must appear in the class
Student Record (سجل الطلاب) after the session.

Root cause fixed: check/text values are — by design — never materialized into
student_grades (the record AVG casts score::float, so a text value there would
poison the aggregation). They live only in the followup_records blob keyed
(class_id, subject_id). But GET /class/{id}/student-grades read ONLY the
student_grades aggregation, so the class-page sheet could never render them:
the cells always came back empty after the lesson ended.

Contract under test (both school teacher and independent teacher):
  * check/text values saved to the sheet surface in the student-grades
    response under `manual_values` (raw, uncoerced: "test" stays a string,
    check stays 1) — never inside the numeric `grades` list;
  * grade-type manual values do NOT appear in manual_values (they reach the
    record via the commit_session_scores materialization instead);
  * clearing the cells drops them from manual_values (no stale display);
  * omitting subject_id still returns the values (class-wide merge).
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert
from src.modules.portals.controllers.role_dashboards_mod import session_engine


def _auth(user_id: str, role: str, tenant_id: str) -> dict:
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _setup(school_type: str):
    teacher_id = str(uuid.uuid4())
    role = "independent_teacher" if school_type == "independent_teacher" else "teacher"
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
        "date": "2026-08-06", "status": "active", "start_time": now, "created_at": now,
    })
    await session_engine._ensure_grade_columns(class_id)
    return {
        "tenant_id": tenant_id, "teacher_id": teacher_id, "class_id": class_id,
        "subject_id": subject_id, "student_id": student_id, "session_id": session_id,
        "headers": _auth(teacher_id, role, tenant_id),
    }


async def _add_column(client, ctx, name: str, input_type: str) -> str:
    r = await client.post(
        f"/class/{ctx['class_id']}/grade-columns",
        headers=ctx["headers"],
        json={"name": name, "column_type": "coursework", "input_type": input_type,
              "max_grade": 10, "order": 40},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _save_sheet(client, ctx, cells: dict):
    r = await client.post(
        f"/session/{ctx['session_id']}/followup-record",
        headers=ctx["headers"],
        json={"data": {ctx["student_id"]: cells} if cells else {}, "absences": {}},
    )
    assert r.status_code == 200, r.text


async def _record(client, ctx, with_subject: bool = True):
    params = {"subject_id": ctx["subject_id"]} if with_subject else None
    r = await client.get(
        f"/class/{ctx['class_id']}/student-grades",
        headers=ctx["headers"], params=params,
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_check_text_values_surface_in_student_record(client, school_type):
    ctx = await _setup(school_type)
    text_col = await _add_column(client, ctx, "عمود نص", "text")
    check_col = await _add_column(client, ctx, "عمود تحقق", "check")

    # Teacher fills the sheet during the lesson: text + checked box.
    await _save_sheet(client, ctx, {text_col: "test", check_col: 1})

    body = await _record(client, ctx)
    manual = {(m["student_id"], m["column_id"]): m["value"]
              for m in body.get("manual_values", [])}
    # Raw, uncoerced values — string stays string, check stays numeric truthy.
    assert manual.get((ctx["student_id"], text_col)) == "test", body
    assert manual.get((ctx["student_id"], check_col)) == 1, body
    # Never inside the numeric grades list (AVG casts score::float).
    grade_cols = {g["column_id"] for g in body["grades"]}
    assert text_col not in grade_cols
    assert check_col not in grade_cols

    # Same values must surface without the subject filter (class-wide read).
    body_nosub = await _record(client, ctx, with_subject=False)
    manual_nosub = {(m["student_id"], m["column_id"]): m["value"]
                    for m in body_nosub.get("manual_values", [])}
    assert manual_nosub.get((ctx["student_id"], text_col)) == "test"
    assert manual_nosub.get((ctx["student_id"], check_col)) == 1


@pytest.mark.asyncio
async def test_grade_values_excluded_and_clear_drops_cells(client):
    ctx = await _setup("real")
    text_col = await _add_column(client, ctx, "عمود نص", "text")
    grade_col = await _add_column(client, ctx, "عمود درجة", "grade")

    await _save_sheet(client, ctx, {text_col: "ملاحظة", grade_col: 7})
    body = await _record(client, ctx)
    manual_cols = {m["column_id"] for m in body.get("manual_values", [])}
    # Grade-type manual values flow through commit materialization, not here.
    assert grade_col not in manual_cols
    assert text_col in manual_cols

    # Clearing the sheet drops the stored overrides → nothing stale shown.
    await _save_sheet(client, ctx, {})
    body = await _record(client, ctx)
    assert body.get("manual_values", []) == []


@pytest.mark.asyncio
async def test_foreign_tenant_stamped_doc_is_filtered(client):
    """Defense-in-depth: a malformed followup_records doc that collides on
    class_id but is stamped with a FOREIGN school_id must never surface its
    values; a legacy doc without the stamp stays readable."""
    ctx = await _setup("real")
    text_col = await _add_column(client, ctx, "عمود نص", "text")

    # Legacy-shaped doc (no school_id stamp) with a value for our column.
    await gd_insert(db.session, "followup_records", {
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
        "data": {ctx["student_id"]: {text_col: "قديم"}},
        "updated_at": "2026-01-01T00:00:00+00:00",
    })
    # Malformed doc colliding on class_id but stamped with a foreign tenant.
    await gd_insert(db.session, "followup_records", {
        "class_id": ctx["class_id"], "subject_id": str(uuid.uuid4()),
        "school_id": str(uuid.uuid4()),
        "data": {ctx["student_id"]: {text_col: "دخيل"}},
        "updated_at": "2026-12-31T00:00:00+00:00",
    })

    body = await _record(client, ctx, with_subject=False)
    values = {m["value"] for m in body.get("manual_values", [])}
    assert "دخيل" not in values, body
    assert "قديم" in values, body
