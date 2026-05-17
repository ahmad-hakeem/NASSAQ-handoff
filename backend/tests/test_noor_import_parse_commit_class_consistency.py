"""Regression: parse-time class_id annotation MUST equal commit-time
class write for the same row (task #387).

Locks the invariant that the preview never lies — when the preview
says a row resolves to a class, the commit MUST attach that class;
when the preview says unresolved, the commit MUST leave it NULL.
"""
from unittest.mock import AsyncMock, patch

import pytest

from routes.noor_import_routes import _annotate_student_rows, _commit_students


class _NestedCM:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class _FakeSession:
    def begin_nested(self): return _NestedCM()
    async def execute(self, *a, **kw): return None


def _row(idx, num, name, grade, section):
    return {
        "row_index": idx,
        "data": {
            "student_number": num,
            "full_name": name,
            "grade_code": grade,
            "section_code": section,
        },
    }


# A school with class_id "c-grade1-A" for grade=1, section=A AND a
# class_id "c-grade2-A" for grade=2, section=A — only the matching
# pair must resolve. A third class with normalized-equal keys would
# trigger ambiguity (covered separately).
_CLASS_INDEX = [
    {"id": "c-grade1-A", "grade_level": "1", "grade_id": "1", "section": "A"},
    {"id": "c-grade2-A", "grade_level": "2", "grade_id": "2", "section": "A"},
]


@pytest.mark.asyncio
async def test_preview_resolved_then_commit_writes_class():
    """`الأول الابتدائي` / `أ` resolves to c-grade1-A in BOTH the
    preview annotation and the commit write — the literal-match bug
    fix from #387."""
    rows = [_row(1, "1000", "طالب أ", "الأول الابتدائي", "أ")]
    with patch("routes.noor_import_routes.load_school_student_index",
               new=AsyncMock(return_value={})), \
         patch("routes.noor_import_routes.load_school_class_index",
               new=AsyncMock(return_value=_CLASS_INDEX)):
        annotated = await _annotate_student_rows(
            session=None, school_id="s1", parsed_rows=rows
        )
    assert annotated[0]["class_id"] == "c-grade1-A"
    assert annotated[0]["class_unresolved"] is False

    insert_mock = AsyncMock(return_value="new-1")
    with patch("routes.noor_import_routes.load_school_student_index",
               new=AsyncMock(return_value={})), \
         patch("routes.noor_import_routes.load_school_class_index",
               new=AsyncMock(return_value=_CLASS_INDEX)), \
         patch("routes.noor_import_routes.insert_student_record_only",
               new=insert_mock), \
         patch("routes.noor_import_routes.update_student_mutable_fields",
               new=AsyncMock()):
        out = await _commit_students(
            session=_FakeSession(), school_id="s1",
            rows=[{**annotated[0], "issues": []}],
            created_by="u1", ambiguous_treat_as_new=set(),
        )
    assert out["imported"] == 1
    assert out["unclassified"] == 0
    # Confirm the INSERT call carried the matching class_id — no NULL.
    kwargs = insert_mock.await_args.kwargs
    assert kwargs.get("class_id") == "c-grade1-A"


@pytest.mark.asyncio
async def test_preview_unresolved_then_commit_keeps_null():
    """Grade `9` doesn't exist in the school → preview marks
    class_unresolved, commit MUST insert with class_id=NULL and
    count it under `unclassified`."""
    rows = [_row(1, "1001", "طالب ب", "9", "أ")]
    with patch("routes.noor_import_routes.load_school_student_index",
               new=AsyncMock(return_value={})), \
         patch("routes.noor_import_routes.load_school_class_index",
               new=AsyncMock(return_value=_CLASS_INDEX)):
        annotated = await _annotate_student_rows(
            session=None, school_id="s1", parsed_rows=rows
        )
    assert annotated[0]["class_id"] is None
    assert annotated[0]["class_unresolved"] is True

    insert_mock = AsyncMock(return_value="new-2")
    with patch("routes.noor_import_routes.load_school_student_index",
               new=AsyncMock(return_value={})), \
         patch("routes.noor_import_routes.load_school_class_index",
               new=AsyncMock(return_value=_CLASS_INDEX)), \
         patch("routes.noor_import_routes.insert_student_record_only",
               new=insert_mock), \
         patch("routes.noor_import_routes.update_student_mutable_fields",
               new=AsyncMock()):
        out = await _commit_students(
            session=_FakeSession(), school_id="s1",
            rows=[{**annotated[0], "issues": []}],
            created_by="u1", ambiguous_treat_as_new=set(),
        )
    assert out["imported"] == 1
    assert out["unclassified"] == 1
    kwargs = insert_mock.await_args.kwargs
    assert kwargs.get("class_id") is None
