"""add revoked_tokens table for JWT logout invalidation

Revision ID: k1l2m3n4o5p6
Revises: j1k2l3m4n5o6
Create Date: 2026-04-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'k1l2m3n4o5p6'
down_revision: Union[str, Sequence[str], None] = 'j1k2l3m4n5o6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'revoked_tokens',
        sa.Column('jti', sa.String(36), primary_key=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_revoked_tokens_expires_at', table_name='revoked_tokens')
    op.drop_table('revoked_tokens')
