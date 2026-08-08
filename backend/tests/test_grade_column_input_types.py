"""Evaluation-type dropdown (درجة/تحقق/نص) audit — persistence + sync contract.

Root cause fixed: the أنماط التقييم editor offered grade/check/text input
types, but the class grade-columns API had no field for them — the selection
was never saved (every reload silently reset columns to درجة) and the sheet
rendered numeric inputs regardless.

Contract under test (both school teacher and independent teacher):
  * POST /class/{id}/grade-columns accepts input_type (grade|check|text),
    persists it, and GET returns it;
  * input_type defaults to "grade" when omitted; invalid values are 422;
  * PUT /grade-column/{id} can change input_type and it round-trips;
  * seeded default columns carry input_type "grade";
  * commit_session_scores NEVER materializes check/text column values into
    student_grades/grades — the record AVG casts score to float, so a text
    value there would poison the whole aggregation. Grade columns still sync.
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
    return {
        "tenant_id": tenant_id, "teacher_id": teacher_id, "class_id": class_id,
        "subject_id": subject_id, "student_id": student_id, "session_id": session_id,
        "headers": _auth(teacher_id, role, tenant_id),
    }


async def _create_col(client, ctx, name, input_type=None, column_type="coursework"):
    body = {"name": name, "column_type": column_type, "max_grade": 10, "order": 20}
    if input_type is not None:
        body["input_type"] = input_type
    r = await client.post(
        f"/class/{ctx['class_id']}/grade-columns", headers=ctx["headers"], json=body
    )
    return r


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["public", "independent_teacher"])
async def test_input_type_persists_and_round_trips(client, school_type):
    ctx = await _setup(school_type)

    # Seeded defaults carry input_type "grade".
    r = await client.get(f"/class/{ctx['class_id']}/grade-columns", headers=ctx["headers"])
    assert r.status_code == 200, r.text
    defaults = r.json()
    assert defaults and all(c.get("input_type") == "grade" for c in defaults)

    # Create one column of each type; omitted input_type defaults to grade.
    for name, itype, expected in [
        ("سلوك", "check", "check"),
        ("ملاحظة", "text", "text"),
        ("نشاط", None, "grade"),
    ]:
        r = await _create_col(client, ctx, name, itype)
        assert r.status_code == 200, r.text
        assert r.json()["input_type"] == expected

    # Invalid value rejected.
    r = await _create_col(client, ctx, "خاطئ", "emoji")
    assert r.status_code == 422

    # GET reflects the stored types (the reload path that used to reset to درجة).
    r = await client.get(f"/class/{ctx['class_id']}/grade-columns", headers=ctx["headers"])
    by_name = {c["name"]: c for c in r.json()}
    assert by_name["سلوك"]["input_type"] == "check"
    assert by_name["ملاحظة"]["input_type"] == "text"
    assert by_name["نشاط"]["input_type"] == "grade"

    # PUT changes the type and it round-trips; invalid value rejected.
    col_id = by_name["نشاط"]["id"]
    r = await client.put(
        f"/grade-column/{col_id}", headers=ctx["headers"], json={"input_type": "text"}
    )
    assert r.status_code == 200, r.text
    r = await client.put(
        f"/grade-column/{col_id}", headers=ctx["headers"], json={"input_type": "nope"}
    )
    assert r.status_code == 422
    r = await client.get(f"/class/{ctx['class_id']}/grade-columns", headers=ctx["headers"])
    assert {c["name"]: c["input_type"] for c in r.json()}["نشاط"] == "text"


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["public", "independent_teacher"])
async def test_commit_skips_check_and_text_columns(client, school_type):
    ctx = await _setup(school_type)
    check = (await _create_col(client, ctx, "أحضر الكتاب", "check")).json()
    text = (await _create_col(client, ctx, "ملاحظة المعلم", "text")).json()
    grade = (await _create_col(client, ctx, "نشاط إثرائي", "grade")).json()

    r = await client.post(
        f"/session/{ctx['session_id']}/followup-record",
        headers=ctx["headers"],
        json={
            "data": {ctx["student_id"]: {
                check["id"]: 1,
                text["id"]: "ممتاز في القراءة",
                grade["id"]: 7,
            }},
            "absences": {},
        },
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/session/{ctx['session_id']}/commit-scores", headers=ctx["headers"]
    )
    assert r.status_code == 200, r.text

    docs = await gd_find(db.session, "student_grades", {"student_id": ctx["student_id"]})
    cols_written = {d.get("column_id") for d in docs}
    assert grade["id"] in cols_written
    assert check["id"] not in cols_written
    assert text["id"] not in cols_written

    # Record aggregation still healthy (would 500 if a text score hit the
    # float cast) and only surfaces the numeric column.
    r = await client.get(
        f"/class/{ctx['class_id']}/student-grades",
        headers=ctx["headers"],
        params={"subject_id": ctx["subject_id"]},
    )
    assert r.status_code == 200, r.text
    grades = {(g["student_id"], g["column_id"]): g for g in r.json()["grades"]}
    assert (ctx["student_id"], grade["id"]) in grades
    assert grades[(ctx["student_id"], grade["id"])]["score"] == 7
    assert (ctx["student_id"], check["id"]) not in grades
    assert (ctx["student_id"], text["id"]) not in grades

    # The raw values stay intact in the follow-up record for the sheet itself.
    r = await client.get(
        f"/session/{ctx['session_id']}/followup-record", headers=ctx["headers"]
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    row = (payload.get("data") or {}).get(ctx["student_id"]) or {}
    assert row.get(text["id"]) == "ممتاز في القراءة"
    assert row.get(check["id"]) in (1, "1", True)


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["public", "independent_teacher"])
async def test_bucket_named_column_flipped_to_text_leaves_numeric_pipeline(client, school_type):
    """A column whose NAME matches a derived bucket (e.g. المشاركة) but whose
    input_type was switched to text/check must drop out of the derived bucket
    universe: hydration/commit must not overlay numerics onto it, its free-text
    value must survive commit, and nothing lands in student_grades for it."""
    ctx = await _setup(school_type)
    # Seed the canonical defaults, then flip المشاركة to a text column.
    r = await client.get(f"/class/{ctx['class_id']}/grade-columns", headers=ctx["headers"])
    part = next(c for c in r.json() if c["name"] == "المشاركة")
    r = await client.put(
        f"/grade-column/{part['id']}", headers=ctx["headers"], json={"input_type": "text"}
    )
    assert r.status_code == 200, r.text

    buckets = await session_engine._resolve_coursework_columns(ctx["class_id"])
    assert all(c["id"] != part["id"] for c in buckets.values())

    r = await client.post(
        f"/session/{ctx['session_id']}/followup-record",
        headers=ctx["headers"],
        json={"data": {ctx["student_id"]: {part["id"]: "مشاركة رائعة"}}, "absences": {}},
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/session/{ctx['session_id']}/commit-scores", headers=ctx["headers"]
    )
    assert r.status_code == 200, r.text

    docs = await gd_find(db.session, "student_grades", {"student_id": ctx["student_id"]})
    assert part["id"] not in {d.get("column_id") for d in docs}

    r = await client.get(
        f"/session/{ctx['session_id']}/followup-record", headers=ctx["headers"]
    )
    assert r.status_code == 200, r.text
    row = (r.json().get("data") or {}).get(ctx["student_id"]) or {}
    assert row.get(part["id"]) == "مشاركة رائعة"
