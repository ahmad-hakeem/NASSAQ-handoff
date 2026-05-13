"""Merge IT workspace branches into a single head.

Revision ID: f1a2b3c4d5e7
Revises: ('c1d2e3f4a5b6', 'e7f8a9b0c1d2')
Create Date: 2026-05-13

Empty merge node that joins the two open §6.x heads:

* ``c1d2e3f4a5b6`` — lesson_plans + workspace_quota counter columns
  (which itself merged the renumbered b1/b4 branches).
* ``e7f8a9b0c1d2`` — schools.reactivation_banner columns
  (chained off c5d6e7f8a9b0 → b4c5d6e7f8a9 archive columns).

Both branches grew in parallel after the original duplicate-revision
mistake on ``b4c5d6e7f8a9`` / ``b1c2d3e4f5a6``. Now that those are
renumbered, this merge gives ``alembic upgrade head`` a single
deterministic target on a fresh database.
"""
from typing import Sequence, Union


revision: str = "f1a2b3c4d5e7"
down_revision: Union[str, Sequence[str], None] = ("c1d2e3f4a5b6", "e7f8a9b0c1d2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
