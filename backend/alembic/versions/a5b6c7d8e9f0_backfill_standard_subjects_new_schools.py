"""Backfill standard subjects for real schools created after the first seed

Revision ID: a5b6c7d8e9f0
Revises: d9e8f7a6b5c4
Create Date: 2026-06-10

Idempotent, additive data migration. A previous migration
(``f7a3c9b1d2e4``) seeded the standard subject catalog into every real
school that existed on 2026-06-03, but ``create_school`` was not updated to
seed NEW schools until now. Any real school created between that backfill
and this fix therefore has zero subjects, which leaves the add-teacher
wizard's subjects step empty.

This migration re-runs the same idempotent backfill so those schools (and
any that slipped through) receive the catalog. It mirrors the behaviour of
``f7a3c9b1d2e4`` exactly:

  * Scope: schools where ``tenant_type`` is NOT ``independent_teacher``.
    Independent-Teacher workspaces manage their own subjects and are left
    untouched.
  * Per school, each standard subject is inserted only when the school does
    not already have a subject with the same (normalised) name. Existing,
    custom, or soft-deleted subjects are never duplicated, modified, or
    deleted. Re-running is a no-op.

The downgrade is intentionally a no-op: removing seeded reference data could
delete subjects that schools have since attached to teachers, schedules, and
grades, violating the project's "production data must never be lost" rule.
"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "d9e8f7a6b5c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (name_ar, name_en, code, category, default_periods_per_week)
# Frozen copy of the canonical catalogue — kept in sync with
# backend/constants/default_subjects.py and migration f7a3c9b1d2e4.
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
