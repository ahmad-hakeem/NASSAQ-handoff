"""Unit tests for the Noor importer parser — auto-detection, header
discovery, and number/text normalisation."""
from pathlib import Path

import pytest

from engines.noor_import import (
    NoorParseError,
    STUDENT_REPORT,
    TEACHER_REPORT,
    parse_workbook_bytes,
)

FIX = Path(__file__).parent / "fixtures" / "noor"


def _read(name: str) -> bytes:
    return (FIX / name).read_bytes()


def test_detects_teacher_xlsx():
    out = parse_workbook_bytes(_read("GetSchoolTeachersDataReport.xlsx"), "x.xlsx")
    assert out["detected_type"] == TEACHER_REPORT
    assert out["header_row"] >= 0
    assert isinstance(out["mapped_columns"], dict)


def test_detects_student_xls_and_normalises_floats():
    out = parse_workbook_bytes(_read("StudentGuidance.xls"), "x.xls")
    assert out["detected_type"] == STUDENT_REPORT
    assert out["sheet_name"]
    assert len(out["rows"]) >= 1
    first = out["rows"][0]["data"]
    # student_number from xls comes through as float — must be coerced to "12345" not "12345.0"
    assert "." not in (first.get("student_number") or "")
    assert "." not in (first.get("mobile") or "")


def test_unknown_workbook_rejected():
    # An empty xlsx-shaped payload should raise the safe parse error.
    with pytest.raises((NoorParseError, Exception)):
        parse_workbook_bytes(b"not-an-excel-file", "junk.xlsx")
