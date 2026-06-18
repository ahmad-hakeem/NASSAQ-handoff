"""Add audit columns to timetables table

Revision ID: z8h9i0j1k2l3
Revises: z7f8g9h0i1j2
Create Date: 2026-06-18

Adds four audit columns and is_published flag to the ``timetables`` table.
Previously these values were stored via gd_update_one (JSONB patch) only,
making them unreliable for ORM-level queries. The migration is additive-only
(no DROP, no RENAME, no TRUNCATE) so it is safe on production data.

  - is_published  (Boolean, nullable, default False)
  - published_at  (TimestampTZ, nullable)
  - published_by  (String, nullable)
  - created_by    (String, nullable)
  - updated_by    (String, nullable)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z8h9i0j1k2l3"
down_revision: Union[str, Sequence[str], None] = "z7f8g9h0i1j2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c AND table_schema = 'public'"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _column_exists("timetables", "is_published"):
        op.add_column(
            "timetables",
            sa.Column("is_published", sa.Boolean(), nullable=True, server_default=sa.text("false")),
        )
    if not _column_exists("timetables", "published_at"):
        op.add_column(
            "timetables",
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("timetables", "published_by"):
        op.add_column(
            "timetables",
            sa.Column("published_by", sa.String(), nullable=True),
        )
    if not _column_exists("timetables", "created_by"):
        op.add_column(
            "timetables",
            sa.Column("created_by", sa.String(), nullable=True),
        )
    if not _column_exists("timetables", "updated_by"):
        op.add_column(
            "timetables",
            sa.Column("updated_by", sa.String(), nullable=True),
        )


def downgrade() -> None:
    for col in ("updated_by", "created_by", "published_by", "published_at", "is_published"):
        if _column_exists("timetables", col):
            op.drop_column("timetables", col)
