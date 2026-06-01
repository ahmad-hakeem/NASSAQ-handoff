"""add calendar_events table for administrative calendar widget

Revision ID: q1r2s3t4u5v6
Revises: p1q2r3s4t5u6
Create Date: 2026-04-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_idempotent import has_table

revision: str = 'q1r2s3t4u5v6'
down_revision: Union[str, Sequence[str], None] = 'p1q2r3s4t5u6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table('calendar_events'):
        op.create_table(
            'calendar_events',
            sa.Column('id', sa.String(), primary_key=True, nullable=False),
            sa.Column('tenant_id', sa.String(), sa.ForeignKey('schools.id', ondelete='CASCADE'), nullable=True),
            sa.Column('title_ar', sa.String(), nullable=False),
            sa.Column('title_en', sa.String(), nullable=True),
            sa.Column('type', sa.String(), nullable=False, server_default='meeting'),
            sa.Column('date', sa.String(), nullable=False),
            sa.Column('details_ar', sa.Text(), nullable=True),
            sa.Column('details_en', sa.Text(), nullable=True),
            sa.Column('created_by', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        )
    op.create_index('ix_calendar_events_tenant_id', 'calendar_events', ['tenant_id'], if_not_exists=True)
    op.create_index('ix_calendar_events_type', 'calendar_events', ['type'], if_not_exists=True)
    op.create_index('ix_calendar_events_date', 'calendar_events', ['date'], if_not_exists=True)
    op.create_index('idx_calendar_events_tenant_date', 'calendar_events', ['tenant_id', 'date'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('idx_calendar_events_tenant_date', table_name='calendar_events')
    op.drop_index('ix_calendar_events_date', table_name='calendar_events')
    op.drop_index('ix_calendar_events_type', table_name='calendar_events')
    op.drop_index('ix_calendar_events_tenant_id', table_name='calendar_events')
    op.drop_table('calendar_events')
