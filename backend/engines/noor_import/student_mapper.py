"""
Student mapping for the Noor importer.

The Noor StudentGuidance report only carries:
    student_number, full_name, grade_code, section_code, mobile

There is no national_id, DOB, gender, email, or parent column. Therefore
the dedupe key is `(school_id, student_number)`. Students are written as
records only — NO `users` row, NO login. Class/section is resolved
deterministically; partial/no match → `class_unresolved`, never silently
created.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _norm_name(value: Optional[str]) -> str:
    if not value:
        return ""
    s = re.sub(r"\s+", " ", value).strip()
    return s


async def load_school_student_index(
    session, school_id: str
) -> Dict[str, Dict[str, Any]]:
    """Pre-load all students for a school as a dict keyed by student_number.

    Includes soft-deleted (`is_active = FALSE`) rows ON PURPOSE: the dedupe
    logic needs to SEE them so a corrected re-import of a previously-deleted
    student is classified as a RESTORE (reactivate the existing row) rather
    than a blind INSERT — which would otherwise collide with the surviving
    `uq_students_number_school` unique constraint. `is_active` is selected so
    callers can tell an active match (update) from a deleted one (restore).
    """
    result = await session.execute(
        text(
            """
            SELECT id, student_number, full_name, grade, class_id, is_active
            FROM students
            WHERE school_id = :sid
            """
        ),
        {"sid": school_id},
    )
    out: Dict[str, Dict[str, Any]] = {}
    for row in result.mappings().all():
        num = (row.get("student_number") or "").strip()
        if num:
            out[num] = dict(row)
    return out


async def load_school_class_index(
    session, school_id: str
) -> List[Dict[str, Any]]:
    """All classes for the school, used for deterministic (grade, section) match."""
    result = await session.execute(
        text(
            """
            SELECT id, name, grade_id, grade_level, section, capacity
            FROM classes
            WHERE school_id = :sid AND COALESCE(is_active, TRUE) = TRUE
            """
        ),
        {"sid": school_id},
    )
    return [dict(r) for r in result.mappings().all()]


def resolve_class(
    *,
    grade_code: Optional[str],
    section_code: Optional[str],
    class_index: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Deterministic match on the NORMALISED (grade, section) pair.
    Returns the class id on a unique match; None otherwise (including
    ambiguity — fail closed, never invent or guess a class).

    Tolerates the common Noor ↔ school shape differences (Arabic-Indic
    digits, stage prefixes like `الأول الابتدائي`, equivalent section
    labels `أ↔A↔١↔1`) via `class_match.normalize_*`.
    """
    from .class_match import normalize_grade, normalize_section

    g = normalize_grade(grade_code)
    s = normalize_section(section_code)
    if not g or not s:
        # BOTH grade and section are required for a match.
        return None
    matches = []
    for cls in class_index:
        cls_grade = normalize_grade(cls.get("grade_level") or cls.get("grade_id"))
        cls_section = normalize_section(cls.get("section"))
        if g and s and g == cls_grade and s == cls_section:
            matches.append(cls["id"])
    if len(matches) == 1:
        return matches[0]
    return None


async def insert_student_record_only(
    session,
    *,
    school_id: str,
    student_number: str,
    full_name: str,
    grade_code: Optional[str],
    section_code: Optional[str],
    class_id: Optional[str],
    mobile: Optional[str],
    created_by: str,
) -> str:
    """
    Insert a `students` row WITHOUT creating a `users` row (login-suppressed).
    Returns the new student id.
    """
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await session.execute(
        text(
            """
            INSERT INTO students
                (id, full_name, school_id, class_id, student_number, grade,
                 phone, is_active, created_at, updated_at)
            VALUES
                (:id, :name, :sid, :cid, :num, :grade,
                 :phone, TRUE, :now, :now)
            """
        ),
        {
            "id": sid,
            "name": full_name,
            "sid": school_id,
            "cid": class_id,
            "num": student_number,
            "grade": grade_code,
            "phone": mobile,
            "now": now,
        },
    )
    return sid


async def update_student_mutable_fields(
    session,
    *,
    student_id: str,
    school_id: str,
    full_name: Optional[str],
    grade_code: Optional[str],
    class_id: Optional[str],
    mobile: Optional[str],
    reactivate: bool = False,
    clear_class: bool = False,
) -> None:
    """Patch the small set of mutable Noor fields on an existing student.

    When ``reactivate`` is set (the RESTORE path — re-importing a previously
    soft-deleted student), `is_active` is forced back to TRUE so the corrected
    record becomes visible again. A restore always writes even if no other
    field changed, because reviving the row is itself the meaningful change.
    """
    now = datetime.now(timezone.utc)
    sets: List[str] = []
    params: Dict[str, Any] = {"id": student_id, "sid": school_id, "now": now}
    if full_name:
        sets.append("full_name = :name")
        params["name"] = full_name
    if grade_code is not None:
        sets.append("grade = :grade")
        params["grade"] = grade_code
    if clear_class:
        sets.append("class_id = NULL")
    elif class_id is not None:
        sets.append("class_id = :cid")
        params["cid"] = class_id
    if mobile is not None:
        sets.append("phone = :phone")
        params["phone"] = mobile
    if reactivate:
        sets.append("is_active = TRUE")
    if not sets:
        return
    sets.append("updated_at = :now")
    await session.execute(
        text(
            f"UPDATE students SET {', '.join(sets)} "
            f"WHERE id = :id AND school_id = :sid"
        ),
        params,
    )
