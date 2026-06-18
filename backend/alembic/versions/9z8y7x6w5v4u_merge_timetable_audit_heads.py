"""Merge timetable audit columns branch into main

Revision ID: 9z8y7x6w5v4u
Revises: hw0nd1zr2gr3, z8h9i0j1k2l3
Create Date: 2026-06-18

Merge migration — no schema changes. Brings together the main branch
(hw0nd1zr2gr3) with the timetables audit-columns branch (z8h9i0j1k2l3)
so that 'alembic upgrade head' has a single head again.
"""
from typing import Sequence, Union

revision: str = "9z8y7x6w5v4u"
down_revision: Union[str, Sequence[str], None] = ("hw0nd1zr2gr3", "z8h9i0j1k2l3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
