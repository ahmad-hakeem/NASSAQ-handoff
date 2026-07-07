"""Seed global default behaviour types

Revision ID: bt1seed2glob3
Revises: sk2pt3val4ue5
Create Date: 2026-07-07

The ``behaviour_types`` table shipped empty in existing databases: the global
default types were only ever inserted by the platform-admin
``POST /behaviour-types/seed-defaults`` endpoint, which was never run. As a
result the "Behavior Type / نوع السلوك" dropdown in the Add Behaviour Record
modal had no options for ANY school, and no behaviour record could be created.

This data migration inserts the eleven global default behaviour types
(``is_global = true``, ``tenant_id = NULL``) that every school's dropdown reads
via ``GET /behaviour-types`` (which unions global + tenant-scoped rows).

It is INSERT-only and idempotent: a default is inserted only when no global row
with the same ``name_ar`` already exists, so re-running the migration — or a
later call to the ``seed-defaults`` endpoint, which uses the same name_ar +
is_global guard — never creates duplicates. No school/user data is touched.
"""
from typing import Sequence, Union
from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "bt1seed2glob3"
down_revision: Union[str, Sequence[str], None] = "sk2pt3val4ue5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mirrors the defaults in POST /behaviour-types/seed-defaults so the two paths
# stay consistent. name_ar is the idempotency key (matched against is_global rows).
DEFAULT_TYPES = [
    {"name_ar": "تميز أكاديمي", "name_en": "Academic Excellence", "category": "positive", "default_severity": "minor", "default_points": 10, "auto_escalate": False, "escalation_threshold": None},
    {"name_ar": "مساعدة الزملاء", "name_en": "Helping Peers", "category": "positive", "default_severity": "minor", "default_points": 5, "auto_escalate": False, "escalation_threshold": None},
    {"name_ar": "مشاركة فعالة", "name_en": "Active Participation", "category": "positive", "default_severity": "minor", "default_points": 3, "auto_escalate": False, "escalation_threshold": None},
    {"name_ar": "سلوك قيادي", "name_en": "Leadership Behaviour", "category": "positive", "default_severity": "moderate", "default_points": 15, "auto_escalate": False, "escalation_threshold": None},
    {"name_ar": "تأخر عن الحصة", "name_en": "Late to Class", "category": "negative", "default_severity": "minor", "default_points": -2, "auto_escalate": False, "escalation_threshold": None},
    {"name_ar": "عدم إحضار الواجب", "name_en": "Missing Homework", "category": "negative", "default_severity": "minor", "default_points": -3, "auto_escalate": False, "escalation_threshold": None},
    {"name_ar": "تشويش في الفصل", "name_en": "Classroom Disruption", "category": "negative", "default_severity": "moderate", "default_points": -5, "auto_escalate": True, "escalation_threshold": 3},
    {"name_ar": "استخدام الهاتف", "name_en": "Phone Usage", "category": "negative", "default_severity": "moderate", "default_points": -5, "auto_escalate": False, "escalation_threshold": None},
    {"name_ar": "تنمر", "name_en": "Bullying", "category": "negative", "default_severity": "major", "default_points": -20, "auto_escalate": True, "escalation_threshold": 1},
    {"name_ar": "شجار", "name_en": "Fighting", "category": "negative", "default_severity": "severe", "default_points": -30, "auto_escalate": True, "escalation_threshold": 1},
    {"name_ar": "غش في الاختبار", "name_en": "Cheating", "category": "negative", "default_severity": "major", "default_points": -25, "auto_escalate": True, "escalation_threshold": 1},
]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    exists_sql = sa.text(
        "SELECT 1 FROM behaviour_types "
        "WHERE name_ar = :name_ar AND is_global = true LIMIT 1"
    )
    insert_sql = sa.text(
        "INSERT INTO behaviour_types "
        "(id, tenant_id, name_ar, name_en, description, category, "
        " default_severity, default_points, auto_escalate, escalation_threshold, "
        " is_active, is_global, created_at) "
        "VALUES "
        "(:id, NULL, :name_ar, :name_en, NULL, :category, "
        " :default_severity, :default_points, :auto_escalate, :escalation_threshold, "
        " true, true, :created_at)"
    )

    for bt in DEFAULT_TYPES:
        if bind.execute(exists_sql, {"name_ar": bt["name_ar"]}).first():
            continue
        bind.execute(
            insert_sql,
            {
                "id": str(uuid.uuid4()),
                "name_ar": bt["name_ar"],
                "name_en": bt["name_en"],
                "category": bt["category"],
                "default_severity": bt["default_severity"],
                "default_points": bt["default_points"],
                "auto_escalate": bt["auto_escalate"],
                "escalation_threshold": bt["escalation_threshold"],
                "created_at": now,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    names = [bt["name_ar"] for bt in DEFAULT_TYPES]
    bind.execute(
        sa.text(
            "DELETE FROM behaviour_types "
            "WHERE is_global = true AND name_ar = ANY(:names)"
        ),
        {"names": names},
    )
