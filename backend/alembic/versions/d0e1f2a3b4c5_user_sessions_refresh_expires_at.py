"""add refresh_expires_at to user_sessions

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-05-14

Task #374 follow-up — when a session is revoked we insert its refresh
JTI into ``revoked_tokens`` with an ``expires_at`` value. Until now we
were using ``user_sessions.expires_at`` for that, but that column is
derived from the ACCESS token's ``exp`` (~15 min). The background
cleanup loop in ``backend/app/lifecycle.py`` deletes ``revoked_tokens``
rows whose ``expires_at < now``, so the revoked refresh JTI was being
purged hours-to-days before the matching refresh token actually expired
(remember-me refresh = 30d). After cleanup, the ended device could
``/auth/refresh`` again and silently revive — defeating the entire fix.

Persist the refresh token's own expiry on the session row so the revoke
chain can use it. Nullable so legacy rows (and future rows where the
refresh was not supplied at insert time) keep working — they degrade to
the conservative fallback ``now + REFRESH_TOKEN_EXPIRE_MAX``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_sessions") as batch:
        batch.add_column(
            sa.Column(
                "refresh_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("user_sessions") as batch:
        batch.drop_column("refresh_expires_at")
