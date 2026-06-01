"""add daily_tasks table for Hakeem's Daily Plan widget

Revision ID: r1s2t3u4v5w6
Revises: q1r2s3t4u5v6
Create Date: 2026-04-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_table
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'r1s2t3u4v5w6'
down_revision: Union[str, Sequence[str], None] = 'q1r2s3t4u5v6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table('daily_tasks'):
        op.create_table(
            'daily_tasks',
            sa.Column('id', sa.String(), primary_key=True, nullable=False),
            sa.Column('tenant_id', sa.String(), sa.ForeignKey('schools.id', ondelete='CASCADE'), nullable=True),
            sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('priority', sa.String(), nullable=False, server_default='normal'),
            sa.Column('status', sa.String(), nullable=False, server_default='active'),
            sa.Column('source', sa.String(), nullable=False, server_default='manual'),
            sa.Column('task_date', sa.String(), nullable=False),
            sa.Column('ai_meta', JSONB(), nullable=True),
            sa.Column('created_by', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        )
    op.create_index('ix_daily_tasks_tenant_id', 'daily_tasks', ['tenant_id'], if_not_exists=True)
    op.create_index('ix_daily_tasks_user_id', 'daily_tasks', ['user_id'], if_not_exists=True)
    op.create_index('ix_daily_tasks_priority', 'daily_tasks', ['priority'], if_not_exists=True)
    op.create_index('ix_daily_tasks_status', 'daily_tasks', ['status'], if_not_exists=True)
    op.create_index('ix_daily_tasks_source', 'daily_tasks', ['source'], if_not_exists=True)
    op.create_index('ix_daily_tasks_task_date', 'daily_tasks', ['task_date'], if_not_exists=True)
    op.create_index('idx_daily_tasks_user_date', 'daily_tasks', ['user_id', 'task_date'], if_not_exists=True)
    op.create_index('idx_daily_tasks_tenant_date', 'daily_tasks', ['tenant_id', 'task_date'], if_not_exists=True)
    op.create_index('idx_daily_tasks_user_status', 'daily_tasks', ['user_id', 'status'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('idx_daily_tasks_user_status', table_name='daily_tasks')
    op.drop_index('idx_daily_tasks_tenant_date', table_name='daily_tasks')
    op.drop_index('idx_daily_tasks_user_date', table_name='daily_tasks')
    op.drop_index('ix_daily_tasks_task_date', table_name='daily_tasks')
    op.drop_index('ix_daily_tasks_source', table_name='daily_tasks')
    op.drop_index('ix_daily_tasks_status', table_name='daily_tasks')
    op.drop_index('ix_daily_tasks_priority', table_name='daily_tasks')
    op.drop_index('ix_daily_tasks_user_id', table_name='daily_tasks')
    op.drop_index('ix_daily_tasks_tenant_id', table_name='daily_tasks')
    op.drop_table('daily_tasks')
