"""Opt-in live development-DB regression for open-ended class rosters.

This is deliberately a single integration test rather than a fixture shared by
the normal test suite.  It creates four synthetic rosters (31, 50, 100, and
300 students), exercises the write/read paths that matter for a large class,
and owns one outer transaction for the complete test.  It must never be run
against a production database:

    RUN_OPEN_ENDED_ROSTERS_LIVE=1 \
    OPEN_ENDED_ROSTERS_DATABASE=development \
    pytest -q tests/test_open_ended_class_rosters_live.py

Elapsed times and memory figures printed by this test are development-only
observations.  They are not production performance claims.
"""
from __future__ import annotations

import csv
import io
import os
import resource
import sys
import time
import tracemalloc
import uuid
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool


if os.environ.get("RUN_OPEN_ENDED_ROSTERS_LIVE") != "1":
    pytest.skip(
        "opt-in live development DB regression "
        "(set RUN_OPEN_ENDED_ROSTERS_LIVE=1)",
        allow_module_level=True,
    )
if os.environ.get("OPEN_ENDED_ROSTERS_DATABASE") != "development":
    pytest.skip(
        "refusing to run unless OPEN_ENDED_ROSTERS_DATABASE=development",
        allow_module_level=True,
    )


_BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
os.environ.setdefault("TESTING", "1")

from dependencies import create_access_token, db  # noqa: E402
from engines.sql_utils import (  # noqa: E402
    gd_count,
    gd_find,
    gd_insert,
    gd_insert_many,
)
from server import app  # noqa: E402
from src.core.database.db import _get_async_url  # noqa: E402


pytestmark = pytest.mark.asyncio

_SCALES = (31, 50, 100, 300)
_SOURCE_MARKERS = (
    "from students",
    "from classes",
    "from attendance",
    "from teacher_assignments",
    "from subjects",
    "from grade_levels",
)


def _id() -> str:
    return str(uuid.uuid4())


def _json_body(response, envelope: str | None = None):
    """Read route JSON while tolerating the API's optional data envelope.

    Most endpoints return a list or a direct object.  The class-create wizard
    intentionally returns ``{"class": {...}, "class_id": ...}`` instead, so
    callers can request that named envelope without baking that one route's
    shape into the fixture.  A response middleware may also wrap direct JSON
    in ``{"data": ...}``; unwrap that only when it is the sole top-level key.
    """
    payload = response.json()
    # Allow either ordering: {"class": ...}, {"data": {"class": ...}}, or
    # a direct {"data": ...} response.  The loop is bounded so a legitimate
    # nested payload cannot cause an accidental unbounded unwrap.
    for _ in range(2):
        if (
            envelope
            and isinstance(payload, dict)
            and envelope in payload
            and isinstance(payload[envelope], (dict, list))
        ):
            payload = payload[envelope]
            continue
        if (
            isinstance(payload, dict)
            and set(payload) == {"data"}
            and isinstance(payload["data"], (dict, list))
        ):
            payload = payload["data"]
            continue
        break
    return payload


def _school_doc(school_id: str, principal_id: str) -> dict:
    return {
        "id": school_id,
        "name": f"Open roster regression {school_id[:8]}",
        "code": f"OR-{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "tenant_type": "development",
        "principal_id": principal_id,
        "current_students": 0,
        "current_teachers": 0,
    }


def _user_doc(
    user_id: str,
    school_id: str,
    *,
    role: str,
    email: str,
    name: str,
) -> dict:
    return {
        "id": user_id,
        "email": email,
        "full_name": name,
        "password_hash": "open-roster-regression-not-used",
        "role": role,
        "tenant_id": school_id,
        "is_active": True,
        "must_change_password": False,
    }


def _headers(user_id: str, role: str, school_id: str, **claims) -> dict:
    payload = {
        "sub": user_id,
        "role": role,
        "tenant_id": school_id,
        **claims,
    }
    return {"Authorization": f"Bearer {create_access_token(payload)}"}


def _grade_doc(school_id: str, grade_id: str) -> dict:
    return {
        "id": grade_id,
        "school_id": school_id,
        "name": "الصف الأول الابتدائي",
        "name_ar": "الصف الأول الابتدائي",
        "name_en": "Grade 1",
        "code": "open-roster-g1",
        "stage": "primary",
        "order": 1,
        "is_active": True,
    }


def _class_doc(school_id: str, class_id: str, name: str) -> dict:
    # Deliberately retain the legacy 30-student metadata value.  Every
    # requested roster exceeds it, proving that open-ended membership no
    # longer treats this legacy field as an admission limit.
    return {
        "id": class_id,
        "school_id": school_id,
        "name": name,
        "name_en": name,
        "grade_level": "1",
        "section": name,
        "capacity": 30,
        "current_students": 0,
        "is_active": True,
    }


def _student_doc(
    school_id: str,
    student_id: str,
    *,
    class_id: str | None,
    number: str,
) -> dict:
    return {
        "id": student_id,
        "school_id": school_id,
        "class_id": class_id,
        "full_name": f"Open roster student {number}",
        "full_name_en": f"Open roster student {number}",
        "student_number": number,
        "national_id": number,
        "grade": "1",
        "is_active": True,
    }


@contextmanager
def _count_sql():
    stats = {"total": 0, "source": 0}

    def _after(conn, cursor, statement, parameters, context, executemany):
        flat = " ".join(str(statement).split()).casefold()
        stats["total"] += 1
        if any(marker in flat for marker in _SOURCE_MARKERS):
            stats["source"] += 1

    event.listen(Engine, "after_cursor_execute", _after)
    try:
        yield stats
    finally:
        event.remove(Engine, "after_cursor_execute", _after)


async def _measured_request(client: AsyncClient, method: str, url: str, **kwargs):
    """Measure one already-warm request without retaining response row data."""
    if not tracemalloc.is_tracing():
        tracemalloc.start()
    tracemalloc.reset_peak()
    before_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = time.perf_counter()
    with _count_sql() as sql:
        response = await client.request(method, url, **kwargs)
    elapsed_ms = (time.perf_counter() - started) * 1000
    _, peak_bytes = tracemalloc.get_traced_memory()
    after_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return response, {
        "sql_total": sql["total"],
        "sql_source": sql["source"],
        "elapsed_ms": round(elapsed_ms, 2),
        "peak_bytes": peak_bytes,
        "rss_delta": max(0, after_rss - before_rss),
    }


async def _snapshot(session: AsyncSession, school_id: str) -> dict:
    return {
        "students": await gd_count(session, "students", {"school_id": school_id}),
        "classes": await gd_count(session, "classes", {"school_id": school_id}),
        "attendance": await gd_count(
            session, "attendance", {"school_id": school_id}
        ),
        "parents": await gd_count(session, "parents", {"school_id": school_id}),
        "batches": await gd_count(
            session, "bulk_import_batches", {"school_id": school_id}
        ),
    }


async def _assert_cleanup(engine, school_id: str) -> None:
    async with engine.connect() as connection:
        async with AsyncSession(
            bind=connection, expire_on_commit=False
        ) as verification:
            cleanup_fields = {
                "schools": "id",
                "users": "tenant_id",
                "teachers": "school_id",
                "students": "school_id",
                "classes": "school_id",
                "subjects": "school_id",
                "attendance": "school_id",
                "parents": "school_id",
                "guardian_links": "tenant_id",
                "bulk_import_batches": "school_id",
            }
            for table, field in cleanup_fields.items():
                assert await gd_count(verification, table, {field: school_id}) == 0


async def _seed(
    session: AsyncSession,
    school_id: str,
    principal_id: str,
    teacher_user_id: str,
    teacher_id: str,
    grade_id: str,
    subject_id: str,
) -> dict:
    await gd_insert(session, "schools", _school_doc(school_id, principal_id))
    await gd_insert(
        session,
        "users",
        _user_doc(
            principal_id,
            school_id,
            role="school_principal",
            email=f"principal-{school_id[:8]}@example.test",
            name="Open roster principal",
        ),
    )
    await gd_insert(
        session,
        "users",
        _user_doc(
            teacher_user_id,
            school_id,
            role="teacher",
            email=f"teacher-{school_id[:8]}@example.test",
            name="Open roster teacher",
        ),
    )
    await gd_insert(
        session,
        "teachers",
        {
            "id": teacher_id,
            "user_id": teacher_user_id,
            "school_id": school_id,
            "full_name": "Open roster teacher",
            "email": f"teacher-{school_id[:8]}@example.test",
            "is_active": True,
        },
    )
    await gd_insert(
        session,
        "grade_levels",
        _grade_doc(school_id, grade_id),
    )
    await gd_insert(
        session,
        "subjects",
        {
            "id": subject_id,
            "school_id": school_id,
            "name": "Open roster subject",
            "name_ar": "مادة اختبار القوائم",
            "is_active": True,
        },
    )

    manual_class_id = _id()
    move_class_id = _id()
    move_target_id = _id()
    bulk_class_id = _id()
    import_class_id = _id()
    await gd_insert_many(
        session,
        "classes",
        [
            _class_doc(school_id, move_class_id, "MOVE-50"),
            _class_doc(school_id, move_target_id, "MOVE-TARGET"),
            _class_doc(school_id, bulk_class_id, "BULK-100"),
            {
                **_class_doc(school_id, import_class_id, "IMP-300"),
                "section": "IMP",
                "grade_id": grade_id,
                "grade_level": "الصف الأول الابتدائي",
            },
        ],
    )

    manual_students = [
        _student_doc(
            school_id,
            _id(),
            class_id=None,
            number=f"1{index:09d}",
        )
        for index in range(_SCALES[0])
    ]
    move_students = [
        _student_doc(
            school_id,
            _id(),
            class_id=move_class_id,
            number=f"2{index:09d}",
        )
        for index in range(_SCALES[1])
    ]
    bulk_students = [
        _student_doc(
            school_id,
            _id(),
            class_id=None,
            number=f"3{index:09d}",
        )
        for index in range(_SCALES[2])
    ]
    await gd_insert_many(session, "students", manual_students + move_students + bulk_students)

    # A second school makes every cross-school assertion exercise an existing
    # row rather than a merely malformed UUID.
    foreign_school_id = _id()
    foreign_principal_id = _id()
    foreign_class_id = _id()
    foreign_student_id = _id()
    await gd_insert(
        session,
        "schools",
        _school_doc(foreign_school_id, foreign_principal_id),
    )
    await gd_insert(
        session,
        "classes",
        _class_doc(foreign_school_id, foreign_class_id, "FOREIGN"),
    )
    await gd_insert(
        session,
        "students",
        _student_doc(
            foreign_school_id,
            foreign_student_id,
            class_id=foreign_class_id,
            number="9999999999",
        ),
    )
    await session.flush()
    return {
        "manual_class_id": manual_class_id,
        "move_class_id": move_class_id,
        "move_target_id": move_target_id,
        "bulk_class_id": bulk_class_id,
        "import_class_id": import_class_id,
        "manual_students": manual_students,
        "move_students": move_students,
        "bulk_students": bulk_students,
        "foreign_class_id": foreign_class_id,
        "foreign_student_id": foreign_student_id,
    }


def _import_frame(school_id: str, class_name: str, count: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "first name": f"Imported {index}",
                "father name": "Synthetic",
                "grandfather name": "Open",
                "last name": "Open Roster",
                "national id": f"4{index:09d}",
                "grade": "1",
                "class": class_name,
                "parent name": "Synthetic Guardian",
                "parent phone": "0500000000",
                "parent email": f"guardian-{school_id[:8]}@example.test",
            }
            for index in range(count)
        ]
    )


def _xlsx_bytes(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        frame.to_excel(writer, index=False, sheet_name="Students")
    return buf.getvalue()


def _csv_student_rows(content: bytes) -> int:
    text_content = content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text_content)))
    if not rows:
        return 0
    # Legacy export has a header row followed by one row per student.
    return max(0, len(rows) - 1)


async def test_open_ended_rosters_live_development_regression():
    """Exercise writes, reads, isolation, idempotency, and bounded scaling."""
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    school_id = _id()
    principal_id = _id()
    teacher_user_id = _id()
    teacher_id = _id()
    grade_id = _id()
    subject_id = _id()
    connection = None
    outer_transaction = None
    session = None
    previous_session = db.session

    try:
        connection = await engine.connect()
        outer_transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        db.set_session(session)
        fixture = await _seed(
            session,
            school_id,
            principal_id,
            teacher_user_id,
            teacher_id,
            grade_id,
            subject_id,
        )
        principal_headers = _headers(principal_id, "school_principal", school_id)
        teacher_headers = _headers(
            teacher_user_id,
            "teacher",
            school_id,
            teacher_id=teacher_id,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test/api") as client:
            # (1) Manual creation of a 31-student open-ended roster.
            manual_response, manual_metrics = await _measured_request(
                client,
                "POST",
                "/classes/create",
                headers=principal_headers,
                json={
                    "name": "MANUAL-31",
                    "name_en": "MANUAL-31",
                    "grade_id": grade_id,
                    "grade": 1,
                    "stage": "primary",
                    "section": "MANUAL",
                    "capacity": 30,
                    "student_ids": [
                        student["id"] for student in fixture["manual_students"]
                    ],
                },
            )
            assert manual_response.status_code == 200, manual_response.text
            manual_class_id = _json_body(manual_response, envelope="class")["id"]
            fixture_classes = await gd_find(
                session,
                "classes",
                {"school_id": school_id, "is_active": True},
                limit=20,
            )
            assert len(fixture_classes) == 5
            assert {row.get("capacity") for row in fixture_classes} == {30}
            manual_roster = await gd_find(
                session,
                "students",
                {"school_id": school_id, "class_id": manual_class_id},
                limit=100,
            )
            assert len(manual_roster) == 31

            # (2) Transfer a student out and back.  The final 50-student
            # source roster proves a real move did not silently drop anyone.
            move_student_id = fixture["move_students"][0]["id"]
            for source_id, target_id in (
                (fixture["move_class_id"], fixture["move_target_id"]),
                (fixture["move_target_id"], fixture["move_class_id"]),
            ):
                response, _ = await _measured_request(
                    client,
                    "POST",
                    "/students/transfer-class",
                    headers=principal_headers,
                    json={
                        "student_id": move_student_id,
                        "target_class_id": target_id,
                    },
                )
                assert response.status_code == 200, response.text
            moved_rows = await gd_find(
                session,
                "students",
                {"school_id": school_id, "class_id": fixture["move_class_id"]},
                limit=100,
            )
            assert len(moved_rows) == 50

            # (3) Bulk assignment of 100 previously unassigned students.
            bulk_response, bulk_metrics = await _measured_request(
                client,
                "POST",
                "/students/bulk-assign",
                headers=principal_headers,
                json={
                    "student_ids": [s["id"] for s in fixture["bulk_students"]],
                    "target_class_id": fixture["bulk_class_id"],
                },
            )
            assert bulk_response.status_code == 200, bulk_response.text
            assert _json_body(bulk_response)["assigned_count"] == 100
            bulk_roster = await gd_find(
                session,
                "students",
                {"school_id": school_id, "class_id": fixture["bulk_class_id"]},
                limit=200,
            )
            assert len(bulk_roster) == 100

            # (4) Principal Excel import of 300 rows, followed by an identical
            # retry.  The existing class is intentionally capacity-independent.
            import_frame = _import_frame(school_id, "IMP", 300)
            workbook = _xlsx_bytes(import_frame)
            import_kwargs = {
                "headers": principal_headers,
                "files": {
                    "file": (
                        "open-ended-roster.xlsx",
                        workbook,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            }
            import_response, import_metrics = await _measured_request(
                client,
                "POST",
                "/bulk/import/students",
                **import_kwargs,
            )
            assert import_response.status_code == 200, import_response.text
            first_import = _json_body(import_response)
            assert first_import["imported"] == 300
            assert first_import["failed"] == 0

            retry_response, retry_metrics = await _measured_request(
                client,
                "POST",
                "/bulk/import/students",
                **import_kwargs,
            )
            assert retry_response.status_code == 200, retry_response.text
            retry_import = _json_body(retry_response)
            assert retry_import["imported"] == 300
            assert retry_import["updated"] == 300
            assert retry_import["created"] == 0
            assert retry_import["failed"] == 0
            imported_roster = await gd_find(
                session,
                "students",
                {
                    "school_id": school_id,
                    "class_id": fixture["import_class_id"],
                    "is_active": True,
                },
                limit=500,
            )
            assert len(imported_roster) == 300
            assert len(
                {
                    student.get("national_id")
                    for student in imported_roster
                }
            ) == 300

            # No active fixture student may be left unassigned at 31+.
            all_fixture_students = await gd_find(
                session,
                "students",
                {"school_id": school_id, "is_active": True},
                limit=1000,
            )
            assert len(all_fixture_students) == 31 + 50 + 100 + 300
            assert all(student.get("class_id") for student in all_fixture_students)

            # Invalid and cross-school references must fail closed without
            # mutating a valid roster.
            before_invalid = await _snapshot(session, school_id)
            invalid_bulk, _ = await _measured_request(
                client,
                "POST",
                "/students/bulk-assign",
                headers=principal_headers,
                json={
                    "student_ids": [fixture["foreign_student_id"]],
                    "target_class_id": fixture["bulk_class_id"],
                },
            )
            assert invalid_bulk.status_code == 404
            invalid_move, _ = await _measured_request(
                client,
                "POST",
                "/students/transfer-class",
                headers=principal_headers,
                json={
                    "student_id": fixture["move_students"][0]["id"],
                    "target_class_id": fixture["foreign_class_id"],
                },
            )
            assert invalid_move.status_code == 404
            invalid_roster, _ = await _measured_request(
                client,
                "GET",
                f"/classes/{fixture['foreign_class_id']}/students",
                headers=principal_headers,
            )
            assert invalid_roster.status_code == 404
            missing_roster, _ = await _measured_request(
                client,
                "GET",
                f"/classes/{_id()}/students",
                headers=principal_headers,
            )
            assert missing_roster.status_code == 404
            assert await _snapshot(session, school_id) == before_invalid

            # Assign one teacher to each resulting scale and read all surfaces.
            resulting_classes = [
                (manual_class_id, 31),
                (fixture["move_class_id"], 50),
                (fixture["bulk_class_id"], 100),
                (fixture["import_class_id"], 300),
            ]
            await gd_insert_many(
                session,
                "teacher_assignments",
                [
                    {
                        "id": _id(),
                        "school_id": school_id,
                        "teacher_id": teacher_id,
                        "class_id": class_id,
                        "subject_id": subject_id,
                        "subject_name": "Open roster subject",
                        "class_name": class_id,
                        "is_active": True,
                    }
                    for class_id, _ in resulting_classes
                ],
            )
            attendance_rows = []
            for class_id, expected_count in resulting_classes:
                rows = await gd_find(
                    session,
                    "students",
                    {"school_id": school_id, "class_id": class_id},
                    limit=expected_count + 1,
                )
                assert len(rows) == expected_count
                attendance_rows.extend(
                    {
                        "id": _id(),
                        "school_id": school_id,
                        "tenant_id": school_id,
                        "class_id": class_id,
                        "student_id": student["id"],
                        "date": "2026-05-14",
                        "status": "present",
                        "recorded_by": teacher_user_id,
                    }
                    for student in rows
                )
            await gd_insert_many(session, "attendance", attendance_rows)
            await session.flush()

            roster_metrics = []
            attendance_metrics = []
            for class_id, expected_count in resulting_classes:
                # Warm once; first-call imports and response-model setup are
                # excluded from the reported development-only measurement.
                warm_roster = await client.get(
                    f"/classes/{class_id}/students",
                    headers=principal_headers,
                )
                assert warm_roster.status_code == 200, warm_roster.text
                response, metrics = await _measured_request(
                    client,
                    "GET",
                    f"/classes/{class_id}/students",
                    headers=principal_headers,
                )
                assert response.status_code == 200, response.text
                assert len(_json_body(response)) == expected_count
                roster_metrics.append((expected_count, metrics))

                warm_attendance = await client.get(
                    f"/attendance/class/{class_id}?date=2026-05-14",
                    headers=principal_headers,
                )
                assert warm_attendance.status_code == 200, warm_attendance.text
                response, metrics = await _measured_request(
                    client,
                    "GET",
                    f"/attendance/class/{class_id}?date=2026-05-14",
                    headers=principal_headers,
                )
                assert response.status_code == 200, response.text
                assert len(_json_body(response)) == expected_count
                attendance_metrics.append((expected_count, metrics))

            teacher_response, teacher_metrics = await _measured_request(
                client,
                "GET",
                f"/teacher/classes/{teacher_id}",
                headers=teacher_headers,
            )
            assert teacher_response.status_code == 200, teacher_response.text
            teacher_classes = _json_body(teacher_response)
            counts_by_class = {
                row["id"]: row.get("student_count") for row in teacher_classes
            }
            assert len(teacher_classes) == 4
            assert all(
                counts_by_class[class_id] == expected_count
                for class_id, expected_count in resulting_classes
            )

            counter_response, counter_metrics = await _measured_request(
                client,
                "GET",
                "/classes",
                headers=principal_headers,
            )
            assert counter_response.status_code == 200, counter_response.text
            counter_rows = {
                row["id"]: row for row in _json_body(counter_response)
            }
            assert all(
                int(counter_rows[class_id].get("student_count", 0)) == expected_count
                for class_id, expected_count in resulting_classes
            )

            # The legacy full-roster export is an explicit student export and
            # must include every row, rather than a UI-sized preview.
            export_response, export_metrics = await _measured_request(
                client,
                "GET",
                f"/export/students?fmt=csv&class_id={fixture['import_class_id']}",
                headers=principal_headers,
            )
            assert export_response.status_code == 200, export_response.text
            assert _csv_student_rows(export_response.content) == 300

            # The class report route is read-only and must retain the complete
            # explicit roster, not a UI-sized preview.
            class_report_response, class_report_metrics = await _measured_request(
                client,
                "GET",
                f"/reports/class/{fixture['import_class_id']}",
                headers=principal_headers,
            )
            assert class_report_response.status_code == 200, class_report_response.text
            class_report_body = _json_body(class_report_response)
            class_report_count = len(class_report_body.get("student_summaries", []))

            report_export_response, report_export_metrics = await _measured_request(
                client,
                "GET",
                "/export/report/class_report"
                f"?format=csv&class_id={fixture['import_class_id']}",
                headers=principal_headers,
            )
            assert report_export_response.status_code == 200, report_export_response.text
            report_export_text = report_export_response.content.decode("utf-8-sig")
            report_export_section = report_export_text.split("# ملخص الطلاب", 1)
            report_export_count = 0
            if len(report_export_section) == 2:
                report_export_count = max(
                    0,
                    len(
                        list(
                            csv.reader(
                                io.StringIO(
                                    report_export_section[1].split("# ", 1)[0]
                                )
                            )
                        )
                    )
                    - 2,
                )

            # Precisely isolate the PDF renderer's roster row count.  The
            # monkeypatch is local to this test and never changes production
            # code or the ASGI process; it also avoids a PDF text extractor
            # dependency and does not log student values.
            import engines.export_engine as export_engine_module

            captured_pdf = {}
            original_build_table = export_engine_module._build_table

            def _capture_build_table(headers, rows, col_widths=None):
                if headers == ["التفاعلات", "نسبة الحضور", "الاسم"]:
                    captured_pdf["rows"] = len(rows)
                return original_build_table(headers, rows, col_widths)

            export_engine_module._build_table = _capture_build_table
            try:
                renderer = export_engine_module.ExportEngine(None)
                renderer._pdf_class_report(
                    [],
                    {
                        "student_summaries": [
                            {
                                "student_id": str(index),
                                "full_name": f"synthetic-{index}",
                                "attendance_rate": 100,
                                "interactions": 1,
                            }
                            for index in range(300)
                        ]
                    },
                    export_engine_module._ar_styles(),
                )
            finally:
                export_engine_module._build_table = original_build_table
            pdf_roster_count = captured_pdf.get("rows", 0)

            # SQL reads should stay bounded as rows grow.  This assertion is
            # intentionally loose about middleware/auth statements, while
            # preventing a roster-sized source-query loop.
            for measurements in (roster_metrics, attendance_metrics):
                source_counts = [metrics["sql_source"] for _, metrics in measurements]
                assert max(source_counts) <= min(source_counts) + 2, source_counts
                assert max(metrics["sql_total"] for _, metrics in measurements) <= 30

            snapshot = await _snapshot(session, school_id)
            assert snapshot["students"] == 31 + 50 + 100 + 300
            assert snapshot["attendance"] == 31 + 50 + 100 + 300

            print(
                "OPEN_ENDED_ROSTER_DEVELOPMENT_ONLY "
                f"roster_metrics={[(n, m['sql_total'], m['elapsed_ms'], m['peak_bytes']) for n, m in roster_metrics]} "
                f"attendance_metrics={[(n, m['sql_total'], m['elapsed_ms'], m['peak_bytes']) for n, m in attendance_metrics]} "
                f"teacher={teacher_metrics['sql_total']}:{teacher_metrics['elapsed_ms']}ms "
                f"counters={counter_metrics['sql_total']}:{counter_metrics['elapsed_ms']}ms "
                f"bulk={bulk_metrics['sql_total']}:{bulk_metrics['elapsed_ms']}ms "
                f"import={import_metrics['sql_total']}:{import_metrics['elapsed_ms']}ms "
                f"retry={retry_metrics['sql_total']}:{retry_metrics['elapsed_ms']}ms "
                f"student_export={export_metrics['sql_total']}:{export_metrics['elapsed_ms']}ms "
                f"report={class_report_count} report_export={report_export_count} "
                f"pdf_renderer_rows={pdf_roster_count} "
                f"report_export_sql={report_export_metrics['sql_total']}"
            )

            assert class_report_count == 300, (
                "class report omitted roster rows; fix "
                "backend/engines/reporting_engine.py:1145-1146 "
                "(the prior students limit=200)"
            )
            assert report_export_count == 300, (
                "class report export omitted roster rows; fix "
                "backend/engines/reporting_engine.py:1145-1146 "
                "(the prior students limit=200)"
            )
            assert pdf_roster_count == 300, (
                "PDF class-roster renderer omitted rows; "
                "backend/engines/export_engine.py PDF roster cap was removed"
            )
    finally:
        db.set_session(previous_session)
        if session is not None:
            await session.rollback()
            await session.close()
        if outer_transaction is not None and outer_transaction.is_active:
            await outer_transaction.rollback()
        if connection is not None:
            await connection.close()
        try:
            await _assert_cleanup(engine, school_id)
        finally:
            await engine.dispose()
            if tracemalloc.is_tracing():
                tracemalloc.stop()