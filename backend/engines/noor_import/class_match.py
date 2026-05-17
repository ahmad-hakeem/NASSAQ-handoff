"""Normalization helpers for Noor class matching.

Goal: bridge the common shape differences between Noor exports and
the school's stored `classes.grade_level` / `classes.section` so a
deterministic match can still be made. Fail closed on ambiguity —
never invent a class.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

_AR_DIGITS = {
    "\u0660": "0", "\u0661": "1", "\u0662": "2", "\u0663": "3", "\u0664": "4",
    "\u0665": "5", "\u0666": "6", "\u0667": "7", "\u0668": "8", "\u0669": "9",
    "\u06F0": "0", "\u06F1": "1", "\u06F2": "2", "\u06F3": "3", "\u06F4": "4",
    "\u06F5": "5", "\u06F6": "6", "\u06F7": "7", "\u06F8": "8", "\u06F9": "9",
}

_TATWEEL = "\u0640"
_INVISIBLE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\ufeff]")

_GRADE_WORDS = {
    "الاول": 1, "الأول": 1, "الاولى": 1, "الأولى": 1, "اول": 1,
    "الثاني": 2, "الثانى": 2, "الثانية": 2, "ثاني": 2,
    "الثالث": 3, "الثالثة": 3, "ثالث": 3,
    "الرابع": 4, "الرابعة": 4, "رابع": 4,
    "الخامس": 5, "الخامسة": 5, "خامس": 5,
    "السادس": 6, "السادسة": 6, "سادس": 6,
    "السابع": 7, "السابعة": 7, "سابع": 7,
    "الثامن": 8, "الثامنة": 8, "ثامن": 8,
    "التاسع": 9, "التاسعة": 9, "تاسع": 9,
    "العاشر": 10, "العاشرة": 10, "عاشر": 10,
    "الحادي عشر": 11, "الحاديعشر": 11,
    "الثاني عشر": 12, "الثانيعشر": 12,
}

_STAGE_BASE = {
    "الابتدائي": 0,
    "الابتدائية": 0,
    "المتوسط": 6,
    "المتوسطة": 6,
    "الثانوي": 9,
    "الثانوية": 9,
}

_SECTION_LETTERS = {
    "أ": 1, "ا": 1, "إ": 1, "آ": 1,
    "ب": 2, "ج": 3, "د": 4,
    "ه": 5, "هـ": 5, "ة": 5,
    "و": 6, "ز": 7, "ح": 8, "ط": 9, "ي": 10,
}


def _ascii_digits(s: str) -> str:
    return "".join(_AR_DIGITS.get(c, c) for c in s)


def _strip_arabic_marks(s: str) -> str:
    # Drop combining diacritics (harakat), tatweel, invisibles
    s = s.replace(_TATWEEL, "")
    s = _INVISIBLE.sub("", s)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return s


def normalize_grade(value: Optional[str]) -> str:
    """Canonical digit string (`"1"`..`"12"`) when recognisable; else
    a normalised lowercase comparison key for tolerant equality.

    Handles:
      - Arabic-Indic ↔ ASCII digits
      - Tatweel/diacritics/whitespace
      - Leading-zero numeric forms (`"01"` → `"1"`)
      - Stage prefixes: `الصف الأول`, `الأول الابتدائي`,
        `الثاني المتوسط`, `الثالث الثانوي`, ...
    """
    if value is None:
        return ""
    s = _ascii_digits(str(value))
    s = _strip_arabic_marks(s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""

    # Pure ASCII digits — strip leading zeros, keep as canonical digit.
    if re.fullmatch(r"\d+", s):
        n = s.lstrip("0") or "0"
        # Reject pathological values; keep only 1..12 as canonical.
        if n.isdigit() and 1 <= int(n) <= 12:
            return str(int(n))
        return n  # comparable as-is, won't match a grade-level row

    # Strip the literal word "الصف" — purely a label prefix.
    cleaned = re.sub(r"\bالصف\b", "", s).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    # "الأول الابتدائي" → 1 + stage_base(0) = 1
    # "الثاني المتوسط"  → 2 + stage_base(6) = 8
    # "الثالث الثانوي"  → 3 + stage_base(9) = 12
    ord_val = None
    stage_val = 0
    # Longest token first so `"الثاني عشر"` (12) wins over `"الثاني"` (2).
    for word, n in sorted(_GRADE_WORDS.items(), key=lambda kv: -len(kv[0])):
        if word in cleaned:
            ord_val = n
            cleaned = cleaned.replace(word, "").strip()
            break
    for stage, base in _STAGE_BASE.items():
        if stage in cleaned:
            stage_val = base
            break

    if ord_val is not None:
        total = ord_val + stage_val
        if 1 <= total <= 12:
            return str(total)

    # Fallback: lowercase comparison key (Arabic has no case, but
    # this preserves the original for last-resort equality).
    return s.lower()


def normalize_section(value: Optional[str]) -> str:
    """Canonical lowercase digit string for sections.

    `أ ↔ A ↔ ١ ↔ 1` all collapse to `"1"`. Numeric inputs are
    Arabic-Indic-folded and leading zeros are stripped.
    """
    if value is None:
        return ""
    s = _ascii_digits(str(value))
    s = _strip_arabic_marks(s)
    s = re.sub(r"\s+", "", s).strip()
    if not s:
        return ""
    if re.fullmatch(r"\d+", s):
        return s.lstrip("0") or "0"
    lowered = s.lower()
    # Single Arabic letter section labels.
    if s in _SECTION_LETTERS:
        return str(_SECTION_LETTERS[s])
    # Single ASCII letter — fold A→1, B→2, ...
    if re.fullmatch(r"[a-z]", lowered):
        return str(ord(lowered) - ord("a") + 1)
    return lowered
