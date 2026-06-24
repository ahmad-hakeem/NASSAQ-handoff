"""Add points to skills_types for configured per-skill score values

Revision ID: sk2pt3val4ue5
Revises: a7d4e1c9b2f3
Create Date: 2026-06-24

Adds a nullable ``points`` column to ``skills_types`` so that a skill type's
configured per-skill point value can be stored and treated as authoritative by
the scoring engine. Existing rows (seed/default skills) keep ``points = NULL``,
which the application treats as "no configured value" and continues to score
via the global ``special_skill`` rule — so default behaviour is unchanged.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column


revision: str = "sk2pt3val4ue5"
down_revision: Union[str, Sequence[str], None] = "a7d4e1c9b2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("skills_types", "points"):
        op.add_column(
            "skills_types",
            sa.Column(
                "points",
                sa.Integer(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    if has_column("skills_types", "points"):
        op.drop_column("skills_types", "points")
