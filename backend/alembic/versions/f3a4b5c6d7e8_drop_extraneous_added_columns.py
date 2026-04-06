"""drop extraneous columns added by earlier migration

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None

COLUMNS_TO_DROP = [
    ("issue_comments", "created_at"),
    ("issue_comments", "updated_at"),
    ("counters", "updated_at"),
    ("approval_events", "created_at"),
]


def _column_exists(conn, table, column):
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column}
    )
    return result.scalar() is not None


def upgrade():
    conn = op.get_bind()
    for table, column in COLUMNS_TO_DROP:
        if _column_exists(conn, table, column):
            op.drop_column(table, column)


def downgrade():
    conn = op.get_bind()
    for table, column in COLUMNS_TO_DROP:
        if not _column_exists(conn, table, column):
            op.add_column(table, sa.Column(column, sa.DateTime(timezone=True), nullable=True))
