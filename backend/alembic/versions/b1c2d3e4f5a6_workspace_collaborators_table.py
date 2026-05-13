"""IT Phase 2 §6.7 — workspace_collaborators table

Revision ID: b1c2d3e4f5a6
Revises: a3b4c5d6e7f8
Create Date: 2026-05-12

Backs the IT §6.7 cross-workspace co-teaching envelope (Task #210).

A row links one **host** Independent-Teacher workspace's class to exactly
one **collaborator** Independent-Teacher workspace. While ``status =
'accepted'`` the collaborator may read (and, when ``scope.mode = 'write'``
is granted, mutate) data scoped to the named ``class_id`` only — never
the rest of the host workspace.

Lifecycle::

    pending -> accepted   (collaborator clicks the invite + accepts)
    pending -> cancelled  (host or collaborator cancels before accept)
    accepted -> revoked   (host or collaborator revokes after accept)
    pending -> expired    (sweep job; 7-day TTL on the token)

The partial unique index keeps "at most one *active* link" per
``(host, collaborator, class)`` triple but still allows the audit trail
of historical invites (cancelled / revoked / expired rows) to coexist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_collaborators",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("host_school_id", sa.String(), nullable=False),
        sa.Column("collaborator_school_id", sa.String(), nullable=True),
        sa.Column("class_id", sa.String(), nullable=False),
        sa.Column("collaborator_email", sa.String(), nullable=True),
        sa.Column("collaborator_user_id", sa.String(), nullable=True),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column(
            "scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
            server_default=sa.text("'{\"mode\": \"read\"}'::jsonb"),
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["host_school_id"], ["schools.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["collaborator_school_id"], ["schools.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked', 'cancelled', 'expired')",
            name="ck_workspace_collaborators_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # "At most one active accepted collab per host+collaborator+class".
    op.create_index(
        "ux_workspace_collab_accepted",
        "workspace_collaborators",
        ["host_school_id", "collaborator_school_id", "class_id"],
        unique=True,
        postgresql_where=sa.text("status = 'accepted'"),
    )
    # "At most one open pending invite per host+class+email".
    op.create_index(
        "ux_workspace_collab_pending",
        "workspace_collaborators",
        ["host_school_id", "class_id", "collaborator_email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    # Read patterns: list-by-class (host view) and list-by-collaborator
    # (collaborator's "shared with me" view).
    op.create_index(
        "ix_workspace_collab_host_class_status",
        "workspace_collaborators",
        ["host_school_id", "class_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_collab_collab_status",
        "workspace_collaborators",
        ["collaborator_school_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_collab_token_hash",
        "workspace_collaborators",
        ["token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_collab_token_hash", table_name="workspace_collaborators")
    op.drop_index("ix_workspace_collab_collab_status", table_name="workspace_collaborators")
    op.drop_index("ix_workspace_collab_host_class_status", table_name="workspace_collaborators")
    op.drop_index("ux_workspace_collab_pending", table_name="workspace_collaborators")
    op.drop_index("ux_workspace_collab_accepted", table_name="workspace_collaborators")
    op.drop_table("workspace_collaborators")
