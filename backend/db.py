"""
NASSAQ PostgreSQL Database Layer
Async SQLAlchemy engine, session factory, and FastAPI dependency.
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
    url = urlunparse(parsed._replace(query=clean_query))
    return url


def _build_connect_args() -> dict:
    raw_url = os.environ.get("DATABASE_URL", "")
    parsed = urlparse(raw_url)
    params = parse_qs(parsed.query)
    sslmode = params.get("sslmode", [None])[0]
    if sslmode and sslmode != "disable":
        import ssl as _ssl
        ctx = _ssl.create_default_context()
        if sslmode == "require":
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_REQUIRED
        return {"ssl": ctx}
    return {}


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    _get_async_url(),
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    connect_args=_build_connect_args(),
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


async def init_pg_tables():
    import pg_models as _  # noqa: ensure models are imported
    from sqlalchemy import text
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='alembic_version')"))
        has_alembic = result.scalar()
        if has_alembic:
            result = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            version = result.scalar()
            logger.info(f"PostgreSQL schema at Alembic revision: {version}")
        else:
            logger.warning("Alembic version table not found — run 'alembic upgrade head' to initialize schema")
        await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS issue_number_seq START WITH 1 INCREMENT BY 1"))
    logger.info("PostgreSQL tables created/verified")


async def close_pg_engine():
    await engine.dispose()
    logger.info("PostgreSQL engine disposed")
