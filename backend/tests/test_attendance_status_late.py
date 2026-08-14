"""Regression tests for the four-status attendance contract.

Covers the boundary added when `late` (متأخر) was promoted to a first-class
status alongside the existing present/absent/excused set:

  * `TeacherAttendanceRecord` Pydantic model accepts each canonical literal.
  * `AttendanceRecord` (student-side) accepts each canonical literal.
  * Both models reject unknown values at the API boundary (422 surface).
  * The default factory still yields `present` for back-compat with callers
    that omit `status`.
"""
import pytest
from pydantic import ValidationError

from src.modules.attendance.controllers.teacher_attendance_routes import (
    TeacherAttendanceRecord,
    AttendanceStatusLiteral as TeacherStatusLiteral,
)
from src.modules.attendance.controllers.attendance_routes import (
    AttendanceRecord,
    AttendanceCreate,
    AttendanceStatusLiteral as StudentStatusLiteral,
)


CANONICAL = ("present", "absent", "late", "excused")


def test_canonical_set_matches_models():
    """The Literal mirrors the four canonical statuses, in order."""
    # __args__ gives the Literal members in declaration order.
    assert TeacherStatusLiteral.__args__ == CANONICAL
    assert StudentStatusLiteral.__args__ == CANONICAL


@pytest.mark.parametrize("status", CANONICAL)
def test_teacher_record_accepts_each_canonical_status(status):
    rec = TeacherAttendanceRecord(
        teacher_id="t-1", date="2026-05-14", status=status
    )
    assert rec.status == status


@pytest.mark.parametrize("status", CANONICAL)
def test_student_record_accepts_each_canonical_status(status):
    rec = AttendanceRecord(student_id="s-1", status=status)
    assert rec.status == status


@pytest.mark.parametrize("bad", ["LATE", "tardy", "أبي", "", " ", "left_early"])
def test_teacher_record_rejects_unknown_status(bad):
    with pytest.raises(ValidationError):
        TeacherAttendanceRecord(teacher_id="t-1", date="2026-05-14", status=bad)


@pytest.mark.parametrize("bad", ["LATE", "tardy", "left_early", "حاضر", "x"])
def test_student_record_rejects_unknown_status(bad):
    with pytest.raises(ValidationError):
        AttendanceRecord(student_id="s-1", status=bad)


def test_student_record_defaults_to_present():
    """Legacy callers that omit `status` still get a valid record."""
    assert AttendanceRecord(student_id="s-1").status == "present"
    assert AttendanceCreate(
        student_id="s-1",
        section_id="sec-1",
        attendance_date="2026-05-14",
    ).status == "present"
