"""Regression tests for GET /teacher/classes/{teacher_id} (the "فصولي" page).

The endpoint used to be a textbook N+1: for EVERY class it issued one
student COUNT, one subjects fetch, and (when the teacher's own assignments
carried no subject) one school-wide assignment fallback — on top of a
platform-wide ORM selectin cascade that turned every one of those reads into
schools/school_settings round-trips, and a whole-school assignment
materialization pass on every page view.

Measured against real production data that was 230 SQL round-trips for one
request (19 classes) — ~483 ms next to the database and ~7.6 s in
production, where each round-trip pays real network latency.

These tests pin the fix the same way test_class_metrics_batch.py does:

* ``TestTeacherClassesCorrectness`` — the enriched payload (student_count,
  subjects, subject_ids) must stay right while the query plan is rewritten.
* ``TestTeacherClassesQueryCount`` — the number of SQL statements touching
  the endpoint's source tables must stay FLAT as classes/students are added.
"""

import contextlib
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.engine import Engine

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert
from server import app


# Tables the enrichment itself reads. Counting only these keeps the assertion
# about THIS endpoint rather than shared auth/middleware queries.
_SOURCES = ("FROM students", "FROM subjects", "FROM teacher_assignments",
            "FROM classes", "FROM schools", "FROM school_settings")


@contextlib.contextmanager
def count_queries():
    stats = {"n": 0, "source_n": 0, "statements": []}

    def _after(conn, cursor, statement, parameters, context, executemany):
        flat = " ".join(statement.split())
        stats["n"] += 1
        if any(src in flat for src in _SOURCES):
            stats["source_n"] += 1
        stats["statements"].append(flat[:110])

    event.listen(Engine, "after_cursor_execute", _after)
    try:
        yield stats
    finally:
        event.remove(Engine, "after_cursor_execute", _after)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api") as c:
        yield c


async def _mk_school() -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": f"School-{sid[:6]}", "code": f"S{sid[:8]}",
        "status": "active", "country": "SA", "language": "ar",
    })
    return sid


async def _mk_teacher(school_id: str) -> dict:
    user_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    email = f"t-{user_id}@t.test"
    await gd_insert(db.session, "users", {
        "id": user_id, "role": "teacher", "tenant_id": school_id,
        "email": email, "full_name": "Teacher Under Test",
        "is_active": True, "password_hash": "x",
    })
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "user_id": user_id, "school_id": school_id,
        "full_name": "Teacher Under Test", "email": email, "is_active": True,
    })
    return {"user_id": user_id, "teacher_id": teacher_id, "school_id": school_id}


def _headers(t: dict) -> dict:
    token = create_access_token({
        "sub": t["user_id"], "role": "teacher", "tenant_id": t["school_id"],
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_subject(school_id: str, name: str) -> str:
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": school_id,
        "name": name, "name_ar": name,
    })
    return subject_id


async def _mk_class_with_students(school_id: str, teacher_id: str, name: str,
                                  subject_id: str, n_students: int) -> str:
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": school_id, "name": name,
        "grade_level": "1", "is_active": True,
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()), "school_id": school_id,
        "teacher_id": teacher_id, "class_id": class_id,
        "subject_id": subject_id, "is_active": True,
    })
    for _ in range(n_students):
        await gd_insert(db.session, "students", {
            "id": str(uuid.uuid4()), "school_id": school_id,
            "class_id": class_id, "full_name": "ST", "is_active": True,
        })
    # one inactive student that must NOT be counted
    await gd_insert(db.session, "students", {
        "id": str(uuid.uuid4()), "school_id": school_id,
        "class_id": class_id, "full_name": "GONE", "is_active": False,
    })
    return class_id


async def _seed(n_classes: int, n_students: int) -> dict:
    school_id = await _mk_school()
    teacher = await _mk_teacher(school_id)
    subject_id = await _mk_subject(school_id, "رياضيات")
    class_ids = []
    for i in range(n_classes):
        class_ids.append(await _mk_class_with_students(
            school_id, teacher["teacher_id"], f"C{i}", subject_id, n_students,
        ))
    await db.session.flush()
    return {"teacher": teacher, "subject_id": subject_id, "class_ids": class_ids}


class TestTeacherClassesCorrectness:

    @pytest.mark.asyncio
    async def test_enriched_payload(self, client):
        f = await _seed(n_classes=3, n_students=4)
        t = f["teacher"]
        resp = await client.get(f"/teacher/classes/{t['user_id']}", headers=_headers(t))
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list) and len(body) == 3
        for cls in body:
            assert cls["student_count"] == 4          # inactive student excluded
            assert cls["subject_ids"] == [f["subject_id"]]
            assert cls["subjects"] == ["رياضيات"]
            assert cls["subjects_data"] == [{"id": f["subject_id"], "name": "رياضيات"}]
            # no published timetable in this fixture
            assert cls["status"] == "no_upcoming"
            assert cls["schedule_count"] == 0

    @pytest.mark.asyncio
    async def test_empty_assignments_returns_empty_list(self, client):
        school_id = await _mk_school()
        t = await _mk_teacher(school_id)
        await db.session.flush()
        resp = await client.get(f"/teacher/classes/{t['user_id']}", headers=_headers(t))
        assert resp.status_code == 200
        assert resp.json() == []


class TestTeacherClassesQueryCount:

    @pytest.mark.asyncio
    async def test_query_count_stays_flat(self, client):
        small = await _seed(n_classes=2, n_students=2)
        large = await _seed(n_classes=12, n_students=8)

        async def _measure(f):
            t = f["teacher"]
            headers = _headers(t)
            # warm-up: shared caches (auth etc.), not the assertion target
            await client.get(f"/teacher/classes/{t['user_id']}", headers=headers)
            with count_queries() as stats:
                resp = await client.get(f"/teacher/classes/{t['user_id']}", headers=headers)
            assert resp.status_code == 200
            assert len(resp.json()) == len(f["class_ids"])
            return stats

        s_small = await _measure(small)
        s_large = await _measure(large)

        # The N+1 guard: source-table statements must NOT grow with the data.
        assert s_large["source_n"] <= s_small["source_n"], (
            f"query count grew with class count: "
            f"small={s_small['source_n']} large={s_large['source_n']}\n"
            + "\n".join(s_large["statements"])
        )
        # Absolute ceiling: the whole request (incl. auth/middleware) must
        # stay a handful of round-trips, never tens.
        assert s_large["n"] <= 25, (
            f"total statements {s_large['n']} > 25\n"
            + "\n".join(s_large["statements"])
        )
