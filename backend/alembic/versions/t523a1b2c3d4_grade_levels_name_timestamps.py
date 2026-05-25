"""Add name/created_at/updated_at/created_by to grade_levels (Task #523)

Revision ID: t523a1b2c3d4
Revises: t521a1b2c3d4
Create Date: 2026-05-25

The ``grade_levels`` table was created in the initial migration with
only the legacy ``name_ar``/``name_en``/``code``/``stage`` columns.
The actual ``/grade-levels`` route (``backend/routes/academics_year_term_routes.py``)
reads and writes ``name``, ``created_at``, ``updated_at``, and
``created_by``. Because those columns did not exist in Postgres, the
route's Pydantic response validation failed on round-trip (``name`` and
``created_at`` are required on ``GradeLevelResponse``) and the
four-scenario preview-leak regression test for ``/api/grade-levels``
in ``tests/test_preview_tenant_scope_extra.py`` had to be skipped.

This migration adds the four missing columns so the ORM model in
``backend/pg_models.py`` matches both the route and the live schema,
and so the tenant-scope contract for ``/grade-levels`` can be locked
in alongside the other admin list endpoints.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t523a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "t521a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "grade_levels",
        sa.Column("name", sa.String(), nullable=True),
    )
    op.add_column(
        "grade_levels",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "grade_levels",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "grade_levels",
        sa.Column("created_by", sa.String(), nullable=True),
    )
    # Backfill: keep existing rows visible to the route's response model by
    # giving them a non-null ``name`` (fall back to name_ar / name_en / code)
    # and a non-null ``created_at`` timestamp.
    op.execute(
        "UPDATE grade_levels "
        "SET name = COALESCE(name, name_ar, name_en, code) "
        "WHERE name IS NULL"
    )
    op.execute(
        "UPDATE grade_levels "
        "SET created_at = NOW() "
        "WHERE created_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("grade_levels", "created_by")
    op.drop_column("grade_levels", "updated_at")
    op.drop_column("grade_levels", "created_at")
    op.drop_column("grade_levels", "name")
