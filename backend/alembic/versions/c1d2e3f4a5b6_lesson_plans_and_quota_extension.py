"""IT Phase 2 §6.4 — lesson_plans table + workspace_quota counter columns (Task #209)

Revision ID: c1d2e3f4a5b6
Revises: ('b1c2d3e4f5a6', 'b4c5d6e7f8a9')
Create Date: 2026-05-13

Merges the two open §6.x heads (calendar `is_personal` and
`workspace_quota`) and ships the storage backing the §6.4 light
AI lesson-planning assistant for Independent Teachers:

  * NEW table ``lesson_plans`` — one row per saved generation, scoped
    to the IT workspace via ``workspace_school_id`` (always the
    synthetic ``itw_{user_id}`` schools row, never a real-school
    tenant). Authored exclusively by the IT user (``created_by``).
  * Two extra documentation-only columns on ``workspace_quota``:
    ``lesson_plans_today`` (int, default 0) and
    ``lesson_plans_today_date`` (date, nullable). Counters reset on a
    UTC-day boundary in application code, mirroring ``imports_today``.

The runtime persists ``workspace_quota`` rows through the
``GenericDocument`` JSONB fallback (no ORM model exists for that
collection), so the new columns are documentation/audit aids — the
real values flow through the JSONB ``data`` blob. The ``lesson_plans``
table, by contrast, has a typed ORM model so it is queryable directly
in production.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = ("b1c2d3e4f5a6", "b4c5d6e7f8a9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lesson_plans",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_school_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("grade_level", sa.String(length=200), nullable=True),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="ar"),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("class_id", sa.String(), nullable=True),
        sa.Column("is_saved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_school_id"], ["schools.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lesson_plans_ws_created",
        "lesson_plans",
        ["workspace_school_id", "created_at"],
    )
    op.create_index(
        "ix_lesson_plans_ws_author",
        "lesson_plans",
        ["workspace_school_id", "created_by"],
    )

    # Documentation-only columns on workspace_quota — runtime stores the
    # counters in the JSONB ``data`` blob via the GenericDocument
    # fallback, but mirroring them as typed columns keeps the schema
    # self-describing for ad-hoc queries / future promotion.
    op.add_column(
        "workspace_quota",
        sa.Column(
            "lesson_plans_today", sa.Integer(),
            nullable=False, server_default="0",
        ),
    )
    op.add_column(
        "workspace_quota",
        sa.Column(
            "lesson_plans_today_date", sa.Date(), nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("workspace_quota", "lesson_plans_today_date")
    op.drop_column("workspace_quota", "lesson_plans_today")
    op.drop_index("ix_lesson_plans_ws_author", table_name="lesson_plans")
    op.drop_index("ix_lesson_plans_ws_created", table_name="lesson_plans")
    op.drop_table("lesson_plans")
