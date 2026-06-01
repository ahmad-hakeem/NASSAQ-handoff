"""IT first-login onboarding tour — users.it_onboarding_completed_at (Task #250)

Revision ID: a4b5c6d7e8f9
Revises: f1a2b3c4d5e7
Create Date: 2026-05-13

Adds a single nullable timestamp column ``users.it_onboarding_completed_at``
that stamps when an Independent Teacher (IT) finished — or explicitly
skipped — the first-login guided tour. NULL means "should still run the
tour on next IT dashboard mount". The column is global (not IT-scoped)
because non-IT roles never hit the trigger surfaces; their value just
remains NULL forever.

Reset by ``POST /independent-teacher/onboarding/reset`` from the
account-settings "إعادة الجولة" link, which clears the column back to
NULL so the welcome card pops on next dashboard load.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column


revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("users", "it_onboarding_completed_at"):
        op.add_column(
            "users",
            sa.Column(
                "it_onboarding_completed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    op.drop_column("users", "it_onboarding_completed_at")
