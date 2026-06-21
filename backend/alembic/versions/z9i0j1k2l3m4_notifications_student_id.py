"""add student_id column to notifications

Revision ID: z9i0j1k2l3m4
Revises: z8h9i0j1k2l3
Create Date: 2026-06-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'z9i0j1k2l3m4'
down_revision = 'z8h9i0j1k2l3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'notifications',
        sa.Column(
            'student_id',
            sa.String(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        'fk_notifications_student_id',
        'notifications', 'students',
        ['student_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'idx_pg_notifications_tenant_student',
        'notifications',
        ['tenant_id', 'student_id'],
    )
    # Backfill from the metadata JSONB column where legacy triggers stored
    # student_id. Only populate when the referenced student exists in the
    # same tenant so the FK invariant is never violated.
    op.execute(
        """
        UPDATE notifications n
        SET student_id = (n.metadata->>'student_id')
        WHERE n.metadata ? 'student_id'
          AND (n.metadata->>'student_id') IS NOT NULL
          AND (n.metadata->>'student_id') <> ''
          AND EXISTS (
              SELECT 1 FROM students s
              WHERE s.id = (n.metadata->>'student_id')
                AND (n.tenant_id IS NULL OR s.school_id = n.tenant_id)
          )
        """
    )


def downgrade():
    op.drop_index('idx_pg_notifications_tenant_student', table_name='notifications')
    op.drop_constraint('fk_notifications_student_id', 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'student_id')
