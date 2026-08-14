"""Canonical display-name resolution for subject rows.

Why this module exists
----------------------
``subjects`` is a REAL table: ``name`` is NOT NULL, while ``name_ar`` and
``name_en`` are nullable. Rows created through the paths that only set ``name``
(Noor import, seed/bootstrap, the generic create endpoints) therefore come back
from ``gd_find`` as ``{"name": "علوم", "name_ar": None, "name_en": None}`` —
the KEY is always present, its VALUE is ``None``.

That makes the idiomatic-looking

    sub_map = {s["id"]: s.get("name_ar", s.get("name", "")) for s in subs}

silently wrong: ``dict.get(key, default)`` only returns ``default`` when the key
is MISSING, never when its value is ``None``. Every such map yielded ``None``
for a perfectly valid subject, which the caller then rendered as "غير محدد"
(or leaked as a literal ``null`` in the API payload) on the parent home widget,
the parent/student weekly schedule and the student "my teachers" list.

Use :func:`subject_display_name` / :func:`build_subject_name_map` for any
surface that renders a subject name so the fallback chain stays identical
everywhere: Arabic name → canonical name → English name.
"""
from typing import Iterable, Mapping, Optional

__all__ = ["subject_display_name", "build_subject_name_map"]

# Ordered preference for an Arabic-first UI.
_NAME_FIELDS = ("name_ar", "name", "name_en")


def subject_display_name(subject: Optional[Mapping]) -> str:
    """Return the best available display name for a subject row.

    Falls through ``name_ar`` → ``name`` → ``name_en``, treating ``None`` and
    whitespace-only values as absent. Returns ``""`` when the row carries no
    usable name at all, so callers keep control of their own placeholder.
    """
    if not subject:
        return ""
    for field in _NAME_FIELDS:
        value = subject.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def build_subject_name_map(subjects: Optional[Iterable[Mapping]]) -> dict:
    """Map ``subject id -> display name`` for the rows that have a name.

    Nameless rows are omitted rather than mapped to ``""`` so a caller's
    ``name_map.get(sid) or <row fallback> or <placeholder>`` chain keeps
    working instead of short-circuiting on an empty string.
    """
    name_map = {}
    for subject in subjects or []:
        sid = subject.get("id")
        if not sid:
            continue
        name = subject_display_name(subject)
        if name:
            name_map[sid] = name
    return name_map
