"""Seed shared default catalog of standard subjects for every real school

Revision ID: f7a3c9b1d2e4
Revises: e0f1a2b3c4d5
Create Date: 2026-06-03

Idempotent, additive data migration. Ensures every real (non Independent
Teacher) school has the standard catalog of core subjects so that schools
which were never seeded can immediately assign teachers and build schedules.

Behaviour:
  * Scope: schools where ``tenant_type`` is NOT ``independent_teacher``.
    Independent-Teacher workspaces manage their own subjects via the IT
    bootstrap flow and are intentionally left untouched.
  * Per school, each standard subject is inserted only when the school does
    not already have a subject with the same (normalised) name. Existing,
    custom, or soft-deleted subjects are never duplicated, modified, or
    deleted. Re-running the migration is a no-op.
  * The catalogue mirrors the canonical project default list so the names,
    codes, categories, and weekly periods stay consistent with seeded data.

The downgrade is intentionally a no-op: removing seeded reference data could
delete subjects that schools have since attached to teachers, schedules, and
grades, violating the project's "production data must never be lost" rule.
"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "f7a3c9b1d2e4"
down_revision: Union[str, Sequence[str], None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (name_ar, name_en, code, category, default_periods_per_week)
# Canonical standard catalogue — kept in sync with scripts/seed_test_data.py.
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


def _norm(value) -> str:
    return (value or "").strip().casefold()


def upgrade() -> None:
    bind = op.get_bind()

    school_ids = [
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT id FROM schools "
                "WHERE COALESCE(tenant_type, 'production') <> 'independent_teacher'"
            )
        )
    ]
    if not school_ids:
        return

    # Existing subject names per school (active OR soft-deleted) so we never
    # duplicate a name a school already has, and never resurrect one it deleted.
    existing: dict[str, set] = {sid: set() for sid in school_ids}
    for sid, name, name_ar in bind.execute(
        sa.text("SELECT school_id, name, name_ar FROM subjects")
    ):
        bucket = existing.get(sid)
        if bucket is None:
            continue
        if name:
            bucket.add(_norm(name))
        if name_ar:
            bucket.add(_norm(name_ar))

    insert_stmt = sa.text(
        """
        INSERT INTO subjects (
            id, school_id, name, name_ar, name_en, code, category,
            default_periods_per_week, applicable_stages,
            is_active, is_global, created_at, updated_at
        ) VALUES (
            :id, :school_id, :name, :name_ar, :name_en, :code, :category,
            :periods, CAST(:applicable_stages AS JSONB),
            TRUE, FALSE, :now, :now
        )
        """
    )

    now = datetime.now(timezone.utc)
    rows = []
    for sid in school_ids:
        have = existing[sid]
        for name_ar, name_en, code, category, periods in STANDARD_SUBJECTS:
            if _norm(name_ar) in have:
                continue
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "school_id": sid,
                    "name": name_ar,
                    "name_ar": name_ar,
                    "name_en": name_en,
                    "code": code,
                    "category": category,
                    "periods": periods,
                    "applicable_stages": "[]",
                    "now": now,
                }
            )

    if rows:
        bind.execute(insert_stmt, rows)


def downgrade() -> None:
    # Intentional no-op: seeded reference subjects may be referenced by
    # teachers, schedules, and grades. Deleting them on downgrade would risk
    # production data loss, which the project forbids.
    pass
