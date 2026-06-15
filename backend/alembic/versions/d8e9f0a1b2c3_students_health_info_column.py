"""students.health_info column

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-06-15

The School-Manager Student Profile → "الصحة والملاحظات" (Health & Notes)
editor writes a nested ``health_info`` object (blood type, chronic
conditions, allergies, disabilities, current medications, special-care
notes, emergency medical notes) via ``PUT /students/{id}``. Until now the
``Student`` ORM model in ``pg_models.py`` did not declare a ``health_info``
column, and the ``students`` table has no fallback ``data`` JSONB, so
``apply_updates`` silently dropped the field — the route returned 200 but
nothing was persisted, and health could never be added or edited after
student creation.

This migration adds a single ``health_info`` JSONB column to the
``students`` table with a safe server-side default (empty JSONB object),
making the existing route's update-mapping work end-to-end without any ORM
widening or alias logic. Existing student rows back-fill to the default.

The migration is fully reversible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column
from sqlalchemy.dialects import postgresql


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("students", "health_info"):
        op.add_column(
            "students",
            sa.Column(
                "health_info",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade() -> None:
    op.drop_column("students", "health_info")
