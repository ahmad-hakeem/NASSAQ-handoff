import asyncio
import os
import sys
from logging.config import fileConfig
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

try:
    from dotenv import load_dotenv
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv()
except ImportError:
    pass

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import Base
import pg_models  # noqa: ensure all models registered
from src.core.database.preserved_school_columns import (
    assert_online_migrations_allowed,
    is_preserved_school_column,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    """Keep intentional DB-only school compatibility columns out of drops."""

    if is_preserved_school_column(
        object_,
        name,
        type_,
        reflected,
        compare_to,
    ):
        return False
    return True


def _assert_online_migrations_allowed() -> None:
    """Publish owns managed-production schema changes.

    The marker is deliberately checked here rather than ``ENVIRONMENT``:
    development workflows may run the application in production mode, while
    a managed deployment must never mutate its database from a worker's
    Alembic invocation.  Offline SQL rendering remains allowed because it
    does not connect or execute DDL.
    """

    assert_online_migrations_allowed()


def _get_url():
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


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    env = os.environ.get("ENVIRONMENT", "development")
    if env in ("production", "staging"):
        import logging
        logger = logging.getLogger("alembic.env")
        logger.info(f"DEPLOYMENT SAFETY: Running migrations in {env} mode — destructive ops are monitored")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    _assert_online_migrations_allowed()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    _assert_online_migrations_allowed()
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
