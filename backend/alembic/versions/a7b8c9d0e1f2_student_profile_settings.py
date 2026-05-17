"""Add profile_settings JSONB to students + merge heads

Revision ID: a7b8c9d0e1f2
Revises: d0e1f2a3b4c5, c4d5e6f7a8b9
Create Date: 2026-05-17

Adds a single ``profile_settings`` JSONB column on ``students`` to hold
per-student parent-editable profile metadata (health conditions,
behavioural/learning indicators, family situation, family other-situation
tags, avatar emoji). Storage is per-student (keyed by students.id), so
siblings under the same parent account are fully independent.

Also merges the two existing migration heads.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = ("d0e1f2a3b4c5", "c4d5e6f7a8b9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column(
            "profile_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("students", "profile_settings")
