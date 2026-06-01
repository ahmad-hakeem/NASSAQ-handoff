"""add user_sessions table for active session tracking

Revision ID: o1p2q3r4s5t6
Revises: n1o2p3q4r5s6
Create Date: 2026-04-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_idempotent import has_table

revision: str = 'o1p2q3r4s5t6'
down_revision: Union[str, Sequence[str], None] = 'n1o2p3q4r5s6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table('user_sessions'):
        op.create_table(
            'user_sessions',
            sa.Column('id', sa.String(36), primary_key=True, nullable=False),
            sa.Column('user_id', sa.String(36), nullable=False),
            sa.Column('jti', sa.String(64), nullable=False, unique=True),
            sa.Column('device', sa.String(128), nullable=True),
            sa.Column('browser', sa.String(64), nullable=True),
            sa.Column('os', sa.String(64), nullable=True),
            sa.Column('ip_address', sa.String(64), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('location', sa.String(128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        )
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'], if_not_exists=True)
    op.create_index('ix_user_sessions_jti', 'user_sessions', ['jti'], if_not_exists=True)
    op.create_index('ix_user_sessions_revoked_at', 'user_sessions', ['revoked_at'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_user_sessions_revoked_at', table_name='user_sessions')
    op.drop_index('ix_user_sessions_jti', table_name='user_sessions')
    op.drop_index('ix_user_sessions_user_id', table_name='user_sessions')
    op.drop_table('user_sessions')
