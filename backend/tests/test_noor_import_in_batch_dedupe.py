"""In-batch duplicate detection for Noor import.

Covers the regression where every row in the source file shared the
same student_number — preview said "0 added / 6 updated" and only one
DB row survived because rows 2..N silently UPDATEd the row inserted
by row 1.
"""
import pytest
from unittest.mock import patch, AsyncMock

from routes.noor_import_routes import (
    _annotate_student_rows,
    _annotate_teacher_rows,
    _commit_students,
    _summarise_counts,
)


def _student_row(idx, num, name="طالب", grade="1", section="أ"):
    return {
        "row_index": idx,
        "data": {
            "student_number": num,
            "full_name": name,
            "grade_code": grade,
            "section_code": section,
        },
    }


def _teacher_row(idx, nid, name="معلم", phone="0500000000"):
    return {
        "row_index": idx,
        "data": {
            "national_id": nid,
            "full_name": name,
            "phone": phone,
            "email": None,
        },
    }


@pytest.mark.asyncio
async def test_student_rows_with_same_number_flag_dupes_after_first():
    """Six rows sharing student_number=1234567899 → row 1 = insert,
    rows 2..6 = duplicate_in_file (the bug fix)."""
    rows = [_student_row(i + 1, "1234567899", name=f"طالب {i+1}") for i in range(6)]

    with patch(
        "routes.noor_import_routes.load_school_student_index", return_value={}
    ), patch(
        "routes.noor_import_routes.load_school_class_index", return_value={}
    ):
        out = await _annotate_student_rows(
            session=None, school_id="s1", parsed_rows=rows
        )

    verdicts = [r["dedupe"] for r in out]
    assert verdicts == [
        "insert",
        "duplicate_in_file",
        "duplicate_in_file",
        "duplicate_in_file",
        "duplicate_in_file",
        "duplicate_in_file",
    ]
    counts = _summarise_counts(out)
    assert counts["insert"] == 1
    assert counts["duplicate_in_file"] == 5
    assert counts["update"] == 0


@pytest.mark.asyncio
async def test_student_unique_numbers_all_insert():
    rows = [_student_row(i + 1, f"100{i}") for i in range(3)]
    with patch(
        "routes.noor_import_routes.load_school_student_index", return_value={}
    ), patch(
        "routes.noor_import_routes.load_school_class_index", return_value={}
    ):
        out = await _annotate_student_rows(
            session=None, school_id="s1", parsed_rows=rows
        )
    assert [r["dedupe"] for r in out] == ["insert", "insert", "insert"]
    assert _summarise_counts(out)["duplicate_in_file"] == 0


@pytest.mark.asyncio
async def test_teacher_rows_with_same_nid_flag_dupes_after_first():
    rows = [_teacher_row(i + 1, "1234567890", name=f"م {i+1}") for i in range(4)]

    with patch(
        "routes.noor_import_routes._load_teacher_index", return_value=({}, {})
    ):
        out = await _annotate_teacher_rows(
            session=None, school_id="s1", parsed_rows=rows
        )

    verdicts = [r["dedupe"] for r in out]
    assert verdicts == [
        "insert",
        "duplicate_in_file",
        "duplicate_in_file",
        "duplicate_in_file",
    ]


class _NestedCM:
    """Stand-in for AsyncSession.begin_nested() — does nothing."""
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class _FakeSession:
    def __init__(self):
        self.execute_calls = []
    def begin_nested(self): return _NestedCM()
    async def execute(self, *a, **kw):
        self.execute_calls.append((a, kw))
        return None


@pytest.mark.asyncio
async def test_commit_students_blocks_dupes_after_insert():
    """Row 1 inserts; rows 2..6 with same student_number are rejected
    as in-file duplicates — the original bug regression."""
    rows = [
        {"row_index": i + 1, "data": {"student_number": "1234567899",
                                       "full_name": f"طالب {i+1}",
                                       "grade_code": "1", "section_code": "أ"},
         "issues": []}
        for i in range(6)
    ]
    insert_mock = AsyncMock(side_effect=[f"sid-{i}" for i in range(6)])
    with patch("routes.noor_import_routes.load_school_student_index",
               new=AsyncMock(return_value={})), \
         patch("routes.noor_import_routes.load_school_class_index",
               new=AsyncMock(return_value={})), \
         patch("routes.noor_import_routes.insert_student_record_only",
               new=insert_mock), \
         patch("routes.noor_import_routes.update_student_mutable_fields",
               new=AsyncMock()):
        out = await _commit_students(
            session=_FakeSession(), school_id="s1", rows=rows,
            created_by="u1", ambiguous_treat_as_new=set(),
        )
    assert out["imported"] == 1
    assert out["duplicates"] == 5
    assert out["updated"] == 0
    assert out["failed"] == 0
    assert insert_mock.await_count == 1


@pytest.mark.asyncio
async def test_commit_students_blocks_dupes_after_live_update():
    """First sighting hits a pre-existing DB row (UPDATE). A second row
    with the same student_number must be rejected as duplicate — NOT
    allowed to re-update the same record (review finding #1)."""
    rows = [
        {"row_index": 1, "data": {"student_number": "9999",
                                   "full_name": "أحمد",
                                   "grade_code": "2", "section_code": "ب"},
         "issues": []},
        {"row_index": 2, "data": {"student_number": "9999",
                                   "full_name": "أحمد المكرر",
                                   "grade_code": "2", "section_code": "ب"},
         "issues": []},
    ]
    update_mock = AsyncMock()
    with patch("routes.noor_import_routes.load_school_student_index",
               new=AsyncMock(return_value={"9999": {"id": "exists-1",
                                                     "student_number": "9999",
                                                     "full_name": "أحمد",
                                                     "grade": "2",
                                                     "class_id": None}})), \
         patch("routes.noor_import_routes.load_school_class_index",
               new=AsyncMock(return_value={})), \
         patch("routes.noor_import_routes.insert_student_record_only",
               new=AsyncMock()), \
         patch("routes.noor_import_routes.update_student_mutable_fields",
               new=update_mock):
        out = await _commit_students(
            session=_FakeSession(), school_id="s1", rows=rows,
            created_by="u1", ambiguous_treat_as_new=set(),
        )
    assert out["updated"] == 1
    assert out["duplicates"] == 1
    assert out["imported"] == 0
    assert update_mock.await_count == 1, "UPDATE must run exactly once, not twice"


@pytest.mark.asyncio
async def test_annotate_invalid_first_does_not_poison_valid_second():
    """An invalid row (missing name) must NOT reserve its student_number
    against a later valid row (review finding #2)."""
    rows = [
        {"row_index": 1, "data": {"student_number": "555",
                                   "full_name": "",
                                   "grade_code": "1", "section_code": "أ"}},
        {"row_index": 2, "data": {"student_number": "555",
                                   "full_name": "صحيح",
                                   "grade_code": "1", "section_code": "أ"}},
    ]
    with patch("routes.noor_import_routes.load_school_student_index",
               new=AsyncMock(return_value={})), \
         patch("routes.noor_import_routes.load_school_class_index",
               new=AsyncMock(return_value={})):
        out = await _annotate_student_rows(
            session=None, school_id="s1", parsed_rows=rows
        )
    assert out[0]["dedupe"] == "skip"
    assert out[1]["dedupe"] == "insert", \
        "valid row must not be marked duplicate by an invalid earlier row"


def test_summarise_counts_includes_unclassified():
    rows = [
        {"dedupe": "insert", "class_unresolved": True},
        {"dedupe": "insert", "class_unresolved": False},
        {"dedupe": "duplicate_in_file", "class_unresolved": True},
    ]
    counts = _summarise_counts(rows)
    assert counts["unclassified"] == 2
    assert counts["insert"] == 2
    assert counts["duplicate_in_file"] == 1
    assert counts["total"] == 3
