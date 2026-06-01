"""IT Phase 2 §6.8 — schools.archived_at + schools.pending_hard_delete

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-05-12

Adds the two columns the §6.8 workspace soft-delete + reactivate
contract needs:

* ``archived_at`` (nullable timestamptz) — set the moment the IT user
  POSTs ``/independent-teacher/workspace/soft-delete``. Reactivation
  is allowed within 30 days; after that the row flips to
  ``pending_hard_delete=TRUE`` and reactivation 410s. ``status``
  ('active' / 'archived') is unchanged in this revision — the column
  already exists and is the canonical lifecycle flag.

* ``pending_hard_delete`` (bool, default FALSE) — flipped by the
  on-login lazy sweep when ``archived_at`` is older than 30 days.
  Platform-admin out-of-band tooling picks rows up by this flag for
  the destructive hard-delete; this task does NOT implement the
  hard-delete itself.

Both columns are added with a server default + ``nullable=False`` for
``pending_hard_delete`` so existing rows backfill cleanly. No data
migration is required because the default is the inactive state for
every existing tenant.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column


revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("schools", "archived_at"):
        op.add_column(
            "schools",
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not has_column("schools", "pending_hard_delete"):
        op.add_column(
            "schools",
            sa.Column(
                "pending_hard_delete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not has_column("schools", "last_export_at"):
        op.add_column(
            "schools",
            sa.Column("last_export_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.create_index(
        "idx_schools_archived_at",
        "schools",
        ["archived_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_schools_pending_hard_delete",
        "schools",
        ["pending_hard_delete"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_schools_pending_hard_delete", table_name="schools")
    op.drop_index("idx_schools_archived_at", table_name="schools")
    op.drop_column("schools", "last_export_at")
    op.drop_column("schools", "pending_hard_delete")
    op.drop_column("schools", "archived_at")
