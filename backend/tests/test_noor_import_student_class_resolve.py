"""Unit tests for deterministic Noor student class resolution."""
from engines.noor_import.student_mapper import resolve_class


def _cls(cid, grade, section):
    return {"id": cid, "grade_level": grade, "grade_id": grade, "section": section}


def test_unique_match_resolves():
    classes = [
        _cls("c1", "1", "1"),
        _cls("c2", "1", "2"),
    ]
    assert resolve_class(grade_code="1", section_code="1", class_index=classes) == "c1"


def test_no_match_returns_none():
    classes = [_cls("c1", "1", "1")]
    assert resolve_class(grade_code="9", section_code="9", class_index=classes) is None


def test_ambiguous_returns_none_no_silent_create():
    # Two classes match same grade+section — never pick arbitrarily.
    classes = [_cls("c1", "1", "1"), _cls("c2", "1", "1")]
    assert resolve_class(grade_code="1", section_code="1", class_index=classes) is None


def test_only_grade_no_section_returns_none():
    classes = [_cls("c1", "1", "1")]
    assert resolve_class(grade_code="1", section_code=None, class_index=classes) is None


def test_empty_inputs_return_none():
    assert resolve_class(grade_code=None, section_code=None, class_index=[]) is None
