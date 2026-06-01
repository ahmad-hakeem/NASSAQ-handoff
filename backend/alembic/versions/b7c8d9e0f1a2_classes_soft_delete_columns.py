"""Add deleted_at and deleted_by columns to classes for soft delete

Revision ID: b7c8d9e0f1a2
Revises: t523a1b2c3d4
Create Date: 2026-05-25

"""
from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column

revision = 'b7c8d9e0f1a2'
down_revision = 't523a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade():
    if not has_column('classes', 'deleted_at'):
        op.add_column('classes', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    if not has_column('classes', 'deleted_by'):
        op.add_column('classes', sa.Column('deleted_by', sa.String(), nullable=True))


def downgrade():
    op.drop_column('classes', 'deleted_by')
    op.drop_column('classes', 'deleted_at')
