"""phase 3 security hardening — refresh-token families + per-tenant AI consent

Revision ID: w1x2y3z4a5b6
Revises: v1w2x3y4z5a6
Create Date: 2026-05-11

Adds:
  * `revoked_token_families` — when refresh-token reuse is detected, the entire
    family (lineage of rotated tokens descended from a single login) is revoked
    in one shot. Audit Open Question 5.
  * `schools.ai_consent_enabled` — per-tenant kill-switch for Hakim AI flows so
    sovereign / regulated deployments can refuse outbound LLM calls without
    code changes. DPIA prerequisite.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_idempotent import has_table, has_column


revision: str = "w1x2y3z4a5b6"
down_revision: Union[str, Sequence[str], None] = "v1w2x3y4z5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("revoked_token_families"):
        op.create_table(
            "revoked_token_families",
            sa.Column("family_id", sa.String(), primary_key=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column("user_id", sa.String(), nullable=True, index=True),
        )

    # Per-tenant AI consent flag. Default TRUE preserves the existing behaviour
    # for tenants already using Hakim; new sovereign deployments can flip this
    # off centrally to disable any outbound LLM call.
    with op.batch_alter_table("schools") as batch:
        if not has_column("schools", "ai_consent_enabled"):
            batch.add_column(
                sa.Column(
                    "ai_consent_enabled",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("schools") as batch:
        batch.drop_column("ai_consent_enabled")
    op.drop_table("revoked_token_families")
