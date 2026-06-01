"""Add tenant_id and is_global to educational_stages (Task #521)

Revision ID: t521a1b2c3d4
Revises: 629fb4a19af5
Create Date: 2026-05-25

The ``educational_stages`` table was created in the initial migration
without ``tenant_id`` or ``is_global`` columns, even though the
``GET /api/academic/stages`` route filters by ``tenant_id`` and treats
``is_global=True`` as the shared-row fallback. Because the columns did
not exist in Postgres, the tenant-scope filter was silently dropped at
query time, letting every caller — including an impersonating Platform
Admin pinned to a single school — see educational stages from every
tenant in the table.

This migration adds the two missing columns so the route's existing
scope filter actually narrows results, and so the four-scenario
preview-leak regression test for ``/academic/stages`` can be enabled.
``tenant_id`` is a nullable FK to ``schools.id`` (NULL for global rows),
matching the pattern used by ``subjects``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_idempotent import has_column, has_constraint


revision: str = "t521a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "629fb4a19af5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("educational_stages", "tenant_id"):
        op.add_column(
            "educational_stages",
            sa.Column("tenant_id", sa.String(), nullable=True),
        )
    if not has_column("educational_stages", "is_global"):
        op.add_column(
            "educational_stages",
            sa.Column("is_global", sa.Boolean(), nullable=True),
        )
    if not has_constraint("educational_stages", "fk_educational_stages_tenant_id_schools"):
        op.create_foreign_key(
            "fk_educational_stages_tenant_id_schools",
            "educational_stages",
            "schools",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        "idx_educational_stages_tenant_id",
        "educational_stages",
        ["tenant_id"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_educational_stages_is_global",
        "educational_stages",
        ["is_global"],
        if_not_exists=True,
    )
    # Backfill: existing rows are assumed to be global defaults (the
    # seed route inserts them with is_global=True, tenant_id=None).
    op.execute(
        "UPDATE educational_stages SET is_global = TRUE WHERE is_global IS NULL"
    )


def downgrade() -> None:
    op.drop_index("idx_educational_stages_is_global", table_name="educational_stages")
    op.drop_index("idx_educational_stages_tenant_id", table_name="educational_stages")
    op.drop_constraint(
        "fk_educational_stages_tenant_id_schools",
        "educational_stages",
        type_="foreignkey",
    )
    op.drop_column("educational_stages", "is_global")
    op.drop_column("educational_stages", "tenant_id")
