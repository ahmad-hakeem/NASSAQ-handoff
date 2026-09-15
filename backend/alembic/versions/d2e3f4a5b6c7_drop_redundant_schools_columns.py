"""Retire the unsafe ``schools``-column cleanup revision.

Revision ID: d2e3f4a5b6c7
Revises: tch01sch02null
Create Date: 2026-08-31

This revision originally backfilled ``principal_mobile`` into
``principal_phone`` and dropped three still-populated compatibility columns.
That data-destructive body is intentionally retired in place: the revision ID
and graph remain stable, but both directions are now no-ops.  Existing rows
are never rewritten or removed.  The later additive preservation revision
re-adds columns only for databases where an already-applied historical
revision removed them; fresh/older databases retain their original columns.
"""
from typing import Sequence, Union

revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'tch01sch02null'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Safely retire the historical destructive upgrade as a no-op."""

    pass


def downgrade() -> None:
    """Never recreate or backfill columns during a graph downgrade."""

    pass
