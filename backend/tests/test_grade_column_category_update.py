"""Grade-column category (أعمال السنة/الاختبارات) — PUT contract.

Root cause under test: the أنماط التقييم editor could never change a
column's category. ``GradeColumnUpdate`` had no ``column_type`` field, so
gd_update silently dropped the key — a column created as coursework stayed
coursework forever, and the pattern editor offered no selector at all.

Contract (both school teacher and independent teacher):
  * PUT /grade-column/{id} accepts column_type (coursework|exams), persists
    it, and GET round-trips it;
  * invalid column_type values are 422;
  * omitting column_type in a PUT leaves the stored category untouched.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert


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
    # Class access for a plain school teacher is granted via
    # teacher_assignments ∪ class_sessions — seed a session like the
    # sibling input-types suite does.
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": str(uuid.uuid4()), "school_id": tenant_id, "tenant_id": tenant_id,
        "class_id": class_id, "teacher_id": teacher_id,
        "date": "2026-08-05", "status": "active", "start_time": now, "created_at": now,
    })
    return {
        "tenant_id": tenant_id, "teacher_id": teacher_id, "class_id": class_id,
        "headers": _auth(teacher_id, role, tenant_id),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["public", "independent_teacher"])
async def test_put_column_type_round_trips(client, school_type):
    ctx = await _setup(school_type)

    r = await client.post(
        f"/class/{ctx['class_id']}/grade-columns", headers=ctx["headers"],
        json={"name": "نشاط صفي", "column_type": "coursework", "max_grade": 10, "order": 20},
    )
    assert r.status_code == 200, r.text
    col = r.json()
    assert col["column_type"] == "coursework"

    # PUT flips the category and the response reflects it.
    r = await client.put(
        f"/grade-column/{col['id']}", headers=ctx["headers"],
        json={"column_type": "exams"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["column_type"] == "exams"

    # GET round-trips the stored category (the reload path the sheet uses).
    r = await client.get(f"/class/{ctx['class_id']}/grade-columns", headers=ctx["headers"])
    assert r.status_code == 200, r.text
    stored = next(c for c in r.json() if c["id"] == col["id"])
    assert stored["column_type"] == "exams"

    # Invalid category rejected.
    r = await client.put(
        f"/grade-column/{col['id']}", headers=ctx["headers"],
        json={"column_type": "homework"},
    )
    assert r.status_code == 422

    # PUT without column_type must not disturb the stored category.
    r = await client.put(
        f"/grade-column/{col['id']}", headers=ctx["headers"],
        json={"max_grade": 15},
    )
    assert r.status_code == 200, r.text
    r = await client.get(f"/class/{ctx['class_id']}/grade-columns", headers=ctx["headers"])
    stored = next(c for c in r.json() if c["id"] == col["id"])
    assert stored["column_type"] == "exams"
    assert stored["max_grade"] == 15
