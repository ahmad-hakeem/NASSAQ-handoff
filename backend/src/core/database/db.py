"""
NASSAQ PostgreSQL Database Layer
Async SQLAlchemy engine, session factory, and FastAPI dependency.
Uses Replit's co-located PostgreSQL via DATABASE_URL for <5ms latency.
"""
import os
import logging
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

logger = logging.getLogger("nassaq.db")


def _get_async_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params.pop("sslmode", None)
    clean_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


class Base(DeclarativeBase):
    pass


if os.environ.get("TESTING"):
    # Under pytest every test runs on a fresh event loop; a shared QueuePool
    # would hand a later test an asyncpg connection created on an earlier
    # loop ("Future attached to a different loop"). NullPool opens a fresh
    # connection per checkout, matching the per-test engines in conftest.
    engine = create_async_engine(
        _get_async_url(),
        echo=False,
        poolclass=NullPool,
    )
else:
    engine = create_async_engine(
        _get_async_url(),
        echo=False,
        pool_pre_ping=True,
        pool_size=15,
        max_overflow=25,
        pool_recycle=300,
        pool_use_lifo=True,
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_pg_session():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

get_db = get_pg_session


def is_replit_managed_deployment() -> bool:
    """Return whether Replit Publish owns this deployment's schema.

    ``REPLIT_DEPLOYMENT`` is the existing, explicit Replit deployment marker.
    Its truthiness rules live in the shared preservation registry so Alembic,
    lifecycle startup, and this gate cannot disagree.  Do not infer
    ownership from ``DATABASE_URL``: a managed database URL is also available
    to development and migration-test processes.
    """

    from src.core.database.preserved_school_columns import is_managed_production

    return is_managed_production()


def schema_verification_is_fatal(*, production: bool, managed: bool) -> bool:
    """Whether schema verification failures must stop startup.

    A managed Replit deployment is fail-closed even when a development shell
    or an unset ``ENVIRONMENT`` value accompanies the deployment marker.
    """

    return bool(production or managed)


def get_alembic_head_revision():
    """Return the single Alembic head revision id from the migration scripts.

    Returns None if it cannot be determined — including the unsafe case of
    multiple unresolved heads (which itself is logged as an error). Callers
    treat a None head as "could not verify" rather than "at head".
    """
    try:
        from pathlib import Path
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory

        current_file = Path(__file__).resolve()
        candidate_paths = [
            current_file.parents[3] / "alembic.ini",
            current_file.parent / "alembic.ini",
            Path.cwd() / "alembic.ini",
            Path.cwd() / "backend" / "alembic.ini",
        ]
        ini_path = None
        for candidate in candidate_paths:
            if candidate.is_file():
                ini_path = str(candidate)
                break

        if not ini_path:
            logger.error(f"Could not find alembic.ini in candidates: {[str(c) for c in candidate_paths]}")
            return None

        cfg = AlembicConfig(ini_path)
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        if len(heads) == 1:
            return heads[0]
        logger.error(f"Alembic has {len(heads)} heads (expected exactly 1): {heads}")
        return None
    except Exception as e:
        logger.warning(f"Could not determine Alembic head revision: {e}")
        return None


@dataclass(frozen=True)
class _SchemaContract:
    """One required physical column in the read-only schema gate."""

    table_name: str
    column_name: str
    postgres_type: str
    nullable: bool
    require_no_server_default: bool = False


def _canonical_postgres_type(type_name: str | None) -> str:
    """Normalize equivalent PostgreSQL type spellings for comparison."""

    value = " ".join((type_name or "").replace('"', "").lower().split())
    aliases = {
        "varchar": "character varying",
        "character varying": "character varying",
        "bool": "boolean",
        "int2": "smallint",
        "int4": "integer",
        "int8": "bigint",
        "float4": "real",
        "float8": "double precision",
        "timestamp without time zone": "timestamp without time zone",
        "timestamp with time zone": "timestamp with time zone",
    }
    # PostgreSQL FLOAT without an explicit precision is FLOAT8 /
    # double-precision.  Do not generalize this to every FLOAT(n): FLOAT(24)
    # is a distinct real-precision contract and should still be reported.
    if value in {"float", "float(53)"}:
        return "double precision"
    # Preserve length/precision modifiers while normalizing the base name.
    for source, target in aliases.items():
        if value == source:
            return target
        if value.startswith(f"{source}("):
            return f"{target}{value[len(source):]}"
    return value


def _metadata_type_name(column: Any) -> str:
    """Compile a SQLAlchemy column type using PostgreSQL's dialect."""

    try:
        compiled = column.type.compile(dialect=postgresql.dialect())
    except Exception:
        compiled = str(column.type)
    return _canonical_postgres_type(str(compiled))


def _sqlalchemy_type_name(type_: Any) -> str:
    """Compile a standalone SQLAlchemy type using PostgreSQL's dialect."""

    try:
        compiled = type_.compile(dialect=postgresql.dialect())
    except Exception:
        compiled = str(type_)
    return _canonical_postgres_type(str(compiled))


def _expected_schema_contracts() -> dict[tuple[str, str], _SchemaContract]:
    """Build required columns from ORM metadata plus compatibility contracts."""

    # Importing pg_models registers every mapped entity without touching the
    # database.  The five compatibility columns intentionally remain outside
    # this metadata and are supplied by the explicit registry below.
    import pg_models as _  # noqa: F401

    from src.core.database.preserved_school_columns import (
        KNOWN_PHYSICAL_COLUMN_TYPES,
        PRESERVED_SCHOOL_COLUMNS,
    )

    contracts: dict[tuple[str, str], _SchemaContract] = {}
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            contracts[(table.name, column.name)] = _SchemaContract(
                table_name=table.name,
                column_name=column.name,
                postgres_type=_metadata_type_name(column),
                nullable=bool(column.nullable),
            )

    # Preserve exact deployed widths/text types for the handful of legacy
    # columns whose ORM declarations are intentionally broader.  This is
    # deliberately per-column: all other metadata type comparisons remain
    # strict, and a narrower/unrelated physical type is still a failure.
    for key, type_ in KNOWN_PHYSICAL_COLUMN_TYPES.items():
        existing = contracts.get(key)
        if existing is None:
            raise RuntimeError(
                "Known physical type contract has no ORM metadata column: "
                f"{key[0]}.{key[1]}"
            )
        contracts[key] = _SchemaContract(
            table_name=existing.table_name,
            column_name=existing.column_name,
            postgres_type=_sqlalchemy_type_name(type_),
            nullable=existing.nullable,
            require_no_server_default=existing.require_no_server_default,
        )

    for name, type_ in PRESERVED_SCHOOL_COLUMNS.items():
        contracts[("schools", name)] = _SchemaContract(
            table_name="schools",
            column_name=name,
            postgres_type=_sqlalchemy_type_name(type_),
            nullable=True,
            require_no_server_default=True,
        )
    return contracts


def expected_schema_contracts() -> dict[tuple[str, str], _SchemaContract]:
    """Return the final required physical contracts without touching PostgreSQL.

    This is useful to compare a catalog snapshot or Publish structural diff
    against the same contract used by the startup gate.  It returns metadata
    only; no row values or credentials are included.
    """

    return _expected_schema_contracts()


# One catalog query covers every ORM table and every compatibility column.
# It intentionally does not mention alembic_version or any application table
# data.  Extra physical columns are harmless and are not selected as failures.
_PHYSICAL_SCHEMA_QUERY = text(
    """
    SELECT
        ns.nspname AS table_schema,
        cls.relname AS table_name,
        attr.attname AS column_name,
        format_type(attr.atttypid, attr.atttypmod) AS type_name,
        NOT attr.attnotnull AS nullable,
        pg_get_expr(def.adbin, def.adrelid) AS column_default
    FROM pg_catalog.pg_class AS cls
    JOIN pg_catalog.pg_namespace AS ns
      ON ns.oid = cls.relnamespace
    JOIN pg_catalog.pg_attribute AS attr
      ON attr.attrelid = cls.oid
    LEFT JOIN pg_catalog.pg_attrdef AS def
      ON def.adrelid = attr.attrelid
     AND def.adnum = attr.attnum
    WHERE ns.nspname = 'public'
      AND cls.relkind IN ('r', 'p')
      AND attr.attnum > 0
      AND NOT attr.attisdropped
      AND cls.relname = ANY(:table_names)
    """
).bindparams(
    bindparam(
        "table_names",
        type_=postgresql.ARRAY(postgresql.VARCHAR()),
    )
)


async def verify_physical_schema() -> dict[str, Any]:
    """Verify required physical columns with one read-only catalog query.

    The result is deliberately a diagnostic mapping rather than an exception:
    the lifecycle gate decides whether a production process may serve traffic.
    This function never reads school values and never performs DDL or Alembic
    bookkeeping writes.
    """

    expected = _expected_schema_contracts()
    expected_tables = sorted({table for table, _ in expected})

    async with engine.connect() as conn:
        result = await conn.execute(
            _PHYSICAL_SCHEMA_QUERY,
            {"table_names": expected_tables},
        )
        rows = result.mappings().all()

    observed = {
        (row["table_name"], row["column_name"]): row
        for row in rows
    }
    observed_tables = {row["table_name"] for row in rows}

    missing_tables = sorted(set(expected_tables) - observed_tables)
    missing_columns: list[str] = []
    type_mismatches: list[str] = []
    nullability_mismatches: list[str] = []
    default_mismatches: list[str] = []

    for key, contract in expected.items():
        label = f"{contract.table_name}.{contract.column_name}"
        actual = observed.get(key)
        if actual is None:
            missing_columns.append(label)
            continue

        actual_type = _canonical_postgres_type(actual["type_name"])
        if actual_type != contract.postgres_type:
            type_mismatches.append(
                f"{label}: expected {contract.postgres_type}, got {actual_type}"
            )
        if bool(actual["nullable"]) != contract.nullable:
            nullability_mismatches.append(
                f"{label}: expected nullable={contract.nullable}, "
                f"got nullable={bool(actual['nullable'])}"
            )
        if contract.require_no_server_default and actual["column_default"] is not None:
            default_mismatches.append(
                f"{label}: expected no server default, "
                f"got {actual['column_default']}"
            )

    ok = not (
        missing_tables
        or missing_columns
        or type_mismatches
        or nullability_mismatches
        or default_mismatches
    )
    return {
        "ok": ok,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "type_mismatches": type_mismatches,
        "nullability_mismatches": nullability_mismatches,
        "default_mismatches": default_mismatches,
        "expected_column_count": len(expected),
        "catalog_row_count": len(rows),
    }


async def init_pg_tables():
    """Verify the deployment-owned schema without changing PostgreSQL.

    Replit Publish does not copy ``alembic_version`` data when it applies its
    structural diff.  In a published deployment, therefore, the gate checks
    the physical schema from one catalog query and never consults or stamps
    Alembic bookkeeping.  Other environments retain the strict, single-row
    Alembic head check.

    No path in this function creates tables, sequences, or columns.
    """
    import pg_models as _  # noqa: ensure models are imported

    if is_replit_managed_deployment():
        physical = await verify_physical_schema()
        return {
            "managed": True,
            "schema_mode": "physical",
            "physical_schema_ok": physical["ok"],
            "schema_ready": physical["ok"],
            # Deliberately not a version claim: managed deployments do not
            # trust alembic_version and never stamp it.
            "at_head": None,
            **physical,
        }

    head_version = get_alembic_head_revision()
    db_version = None
    has_alembic = False
    version_row_count = 0
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='alembic_version')"))
        has_alembic = bool(result.scalar())
        if has_alembic:
            rows = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
            version_row_count = len(rows)
            if version_row_count == 1:
                db_version = rows[0]
                logger.info(f"PostgreSQL schema at Alembic revision: {db_version}")
            else:
                logger.warning(f"alembic_version has {version_row_count} rows (expected exactly 1): {rows}")
        else:
            logger.warning("Alembic version table not found — run 'alembic upgrade head' to initialize schema")
    at_head = bool(has_alembic and head_version and version_row_count == 1 and db_version == head_version)
    if has_alembic and head_version and not at_head:
        logger.warning(f"Schema drift: DB at {db_version} (alembic_version rows={version_row_count}) but migration head is {head_version}")
    logger.info("PostgreSQL schema verified (Alembic-managed)")
    return {
        "managed": False,
        "schema_mode": "alembic",
        "has_alembic": has_alembic,
        "db_version": db_version,
        "head_version": head_version,
        "version_row_count": version_row_count,
        "at_head": at_head,
        "schema_ready": at_head,
    }


async def ensure_runtime_sequences():
    """Idempotently create runtime-only sequences not owned by Alembic.

    ``issue_number_seq`` is not created by any migration, so it is ensured here
    with ``CREATE SEQUENCE IF NOT EXISTS``. This is intentionally separate from
    the read-only schema gate in ``init_pg_tables`` so a DDL/privilege problem
    here can never block production boot — the caller logs and continues.
    """
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS issue_number_seq START WITH 1 INCREMENT BY 1"))


def get_sync_engine():
    """Return the underlying synchronous engine for event listeners and pool stats."""
    return engine.sync_engine


async def close_pg_engine():
    from src.core.middleware.query_monitor import stop_pool_monitor
    stop_pool_monitor()
    await engine.dispose()
    logger.info("PostgreSQL engine disposed")
