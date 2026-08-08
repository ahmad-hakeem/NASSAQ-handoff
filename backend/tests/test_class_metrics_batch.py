"""Regression tests for GET /teacher/{teacher_id}/class-metrics.

The endpoint used to be a nested N+1: the route looped over every class of
the teacher and, for each class, ``get_class_metrics`` issued one query for
the class' sessions, one student COUNT, one "is there an in-progress session"
lookup, and then **two more queries per completed session** (attendance +
interactions).

Measured against real production data that was 187 SQL round-trips for a
single request (14 classes / 57 completed sessions). The row volumes involved
are tiny — the cost was almost entirely per-query network latency, which is
why the same endpoint served in ~250 ms next to the database and 8-9 s in
production.

These tests pin both halves of the contract:

* ``TestClassMetricsCorrectness`` — the aggregate maths (which sessions
  count, what "participation" means, how an in-progress session surfaces)
  must not drift while the query plan is rewritten.
* ``TestClassMetricsQueryCount`` — the number of SQL statements must stay
  flat as classes and sessions are added. This is the actual N+1 guard: it
  fails loudly on the old per-session loop.
"""

import contextlib
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.engine import Engine

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

# Tables the metric computation itself reads. Counting only these keeps the
# assertion about *this* endpoint rather than about shared auth/middleware
# queries, which are unrelated and may legitimately change.
_METRIC_SOURCES = ("generic_documents", "session_interactions", "FROM students")


@contextlib.contextmanager
def count_queries():
    """Count SQL statements executed inside the block.

    ``n`` is every statement; ``metric_n`` counts only the statements that
    read the collections the metric maths is built from.
    """
    stats = {"n": 0, "metric_n": 0, "statements": []}

    def _after(conn, cursor, statement, parameters, context, executemany):
        flat = " ".join(statement.split())
        stats["n"] += 1
        if any(src in flat for src in _METRIC_SOURCES):
            stats["metric_n"] += 1
        stats["statements"].append(flat[:90])

    event.listen(Engine, "after_cursor_execute", _after)
    try:
        yield stats
    finally:
        event.remove(Engine, "after_cursor_execute", _after)


async def _mk_teacher(school_id: str) -> dict:
    """Create the users + teachers pair a teacher-scoped endpoint needs."""
    user_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    email = f"t-{user_id}@t.test"
    await gd_insert(db.session, "users", {
        "id": user_id,
        "role": "teacher",
        "tenant_id": school_id,
        "email": email,
        "full_name": "Teacher Under Test",
        "is_active": True,
        "password_hash": "x",
    })
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "user_id": user_id,
        "school_id": school_id,
        "full_name": "Teacher Under Test",
        "email": email,
        "is_active": True,
    })
    return {"user_id": user_id, "teacher_id": teacher_id, "school_id": school_id}


def _teacher_headers(teacher: dict) -> dict:
    token = create_access_token({
        "sub": teacher["user_id"],
        "role": "teacher",
        "tenant_id": teacher["school_id"],
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_subject(school_id: str) -> str:
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": school_id, "name": f"SUB-{subject_id[:6]}",
    })
    return subject_id


async def _mk_class(school_id: str, teacher_id: str, name: str) -> str:
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": school_id, "name": name,
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "teacher_id": teacher_id,
        "class_id": class_id,
        "school_id": school_id,
        "subject_id": await _mk_subject(school_id),
        "is_active": True,
    })
    return class_id


async def _mk_students(school_id: str, class_id: str, n: int) -> list:
    ids = []
    for _ in range(n):
        sid = str(uuid.uuid4())
        await gd_insert(db.session, "students", {
            "id": sid, "school_id": school_id, "class_id": class_id,
            "full_name": f"ST-{sid[:6]}", "is_active": True,
        })
        ids.append(sid)
    return ids


async def _mk_session(school_id: str, class_id: str, teacher_id: str,
                      status: str = "completed", start_time: str = None) -> str:
    session_id = str(uuid.uuid4())
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "class_id": class_id,
        "teacher_id": teacher_id,
        "school_id": school_id,
        "status": status,
        "start_time": start_time or "2026-05-14T09:00:00+00:00",
        "date": "2026-05-14",
    })
    return session_id


async def _mk_attendance(session_id: str, student_id: str, status: str) -> None:
    await gd_insert(db.session, "session_attendance", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "status": status,
    })


async def _mk_interaction(session_id: str, student_id: str, itype: str,
                          recorded_by: str, answer_result: str = None,
                          write_json_type: bool = True) -> None:
    """Insert an interaction.

    Live rows carry the kind in BOTH the ``type`` column and
    ``data.interaction_type`` (verified: 793/793 rows agree, none missing).
    ``write_json_type=False`` simulates a row that only has the column, which
    the metric roll-up must still classify — see
    ``test_column_only_interaction_type_is_still_counted``.
    """
    data = {}
    if write_json_type:
        data["interaction_type"] = itype
    if answer_result:
        data["answer_result"] = answer_result
    await gd_insert(db.session, "session_interactions", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "type": itype,
        "data": data,
        "recorded_by": recorded_by,
    })


# --------------------------------------------------------------------------
# fixture: a small, fully hand-computable dataset
# --------------------------------------------------------------------------

@pytest_asyncio.fixture
async def metrics_fixture(tenant_a):
    """Three classes exercising every branch of the metric maths.

    class_a — 2 completed sessions, mixed attendance, participation from
              several interaction types (one of which must NOT count).
    class_b — 1 completed + 1 in-progress session (the in-progress one must
              be excluded from the totals but reported as ``next_session``).
    class_c — no sessions at all (must still be present, all zeros).
    """
    teacher = await _mk_teacher(tenant_a)
    tid = teacher["teacher_id"]
    uid = teacher["user_id"]

    class_a = await _mk_class(tenant_a, tid, "A")
    class_b = await _mk_class(tenant_a, tid, "B")
    class_c = await _mk_class(tenant_a, tid, "C")

    a_students = await _mk_students(tenant_a, class_a, 3)
    b_students = await _mk_students(tenant_a, class_b, 2)
    await _mk_students(tenant_a, class_c, 1)

    # -- class_a session 1: 3 attendance (2 present), participants {s0, s1}
    s1 = await _mk_session(tenant_a, class_a, tid)
    await _mk_attendance(s1, a_students[0], "present")
    await _mk_attendance(s1, a_students[1], "present")
    await _mk_attendance(s1, a_students[2], "absent")
    await _mk_interaction(s1, a_students[0], "participation", uid)
    await _mk_interaction(s1, a_students[0], "question", uid, "correct")
    await _mk_interaction(s1, a_students[1], "question", uid, "wrong")
    # recitation is grade-neutral and is NOT a participation signal
    await _mk_interaction(s1, a_students[2], "recitation", uid)

    # -- class_a session 2: 3 attendance (3 present), participants {s0}
    s2 = await _mk_session(tenant_a, class_a, tid)
    for st in a_students:
        await _mk_attendance(s2, st, "present")
    await _mk_interaction(s2, a_students[0], "question", uid, "correct")

    # -- class_b: one completed session with a behaviour-only interaction
    s3 = await _mk_session(tenant_a, class_b, tid)
    await _mk_attendance(s3, b_students[0], "present")
    await _mk_attendance(s3, b_students[1], "absent")
    await _mk_interaction(s3, b_students[0], "behaviour", uid)

    # -- class_b: an in-progress session that must not affect the totals
    await _mk_session(tenant_a, class_b, tid, status="in_progress",
                      start_time="2026-05-14T11:30:00+00:00")

    await db.session.flush()
    return {
        "teacher": teacher,
        "headers": _teacher_headers(teacher),
        "class_a": class_a, "class_b": class_b, "class_c": class_c,
    }


# --------------------------------------------------------------------------
# correctness
# --------------------------------------------------------------------------

class TestClassMetricsCorrectness:

    @pytest.mark.asyncio
    async def test_aggregates_match_hand_computed_values(self, client, metrics_fixture):
        f = metrics_fixture
        resp = await client.get(
            f"/teacher/{f['teacher']['teacher_id']}/class-metrics",
            headers=f["headers"],
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert set(data) == {f["class_a"], f["class_b"], f["class_c"]}

        # class_a: attendance 5 present / 6 records            -> 83.3
        #          participation 3 distinct-per-session / 5 present -> 60.0
        #          performance 2 correct / 3 questions          -> 66.7
        a = data[f["class_a"]]
        assert a["attendance_rate"] == 83.3
        assert a["participation_rate"] == 60.0
        assert a["avg_performance"] == 66.7
        assert a["total_sessions"] == 2
        assert a["total_students"] == 3
        assert a["next_session"] is None

        # class_b: only the completed session counts (1 present / 2 records).
        # A behaviour interaction is not participation, and there are no
        # questions, so both derived rates stay at zero.
        b = data[f["class_b"]]
        assert b["attendance_rate"] == 50.0
        assert b["participation_rate"] == 0
        assert b["avg_performance"] == 0
        assert b["total_sessions"] == 1
        assert b["total_students"] == 2
        assert b["next_session"] == {
            "status": "in_progress",
            "start_time": "2026-05-14T11:30:00+00:00",
        }

        # class_c: no sessions, but the class must still be reported.
        c = data[f["class_c"]]
        assert c == {
            "class_id": f["class_c"],
            "attendance_rate": 0,
            "participation_rate": 0,
            "avg_performance": 0,
            "total_sessions": 0,
            "total_students": 1,
            "next_session": None,
        }

    @pytest.mark.asyncio
    async def test_teacher_with_no_classes_returns_empty(self, client, tenant_a):
        teacher = await _mk_teacher(tenant_a)
        await db.session.flush()
        resp = await client.get(
            f"/teacher/{teacher['teacher_id']}/class-metrics",
            headers=_teacher_headers(teacher),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {}

    @pytest.mark.asyncio
    async def test_column_only_interaction_type_is_still_counted(
        self, client, tenant_a
    ):
        """A row carrying its kind only in the ``type`` column must count.

        Live rows populate both the column and ``data.interaction_type``, so
        this is a fail-safe rather than a live data path. It is pinned because
        the roll-up resolves the kind with
        ``COALESCE(data->>'interaction_type', type)``: the pre-refactor Python
        loop read the flattened dict key, which only ever came from the JSON
        payload, so a column-only row was silently excluded from BOTH the
        participation and the performance maths.
        """
        teacher = await _mk_teacher(tenant_a)
        class_id = await _mk_class(tenant_a, teacher["teacher_id"], "column-only")
        students = await _mk_students(tenant_a, class_id, 1)
        session_id = await _mk_session(
            tenant_a, class_id, teacher["teacher_id"], "completed"
        )
        await _mk_attendance(session_id, students[0], "present")
        # One correct question, recorded WITHOUT data.interaction_type.
        await _mk_interaction(
            session_id, students[0], "question", teacher["user_id"],
            answer_result="correct", write_json_type=False,
        )
        await db.session.flush()

        resp = await client.get(
            f"/teacher/{teacher['teacher_id']}/class-metrics",
            headers=_teacher_headers(teacher),
        )
        assert resp.status_code == 200, resp.text
        metrics = resp.json()[class_id]

        assert metrics["avg_performance"] == 100.0, (
            "a column-only question row was dropped from the performance maths"
        )
        assert metrics["participation_rate"] == 100.0, (
            "a column-only question row was dropped from the participation maths"
        )

    async def test_other_teachers_sessions_are_not_counted(self, client, metrics_fixture, tenant_a):
        """A second teacher teaching the same class must not inflate the metrics."""
        f = metrics_fixture
        other = await _mk_teacher(tenant_a)
        s = await _mk_session(tenant_a, f["class_a"], other["teacher_id"])
        students = await _mk_students(tenant_a, f["class_a"], 0)  # noqa: F841
        await _mk_attendance(s, str(uuid.uuid4()), "absent")
        await db.session.flush()

        resp = await client.get(
            f"/teacher/{f['teacher']['teacher_id']}/class-metrics",
            headers=f["headers"],
        )
        assert resp.status_code == 200, resp.text
        a = resp.json()[f["class_a"]]
        assert a["total_sessions"] == 2, "another teacher's session leaked in"
        assert a["attendance_rate"] == 83.3


# --------------------------------------------------------------------------
# the N+1 guard
# --------------------------------------------------------------------------

class TestClassMetricsQueryCount:

    @pytest.mark.asyncio
    async def test_query_count_does_not_grow_with_classes_or_sessions(self, client, tenant_a):
        """Adding classes and sessions must not add SQL round-trips.

        Under the old implementation the large teacher below issued roughly
        4x the statements of the small one; the endpoint now resolves every
        class in a fixed number of set-based queries.
        """
        async def _measure(n_classes: int, n_sessions: int) -> dict:
            teacher = await _mk_teacher(tenant_a)
            for c in range(n_classes):
                class_id = await _mk_class(tenant_a, teacher["teacher_id"], f"C{c}")
                students = await _mk_students(tenant_a, class_id, 2)
                for _ in range(n_sessions):
                    sid = await _mk_session(tenant_a, class_id, teacher["teacher_id"])
                    for st in students:
                        await _mk_attendance(sid, st, "present")
                        await _mk_interaction(sid, st, "question",
                                              teacher["user_id"], "correct")
            await db.session.flush()

            headers = _teacher_headers(teacher)
            url = f"/teacher/{teacher['teacher_id']}/class-metrics"
            # warm up so first-call artefacts (statement prep, lazy imports)
            # are not attributed to the measured call
            warm = await client.get(url, headers=headers)
            assert warm.status_code == 200, warm.text
            with count_queries() as stats:
                resp = await client.get(url, headers=headers)
            assert resp.status_code == 200, resp.text
            assert len(resp.json()) == n_classes
            return stats

        small = await _measure(n_classes=2, n_sessions=2)
        large = await _measure(n_classes=6, n_sessions=4)

        assert large["n"] <= small["n"], (
            f"total query count grew with the dataset: "
            f"{small['n']} -> {large['n']}. The per-class / per-session loop is back."
        )
        # The metric maths is four set-based reads: sessions, attendance
        # roll-up, interaction roll-up, student head-count. It must stay
        # exactly four however many classes and sessions exist.
        assert small["metric_n"] == large["metric_n"] == 4, (
            f"expected 4 set-based metric queries, got {small['metric_n']} "
            f"(small) and {large['metric_n']} (large): {large['statements']}"
        )
