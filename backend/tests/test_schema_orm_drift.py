"""Guard against drift between the live Postgres schema and the ORM models.

This test catches the class of bug from Task #218 (duplicate migration), where
``pg_models.School`` was missing ``reactivation_reminder_sent_at`` and the
schools archive columns weren't reachable on a fresh DB.

Run locally with:

    cd backend && alembic upgrade head
    pytest tests/test_schema_orm_drift.py -v

It uses Alembic's ``compare_metadata`` to diff ``Base.metadata`` (the declared
ORM in ``backend/pg_models.py``) against the live database, and fails on any
column or table that is in one but not the other.

If you intentionally add/drop a table or column outside the ORM (e.g. a raw
SQL-managed bookkeeping table), update ``KNOWN_DB_ONLY_TABLES`` /
``KNOWN_DB_ONLY_COLUMNS`` below with a comment explaining why.
"""
from __future__ import annotations

import asyncio

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from sqlalchemy import inspect as sa_inspect

from db import Base, _get_async_url
import pg_models  # noqa: F401  ensure all ORM tables are registered on Base.metadata


# Tables present in the live DB that are intentionally not modeled in
# ``pg_models.py`` (managed via raw SQL / migrations / framework bookkeeping).
# Each entry is technical debt: prefer adding the ORM model over extending
# this list.
KNOWN_DB_ONLY_TABLES: frozenset[str] = frozenset({
    "alembic_version",          # alembic bookkeeping
    "_deployment_markers",      # deploy-time marker rows, raw-SQL managed
    "impersonation_sessions",   # legacy table, accessed only via raw SQL
    "revoked_token_families",   # legacy table, accessed only via raw SQL
})

# Columns present in the live DB but intentionally absent from the ORM model
# (keyed by ``(table_name, column_name)``).
KNOWN_DB_ONLY_COLUMNS: frozenset[tuple[str, str]] = frozenset({
    ("schools", "ai_consent_enabled"),  # legacy column, no longer surfaced via ORM
    ("teachers", "created_by"),         # legacy column, no longer surfaced via ORM
})


async def _collect_db_tables_and_columns_async() -> dict[str, set[str]]:
    """Return ``{table_name: {column_name, ...}}`` for the live database."""
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            def _introspect(sync_conn):
                insp = sa_inspect(sync_conn)
                return {
                    tbl: {col["name"] for col in insp.get_columns(tbl)}
                    for tbl in insp.get_table_names()
                }
            return await conn.run_sync(_introspect)
    finally:
        await engine.dispose()


def _collect_db_tables_and_columns() -> dict[str, set[str]]:
    return asyncio.run(_collect_db_tables_and_columns_async())


def test_every_orm_column_exists_in_db():
    """Fail if any column declared on a mapped ORM model is missing from
    Postgres.

    This is the direction Task #592 hit in production: ``grade_levels`` had
    four ORM-only columns that didn't exist in the database, so every write
    raised ``UndefinedColumn`` at runtime. Catching this in CI blocks deploys
    that would 500 on first write.

    Implemented as a direct introspection check (rather than relying on
    Alembic's ``compare_metadata``) so any ghost column is reported with its
    table and column name regardless of type/default/nullable differences.
    """
    db_schema = _collect_db_tables_and_columns()

    missing: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        db_cols = db_schema.get(table_name)
        if db_cols is None:
            missing.append(f"{table_name} (entire table missing)")
            continue
        for col in table.columns:
            if col.name not in db_cols:
                missing.append(f"{table_name}.{col.name}")

    if missing:
        pytest.fail(
            "ORM columns declared in pg_models.py but missing from the "
            "live database. These will raise UndefinedColumn at runtime on "
            "first write — add a migration or remove the ORM column before "
            "deploying.\n\n  - " + "\n  - ".join(sorted(missing))
        )


async def _collect_diffs_async():
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(
                lambda sc: compare_metadata(
                    MigrationContext.configure(sc), Base.metadata
                )
            )
    finally:
        await engine.dispose()


def _collect_diffs():
    return asyncio.run(_collect_diffs_async())


def _structural_diffs():
    """Return only diffs that change the table-or-column shape."""
    raw = _collect_diffs()
    structural = []
    for entry in raw:
        # compare_metadata yields either a tuple op or a list of tuple ops.
        items = entry if isinstance(entry, list) else [entry]
        for op in items:
            if not isinstance(op, tuple) or not op:
                continue
            if op[0] in ("add_table", "remove_table", "add_column", "remove_column"):
                structural.append(op)
    return structural


def test_no_orm_db_schema_drift():
    """Fail if any column/table is in the ORM but missing from Postgres,
    or in Postgres but missing from the ORM (outside the known allowlist).
    """
    missing_in_db_tables: list[str] = []      # ORM has it, DB doesn't (migration missing)
    missing_in_orm_tables: list[str] = []     # DB has it, ORM doesn't
    missing_in_db_columns: list[str] = []     # ORM has it, DB doesn't
    missing_in_orm_columns: list[str] = []    # DB has it, ORM doesn't

    for op in _structural_diffs():
        kind = op[0]
        if kind == "add_table":
            tbl = op[1]
            missing_in_db_tables.append(tbl.name)
        elif kind == "remove_table":
            tbl = op[1]
            if tbl.name not in KNOWN_DB_ONLY_TABLES:
                missing_in_orm_tables.append(tbl.name)
        elif kind == "add_column":
            _, _schema, table_name, column = op
            missing_in_db_columns.append(f"{table_name}.{column.name}")
        elif kind == "remove_column":
            _, _schema, table_name, column = op
            if (table_name, column.name) not in KNOWN_DB_ONLY_COLUMNS:
                missing_in_orm_columns.append(f"{table_name}.{column.name}")

    problems: list[str] = []
    if missing_in_db_tables:
        problems.append(
            "Tables declared in pg_models.py but missing from the database "
            "(missing migration?): " + ", ".join(sorted(missing_in_db_tables))
        )
    if missing_in_db_columns:
        problems.append(
            "Columns declared in pg_models.py but missing from the database "
            "(missing migration?): " + ", ".join(sorted(missing_in_db_columns))
        )
    if missing_in_orm_tables:
        problems.append(
            "Tables present in the database but not in pg_models.py "
            "(add an ORM model or extend KNOWN_DB_ONLY_TABLES): "
            + ", ".join(sorted(missing_in_orm_tables))
        )
    if missing_in_orm_columns:
        problems.append(
            "Columns present in the database but not in pg_models.py "
            "(add to the ORM model or extend KNOWN_DB_ONLY_COLUMNS): "
            + ", ".join(sorted(missing_in_orm_columns))
        )

    if problems:
        pytest.fail(
            "ORM <-> database schema drift detected. Run "
            "`cd backend && alembic upgrade head` first; if drift remains, "
            "either add the missing migration / ORM column or update the "
            "allowlist in tests/test_schema_orm_drift.py.\n\n  - "
            + "\n  - ".join(problems)
        )
