"""Merge issue_versions and skill_types heads

Revision ID: z5d6e7f8g9h0
Revises: sk1ty2pe3sc4h5, z4c5d6e7f8g9
Create Date: 2026-06-17

Merge migration to reconcile two parallel heads:
- sk1ty2pe3sc4h5: Add school_id to skills_types for tenant-scoped skill types
- z4c5d6e7f8g9: Add issue_versions table for auditable edit history
"""
from typing import Sequence, Union

revision: str = "z5d6e7f8g9h0"
down_revision: Union[str, Sequence[str], None] = ("sk1ty2pe3sc4h5", "z4c5d6e7f8g9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
