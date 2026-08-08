"""Prune recursively nested "data" duplicates from teacher_portfolio_meta docs.

_save_meta used to read-modify-write the doc returned by model_to_dict, which
keeps the raw JSONB column under a "data" key alongside the flattened fields.
Each save therefore re-embedded the previous full document, snowballing one
doc to 62 MB (nesting depth 6). Every /teacher/portfolio/sections request paid
~1.6 s detoasting that row just to filter 45 candidates.

The nested copy is pure stale duplicate: all reads use the flattened top-level
keys, and current attachments were already relocated to portfolio_files by
pf01files02blob. Removing the top-level nested key drops the whole chain.

Revision ID: pf02meta03prune
Revises: pf01files02blob
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op

revision = "pf02meta03prune"
down_revision = "pf01files02blob"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().execute(sa.text(
        "UPDATE generic_documents SET data = data - 'data' "
        "WHERE collection = 'teacher_portfolio_meta' "
        "AND jsonb_typeof(data->'data') = 'object'"
    ))


def downgrade():
    # The removed content was a stale self-copy; nothing to restore.
    pass
