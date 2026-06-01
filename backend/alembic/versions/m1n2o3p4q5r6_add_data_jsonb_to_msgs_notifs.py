"""add data JSONB column to messages and notifications

Revision ID: m1n2o3p4q5r6
Revises: l1m2n3o4p5q6
Create Date: 2026-04-16

The Communication Center, parent/teacher messaging, and several other
flows write rich documents (title, content, audience, audience_ids,
status, sent_count, sender_name, sender_role, receiver_id, etc.) into
the `messages` and `notifications` tables via the gd_insert helper.
The ORM models for these tables only had a small set of typed columns,
and the helper silently dropped any field that did not match a column.
As a result, sent broadcasts/announcements lost almost all of their
content and never reached recipients (no fan-out notifications either,
because the request would proceed but the message body was empty).

Adding a `data` JSONB column matches the GenericDocument fallback used
elsewhere in the codebase and lets the helper preserve any extra
fields, restoring the full Communication Center pipeline without
forcing every caller to change shape.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from migration_idempotent import has_column


revision: str = 'm1n2o3p4q5r6'
down_revision: Union[str, Sequence[str], None] = 'l1m2n3o4p5q6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column('messages', 'data'):
        op.add_column(
            'messages',
            sa.Column('data', JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        )
    if not has_column('notifications', 'data'):
        op.add_column(
            'notifications',
            sa.Column('data', JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        )


def downgrade() -> None:
    op.drop_column('notifications', 'data')
    op.drop_column('messages', 'data')
