"""Add issue_versions table for auditable edit history

Revision ID: z4c5d6e7f8g9
Revises: z3b4c5d6e7f8
Create Date: 2026-06-17

Adds ``issue_versions`` to record every content-edit made to a
ProductIssue via the PATCH /product-hub/issues/{id} endpoint.
Each row captures the editor identity, the ISO timestamp, the
list of changed field names, and a before/after JSON snapshot.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "z4c5d6e7f8g9"
down_revision: Union[str, Sequence[str], None] = "z3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :name AND table_schema = 'public'"
        ),
        {"name": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if _table_exists("issue_versions"):
        return

    op.create_table(
        "issue_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("issue_id", sa.String(), nullable=False),
        sa.Column("changed_by_user_id", sa.String(), nullable=True),
        sa.Column("changed_by_name", sa.String(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("changed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("previous_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issue_id"], ["product_issues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pg_versions_issue_id", "issue_versions", ["issue_id"])
    op.create_index("idx_pg_versions_changed_at", "issue_versions", ["changed_at"])
    op.create_index("idx_pg_versions_issue_time", "issue_versions", ["issue_id", "changed_at"])


def downgrade() -> None:
    op.drop_index("idx_pg_versions_issue_time", table_name="issue_versions")
    op.drop_index("idx_pg_versions_changed_at", table_name="issue_versions")
    op.drop_index("idx_pg_versions_issue_id", table_name="issue_versions")
    op.drop_table("issue_versions")
