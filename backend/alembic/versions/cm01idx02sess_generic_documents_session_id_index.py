"""Index generic_documents by (collection, data->>'session_id').

The class-metrics roll-up reads every ``session_attendance`` document for a
teacher's sessions in one query. Without this index Postgres can only seek on
``collection`` and then filters the rest of the collection away row by row
(measured: 848 rows kept, 835 discarded).

That is cheap today, but ``session_attendance`` is the fastest-growing
collection in the product — it gains one row per student per lesson, so it
scales with enrolment x timetable density, unlike ``class_sessions`` which
gains one row per lesson. A plain btree expression index keeps this a seek as
the collection grows, and it matches the shape of the existing
``idx_gd_collection_school`` / ``idx_gd_collection_date`` indexes.

Deliberately a plain btree, not a GIN/trigram index: the publish-time schema
diff rewrites trigram GIN indexes into an invalid form and breaks deploys.

Revision ID: cm01idx02sess
Revises: avt01size02norm
Create Date: 2026-08-03
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'cm01idx02sess'
down_revision = 'avt01size02norm'
branch_labels = None
depends_on = None

INDEX_NAME = 'idx_gd_collection_session'


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} "
        "ON generic_documents (collection, ((data ->> 'session_id')))"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
