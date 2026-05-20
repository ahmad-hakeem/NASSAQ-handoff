"""merge heads after task #450

Revision ID: 629fb4a19af5
Revises: 4190214c47ac, p1c2h3a4r5t6
Create Date: 2026-05-20 11:08:10.955120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '629fb4a19af5'
down_revision: Union[str, Sequence[str], None] = ('4190214c47ac', 'p1c2h3a4r5t6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
