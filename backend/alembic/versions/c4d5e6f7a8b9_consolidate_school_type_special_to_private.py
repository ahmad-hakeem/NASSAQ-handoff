"""Consolidate deprecated school_type "special"/"special_needs" → "private"

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-05-14

The school-type domain historically exposed two distinct UI options for
the same business category:

    * "أهلية"  — canonical, stored as ``"private"``
    * "خاصة"   — deprecated synonym, stored as ``"special"`` (from the
                 settings page) or ``"special_needs"`` (from earlier
                 enum-driven flows).

Because both options were saved straight into ``schools.school_type``,
historical rows fragmented across three values for the same concept.
This migration backfills every existing row to the canonical
``"private"`` value before strict normalization is enforced at the API
boundary by ``utils.school_type.normalize_school_type``.

Scope is intentionally narrow: only the two deprecated aliases are
rewritten. The independent-teacher domain values
(``"independent_teacher"``, ``"independent_teacher_workspace"``) and
all other valid keys (``"public"``, ``"private"``, ``"international"``)
are left untouched.

This revision is data-only; no DDL changes. It is reversible — the
``downgrade`` is a no-op because the source values are no longer
distinguishable after backfill.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE schools
           SET school_type = 'private'
         WHERE school_type IN ('special', 'special_needs')
        """
    )


def downgrade() -> None:
    # No-op: the deprecated alias is no longer distinguishable from
    # canonically-stored ``private`` rows after the backfill, so we
    # cannot safely undo the consolidation.
    pass
