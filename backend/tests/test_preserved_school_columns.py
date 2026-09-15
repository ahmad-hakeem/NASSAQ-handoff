"""Focused guards for the DB-only school compatibility-column contract."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from src.core.database.preserved_school_columns import (
    PRESERVED_SCHOOL_COLUMNS,
    assert_online_migrations_allowed,
    is_preserved_school_column,
)


_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "d4e5f6a7b8c9_preserve_legacy_school_columns.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "preserve_legacy_school_columns", _MIGRATION_PATH
)
_MIGRATION = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MIGRATION)


def _load_migration(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(
        module_name,
        Path(__file__).resolve().parent.parent / "alembic" / "versions" / filename,
    )
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    return migration


_RETIRED_MIGRATIONS = (
    _load_migration(
        "d2e3f4a5b6c7_drop_redundant_schools_columns.py",
        "retired_drop_redundant_school_columns",
    ),
    _load_migration(
        "e3f4a5b6c7d8_drop_setup_completed_and_setup_steps_completed.py",
        "retired_drop_setup_school_columns",
    ),
)


EXPECTED_TYPES = {
    "configuration": JSONB,
    "location": JSONB,
    "setup_completed": sa.Boolean,
    "setup_steps_completed": JSONB,
    "principal_mobile": sa.String,
}


def _reflected_column(table: str = "schools", schema: str | None = "public"):
    return SimpleNamespace(table=SimpleNamespace(name=table, schema=schema))


def test_registry_has_exact_nullable_unbounded_production_contract() -> None:
    assert set(PRESERVED_SCHOOL_COLUMNS) == set(EXPECTED_TYPES)

    for name, expected_type in EXPECTED_TYPES.items():
        column_type = PRESERVED_SCHOOL_COLUMNS[name]
        assert isinstance(column_type, expected_type), name
        if name == "principal_mobile":
            assert column_type.length is None, "mobile must remain unbounded VARCHAR"


@pytest.mark.parametrize("name", sorted(PRESERVED_SCHOOL_COLUMNS))
def test_autogenerate_guard_rejects_only_preserved_school_drops(name: str) -> None:
    assert is_preserved_school_column(
        _reflected_column(),
        name,
        "column",
        reflected=True,
        compare_to=None,
    )

    # A missing ORM column in another table, or a non-reflected/paired column,
    # must retain normal Alembic comparison behavior.
    assert not is_preserved_school_column(
        _reflected_column(table="users"),
        name,
        "column",
        reflected=True,
        compare_to=None,
    )
    assert not is_preserved_school_column(
        _reflected_column(),
        name,
        "column",
        reflected=False,
        compare_to=None,
    )
    assert not is_preserved_school_column(
        _reflected_column(),
        name,
        "column",
        reflected=True,
        compare_to=object(),
    )


def test_autogenerate_guard_does_not_blanket_allow_other_school_columns() -> None:
    assert not is_preserved_school_column(
        _reflected_column(),
        "principal_phone",
        "column",
        reflected=True,
        compare_to=None,
    )
    assert not is_preserved_school_column(
        _reflected_column(schema="tenant_a"),
        "configuration",
        "column",
        reflected=True,
        compare_to=None,
    )


def test_managed_deployment_guard_fails_before_online_migrations() -> None:
    with pytest.raises(RuntimeError, match="Publish owns production schema"):
        assert_online_migrations_allowed({"REPLIT_DEPLOYMENT": "1"})

    # ENVIRONMENT is deliberately irrelevant; development workflows may use
    # production-mode app settings without being a managed deployment.
    assert_online_migrations_allowed(
        {"ENVIRONMENT": "production", "REPLIT_DEPLOYMENT": ""}
    )


def test_migration_is_idempotent_and_never_overwrites_existing_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = set(PRESERVED_SCHOOL_COLUMNS)
    values = {
        "configuration": {"legacy": True},
        "location": {"city": "Riyadh"},
        "setup_completed": True,
        "setup_steps_completed": ["identity"],
        "principal_mobile": "+966555555555",
    }
    before = values.copy()
    added: list[sa.Column] = []

    monkeypatch.setattr(
        _MIGRATION,
        "has_column",
        lambda _table, name: name in existing,
    )

    class _Operations:
        def add_column(self, _table, column, *, schema=None):
            assert schema == "public"
            added.append(column)
            existing.add(column.name)

        def execute(self, *_args, **_kwargs):  # pragma: no cover - tripwire
            raise AssertionError("preservation migration must not execute DML")

    monkeypatch.setattr(_MIGRATION, "op", _Operations())

    _MIGRATION.upgrade()
    _MIGRATION.upgrade()

    assert added == []
    assert values == before


def test_migration_adds_missing_columns_once_with_no_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing: set[str] = set()
    added: list[sa.Column] = []

    monkeypatch.setattr(
        _MIGRATION,
        "has_column",
        lambda _table, name: name in existing,
    )

    class _Operations:
        def add_column(self, _table, column, *, schema=None):
            assert schema == "public"
            added.append(column)
            existing.add(column.name)

    monkeypatch.setattr(_MIGRATION, "op", _Operations())

    _MIGRATION.upgrade()
    _MIGRATION.upgrade()

    assert [column.name for column in added] == list(PRESERVED_SCHOOL_COLUMNS)
    assert all(column.nullable is True for column in added)
    assert all(column.server_default is None for column in added)
    assert all(column.default is None for column in added)


@pytest.mark.parametrize("migration", _RETIRED_MIGRATIONS)
def test_retired_historical_revisions_preserve_populated_synthetic_rows(
    migration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retirement is a safety no-op, not an assertion that old data vanished."""

    synthetic_row = {
        "configuration": {"legacy_flag": True},
        "location": {"city": "Riyadh"},
        "setup_completed": True,
        "setup_steps_completed": ["identity", "principal"],
        # Keep the production phone conflict visible: this old revision must
        # never copy mobile into (or otherwise rewrite) principal_phone.
        "principal_mobile": "+966555555555",
        "principal_phone": "+966500000000",
    }
    before = copy.deepcopy(synthetic_row)

    class _ForbiddenOperations:
        def __getattr__(self, operation):
            raise AssertionError(
                f"retired migration unexpectedly attempted {operation}"
            )

    # Tripwires make any future UPDATE/DROP/ADD reintroduction fail loudly.
    monkeypatch.setattr(migration, "op", _ForbiddenOperations(), raising=False)
    monkeypatch.setattr(
        migration,
        "has_column",
        lambda *_args, **_kwargs: True,
        raising=False,
    )

    migration.upgrade()
    migration.downgrade()

    assert synthetic_row == before
    assert "retired" in (migration.__doc__ or "").lower()
