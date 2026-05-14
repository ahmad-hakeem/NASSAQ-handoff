"""add refresh_jti and refresh_family_id to user_sessions

Revision ID: c9d0e1f2a3b4
Revises: b3c4d5e6f7a8
Create Date: 2026-05-14

Task #374 — parent session revocation must close BOTH the access JTI
(already in revoked_tokens) AND the refresh JTI for the same session,
otherwise the "ended" device silently revives on its next /auth/refresh.
We persist the refresh JTI alongside the access JTI on each session row,
plus the refresh family id so DELETE /settings/sessions/{id} can also
write a revoked_token_families row to kill the whole rotation lineage.

Both columns are nullable so legacy rows minted before this migration
keep working — they just degrade to access-JTI-only revocation, same as
today.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_sessions") as batch:
        batch.add_column(sa.Column("refresh_jti", sa.String(64), nullable=True))
        batch.add_column(sa.Column("refresh_family_id", sa.String(64), nullable=True))
    op.create_index(
        "ix_user_sessions_refresh_jti", "user_sessions", ["refresh_jti"]
    )
    op.create_index(
        "ix_user_sessions_refresh_family_id",
        "user_sessions",
        ["refresh_family_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_sessions_refresh_family_id", table_name="user_sessions"
    )
    op.drop_index("ix_user_sessions_refresh_jti", table_name="user_sessions")
    with op.batch_alter_table("user_sessions") as batch:
        batch.drop_column("refresh_family_id")
        batch.drop_column("refresh_jti")
