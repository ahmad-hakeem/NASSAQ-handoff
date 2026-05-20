"""Task #450 — bind workspace-export download to the bearer JTI that minted it.

Add ``schools.last_export_initiator_jti`` so the public download endpoint can
verify that the bearer token presenting itself is the same session that
minted/refreshed the export.  Any other bearer token must pass full session-
invalidation checks (``is_active`` / ``last_password_change``); only the
initiating JTI is allowed to bypass them so the legitimate post-erasure
download still works.

Revision ID: 4190214c47ac
Revises: c5d6e7f8a9b0
Create Date: 2026-05-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "4190214c47ac"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column("last_export_initiator_jti", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schools", "last_export_initiator_jti")
