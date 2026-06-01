"""Add noor_import_history table

Revision ID: z2a3b4c5d6e7
Revises: z1a2b3c4d5e6
Create Date: 2026-05-17

Adds the ``noor_import_history`` table which records a persistent audit
row for every committed Noor bulk import (teachers or students).

One row is written per /noor-import/commit call that reaches the DB
write phase. Rows are append-only — no UPDATE or DELETE is expected on
this table in normal operation.

Columns of interest:

  * ``actor_id``          — user-id of the principal/admin who clicked commit
  * ``actor_name``        — display name at commit time (denormalised for
                            quick display without a join)
  * ``detected_type``     — "teachers" or "students"
  * ``imported_count``    — rows inserted as new entities
  * ``updated_count``     — rows merged into existing entities
  * ``skipped_count``     — rows skipped due to validation failures
  * ``failed_count``      — rows that errored during write
  * ``duplicates_count``  — in-file duplicate rows ignored
  * ``unclassified_count``— student rows saved without a class link
  * ``created_ids``       — JSONB list of UUIDs inserted by this import
  * ``updated_ids``       — JSONB list of UUIDs updated by this import
  * ``created_class_ids`` — JSONB list of class UUIDs created by the
                            create-missing-classes step in this session
  * ``credentials_csv``   — JSONB list of teacher credential objects for
                            re-download (teacher imports only; contains
                            one-time passwords that must be changed on
                            first login)
  * ``committed_at``      — timestamp of the commit
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_table
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "z2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("noor_import_history"):
        op.create_table(
            "noor_import_history",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("school_id", sa.String(), nullable=False),
            sa.Column("actor_id", sa.String(), nullable=False),
            sa.Column("actor_name", sa.String(), nullable=True),
            sa.Column("detected_type", sa.String(), nullable=False),
            sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duplicates_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unclassified_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_ids", JSONB, nullable=True),
            sa.Column("updated_ids", JSONB, nullable=True),
            sa.Column("created_class_ids", JSONB, nullable=True),
            sa.Column("credentials_csv", JSONB, nullable=True),
            sa.Column(
                "committed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index(
        "idx_noor_import_history_school_committed",
        "noor_import_history",
        ["school_id", "committed_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_noor_import_history_school_id",
        "noor_import_history",
        ["school_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_noor_import_history_school_id", table_name="noor_import_history")
    op.drop_index(
        "idx_noor_import_history_school_committed", table_name="noor_import_history"
    )
    op.drop_table("noor_import_history")
