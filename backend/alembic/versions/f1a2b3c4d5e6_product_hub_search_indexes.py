"""add pg_trgm GIN indexes for product hub issue search

Revision ID: f1a2b3c4d5e6
Revises: z9i0j1k2l3m4
Create Date: 2026-06-21 12:00:00.000000

Performance: eliminates full-table regex scans on GET /product-hub/issues
when a search keyword is provided. The four GIN trigram indexes cover the
columns used by the $or search filter (title, employee_name, page,
current_behavior). PostgreSQL will use these automatically for both ILIKE
and ~* (case-insensitive regex) operators on short literal strings.
"""
from alembic import op

revision = 'f1a2b3c4d5e6'
down_revision = 'aa1bb2cc3dd4'
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_product_issues_title_trgm")
    op.execute("DROP INDEX IF EXISTS idx_product_issues_employee_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_product_issues_page_trgm")
    op.execute("DROP INDEX IF EXISTS idx_product_issues_current_behavior_trgm")
