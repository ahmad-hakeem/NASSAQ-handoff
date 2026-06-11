"""Update stored platform office address from Riyadh to Al-Hofuf.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-06-10

Non-destructive data migration. Replaces the legacy public office address in
platform_settings.contact.address and system_settings contact address fields
so /public/contact-info and the shared footer reflect the new location without
requiring a manual platform-admin edit on every environment.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ADDRESS_AR = "الرياض، المملكة العربية السعودية"
_NEW_ADDRESS_AR = "الهفوف، الاحساء، المملكة العربية السعودية"
_OLD_ADDRESS_EN = "Riyadh, Saudi Arabia"
_NEW_ADDRESS_EN = "Al-Hofuf, Al-Ahsa, Saudi Arabia"


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            UPDATE platform_settings
            SET data = jsonb_set(
                COALESCE(data, '{}'::jsonb),
                '{contact,address}',
                to_jsonb(CAST(:new_addr AS text)),
                true
            ),
            updated_at = NOW()
            WHERE type = 'platform'
              AND COALESCE(data->'contact'->>'address', '') LIKE :old_prefix
            """
        ),
        {"new_addr": _NEW_ADDRESS_AR, "old_prefix": f"{_OLD_ADDRESS_AR}%"},
    )

    conn.execute(
        sa.text(
            """
            UPDATE system_settings
            SET data = jsonb_set(
                COALESCE(data, '{}'::jsonb),
                '{address_ar}',
                to_jsonb(CAST(:new_addr AS text)),
                true
            ),
            updated_at = NOW()
            WHERE type = 'contact'
              AND COALESCE(data->>'address_ar', '') LIKE :old_prefix
            """
        ),
        {"new_addr": _NEW_ADDRESS_AR, "old_prefix": f"{_OLD_ADDRESS_AR}%"},
    )

    conn.execute(
        sa.text(
            """
            UPDATE system_settings
            SET data = jsonb_set(
                COALESCE(data, '{}'::jsonb),
                '{address_en}',
                to_jsonb(CAST(:new_addr AS text)),
                true
            ),
            updated_at = NOW()
            WHERE type = 'contact'
              AND data->>'address_en' = :old_addr
            """
        ),
        {"new_addr": _NEW_ADDRESS_EN, "old_addr": _OLD_ADDRESS_EN},
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            UPDATE platform_settings
            SET data = jsonb_set(
                COALESCE(data, '{}'::jsonb),
                '{contact,address}',
                to_jsonb(CAST(:old_addr AS text)),
                true
            ),
            updated_at = NOW()
            WHERE type = 'platform'
              AND data->'contact'->>'address' = :new_addr
            """
        ),
        {"old_addr": _OLD_ADDRESS_AR, "new_addr": _NEW_ADDRESS_AR},
    )

    conn.execute(
        sa.text(
            """
            UPDATE system_settings
            SET data = jsonb_set(
                COALESCE(data, '{}'::jsonb),
                '{address_ar}',
                to_jsonb(CAST(:old_addr AS text)),
                true
            ),
            updated_at = NOW()
            WHERE type = 'contact'
              AND data->>'address_ar' = :new_addr
            """
        ),
        {"old_addr": _OLD_ADDRESS_AR, "new_addr": _NEW_ADDRESS_AR},
    )

    conn.execute(
        sa.text(
            """
            UPDATE system_settings
            SET data = jsonb_set(
                COALESCE(data, '{}'::jsonb),
                '{address_en}',
                to_jsonb(CAST(:old_addr AS text)),
                true
            ),
            updated_at = NOW()
            WHERE type = 'contact'
              AND data->>'address_en' = :new_addr
            """
        ),
        {"old_addr": _OLD_ADDRESS_EN, "new_addr": _NEW_ADDRESS_EN},
    )
