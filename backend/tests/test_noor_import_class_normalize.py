"""Unit tests for Noor class-match normalization (task #387).

Locks the bug: previously `resolve_class` required byte-equal
`grade_code` / `section_code`, so a Noor row carrying
`الأول الابتدائي` / `أ` against a class stored as `1` / `A` would
return None and route every row to "class_unresolved".
"""
import pytest

from engines.noor_import.class_match import normalize_grade, normalize_section
from engines.noor_import.student_mapper import resolve_class


def _cls(cid, grade, section):
    return {"id": cid, "grade_level": grade, "grade_id": grade, "section": section}


# --- normalize_grade ---------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("1", "1"),
    ("01", "1"),
    ("\u0661", "1"),                    # Arabic-Indic 1
    ("الصف الأول", "1"),
    ("الأول الابتدائي", "1"),
    ("الثاني المتوسط", "8"),
    ("الثالث الثانوي", "12"),
    ("الثاني عشر", "12"),
    ("الصف الثاني عشر", "12"),
    ("الحادي عشر", "11"),
    ("الصف الحادي عشر", "11"),
    (" \u0640الصف الرابع\u0640 ", "4"),  # tatweel + spaces
    ("", ""),
    (None, ""),
])
def test_normalize_grade(raw, expected):
    assert normalize_grade(raw) == expected


# --- normalize_section -------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("أ", "1"), ("A", "1"), ("a", "1"), ("\u0661", "1"), ("1", "1"),
    ("ب", "2"), ("B", "2"),
    ("ج", "3"),
    ("هـ", "5"),
    ("و", "6"),
    ("", ""), (None, ""),
])
def test_normalize_section(raw, expected):
    assert normalize_section(raw) == expected


# --- resolve_class ----------------------------------------------------

def test_locks_bug_noor_stage_prefix_resolves_against_digit_class():
    """The original bug: row says `الأول الابتدائي` / `أ`, class is
    stored as `1` / `أ`. Previously returned None; must now resolve."""
    classes = [_cls("c1", "1", "أ")]
    assert resolve_class(
        grade_code="الأول الابتدائي",
        section_code="أ",
        class_index=classes,
    ) == "c1"


def test_section_letter_to_ascii_equivalent():
    """`أ` (Noor) ↔ `A` (school) must collapse to the same key."""
    classes = [_cls("c1", "1", "A")]
    assert resolve_class(
        grade_code="1", section_code="أ", class_index=classes
    ) == "c1"


def test_arabic_indic_digits_resolve():
    classes = [_cls("c1", "2", "1")]
    assert resolve_class(
        grade_code="\u0662", section_code="\u0661", class_index=classes
    ) == "c1"


def test_leading_zero_grade_resolves():
    classes = [_cls("c1", "1", "1")]
    assert resolve_class(
        grade_code="01", section_code="1", class_index=classes
    ) == "c1"


def test_ambiguous_normalised_match_fails_closed():
    """Two classes normalise to the same (grade, section) → None."""
    classes = [_cls("c1", "1", "أ"), _cls("c2", "01", "A")]
    assert resolve_class(
        grade_code="1", section_code="1", class_index=classes
    ) is None


def test_unrelated_grade_still_returns_none():
    classes = [_cls("c1", "1", "1")]
    assert resolve_class(
        grade_code="9", section_code="1", class_index=classes
    ) is None
