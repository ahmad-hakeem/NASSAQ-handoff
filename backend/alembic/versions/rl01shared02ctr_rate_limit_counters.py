"""Add rate_limit_counters: cross-worker store for auth/brute-force limits

Revision ID: rl01shared02ctr
Revises: usr01time02pref
Create Date: 2026-07-31

The login/auth limiter kept its sliding window in process memory, so a
deployment running N instances (Replit autoscale runs one uvicorn process
per machine and scales to N machines) enforced N x the intended budget for
a single attacker IP. This table is the shared counter store all workers
increment atomically, so the limit holds cluster-wide.

Kept separate from ``public_hakim_rate_counters`` on purpose: different key
space, different retention, and the public-Hakim surface must never be able
to evict auth counters (or vice versa) through the shared cleanup sweep.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_table


revision: str = "rl01shared02ctr"
down_revision: Union[str, Sequence[str], None] = "usr01time02pref"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("rate_limit_counters"):
        op.create_table(
            "rate_limit_counters",
            sa.Column("key", sa.String(length=200), primary_key=True),
            sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
    op.create_index(
        "ix_rate_limit_counters_expires_at",
        "rate_limit_counters",
        ["expires_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rate_limit_counters_expires_at",
        table_name="rate_limit_counters",
    )
    op.drop_table("rate_limit_counters")
