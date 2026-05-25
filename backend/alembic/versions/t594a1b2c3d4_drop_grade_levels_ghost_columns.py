"""Drop grade_levels ghost columns to match ORM (Task #594)

Revision ID: t594a1b2c3d4
Revises: t523a1b2c3d4
Create Date: 2026-05-25

Task #523 added ``name``, ``created_at``, ``updated_at``, and ``created_by``
to ``grade_levels`` to back a Pydantic response shape that was being
exercised by the legacy ``/grade-levels`` route. Task #592 took the
opposite approach: it removed those four columns from
``backend/pg_models.py`` so that ORM inserts/updates against
``grade_levels`` would stop raising ``UndefinedColumnError`` against the
historical schema (which never had them on most environments).

The result was that on any environment which DID apply migration
``t523a1b2c3d4``, the live Postgres table now contained four columns
that no longer exist on the ORM, so ``compare_metadata`` in
``tests/test_schema_orm_drift.py`` flagged drift and
``alembic revision --autogenerate`` would emit drop_column ops on every
run.

This migration formally records the drop so that, after
``alembic upgrade head``, the ``grade_levels`` table matches the ORM
model exactly. The columns are dropped with ``IF EXISTS`` so that
environments where ``t523a1b2c3d4`` was never applied (because head
moved forward before they upgraded) succeed as a no-op.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "t594a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "t523a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE grade_levels DROP COLUMN IF EXISTS created_by")
    op.execute("ALTER TABLE grade_levels DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE grade_levels DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE grade_levels DROP COLUMN IF EXISTS name")


def downgrade() -> None:
    import sqlalchemy as sa

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
