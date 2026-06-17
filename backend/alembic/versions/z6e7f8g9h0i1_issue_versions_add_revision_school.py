"""Add revision and school_id columns to issue_versions

Revision ID: z6e7f8g9h0i1
Revises: z5d6e7f8g9h0
Create Date: 2026-06-17

Adds:
  - revision (INTEGER NOT NULL DEFAULT 0) — immutable per-issue edit counter,
    backfilled from row insertion order so existing rows get stable numbers.
  - school_id (VARCHAR NULL) — nullable tenant context; NULL for platform-admin
    edits (the Product Hub is a platform-wide resource with no school scoping).
  - UNIQUE(issue_id, revision) — ensures no two version rows share a revision
    number for the same issue.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z6e7f8g9h0i1"
down_revision: Union[str, Sequence[str], None] = "z5d6e7f8g9h0"
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


def _constraint_exists(name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = :n AND table_schema = 'public'"
        ),
        {"n": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _column_exists("issue_versions", "revision"):
        op.add_column(
            "issue_versions",
            sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        )
        op.execute(
            sa.text("""
                WITH numbered AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY issue_id ORDER BY changed_at, id
                           ) AS rn
                    FROM issue_versions
                )
                UPDATE issue_versions iv
                SET revision = n.rn
                FROM numbered n
                WHERE iv.id = n.id
            """)
        )

    if not _column_exists("issue_versions", "school_id"):
        op.add_column(
            "issue_versions",
            sa.Column("school_id", sa.String(), nullable=True),
        )
        op.create_index(
            "idx_pg_versions_school_id", "issue_versions", ["school_id"]
        )

    if not _constraint_exists("uq_issue_versions_issue_revision"):
        op.create_unique_constraint(
            "uq_issue_versions_issue_revision",
            "issue_versions",
            ["issue_id", "revision"],
        )


def downgrade() -> None:
    if _constraint_exists("uq_issue_versions_issue_revision"):
        op.drop_constraint(
            "uq_issue_versions_issue_revision",
            "issue_versions",
            type_="unique",
        )
    if _column_exists("issue_versions", "school_id"):
        op.drop_index("idx_pg_versions_school_id", table_name="issue_versions")
        op.drop_column("issue_versions", "school_id")
    if _column_exists("issue_versions", "revision"):
        op.drop_column("issue_versions", "revision")
