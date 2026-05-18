"""Add charter_accepted_at column to users for the Parent Charter blocking guard

Revision ID: p1c2h3a4r5t6
Revises: z3b4c5d6e7f8
Create Date: 2026-05-18

Adds a nullable ``charter_accepted_at`` timestamptz column to ``users``
so the parent portal can enforce a one-time mandatory "ميثاق ولي الأمر"
agreement before granting access to any /parent/* surface. A timestamp
(rather than a boolean) is used so we can audit when the parent accepted
the charter. Existing parent rows default to NULL, which the FE
``CharterGuard`` interprets as "not yet accepted" and intercepts on the
next login.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p1c2h3a4r5t6"
down_revision: Union[str, Sequence[str], None] = "z3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("charter_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "charter_accepted_at")
