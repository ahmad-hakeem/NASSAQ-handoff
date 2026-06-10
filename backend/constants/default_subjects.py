"""Canonical default subject catalog for NASSAQ real schools.

Single source of truth used by ``create_school`` to seed a brand-new real
(non Independent-Teacher) school's subjects so the school can immediately
assign teaching subjects in the add-teacher wizard and build schedules.

NOTE: Alembic data migrations keep a FROZEN inline copy of this list
(migrations must not import mutable application code). If this catalog
changes, add a NEW additive migration rather than editing the frozen
copies inside existing migrations.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# (name_ar, name_en, code, category, default_periods_per_week)
# Kept in sync with the Alembic seed/backfill migrations.
STANDARD_SUBJECTS = [
    ("اللغة العربية", "Arabic Language", "AR", "core", 6),
    ("اللغة الإنجليزية", "English Language", "EN", "core", 5),
    ("الرياضيات", "Mathematics", "MATH", "core", 6),
    ("العلوم", "Science", "SCI", "core", 4),
    ("التربية الإسلامية", "Islamic Studies", "IS", "core", 4),
    ("الدراسات الاجتماعية", "Social Studies", "SS", "core", 3),
    ("التربية البدنية", "Physical Education", "PE", "elective", 2),
    ("التربية الفنية", "Art", "ART", "elective", 2),
    ("الحاسوب", "Computer Science", "CS", "elective", 2),
    ("التاريخ", "History", "HIS", "core", 2),
    ("الجغرافيا", "Geography", "GEO", "core", 2),
    ("الكيمياء", "Chemistry", "CHEM", "secondary", 3),
    ("الفيزياء", "Physics", "PHY", "secondary", 3),
    ("الأحياء", "Biology", "BIO", "secondary", 3),
]


def build_default_subject_docs(
    school_id: str, now_iso: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Build subject rows (matching the real ``subjects`` columns) for a school."""
    if now_iso is None:
        now_iso = datetime.now(timezone.utc).isoformat()
    docs: List[Dict[str, Any]] = []
    for name_ar, name_en, code, category, periods in STANDARD_SUBJECTS:
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "name": name_ar,
                "name_ar": name_ar,
                "name_en": name_en,
                "code": code,
                "category": category,
                "default_periods_per_week": periods,
                "applicable_stages": [],
                "is_active": True,
                "is_global": False,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )
    return docs
