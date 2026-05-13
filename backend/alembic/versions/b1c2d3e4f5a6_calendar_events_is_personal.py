"""IT Phase 2 §6.3 — calendar_events.is_personal flag

Revision ID: b1c2d3e4f5a6
Revises: a3b4c5d6e7f8
Create Date: 2026-05-12

Adds a single nullable boolean column ``is_personal`` (default ``false``) to
``calendar_events`` so the IT personal-event surface (§6.3) can disambiguate
its rows from school-wide principal calendar entries that share the table.

The column is nullable for backfill safety on existing rows; the new IT-only
routes always set it explicitly to ``True`` server-side and the legacy
``calendar_routes_mod`` never touches it (so principal events keep ``NULL``,
which the read filter treats as ``not personal``). No data migration is
needed: every legacy row stays exactly as it was.

Alembic-only — no Pydantic, no business logic, no route changes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "calendar_events",
        sa.Column(
            "is_personal",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_calendar_events_tenant_personal_creator",
        "calendar_events",
        ["tenant_id", "is_personal", "created_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_calendar_events_tenant_personal_creator",
        table_name="calendar_events",
    )
    op.drop_column("calendar_events", "is_personal")
