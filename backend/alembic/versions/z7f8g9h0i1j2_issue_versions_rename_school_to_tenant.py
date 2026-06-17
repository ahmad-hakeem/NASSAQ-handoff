"""Rename issue_versions.school_id -> tenant_id, add composite index

Revision ID: z7f8g9h0i1j2
Revises: z6e7f8g9h0i1
Create Date: 2026-06-17

- RENAME COLUMN school_id → tenant_id (nullable; NULL for platform-admin edits
  since the Product Hub is platform-wide with no school scoping on product_issues)
- DROP old single-column index idx_pg_versions_school_id
- CREATE composite index (issue_id, tenant_id) for the required scoped access path
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z7f8g9h0i1j2"
down_revision: Union[str, Sequence[str], None] = "z6e7f8g9h0i1"
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


def _index_exists(name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE indexname = :n AND schemaname = 'public'"
        ),
        {"n": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if _column_exists("issue_versions", "school_id"):
        if _index_exists("idx_pg_versions_school_id"):
            op.drop_index("idx_pg_versions_school_id", table_name="issue_versions")
        op.alter_column("issue_versions", "school_id", new_column_name="tenant_id")

    if not _index_exists("idx_pg_versions_issue_tenant"):
        op.create_index(
            "idx_pg_versions_issue_tenant",
            "issue_versions",
            ["issue_id", "tenant_id"],
        )


def downgrade() -> None:
    if _index_exists("idx_pg_versions_issue_tenant"):
        op.drop_index("idx_pg_versions_issue_tenant", table_name="issue_versions")
    if _column_exists("issue_versions", "tenant_id"):
        op.alter_column("issue_versions", "tenant_id", new_column_name="school_id")
        op.create_index(
            "idx_pg_versions_school_id", "issue_versions", ["school_id"]
        )
