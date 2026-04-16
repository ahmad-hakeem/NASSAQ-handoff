"""fix approval_events FK to reference registration_requests

Revision ID: l1m2n3o4p5q6
Revises: k1l2m3n4o5p6
Create Date: 2026-04-16
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = 'l1m2n3o4p5q6'
down_revision: Union[str, Sequence[str], None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(
        "DELETE FROM approval_events WHERE request_id NOT IN "
        "(SELECT id FROM registration_requests)"
    ))

    fk_exists = conn.execute(text(
        "SELECT 1 FROM information_schema.table_constraints "
        "WHERE constraint_name = 'approval_events_request_id_fkey' "
        "AND table_name = 'approval_events'"
    )).fetchone()
    if fk_exists:
        op.drop_constraint('approval_events_request_id_fkey', 'approval_events', type_='foreignkey')

    op.create_foreign_key(
        'approval_events_request_id_fkey',
        'approval_events',
        'registration_requests',
        ['request_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('approval_events_request_id_fkey', 'approval_events', type_='foreignkey')
    op.create_foreign_key(
        'approval_events_request_id_fkey',
        'approval_events',
        'approval_requests',
        ['request_id'],
        ['id'],
        ondelete='CASCADE',
    )
