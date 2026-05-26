"""Add deleted_at and deleted_by columns to teachers and subjects for soft delete

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-05-26

Task #645 — gives the principal a "Recently deleted" surface for teachers
and subjects with a parallel Restore action. Both tables previously
lacked the soft-delete bookkeeping columns; ``classes`` already has them
(see migration ``b7c8d9e0f1a2_classes_soft_delete_columns``).
"""
from alembic import op
import sqlalchemy as sa

revision = 'd9e0f1a2b3c4'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('teachers', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('teachers', sa.Column('deleted_by', sa.String(), nullable=True))
    op.add_column('subjects', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subjects', sa.Column('deleted_by', sa.String(), nullable=True))


def downgrade():
    op.drop_column('subjects', 'deleted_by')
    op.drop_column('subjects', 'deleted_at')
    op.drop_column('teachers', 'deleted_by')
    op.drop_column('teachers', 'deleted_at')
