"""
NASSAQ PostgreSQL Database Layer
Async SQLAlchemy engine, session factory, and FastAPI dependency.
Uses Replit's co-located PostgreSQL via DATABASE_URL for <5ms latency.
"""
import os
import logging
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

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
    from sqlalchemy.pool import NullPool

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


def get_alembic_head_revision():
    """Return the single Alembic head revision id from the migration scripts.

    Returns None if it cannot be determined — including the unsafe case of
    multiple unresolved heads (which itself is logged as an error). Callers
    treat a None head as "could not verify" rather than "at head".
    """
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory
        ini_path = os.path.join(os.path.dirname(__file__), "alembic.ini")
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


async def init_pg_tables():
    """Verify (read-only) that the PostgreSQL schema is at the Alembic head.

    Returns a status dict so the caller can fail fast in production when the
    live schema is not at the latest migration head. This function performs NO
    DDL — it never creates, drops, or alters schema. Schema is Alembic-managed
    only; runtime objects are handled separately by ``ensure_runtime_sequences``.

    ``at_head`` is True only when ``alembic_version`` holds EXACTLY one row whose
    revision equals the single computed migration head. A missing table, a
    branched multi-row ``alembic_version``, or unresolved multiple script heads
    all yield ``at_head=False`` (fail-safe).
    """
    import pg_models as _  # noqa: ensure models are imported
    from sqlalchemy import text
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
        "has_alembic": has_alembic,
        "db_version": db_version,
        "head_version": head_version,
        "version_row_count": version_row_count,
        "at_head": at_head,
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
