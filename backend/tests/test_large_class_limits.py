"""Focused regression tests for large class reports and student portal counts."""

from types import SimpleNamespace

import pytest

from engines.export_engine import ExportEngine, LongTable, _ar_styles
from engines.reporting_engine import CLASS_REPORT_BATCH_SIZE, ReportingEngine
from src.modules.portals.controllers import student_portal_routes as portal_routes
from dependencies import UserRole


@pytest.mark.parametrize("student_count", [100, 300])
def test_class_report_pdf_keeps_all_students_and_repeats_header(student_count):
    """The class report table must not silently drop rows after the first 30."""
    story = []
    summaries = [
        {
            "full_name": f"Student {index}",
            "attendance_rate": 90,
            "interactions": index,
        }
        for index in range(student_count)
    ]

    ExportEngine(None)._pdf_class_report(
        story,
        {"student_summaries": summaries},
        _ar_styles(),
    )

    table = story[-1]
    assert isinstance(table, LongTable)
    assert table.repeatRows == 1
    assert len(table._cellvalues) == student_count + 1
    assert table._cellvalues[-1][-1].text == f"Student {student_count - 1}"
    assert all(cell.text for cell in table._cellvalues[0])


def _route(router, path):
    return next(route.endpoint for route in router.routes if route.path == path)


def _portal_router():
    db = SimpleNamespace(session=object())

    def require_roles(_roles):
        async def dependency():
            return None

        return dependency

    return portal_routes.setup_student_portal_routes(
        db, None, require_roles, UserRole
    )


@pytest.mark.asyncio
async def test_student_profile_uses_exact_active_tenant_count(monkeypatch):
    student = {
        "id": "student-1",
        "class_id": "class-1",
        "school_id": "school-1",
        "full_name": "Student 1",
    }
    count_calls = []

    async def find_one(_session, collection, filters):
        if collection == "students":
            return student
        return None

    async def count(_session, collection, filters):
        count_calls.append((collection, filters))
        if collection == "students":
            return 301
        return 0

    async def find(_session, collection, filters, **_kwargs):
        assert collection != "students"
        if collection == "grades":
            return []
        return []

    monkeypatch.setattr(portal_routes, "gd_find_one", find_one)
    monkeypatch.setattr(portal_routes, "gd_count", count)
    monkeypatch.setattr(portal_routes, "gd_find", find)

    profile = await _route(_portal_router(), "/student-portal/profile")(
        current_user={
            "id": "student-1",
            "student_id": "student-1",
            "tenant_id": "school-1",
        }
    )

    class_counts = [
        filters for collection, filters in count_calls if collection == "students"
    ]
    assert class_counts == [{
        "class_id": "class-1",
        "school_id": "school-1",
        "is_active": {"$ne": False},
    }]
    assert profile["stats"]["class_size"] == 301


@pytest.mark.asyncio
async def test_student_points_ranks_large_class_in_bounded_id_batches(monkeypatch):
    student_ids = [f"student-{index}" for index in range(1001)]
    student = {
        "id": student_ids[0],
        "class_id": "class-1",
        "school_id": "school-1",
        "full_name": "Student 0",
    }
    count_calls = []
    row_calls = []

    async def find_one(_session, collection, _filters):
        if collection == "students":
            return student
        return None

    async def count(_session, collection, filters):
        count_calls.append((collection, filters))
        if collection == "students":
            return len(student_ids)
        return 0

    async def find(_session, collection, _filters, **_kwargs):
        if collection in {"participation_records", "grades"}:
            return []
        raise AssertionError(f"unexpected student materialisation: {collection}")

    async def distinct(_session, collection, field, filters):
        assert collection == "students"
        assert field == "id"
        assert filters == {
            "class_id": "class-1",
            "school_id": "school-1",
            "is_active": {"$ne": False},
        }
        return student_ids

    async def rows(_session, collection, filters, **kwargs):
        id_batch = filters["student_id"]["$in"]
        row_calls.append((collection, id_batch, kwargs))
        if False:  # pragma: no cover - keeps this an async generator
            yield {}

    monkeypatch.setattr(portal_routes, "gd_find_one", find_one)
    monkeypatch.setattr(portal_routes, "gd_count", count)
    monkeypatch.setattr(portal_routes, "gd_find", find)
    monkeypatch.setattr(portal_routes, "gd_distinct", distinct)
    monkeypatch.setattr(portal_routes, "gd_iter_rows", rows)

    points = await _route(_portal_router(), "/student-portal/points")(
        current_user={
            "id": student_ids[0],
            "student_id": student_ids[0],
            "tenant_id": "school-1",
        }
    )

    class_counts = [
        filters for collection, filters in count_calls if collection == "students"
    ]
    assert class_counts == [{
        "class_id": "class-1",
        "school_id": "school-1",
        "is_active": {"$ne": False},
    }]
    assert points["class_size"] == len(student_ids)
    assert points["rank"] == 1

    assert len(row_calls) == 4 * 3
    assert all(len(ids) <= portal_routes.CLASSMATE_ID_BATCH_SIZE
               for _collection, ids, _kwargs in row_calls)
    for collection in {
        "participation_records",
        "grades",
        "attendance",
        "behaviour_records",
    }:
        batches = [ids for name, ids, _kwargs in row_calls if name == collection]
        assert [student_id for batch in batches for student_id in batch] == student_ids


@pytest.mark.asyncio
async def test_student_points_streams_beyond_aggregate_row_cap(monkeypatch):
    """Ranking must include every matching activity row, not _gd_aggregate's 50k cap."""
    student_ids = ["student-0", "student-1"]
    student = {
        "id": student_ids[0],
        "class_id": "class-1",
        "school_id": "school-1",
        "full_name": "Student 0",
    }
    rows_seen = 0

    async def find_one(_session, collection, _filters):
        if collection == "students":
            return student
        return None

    async def count(_session, collection, _filters):
        if collection == "students":
            return len(student_ids)
        return 0

    async def find(_session, collection, _filters, **_kwargs):
        if collection in {"participation_records", "grades"}:
            return []
        raise AssertionError(f"unexpected student materialisation: {collection}")

    async def distinct(_session, collection, field, _filters):
        assert collection == "students"
        assert field == "id"
        return student_ids

    async def rows(_session, collection, _filters, **_kwargs):
        nonlocal rows_seen
        if collection == "participation_records":
            # Generate lazily: the regression exercises streaming without
            # constructing a >50,000-row fixture in memory.
            for _ in range(50_001):
                rows_seen += 1
                yield {"student_id": student_ids[1], "points": 1}

    monkeypatch.setattr(portal_routes, "gd_find_one", find_one)
    monkeypatch.setattr(portal_routes, "gd_count", count)
    monkeypatch.setattr(portal_routes, "gd_find", find)
    monkeypatch.setattr(portal_routes, "gd_distinct", distinct)
    monkeypatch.setattr(portal_routes, "gd_iter_rows", rows)

    points = await _route(_portal_router(), "/student-portal/points")(
        current_user={
            "id": student_ids[0],
            "student_id": student_ids[0],
            "tenant_id": "school-1",
        }
    )

    assert rows_seen == 50_001
    assert points["class_size"] == 2
    assert points["rank"] == 2


@pytest.mark.asyncio
async def test_generated_class_report_reads_every_student_without_attendance_n_plus_one(
    monkeypatch,
):
    """The upstream generator must retain >300 students and avoid row N+1."""
    student_ids = [f"student-{index}" for index in range(1001)]
    students = [
        {"id": student_id, "full_name": f"Student {index}"}
        for index, student_id in enumerate(student_ids)
    ]
    report = ReportingEngine(SimpleNamespace(session=object()))
    paginated_calls = []
    row_calls = []
    count_calls = []

    async def paginated(collection, query, **kwargs):
        paginated_calls.append((collection, query, kwargs))
        return students

    async def find_one(_session, collection, filters):
        if collection == "classes":
            assert filters == {"id": "class-1", "school_id": "school-1"}
            return {"id": "class-1", "name": "Class 1"}
        assert collection == "ai_insights"
        return None

    async def find(_session, collection, _filters, **_kwargs):
        assert collection == "class_sessions"
        return [{"id": "session-1"}]

    async def count(_session, collection, filters):
        count_calls.append((collection, filters))
        assert collection == "attendance"
        assert filters["class_id"] == "class-1"
        return 0

    async def rows(_session, collection, filters, **kwargs):
        row_calls.append((collection, filters, kwargs))
        if False:  # pragma: no cover - keeps this an async generator
            yield {}

    monkeypatch.setattr(report, "_paginated_find", paginated)
    monkeypatch.setattr("engines.reporting_engine.gd_find_one", find_one)
    monkeypatch.setattr("engines.reporting_engine.gd_find", find)
    monkeypatch.setattr("engines.reporting_engine.gd_count", count)
    monkeypatch.setattr("engines.reporting_engine.gd_iter_rows", rows)

    result = await report.generate_class_report("class-1", "school-1")

    assert paginated_calls == [(
        "students",
        {
            "class_id": "class-1",
            "school_id": "school-1",
            "is_active": True,
        },
        {"page_size": CLASS_REPORT_BATCH_SIZE},
    )]
    assert result["total_students"] == 1001
    assert len(result["student_summaries"]) == 1001
    assert result["student_summaries"][-1]["full_name"] == "Student 1000"

    # Two class-wide counts only; no attendance count query was issued for a
    # particular student.
    assert len(count_calls) == 2
    assert all("student_id" not in filters for _collection, filters in count_calls)

    assert len(row_calls) == 6  # 3 ID batches × interactions + attendance
    for collection in ("session_interactions", "attendance"):
        calls = [call for call in row_calls if call[0] == collection]
        assert len(calls) == 3
        assert all(len(call[1]["student_id"]["$in"]) <= CLASS_REPORT_BATCH_SIZE
                   for call in calls)
        assert [
            student_id
            for call in calls
            for student_id in call[1]["student_id"]["$in"]
        ] == student_ids
        assert all(call[2] == {} for call in calls)