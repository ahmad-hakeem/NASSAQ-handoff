"""Regression coverage for complete, paged student exports."""

from types import SimpleNamespace

import pytest

from src.modules.bulk_import.controllers import bulk_import_export_routes as routes


@pytest.mark.asyncio
async def test_student_export_pages_past_ten_thousand_rows_without_db_writes(
    monkeypatch,
):
    school_id = "export-school"
    class_id = "export-class"
    students = [
        {
            "id": f"student-{index:05d}",
            "school_id": school_id,
            "class_id": class_id,
            "is_active": True,
            "first_name": f"Student {index}",
            "full_name": f"Student {index}",
            "national_id": f"{index:010d}",
            "grade": "1",
        }
        for index in range(10_001)
    ]
    student_offsets = []
    class_lookups = []

    async def fake_gd_find(
        _session,
        collection,
        filters=None,
        order_by=None,
        desc_order=True,
        limit=None,
        offset=None,
    ):
        assert order_by == "id"
        assert desc_order is False
        start = offset or 0
        if collection == "students":
            assert filters == {"school_id": school_id, "is_active": True}
            student_offsets.append((start, limit))
            return students[start:start + limit]
        if collection == "classes":
            class_lookups.append((filters, limit))
            assert filters["school_id"] == school_id
            assert filters["is_active"] == {"$ne": False}
            assert filters["id"] == {"$in": [class_id]}
            return [{"id": class_id, "section": "A"}]
        raise AssertionError(f"unexpected collection: {collection}")

    monkeypatch.setattr(routes, "gd_find", fake_gd_find)

    frame, filename = await routes._export_students(
        SimpleNamespace(session=object()),
        school_id,
    )

    assert filename == "تصدير_الطلاب.xlsx"
    assert len(frame) == 10_001
    assert frame.iloc[-1]["رقم الهوية"] == "0000010000"
    assert [offset for offset, _limit in student_offsets] == list(range(0, 11_000, 1_000))
    assert all(limit == 1_000 for _offset, limit in student_offsets)
    assert len(class_lookups) == 1