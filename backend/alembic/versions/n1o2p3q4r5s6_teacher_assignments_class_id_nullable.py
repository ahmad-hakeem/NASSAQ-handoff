"""Make teacher_assignments.class_id nullable for subject-only assignments

Revision ID: n1o2p3q4r5s6
Revises: m1n2o3p4q5r6
Create Date: 2026-04-17 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'n1o2p3q4r5s6'
down_revision: Union[str, Sequence[str], None] = 'm1n2o3p4q5r6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'teacher_assignments',
        'class_id',
        existing_type=__import__('sqlalchemy').String(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE teacher_assignments SET class_id = '' WHERE class_id IS NULL")
    op.alter_column(
        'teacher_assignments',
        'class_id',
        existing_type=__import__('sqlalchemy').String(),
        nullable=False,
    )
