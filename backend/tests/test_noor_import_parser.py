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


def test_real_noor_xls_with_school_info_sheet_parses_students():
    """The real Noor .xls export from production has a leading 'School Info'
    sheet and the student data on the second sheet — must still detect as
    students with the correct row count."""
    out = parse_workbook_bytes(_read("student_guidance_real.xls"), "StudentGuidance.xls")
    assert out["detected_type"] == STUDENT_REPORT
    assert len(out["rows"]) == 6
    first = out["rows"][0]["data"]
    assert first["full_name"]
    assert first["student_number"]
    assert "." not in first["student_number"]


def test_html_disguised_xls_parses_students():
    """Noor exports an HTML <table> with .xls extension; both binary
    readers reject it. The pandas/lxml fallback must rescue it."""
    out = parse_workbook_bytes(
        _read("student_guidance_html.xls"), "student_guidance_html.xls"
    )
    assert out["detected_type"] == STUDENT_REPORT
    assert len(out["rows"]) == 3
    assert out["rows"][0]["data"]["full_name"] == "عمر علي"


def test_corrupt_file_raises_with_diagnostics():
    """A genuinely corrupt file must still surface the safe Arabic
    message AND carry server-only diagnostics for the route to log."""
    with pytest.raises(NoorParseError) as ei:
        parse_workbook_bytes(b"\x00\x01\x02not-an-excel-file" * 8, "junk.xls")
    err = ei.value
    assert "تعذّر قراءة الملف" in str(err)
    assert err.diagnostics is not None
    diag = err.diagnostics
    assert diag["filename"] == "junk.xls"
    assert diag["size"] > 0
    assert len(diag["head_hex"]) == 32  # first 16 bytes
    assert diag["looks_like_html"] is False
    readers = diag["readers_tried"]
    assert len(readers) >= 2
    for r in readers:
        assert r["reader"] in {"_read_xls", "_read_xlsx", "_read_html"}
        assert r["error_type"]
        assert r["error_message"]
