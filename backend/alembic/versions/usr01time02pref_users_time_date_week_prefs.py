"""add time_format, date_format, first_day_of_week to users

Revision ID: usr01time02pref
Revises: e5b9c2d7f1a3
Create Date: 2026-07-28 00:00:00.000000

These three preference columns were absent from the users table, so
PUT /users/me/preferences was silently dropping them on every write
(gd_update_one only persists real columns).  As a result:
  - time_format always fell back to the "12h" hardcoded default
  - date_format always fell back to "dd/mm/yyyy"
  - first_day_of_week always fell back to "sunday"
regardless of what the user selected and saved.
"""
from alembic import op
import sqlalchemy as sa

revision = 'usr01time02pref'
down_revision = 'e5b9c2d7f1a3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('time_format', sa.String(), nullable=True, server_default='12h'))
    op.add_column('users', sa.Column('date_format', sa.String(), nullable=True, server_default='dd/mm/yyyy'))
    op.add_column('users', sa.Column('first_day_of_week', sa.String(), nullable=True, server_default='sunday'))


def downgrade():
    op.drop_column('users', 'first_day_of_week')
    op.drop_column('users', 'date_format')
    op.drop_column('users', 'time_format')
