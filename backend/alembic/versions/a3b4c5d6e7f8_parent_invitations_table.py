"""IT Phase 2 §6.2a — parent_invitations table

Revision ID: a3b4c5d6e7f8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-12

Creates the ``parent_invitations`` table that backs the Phase-2 §6.2
Parent invitation + portal deep-linking flow. This revision lands the
schema **only** — no routes, no FE — so the §6.2b route work can build
on a stable contract and the migration can be reviewed in isolation.

Columns are taken verbatim from spec §6.2:

    id, workspace_school_id, parent_email, parent_phone, student_id,
    token_hash, sent_at, accepted_at, expires_at, status, created_by,
    plus standard created_at / updated_at.

``status`` is constrained by a CHECK to the lifecycle values
``pending | accepted | expired | cancelled``. ``expires_at`` is left
to the application (helper computes ``sent_at + 7 days`` at mint time)
so we don't bake a default into the schema and silently disagree with
the helper.

Composite index ``(workspace_school_id, student_id, status)`` makes
"open invitation for this student in this workspace" a single-index
lookup — that's the read pattern §6.2b's create endpoint uses to
refuse duplicate pending invites.

FKs cascade on delete to match existing IT cleanup expectations
(workspace soft-delete in Phase 2 will tear down dependent rows).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_table


revision: str = "a3b4c5d6e7f8"
# Chained off the current Alembic head (``a2b3c4d5e6f7``, the §5.4
# schedule_sessions.version migration) rather than the
# ``z1a2b3c4d5e6`` anchor named in the task description. Rationale:
#
#   * Task #204 was authored before ``a2b3c4d5e6f7`` landed. Anchoring
#     this revision on ``z1a2b3c4d5e6`` would create a sibling head
#     and force a merge revision, which in turn makes
#     ``alembic downgrade -1`` ambiguous (the explicit smoke command
#     called out in the task's "Migration smoke" acceptance bullet).
#   * §6.2a's "isolated review" property is preserved at the **diff**
#     level: this revision creates ``parent_invitations`` only and
#     touches no §5.4 objects. Ancestry is pure ordering — there is
#     no functional dependency on ``schedule_sessions.version``.
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("parent_invitations"):
        op.create_table(
            "parent_invitations",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("workspace_school_id", sa.String(), nullable=False),
            sa.Column("parent_email", sa.String(), nullable=True),
            sa.Column("parent_phone", sa.String(), nullable=True),
            sa.Column("student_id", sa.String(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(
                ["workspace_school_id"], ["schools.id"], ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["student_id"], ["students.id"], ondelete="CASCADE",
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'accepted', 'expired', 'cancelled')",
                name="ck_parent_invitations_status",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index(
        "ix_parent_invitations_workspace_student_status",
        "parent_invitations",
        ["workspace_school_id", "student_id", "status"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_parent_invitations_token_hash",
        "parent_invitations",
        ["token_hash"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_parent_invitations_token_hash",
        table_name="parent_invitations",
    )
    op.drop_index(
        "ix_parent_invitations_workspace_student_status",
        table_name="parent_invitations",
    )
    op.drop_table("parent_invitations")
