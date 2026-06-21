"""Merge notifications student_id branch into main

Revision ID: aa1bb2cc3dd4
Revises: 9z8y7x6w5v4u, z9i0j1k2l3m4
Create Date: 2026-06-21

Merge migration — no schema changes. Reunites the main branch
(9z8y7x6w5v4u) with the notifications student_id branch (z9i0j1k2l3m4)
so that 'alembic upgrade head' has a single head again.
"""
from typing import Sequence, Union

revision: str = "aa1bb2cc3dd4"
down_revision: Union[str, Sequence[str], None] = ("9z8y7x6w5v4u", "z9i0j1k2l3m4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
