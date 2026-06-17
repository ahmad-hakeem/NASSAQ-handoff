"""Add school_id to skills_types for tenant-scoped skill types

Revision ID: sk1ty2pe3sc4h5
Revises: d8e9f0a1b2c4
Create Date: 2026-06-16

Adds a nullable ``school_id`` FK column to ``skills_types`` so that
principals and teachers can create school-scoped skill types that are
not visible to other tenants. Existing rows (global seed skills) keep
``school_id = NULL``, which the application treats as globally visible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column, has_index


revision: str = "sk1ty2pe3sc4h5"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("skills_types", "school_id"):
        op.add_column(
            "skills_types",
            sa.Column(
                "school_id",
                sa.String(),
                nullable=True,
            ),
        )
    if not has_index("skills_types", "ix_skills_types_school_id"):
        op.create_index(
            "ix_skills_types_school_id",
            "skills_types",
            ["school_id"],
            unique=False,
        )


def downgrade() -> None:
    if has_index("skills_types", "ix_skills_types_school_id"):
        op.drop_index("ix_skills_types_school_id", table_name="skills_types")
    if has_column("skills_types", "school_id"):
        op.drop_column("skills_types", "school_id")
