"""
NASSAQ PostgreSQL Database Layer
Async SQLAlchemy engine, session factory, and FastAPI dependency.

Database selection:
- SUPABASE_DATABASE_URL → external Supabase (production + dev when set)
- DATABASE_URL → Replit managed PostgreSQL (fallback)
Supabase pooler requires statement_cache_size=0 and SSL.
"""
import os
import logging
import ssl as _ssl
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger("nassaq.db")


def _is_supabase() -> bool:
    return bool(os.environ.get("SUPABASE_DATABASE_URL", ""))


def _get_raw_url() -> str:
    from urllib.parse import quote
    url = os.environ.get("SUPABASE_DATABASE_URL", "") or os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("No database URL configured (SUPABASE_DATABASE_URL or DATABASE_URL)")
    if _is_supabase() and "@" in url:
        prefix_end = url.index("://") + 3
        prefix = url[:prefix_end]
        rest = url[prefix_end:]
        at_positions = [i for i, c in enumerate(rest) if c == "@"]
        if len(at_positions) > 1:
            last_at = at_positions[-1]
            cred_part = rest[:last_at]
            host_part = rest[last_at + 1:]
            colon_idx = cred_part.index(":")
            user = cred_part[:colon_idx]
            raw_pass = cred_part[colon_idx + 1:]
            encoded_pass = quote(raw_pass, safe="")
            url = f"{prefix}{user}:{encoded_pass}@{host_part}"
            logger.info("Auto-encoded special characters in database password")
    return url


def _get_async_url() -> str:
    url = _get_raw_url()
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params.pop("sslmode", None)
    clean_query = urlencode(params, doseq=True)
    url = urlunparse(parsed._replace(query=clean_query))
    return url


def _build_connect_args() -> dict:
    raw_url = _get_raw_url()
    if _is_supabase() or "supabase" in raw_url:
        import uuid as _uuid
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        return {
            "ssl": ctx,
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{_uuid.uuid4().hex[:12]}__",
        }
    parsed = urlparse(raw_url)
    params = parse_qs(parsed.query)
    sslmode = params.get("sslmode", [None])[0]
    if sslmode and sslmode != "disable":
        ctx = _ssl.create_default_context()
        if sslmode == "require":
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_REQUIRED
        return {"ssl": ctx}
    return {}


class Base(DeclarativeBase):
    pass


_db_source = "Supabase" if _is_supabase() else "Replit"
logger.info(f"Database source: {_db_source}")

_engine_kwargs = dict(
    echo=False,
    pool_pre_ping=False,
    connect_args=_build_connect_args(),
    pool_size=8,
    max_overflow=12,
    pool_recycle=600,
    pool_use_lifo=True,
)

_async_url = _get_async_url()

engine = create_async_engine(
    _async_url,
    **_engine_kwargs,
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
    logger.info("PostgreSQL schema verified (Alembic-managed)")


async def close_pg_engine():
    await engine.dispose()
    logger.info("PostgreSQL engine disposed")
