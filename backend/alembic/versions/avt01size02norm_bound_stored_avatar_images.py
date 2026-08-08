"""Bound stored avatar/logo images that were persisted at full resolution.

Avatars live as base64 ``data:`` URIs on ``users.avatar_url`` and are shipped
inline by every serializer that returns a user — most visibly ``GET /auth/me``,
which the app shell calls on each load. Measured before this change, one
account's avatar was 190,511 bytes and made that response 191 kB; the same
endpoint is 682 bytes for a user without an avatar, so the image was 99% of
the payload. ``schools.logo_url`` carries the same kind of value for
independent-teacher workspaces.

The write paths now normalise on upload (256 px, re-encoded). This backfills
the rows that predate that guard. Re-encoding is lossy but visually
indistinguishable: these images render at 40-128 px throughout the app.

Revision ID: avt01size02norm
Revises: pf02meta03prune
Create Date: 2026-08-02
"""
import logging

import sqlalchemy as sa
from alembic import op

revision = "avt01size02norm"
down_revision = "pf02meta03prune"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# Fixed identifiers, never user input — safe to interpolate.
_TARGETS = (("users", "avatar_url"), ("schools", "logo_url"))


def upgrade():
    try:
        from utils.avatar_image import AvatarImageError, normalize_avatar_data_url
    except ImportError:  # pragma: no cover - defensive
        # This is a data backfill, not a schema step. If the helper is ever
        # moved or removed, a fresh database (which has no rows to convert)
        # must still be able to run `alembic upgrade head`.
        log.warning("avatar backfill: normalizer unavailable, skipping")
        return

    bind = op.get_bind()
    for table, column in _TARGETS:
        rows = bind.execute(
            sa.text(f"SELECT id, {column} FROM {table} WHERE {column} LIKE 'data:%'")
        ).fetchall()

        for row_id, value in rows:
            try:
                normalized = normalize_avatar_data_url(value)
            except AvatarImageError as exc:
                # One undecodable image must never abort the run: this
                # migration is applied behind the boot-time schema head gate,
                # so a hard failure here would stop the app from starting.
                log.warning("avatar backfill: skipping %s.%s id=%s (%s)",
                            table, column, row_id, exc)
                continue
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("avatar backfill: unexpected failure on %s.%s id=%s (%s)",
                            table, column, row_id, exc)
                continue

            # Only ever shrink. A re-encode that grew the payload (already-small
            # or already-optimised images) is not worth the quality loss.
            if normalized and len(normalized) < len(value):
                bind.execute(
                    sa.text(f"UPDATE {table} SET {column} = :v WHERE id = :i"),
                    {"v": normalized, "i": row_id},
                )
                log.info("avatar backfill: %s.%s id=%s %d -> %d bytes",
                         table, column, row_id, len(value), len(normalized))


def downgrade():
    # Re-encoding is lossy; the original bytes are not recoverable.
    pass
