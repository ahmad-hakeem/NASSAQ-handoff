"""Task #331 — students.talents / character_traits / is_gifted columns

Revision ID: b3c4d5e6f7a8
Revises: n1o2o3r4i5m6
Create Date: 2026-05-14

The school-principal Student Profile → "المواهب والمهارات" tab writes
``talents`` (JSONB array of slugs), ``character_traits`` (JSONB array of
slugs) and ``is_gifted`` (Boolean derived from ``len(talents) > 0``) via
``PUT /students/{id}``. Until now the ``Student`` ORM model in
``pg_models.py`` did not declare these columns, and the ``students`` table
has no fallback ``data`` JSONB, so ``apply_updates`` silently dropped the
fields on the floor — the route returned 200, the toast fired, but
nothing was persisted.

This migration adds the three columns directly to the ``students`` table
with safe server-side defaults (empty JSONB arrays, ``false`` for the
gifted flag), making the existing route's update-mapping work end-to-end
without any ORM widening or alias logic. Existing student rows back-fill
to the same defaults via the server defaults.

The migration is fully reversible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "n1o2o3r4i5m6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column(
            "talents",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "students",
        sa.Column(
            "character_traits",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "students",
        sa.Column(
            "is_gifted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("students", "is_gifted")
    op.drop_column("students", "character_traits")
    op.drop_column("students", "talents")
