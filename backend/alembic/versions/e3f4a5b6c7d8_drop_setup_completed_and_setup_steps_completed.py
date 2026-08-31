"""drop setup_completed and setup_steps_completed from schools

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from migration_idempotent import has_column

revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop setup_completed column from schools
    if has_column('schools', 'setup_completed'):
        op.drop_column('schools', 'setup_completed')

    # 2. Drop setup_steps_completed JSONB column from schools
    if has_column('schools', 'setup_steps_completed'):
        op.drop_column('schools', 'setup_steps_completed')


def downgrade() -> None:
    if not has_column('schools', 'setup_completed'):
        op.add_column('schools', sa.Column('setup_completed', sa.Boolean(), nullable=True, server_default=sa.text('false')))

    if not has_column('schools', 'setup_steps_completed'):
        op.add_column('schools', sa.Column('setup_steps_completed', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'[]'::jsonb")))
