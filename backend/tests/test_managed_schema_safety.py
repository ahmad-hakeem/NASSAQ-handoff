"""Regression guards for Replit Publish schema ownership.

These tests are intentionally metadata/source focused.  They do not run the
build script, invoke Alembic, or connect to a production database.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import insert, select
from sqlalchemy.dialects import postgresql

from src.core.database import db as database
from src.modules.bulk_import.entities.bulk_import_entity import BulkImportBatch
from src.modules.schools.entities.schools_entity import School
from src.modules.schools.dto.school_dto import (
    SchoolCreate,
    SchoolInfoUpdate,
    SchoolUpdate,
)
from src.core.database.preserved_school_columns import (
    KNOWN_PHYSICAL_COLUMN_TYPES,
    PRESERVED_SCHOOL_COLUMNS,
)


_ROOT = Path(__file__).resolve().parents[2]


def test_replit_build_is_database_independent() -> None:
    build = (_ROOT / "build.sh").read_text(encoding="utf-8").lower()
    assert "alembic" not in build
    assert "database_url" not in build
    assert "upgrade head" not in build


def test_managed_marker_uses_the_existing_explicit_replit_flag(monkeypatch) -> None:
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    assert database.is_replit_managed_deployment() is True

    monkeypatch.setenv("REPLIT_DEPLOYMENT", "true")
    assert database.is_replit_managed_deployment() is True

    monkeypatch.setenv("REPLIT_DEPLOYMENT", "false")
    assert database.is_replit_managed_deployment() is False
    monkeypatch.delenv("REPLIT_DEPLOYMENT", raising=False)
    assert database.is_replit_managed_deployment() is False


def test_managed_schema_exception_is_fatal_without_environment(
    monkeypatch,
) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")

    # A catalog connection/verification exception must not be downgraded to
    # the development warning merely because ENVIRONMENT is absent.
    assert database.schema_verification_is_fatal(
        production=False,
        managed=database.is_replit_managed_deployment(),
    ) is True

    monkeypatch.setenv("ENVIRONMENT", "development")
    assert database.schema_verification_is_fatal(
        production=False,
        managed=True,
    ) is True


def test_nonmanaged_development_schema_exception_remains_warning_policy(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("REPLIT_DEPLOYMENT", raising=False)
    assert database.schema_verification_is_fatal(
        production=False,
        managed=database.is_replit_managed_deployment(),
    ) is False


@pytest.mark.asyncio
async def test_managed_catalog_exception_is_rejected_before_startup_continues(
    monkeypatch,
) -> None:
    from app import lifecycle as app_lifecycle
    from config import config

    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    monkeypatch.setattr(type(config), "ENVIRONMENT", "development")

    async def _catalog_failure():
        raise OSError("catalog unavailable")

    monkeypatch.setattr(app_lifecycle, "init_pg_tables", _catalog_failure)

    with pytest.raises(OSError, match="catalog unavailable"):
        await app_lifecycle.startup_tasks()


def test_preserved_school_registry_is_exact_and_has_no_defaults() -> None:
    expected = {
        "principal_mobile": "varchar",
        "configuration": "jsonb",
        "location": "jsonb",
        "setup_completed": "boolean",
        "setup_steps_completed": "jsonb",
    }
    actual = {
        name: " ".join(
            type_.compile(dialect=postgresql.dialect()).lower().split()
        )
        for name, type_ in PRESERVED_SCHOOL_COLUMNS.items()
    }
    actual["principal_mobile"] = "varchar"
    assert actual == expected
    # The registry stores types only; nullable/no-default are enforced by the
    # managed verifier and additive migration, not by ORM Column objects.
    assert len(PRESERVED_SCHOOL_COLUMNS) == 5


def test_restored_columns_are_optional_to_startup_and_absent_from_batch_orm() -> None:
    """The restored dump may omit six legacy/optional columns safely."""
    contracts = database.expected_schema_contracts()
    absent = {
        ("schools", "configuration"),
        ("schools", "location"),
        ("schools", "setup_completed"),
        ("schools", "setup_steps_completed"),
        ("schools", "principal_mobile"),
        ("bulk_import_batches", "ownership_version"),
    }
    assert absent.isdisjoint(contracts)

    assert "ownership_version" not in BulkImportBatch.__table__.columns
    orm_statements = (
        select(School),
        insert(School).values(id="school", name="School", code="school"),
        select(BulkImportBatch),
        insert(BulkImportBatch).values(
            id="batch",
            school_id="school",
            import_type="students",
        ),
    )
    for statement in orm_statements:
        sql = str(statement.compile(dialect=postgresql.dialect())).lower()
        assert "ownership_version" not in sql
        assert "principal_mobile" not in sql
        assert "setup_completed" not in sql
        assert "setup_steps_completed" not in sql
        assert "configuration" not in sql
        assert "location" not in sql


@pytest.mark.parametrize(
    ("model", "kwargs"),
    (
        (SchoolCreate, {"name": "School"}),
        (SchoolUpdate, {}),
        (SchoolInfoUpdate, {}),
    ),
)
def test_principal_mobile_dto_alias_is_backed_by_principal_phone(model, kwargs) -> None:
    dto = model(principal_mobile="0500000000", **kwargs)
    assert dto.principal_phone == "0500000000"
    assert dto.principal_mobile == dto.principal_phone


@pytest.mark.parametrize("model", (SchoolUpdate, SchoolInfoUpdate))
def test_principal_mobile_empty_string_clears_canonical_phone(model) -> None:
    dto = model(principal_mobile="")
    assert dto.principal_phone == ""
    assert dto.principal_mobile == ""


@pytest.mark.asyncio
async def test_school_info_consumer_persists_empty_principal_phone_clear(monkeypatch) -> None:
    from src.modules.schools.services import school_settings_service as service

    updates = []

    async def _resolve(*_args, **_kwargs):
        return "school"

    async def _update(_session, collection, _filters, values):
        updates.append((collection, values))
        return 1

    monkeypatch.setattr(service, "resolve_school_context", _resolve)
    monkeypatch.setattr(service, "gd_update_one", _update)

    result = await service.SchoolSettingsService.update_school_info_direct(
        object(),
        SchoolInfoUpdate(principal_mobile=""),
        {},
    )

    assert result["success"] is True
    assert len(updates) == 2
    assert updates[0][0] == "schools"
    assert updates[0][1]["principal_phone"] == ""
    assert updates[1][0] == "users"
    assert updates[1][1]["phone"] == ""


@pytest.mark.asyncio
async def test_startup_gate_allows_missing_restored_columns_but_rejects_required(
    monkeypatch,
) -> None:
    """Optional restored columns do not weaken genuinely required checks."""
    required = database._SchemaContract(
        table_name="schools",
        column_name="name",
        postgres_type="character varying",
        nullable=False,
    )
    monkeypatch.setattr(
        database,
        "_expected_schema_contracts",
        lambda: {("schools", "name"): required},
    )

    class _Result:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "table_name": "schools",
                    "column_name": "name",
                    "type_name": "character varying",
                    "nullable": False,
                    "column_default": None,
                }
            ]

    class _Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def execute(self, *_args, **_kwargs):
            return _Result()

    monkeypatch.setattr(
        database,
        "engine",
        SimpleNamespace(connect=lambda: _Connection()),
    )
    ready = await database.verify_physical_schema()
    assert ready["ok"] is True

    class _MissingRequiredResult(_Result):
        def all(self):
            return []

    class _MissingRequiredConnection(_Connection):
        async def execute(self, *_args, **_kwargs):
            return _MissingRequiredResult()

    monkeypatch.setattr(
        database,
        "engine",
        SimpleNamespace(connect=lambda: _MissingRequiredConnection()),
    )
    rejected = await database.verify_physical_schema()
    assert rejected["ok"] is False
    assert rejected["missing_columns"] == ["schools.name"]


def test_known_physical_contracts_are_exact_not_global_narrowing() -> None:
    expected = {
        ("schools", "last_export_token_hash"): "character varying(64)",
        ("schools", "last_export_initiator_jti"): "character varying(128)",
        ("notifications_preferences", "id"): "character varying(64)",
        ("notifications_preferences", "user_id"): "character varying(64)",
        ("notifications", "category"): "character varying(64)",
        ("notifications", "cta_url"): "character varying(512)",
        ("students", "pending_parent_phone"): "text",
        ("students", "pending_parent_email"): "text",
    }
    actual = {
        key: database._canonical_postgres_type(
            type_.compile(dialect=postgresql.dialect())
        )
        for key, type_ in KNOWN_PHYSICAL_COLUMN_TYPES.items()
    }
    assert actual == expected
    assert ("notifications", "cta_url") in KNOWN_PHYSICAL_COLUMN_TYPES
    assert ("schools", "last_export_token_hash") in KNOWN_PHYSICAL_COLUMN_TYPES
    assert len(KNOWN_PHYSICAL_COLUMN_TYPES) == 8


def test_float_without_precision_matches_postgres_double_precision_only() -> None:
    assert database._canonical_postgres_type("FLOAT") == "double precision"
    assert database._canonical_postgres_type("FLOAT(53)") == "double precision"
    assert database._canonical_postgres_type("FLOAT(24)") != "double precision"


def test_managed_physical_query_is_one_catalog_read_without_version_or_writes() -> None:
    query = str(database._PHYSICAL_SCHEMA_QUERY).lower()
    assert query.count("select") == 1
    assert "alembic_version" not in query
    assert "insert " not in query
    assert "update " not in query
    assert "delete " not in query
    assert "create " not in query
    assert "alter " not in query
    assert "drop " not in query
    assert inspect.getsource(database.verify_physical_schema).count("conn.execute(") == 1


@pytest.mark.asyncio
async def test_managed_init_uses_physical_result_without_reading_alembic_version(
    monkeypatch,
) -> None:
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")

    async def _physical_schema():
        return _ready_physical_schema()

    monkeypatch.setattr(
        database,
        "verify_physical_schema",
        _physical_schema,
    )

    def _unexpected_head_lookup():  # pragma: no cover - tripwire
        raise AssertionError("managed startup must not inspect Alembic heads")

    monkeypatch.setattr(database, "get_alembic_head_revision", _unexpected_head_lookup)

    status = await database.init_pg_tables()

    assert status["managed"] is True
    assert status["schema_mode"] == "physical"
    assert status["schema_ready"] is True
    assert status["at_head"] is None


def _ready_physical_schema() -> dict:
    return {
        "ok": True,
        "missing_tables": [],
        "missing_columns": [],
        "type_mismatches": [],
        "nullability_mismatches": [],
        "default_mismatches": [],
        "expected_column_count": 1,
        "catalog_row_count": 1,
    }


@pytest.mark.asyncio
async def test_physical_verifier_uses_one_catalog_call_and_allows_extra_columns(
    monkeypatch,
) -> None:
    contract = database._SchemaContract(
        table_name="schools",
        column_name="name",
        postgres_type="character varying",
        nullable=True,
    )
    monkeypatch.setattr(
        database,
        "_expected_schema_contracts",
        lambda: {("schools", "name"): contract},
    )

    class _Result:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "table_name": "schools",
                    "column_name": "name",
                    "type_name": "character varying",
                    "nullable": True,
                    "column_default": None,
                },
                {
                    "table_name": "schools",
                    "column_name": "legacy_extra",
                    "type_name": "jsonb",
                    "nullable": True,
                    "column_default": None,
                },
            ]

    class _Connection:
        def __init__(self):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def execute(self, *_args, **_kwargs):
            self.calls += 1
            return _Result()

    connection = _Connection()
    # AsyncEngine uses slots, so patch the module-level engine reference
    # rather than attempting to assign its read-only ``connect`` attribute.
    monkeypatch.setattr(
        database,
        "engine",
        SimpleNamespace(connect=lambda: connection),
    )

    result = await database.verify_physical_schema()

    assert result["ok"] is True
    assert result["missing_columns"] == []
    assert connection.calls == 1


@pytest.mark.asyncio
async def test_known_width_contract_accepts_exact_and_rejects_narrower(
    monkeypatch,
) -> None:
    contract = database._SchemaContract(
        table_name="notifications",
        column_name="cta_url",
        postgres_type="character varying(512)",
        nullable=True,
    )
    monkeypatch.setattr(
        database,
        "_expected_schema_contracts",
        lambda: {("notifications", "cta_url"): contract},
    )

    class _Result:
        def __init__(self, type_name):
            self.type_name = type_name

        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "table_name": "notifications",
                    "column_name": "cta_url",
                    "type_name": self.type_name,
                    "nullable": True,
                    "column_default": None,
                }
            ]

    class _Connection:
        def __init__(self, type_name):
            self.type_name = type_name

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def execute(self, *_args, **_kwargs):
            return _Result(self.type_name)

    monkeypatch.setattr(
        database,
        "engine",
        SimpleNamespace(
            connect=lambda: _Connection("character varying(512)")
        ),
    )
    accepted = await database.verify_physical_schema()
    assert accepted["ok"] is True
    assert accepted["type_mismatches"] == []

    monkeypatch.setattr(
        database,
        "engine",
        SimpleNamespace(
            connect=lambda: _Connection("character varying(64)")
        ),
    )
    rejected = await database.verify_physical_schema()
    assert rejected["ok"] is False
    assert rejected["type_mismatches"] == [
        "notifications.cta_url: expected character varying(512), "
        "got character varying(64)"
    ]