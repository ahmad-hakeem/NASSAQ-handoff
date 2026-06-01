"""independent teacher phase 1 — schedule_sessions.version optimistic concurrency token

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-05-12

Adds a monotonically increasing ``version`` integer to ``schedule_sessions``
so the Independent Teacher manual schedule editor (spec
``2026-05-12-independent-teacher-phased-spec.md`` §5.4) can implement
optimistic concurrency on its single-endpoint upsert
(``PUT /independent-teacher/schedule/slot``).

Design notes
------------
* Column is added with ``server_default='1' NOT NULL`` so PostgreSQL
  back-fills every existing row in a single statement — online-safe even
  on large tables, no separate backfill pass needed.
* The ``server_default`` is intentionally **kept** after the migration.
  Per the spec the application supplies ``version = version + 1`` on
  every UPDATE explicitly, so the default is only a safety net for any
  out-of-band INSERT that forgets to set the column. Keeping it costs
  nothing and matches the conservative posture used elsewhere in the
  schema.
* No existing route reads or writes ``version`` yet — this is the
  foundation ticket; the editor route ships separately and is the only
  caller that will rely on the column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("schedule_sessions", "version"):
        op.add_column(
            "schedule_sessions",
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            ),
        )


def downgrade() -> None:
    op.drop_column("schedule_sessions", "version")
