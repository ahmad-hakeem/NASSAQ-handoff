"""consolidate product_issues type into issue_type

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


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
    if _column_exists(conn, "product_issues", "type"):
        op.execute(
            sa.text(
                'UPDATE "product_issues" SET "issue_type" = "type" '
                'WHERE ("issue_type" IS NULL OR "issue_type" = \'\') '
                'AND "type" IS NOT NULL AND "type" != \'\''
            )
        )
        op.drop_column("product_issues", "type")


def downgrade():
    conn = op.get_bind()
    if not _column_exists(conn, "product_issues", "type"):
        op.add_column("product_issues", sa.Column("type", sa.String(), nullable=True))
        op.execute(sa.text('UPDATE "product_issues" SET "type" = "issue_type"'))
