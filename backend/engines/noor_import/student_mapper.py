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
    """Pre-load all students for a school as a dict keyed by student_number."""
    result = await session.execute(
        text(
            """
            SELECT id, student_number, full_name, grade, class_id
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
            SELECT id, name, grade_id, grade_level, section
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
    Deterministic match: a class matches when BOTH grade and section
    align. Returns the class id on a unique match; None otherwise.
    Never invents a class.
    """
    if not grade_code and not section_code:
        return None
    g = (grade_code or "").strip()
    s = (section_code or "").strip()
    matches = []
    for cls in class_index:
        cls_grade = (cls.get("grade_level") or cls.get("grade_id") or "").strip()
        cls_section = (cls.get("section") or "").strip()
        if g and cls_grade and (g == cls_grade or g.endswith(cls_grade) or cls_grade.endswith(g)):
            if s and cls_section and s == cls_section:
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
) -> None:
    """Patch the small set of mutable Noor fields on an existing student."""
    now = datetime.now(timezone.utc)
    sets: List[str] = []
    params: Dict[str, Any] = {"id": student_id, "sid": school_id, "now": now}
    if full_name:
        sets.append("full_name = :name")
        params["name"] = full_name
    if grade_code is not None:
        sets.append("grade = :grade")
        params["grade"] = grade_code
    if class_id is not None:
        sets.append("class_id = :cid")
        params["cid"] = class_id
    if mobile is not None:
        sets.append("phone = :phone")
        params["phone"] = mobile
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
