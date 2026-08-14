"""
Canonical academic grade catalogue (single source of truth).

The product approves exactly twelve grade levels, grouped into the same
three educational stages used everywhere else in the codebase
(``primary`` 1–6, ``middle`` 7–9, ``high`` 10–12 — see
``utils/stage_grade.py``). Free-text grade entry caused duplicate
variants ("الصف الأول الابتدائي" vs "الأول ابتدائي" vs "1-أ"), so any
surface that persists a *new* grade value (today: the Independent-Teacher
create-class flow, which auto-creates a ``grade_levels`` row from the
selected label) must validate against this list and store the exact
canonical label.

Mirrors ``frontend/src/utils/stageGrade.js`` (``CANONICAL_GRADES``). Keep
the two in sync. The frontend dropdown is a UX convenience; this module is
the fail-closed security/data-integrity boundary so a tampered payload
cannot persist an off-list grade.
"""

from typing import Optional, Dict, Any, List


# Ordered 1..12. ``label_ar`` is the canonical stored value.
CANONICAL_GRADES: List[Dict[str, Any]] = [
    {"grade": 1,  "stage": "primary", "label_ar": "الصف الأول الابتدائي",  "label_en": "Grade 1"},
    {"grade": 2,  "stage": "primary", "label_ar": "الصف الثاني الابتدائي", "label_en": "Grade 2"},
    {"grade": 3,  "stage": "primary", "label_ar": "الصف الثالث الابتدائي", "label_en": "Grade 3"},
    {"grade": 4,  "stage": "primary", "label_ar": "الصف الرابع الابتدائي", "label_en": "Grade 4"},
    {"grade": 5,  "stage": "primary", "label_ar": "الصف الخامس الابتدائي", "label_en": "Grade 5"},
    {"grade": 6,  "stage": "primary", "label_ar": "الصف السادس الابتدائي", "label_en": "Grade 6"},
    {"grade": 7,  "stage": "middle",  "label_ar": "الصف الأول المتوسط",    "label_en": "Grade 7"},
    {"grade": 8,  "stage": "middle",  "label_ar": "الصف الثاني المتوسط",   "label_en": "Grade 8"},
    {"grade": 9,  "stage": "middle",  "label_ar": "الصف الثالث المتوسط",   "label_en": "Grade 9"},
    {"grade": 10, "stage": "high",    "label_ar": "الصف الأول الثانوي",    "label_en": "Grade 10"},
    {"grade": 11, "stage": "high",    "label_ar": "الصف الثاني الثانوي",   "label_en": "Grade 11"},
    {"grade": 12, "stage": "high",    "label_ar": "الصف الثالث الثانوي",   "label_en": "Grade 12"},
]


def _collapse_ws(value: str) -> str:
    """Trim and collapse internal whitespace runs to a single space."""
    return " ".join(str(value).split())


# Lookup by whitespace-normalized canonical Arabic label.
_LABEL_INDEX: Dict[str, Dict[str, Any]] = {
    _collapse_ws(g["label_ar"]): g for g in CANONICAL_GRADES
}
# Lookup by grade number.
_NUMBER_INDEX: Dict[int, Dict[str, Any]] = {g["grade"]: g for g in CANONICAL_GRADES}


def canonical_grade_labels() -> List[str]:
    """The twelve approved canonical Arabic labels, in order."""
    return [g["label_ar"] for g in CANONICAL_GRADES]


def normalize_canonical_grade(value: Any) -> Optional[Dict[str, Any]]:
    """
    Resolve any grade-ish input to its canonical entry, or ``None``.

    Accepts the exact canonical Arabic label (whitespace-insensitive) or a
    grade number (int / digit-string, 1–12). Deliberately strict: arbitrary
    free text ("1-أ", "اول ابتدائي", typos) returns ``None`` so callers can
    fail closed. Returns a *copy* of the catalogue entry.
    """
    if value is None:
        return None

    if isinstance(value, bool):  # guard: bool is an int subclass
        return None

    if isinstance(value, (int, float)):
        entry = _NUMBER_INDEX.get(int(value))
        return dict(entry) if entry else None

    raw = _collapse_ws(value)
    if not raw:
        return None

    if raw.isdigit():
        entry = _NUMBER_INDEX.get(int(raw))
        return dict(entry) if entry else None

    entry = _LABEL_INDEX.get(raw)
    return dict(entry) if entry else None


def is_canonical_grade(value: Any) -> bool:
    """True iff ``value`` resolves to one of the twelve approved grades."""
    return normalize_canonical_grade(value) is not None
