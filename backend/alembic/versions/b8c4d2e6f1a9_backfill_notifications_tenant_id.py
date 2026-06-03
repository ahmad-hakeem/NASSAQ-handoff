"""Backfill notifications.tenant_id from the recipient's school (Task #779)

Revision ID: b8c4d2e6f1a9
Revises: f7a3c9b1d2e4
Create Date: 2026-06-03

One-off, reversible DATA migration. Many legacy notifications were written with
a NULL ``tenant_id`` (e.g. every ``school_principal`` row and many teacher /
parent rows). School-scoped counters such as ``GET /notifications/analytics``
count strictly by ``tenant_id`` whenever present, so a real principal whose only
notifications are legacy NULL-tenant rows sees a 0 total even though the
notifications exist and are visible to them.

This migration derives the school tag from the recipient user's tenant
(``users.tenant_id``) for every NULL-tenant notification where it can be safely
derived, and leaves true platform/global rows NULL (platform admins carry a NULL
``tenant_id``, so they are excluded automatically).

It is NON-DESTRUCTIVE: ``upgrade()`` only CREATEs a bookkeeping table and runs
INSERT/UPDATE. To make the change exactly reversible, the ids of the rows we
touch (and the value we applied) are recorded in
``notifications_tenant_backfill_779``; ``downgrade()`` restores precisely those
rows to NULL — without clobbering any tenant tag written after this migration —
and drops the bookkeeping table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c4d2e6f1a9"
down_revision: Union[str, Sequence[str], None] = "f7a3c9b1d2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BACKFILL_TABLE = "notifications_tenant_backfill_779"


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Record exactly which NULL-tenant notifications we will tag, and with
    #    which school, so the change can be reversed precisely later.
    conn.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS {_BACKFILL_TABLE} (
                notification_id   VARCHAR PRIMARY KEY,
                applied_tenant_id VARCHAR NOT NULL
            )
            """
        )
    )
    conn.execute(
        sa.text(
            f"""
            INSERT INTO {_BACKFILL_TABLE} (notification_id, applied_tenant_id)
            SELECT n.id, u.tenant_id
            FROM notifications n
            JOIN users u ON u.id = n.user_id
            WHERE n.tenant_id IS NULL
              AND u.tenant_id IS NOT NULL
            ON CONFLICT (notification_id) DO NOTHING
            """
        )
    )

    # 2. Apply the backfill. Only touch rows still NULL (idempotent / safe to
    #    re-run). ``users.tenant_id`` is FK-bound to ``schools.id``, so every
    #    value we copy already satisfies the ``notifications.tenant_id`` FK.
    conn.execute(
        sa.text(
            f"""
            UPDATE notifications n
            SET tenant_id = b.applied_tenant_id
            FROM {_BACKFILL_TABLE} b
            WHERE n.id = b.notification_id
              AND n.tenant_id IS NULL
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Restore the rows this migration tagged back to NULL, but only where the
    # stored value is unchanged — never clobber a tenant tag written after this
    # migration ran.
    conn.execute(
        sa.text(
            f"""
            UPDATE notifications n
            SET tenant_id = NULL
            FROM {_BACKFILL_TABLE} b
            WHERE n.id = b.notification_id
              AND n.tenant_id = b.applied_tenant_id
            """
        )
    )
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {_BACKFILL_TABLE}"))
