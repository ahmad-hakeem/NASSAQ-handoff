"""add reset_token_hash and reset_token_created_at to users

Revision ID: t1u2v3w4x5y6
Revises: s1t2u3v4w5x6
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column

revision: str = 't1u2v3w4x5y6'
down_revision: Union[str, Sequence[str], None] = 's1t2u3v4w5x6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column('users', 'reset_token_hash'):
        op.add_column('users', sa.Column('reset_token_hash', sa.String(), nullable=True))
    if not has_column('users', 'reset_token_created_at'):
        op.add_column('users', sa.Column('reset_token_created_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'reset_token_created_at')
    op.drop_column('users', 'reset_token_hash')
