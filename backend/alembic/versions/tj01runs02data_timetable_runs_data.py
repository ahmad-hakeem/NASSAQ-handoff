"""add data JSONB overflow column to timetable_runs

Revision ID: tj01runs02data
Revises: rl01shared02ctr
Create Date: 2026-07-31 00:00:00.000000

``timetable_runs`` is a real table with no ``data`` column, so ``dict_to_model``
silently discarded every key the scheduling engine wrote that had no matching
column: ``started_at``, ``finished_at``, ``completion_percentage``,
``timetable_id``, ``created_by``, ``run_type``, ``conflicts_count``,
``unscheduled_count``, ``optimization_score``, ``notes`` and friends. The
engine's careful progress tracking was being thrown away on every run (visible
as ``sessions_created = 0`` on rows whose status is ``completed``).

Adding a ``data`` JSONB column makes ``dict_to_model`` route those extra keys
into it and ``model_to_dict`` merge them back on read, so the existing engine
writes become durable with no code change. This is what lets a generation run
be polled as a background job: progress and the resulting timetable id now
survive in Postgres, which matters because a poll can land on a different
autoscale instance than the one doing the work.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'tj01runs02data'
down_revision = 'rl01shared02ctr'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'timetable_runs',
        sa.Column(
            'data',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # Historical rows have no overflow payload; give them an empty object so
    # readers never have to distinguish NULL from "nothing was stored".
    op.execute("UPDATE timetable_runs SET data = '{}'::jsonb WHERE data IS NULL")
    # Polling filters unfinished runs by school; keep that lookup cheap.
    op.create_index(
        'idx_timetable_runs_school_status',
        'timetable_runs',
        ['school_id', 'status'],
    )


def downgrade():
    op.drop_index('idx_timetable_runs_school_status', table_name='timetable_runs')
    op.drop_column('timetable_runs', 'data')
