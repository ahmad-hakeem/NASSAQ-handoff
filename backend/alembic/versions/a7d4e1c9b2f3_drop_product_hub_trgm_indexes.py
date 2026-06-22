"""drop product-hub pg_trgm GIN indexes (publish-diff incompatibility)

Revision ID: a7d4e1c9b2f3
Revises: f1a2b3c4d5e6
Create Date: 2026-06-22 00:00:00.000000

Why this exists
---------------
Revision f1a2b3c4d5e6 added four ``pg_trgm`` GIN trigram indexes on
``product_issues`` (title, employee_name, page, current_behavior) to speed up
keyword search on GET /product-hub/issues. Those indexes use the non-default
``gin_trgm_ops`` operator class.

Replit's publish-time schema diff introspects the development database and
replays the resulting DDL on production. Its reconstruction of a trigram GIN
index drops the ``gin_trgm_ops`` operator class, emitting:

    CREATE INDEX "idx_product_issues_current_behavior_trgm"
        ON "product_issues" USING gin ("current_behavior");

which Postgres rejects with "data type text has no default operator class for
access method gin", aborting the publish. A plain ``USING gin`` on a ``text``
column is invalid without an operator class.

``product_issues`` is a tiny internal product-feedback table (tens of rows), so
these trigram indexes provide no measurable benefit — a sequential scan is
already instant at this scale. Dropping them removes the only schema object the
publish diff cannot reproduce, unblocking deployment. Schema stays managed
exclusively via Alembic; no data is touched (index drops are schema-shape
changes, not data loss).
"""
from alembic import op

revision = 'a7d4e1c9b2f3'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP INDEX IF EXISTS idx_product_issues_title_trgm")
    op.execute("DROP INDEX IF EXISTS idx_product_issues_employee_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_product_issues_page_trgm")
    op.execute("DROP INDEX IF EXISTS idx_product_issues_current_behavior_trgm")


def downgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_issues_title_trgm "
        "ON product_issues USING GIN (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_issues_employee_name_trgm "
        "ON product_issues USING GIN (employee_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_issues_page_trgm "
        "ON product_issues USING GIN (page gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_issues_current_behavior_trgm "
        "ON product_issues USING GIN (current_behavior gin_trgm_ops)"
    )
