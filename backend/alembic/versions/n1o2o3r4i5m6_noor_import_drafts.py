"""Noor importer draft store

Revision ID: n1o2o3r4i5m6
Revises: e1f2a3b4c5d7, erw1x2y3z4a5, h2i3j4k5l6m7  (merge point that
          consolidates the three pre-existing alembic heads — see
          `down_revision` tuple below for the authoritative list)
Create Date: 2026-05-14

Creates `noor_import_drafts` — a short-lived (1h TTL), principal-bound,
tenant-bound persistence row for the server-authoritative two-step Noor
import (parse → commit). The /commit endpoint reads `payload.rows` back
from this row and NEVER trusts a client-supplied `rows[]` array.

`payload` carries `{rows, mapped_columns, sheet_name}` as JSONB so the
schema stays stable as the parser evolves. Indexed by (principal_id,
school_id) for the load-by-id-and-owner check, and by (expires_at) for
the lazy purge.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "n1o2o3r4i5m6"
# Merge-point: this migration is sequenced after the pre-existing
# multi-heads (e1f2a3b4c5d7, erw1x2y3z4a5, h2i3j4k5l6m7) and the
# students_pending_parent_columns head (z1a2b3c4d5e6) so `alembic
# upgrade head` resolves to a single tip after this revision lands.
down_revision: Union[str, Sequence[str], None] = (
    "e1f2a3b4c5d7",
    "erw1x2y3z4a5",
    "h2i3j4k5l6m7",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "noor_import_drafts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("principal_id", sa.String(), nullable=False, index=True),
        sa.Column("school_id", sa.String(), nullable=False, index=True),
        sa.Column("detected_type", sa.String(length=16), nullable=False),
        sa.Column("header_row", sa.Integer(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "counts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_noor_import_drafts_owner",
        "noor_import_drafts",
        ["principal_id", "school_id"],
    )
    op.create_index(
        "ix_noor_import_drafts_expires_at",
        "noor_import_drafts",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_noor_import_drafts_expires_at", table_name="noor_import_drafts")
    op.drop_index("ix_noor_import_drafts_owner", table_name="noor_import_drafts")
    op.drop_table("noor_import_drafts")
