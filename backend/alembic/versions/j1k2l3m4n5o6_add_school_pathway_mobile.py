"""add principal_mobile and educational_pathway to schools

Revision ID: j1k2l3m4n5o6
Revises: i1j2k3l4m5n6
Create Date: 2026-04-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_idempotent import has_column

revision: str = 'j1k2l3m4n5o6'
down_revision: Union[str, Sequence[str], None] = 'i1j2k3l4m5n6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column('schools', 'principal_mobile'):
        op.add_column('schools', sa.Column('principal_mobile', sa.String(), nullable=True))
    if not has_column('schools', 'educational_pathway'):
        op.add_column('schools', sa.Column('educational_pathway', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('schools', 'educational_pathway')
    op.drop_column('schools', 'principal_mobile')
