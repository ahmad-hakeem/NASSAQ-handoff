"""drop redundant schools columns: principal_mobile, configuration, location

Revision ID: d2e3f4a5b6c7
Revises: tch01sch02null
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from migration_idempotent import has_column

revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'tch01sch02null'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Backfill any non-empty principal_mobile into principal_phone before dropping
    if has_column('schools', 'principal_mobile') and has_column('schools', 'principal_phone'):
        op.execute(
            sa.text(
                "UPDATE schools SET principal_phone = principal_mobile "
                "WHERE (principal_phone IS NULL OR principal_phone = '') "
                "AND principal_mobile IS NOT NULL AND principal_mobile != ''"
            )
        )

    # 2. Drop redundant principal_mobile column
    if has_column('schools', 'principal_mobile'):
        op.drop_column('schools', 'principal_mobile')

    # 3. Drop redundant configuration JSONB column (now managed by school_settings table)
    if has_column('schools', 'configuration'):
        op.drop_column('schools', 'configuration')

    # 4. Drop redundant location JSONB column (already explicit columns: city, region, address, etc.)
    if has_column('schools', 'location'):
        op.drop_column('schools', 'location')


def downgrade() -> None:
    if not has_column('schools', 'location'):
        op.add_column('schools', sa.Column('location', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'))

    if not has_column('schools', 'configuration'):
        op.add_column('schools', sa.Column('configuration', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'))

    if not has_column('schools', 'principal_mobile'):
        op.add_column('schools', sa.Column('principal_mobile', sa.String(), nullable=True))
        op.execute(sa.text("UPDATE schools SET principal_mobile = principal_phone WHERE principal_mobile IS NULL"))
