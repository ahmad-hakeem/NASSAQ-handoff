"""add product issue number sequence

Revision ID: f3a1b2c4d5e6
Revises: e052f4eb5993
Create Date: 2026-04-05

"""
from alembic import op

revision = 'f3a1b2c4d5e6'
down_revision = 'e052f4eb5993'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE SEQUENCE IF NOT EXISTS product_issue_number_seq START 1")
    op.execute("""
        DO $$
        DECLARE max_num INTEGER;
        BEGIN
            SELECT COALESCE(MAX(issue_number), 0) INTO max_num FROM product_issues;
            IF max_num > 0 THEN
                PERFORM setval('product_issue_number_seq', max_num);
            END IF;
        END $$;
    """)

def downgrade():
    op.execute("DROP SEQUENCE IF EXISTS product_issue_number_seq")
