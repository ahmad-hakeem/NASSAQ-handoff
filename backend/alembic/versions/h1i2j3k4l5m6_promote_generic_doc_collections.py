"""promote generic_documents events and system_settings to typed tables

Revision ID: h1i2j3k4l5m6
Revises: g1h2i3j4k5l6
Create Date: 2026-04-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'h1i2j3k4l5m6'
down_revision: Union[str, Sequence[str], None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('student_id', sa.String(), nullable=True),
        sa.Column('class_id', sa.String(), nullable=True),
        sa.Column('recorded_by', sa.String(), nullable=True),
        sa.Column('date', sa.String(), nullable=True),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_events_tenant_type', 'events', ['tenant_id', 'type'])
    op.create_index('idx_events_tenant_date', 'events', ['tenant_id', 'created_at'])
    op.create_index(op.f('ix_events_type'), 'events', ['type'])
    op.create_index(op.f('ix_events_tenant_id'), 'events', ['tenant_id'])
    op.create_index(op.f('ix_events_student_id'), 'events', ['student_id'])
    op.create_index(op.f('ix_events_class_id'), 'events', ['class_id'])

    op.create_table('system_settings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('updated_by', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('type'),
    )
    op.create_index(op.f('ix_system_settings_type'), 'system_settings', ['type'], unique=True)

    conn = op.get_bind()

    conn.execute(sa.text("""
        INSERT INTO events (id, tenant_id, type, status, student_id, class_id, recorded_by, date, data, created_at)
        SELECT
            COALESCE(gd.data->>'id', gd.id),
            CASE WHEN sc.id IS NOT NULL THEN gd.data->>'tenant_id' ELSE NULL END,
            COALESCE(gd.data->>'type', 'unknown'),
            gd.data->>'status',
            CASE WHEN s.id IS NOT NULL THEN gd.data->>'student_id' ELSE NULL END,
            CASE WHEN c.id IS NOT NULL THEN gd.data->>'class_id' ELSE NULL END,
            CASE WHEN u.id IS NOT NULL THEN gd.data->>'recorded_by' ELSE NULL END,
            gd.data->>'date',
            gd.data,
            CASE WHEN gd.data->>'created_at' IS NOT NULL
                 THEN (gd.data->>'created_at')::timestamptz
                 ELSE gd.created_at END
        FROM generic_documents gd
        LEFT JOIN schools sc ON sc.id = gd.data->>'tenant_id'
        LEFT JOIN students s ON s.id = gd.data->>'student_id'
        LEFT JOIN classes c ON c.id = gd.data->>'class_id'
        LEFT JOIN users u ON u.id = gd.data->>'recorded_by'
        WHERE gd.collection = 'events'
        ON CONFLICT (id) DO NOTHING
    """))

    conn.execute(sa.text("""
        INSERT INTO system_settings (id, type, data, updated_by, updated_at)
        SELECT
            COALESCE(gd.data->>'id', gd.id),
            COALESCE(gd.data->>'type', 'unknown'),
            COALESCE(gd.data->'data', '{}'::jsonb),
            CASE WHEN u2.id IS NOT NULL THEN gd.data->>'updated_by' ELSE NULL END,
            CASE WHEN gd.data->>'updated_at' IS NOT NULL
                 THEN (gd.data->>'updated_at')::timestamptz
                 ELSE gd.created_at END
        FROM generic_documents gd
        LEFT JOIN users u2 ON u2.id = gd.data->>'updated_by'
        WHERE gd.collection = 'system_settings'
        ON CONFLICT (id) DO NOTHING
    """))

    conn.execute(sa.text(
        "DELETE FROM generic_documents WHERE collection IN ('events', 'system_settings')"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    import json
    events_rows = conn.execute(sa.text("SELECT id, data, created_at FROM events")).fetchall()
    for row in events_rows:
        conn.execute(sa.text(
            "INSERT INTO generic_documents (id, collection, data, created_at) "
            "VALUES (:id, 'events', :data, :created_at) ON CONFLICT (id) DO NOTHING"
        ), {"id": row[0], "data": row[1], "created_at": row[2]})

    ss_rows = conn.execute(sa.text("SELECT id, type, data, updated_by, updated_at FROM system_settings")).fetchall()
    for row in ss_rows:
        doc = json.loads(row[2]) if isinstance(row[2], str) else (row[2] or {})
        full_doc = {"id": row[0], "type": row[1], "data": doc, "updated_by": row[3], "updated_at": str(row[4]) if row[4] else None}
        conn.execute(sa.text(
            "INSERT INTO generic_documents (id, collection, data, created_at) "
            "VALUES (:id, 'system_settings', :data, :updated_at) ON CONFLICT (id) DO NOTHING"
        ), {"id": row[0], "data": json.dumps(full_doc), "updated_at": row[4]})

    op.drop_index(op.f('ix_system_settings_type'), table_name='system_settings')
    op.drop_table('system_settings')
    op.drop_index(op.f('ix_events_class_id'), table_name='events')
    op.drop_index(op.f('ix_events_student_id'), table_name='events')
    op.drop_index(op.f('ix_events_tenant_id'), table_name='events')
    op.drop_index(op.f('ix_events_type'), table_name='events')
    op.drop_index('idx_events_tenant_date', table_name='events')
    op.drop_index('idx_events_tenant_type', table_name='events')
    op.drop_table('events')
