"""Schema-only compatibility metadata for legacy ``schools`` columns.

These columns intentionally do *not* belong to the ORM model.  They remain
database-owned compatibility storage while older tenants are being preserved;
application serializers and authentication code must not start reading or
writing them again.

The type instances are kept here (rather than duplicating them in the
migration and Alembic environment) so the migration, autogenerate guard, and
schema-drift test all agree on the exact five-column contract.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# SQLAlchemy type definitions for the columns as they existed in the
# production schema.  ``String()`` deliberately has no length: principal
# mobile values are unbounded VARCHAR, not a newly-imposed phone limit.
PRESERVED_SCHOOL_COLUMNS: Mapping[str, sa.types.TypeEngine[Any]] = {
    "configuration": JSONB(astext_type=sa.Text()),
    "location": JSONB(astext_type=sa.Text()),
    "setup_completed": sa.Boolean(),
    "setup_steps_completed": JSONB(astext_type=sa.Text()),
    "principal_mobile": sa.String(),
}

# A small set of already-deployed columns have intentionally narrower or
# ``TEXT`` physical definitions than their current unbounded ORM ``String``.
# These are explicit compatibility contracts, not a global "accept any
# narrowing" rule.  Keep the widths tied to the migrations that introduced
# them so a future accidental VARCHAR(32) / TEXT drift still fails closed.
KNOWN_PHYSICAL_COLUMN_TYPES: Mapping[
    tuple[str, str], sa.types.TypeEngine[Any]
] = {
    ("schools", "last_export_token_hash"): sa.String(length=64),
    ("schools", "last_export_initiator_jti"): sa.String(length=128),
    ("notifications_preferences", "id"): sa.String(length=64),
    ("notifications_preferences", "user_id"): sa.String(length=64),
    ("notifications", "category"): sa.String(length=64),
    ("notifications", "cta_url"): sa.String(length=512),
    ("students", "pending_parent_phone"): sa.Text(),
    ("students", "pending_parent_email"): sa.Text(),
}


def is_preserved_school_column(
    object_: Any,
    name: str,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Return whether Alembic is looking at a DB-only preserved column.

    Alembic calls ``include_object`` for a reflected database column that is
    absent from ``target_metadata`` with ``reflected=True`` and
    ``compare_to=None``.  Returning ``False`` for only this precise case
    prevents autogenerate from proposing a DROP while leaving all other
    tables/columns fully comparable.
    """

    if type_ != "column" or not reflected or compare_to is not None:
        return False

    table = getattr(object_, "table", None)
    table_name = getattr(table, "name", None)
    table_schema = getattr(table, "schema", None)
    if table_name != "schools" or table_schema not in (None, "public"):
        return False

    return name in PRESERVED_SCHOOL_COLUMNS


def is_managed_production(environ: Mapping[str, str] | None = None) -> bool:
    """Whether Alembic is running inside a managed Replit deployment.

    ``ENVIRONMENT`` is intentionally not consulted: development workflows can
    exercise production-mode application settings, while ``REPLIT_DEPLOYMENT``
    is the deployment marker owned by the managed runtime.  Empty and common
    explicit false values mean "not managed"; any other non-empty marker is
    treated as managed (fail closed for unexpected marker values).
    """

    values = os.environ if environ is None else environ
    marker = (values.get("REPLIT_DEPLOYMENT") or "").strip().lower()
    return bool(marker) and marker not in {"0", "false", "no", "off"}


def assert_online_migrations_allowed(
    environ: Mapping[str, str] | None = None,
) -> None:
    """Fail closed before an online Alembic connection is created."""

    if is_managed_production(environ):
        raise RuntimeError(
            "Refusing online Alembic migrations in a managed Replit "
            "deployment (REPLIT_DEPLOYMENT is truthy). Publish owns "
            "production schema changes; use offline SQL generation for a "
            "read-only migration plan."
        )


__all__ = [
    "KNOWN_PHYSICAL_COLUMN_TYPES",
    "PRESERVED_SCHOOL_COLUMNS",
    "assert_online_migrations_allowed",
    "is_managed_production",
    "is_preserved_school_column",
]