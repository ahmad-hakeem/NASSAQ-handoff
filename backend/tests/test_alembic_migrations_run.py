"""Run Alembic migrations against an empty Postgres database.

The static integrity checks in ``test_alembic_migrations_integrity.py`` catch
duplicate revision ids and multi-head divergences but never *execute* a
migration's ``upgrade()`` / ``downgrade()`` body. This test creates a throwaway
Postgres database, runs ``alembic upgrade head`` then ``alembic downgrade
base`` against it, and fails on any error — so a migration that ships with
broken SQL, a wrong column type, or a missing import is caught at PR time
instead of when the next fresh environment is provisioned.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


def _sync_url(url: str) -> str:
    """Return a sync (psycopg / libpq compatible) URL for asyncpg admin work."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


async def _create_temp_db(admin_url: str, dbname: str) -> None:
    import asyncpg

    parsed = urlparse(admin_url)
    # asyncpg connects to a specific database; use 'postgres' for admin ops.
    admin_dsn = urlunparse(parsed._replace(path="/postgres", query=""))
    conn = await asyncpg.connect(admin_dsn)
    try:
        await conn.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await conn.close()


async def _drop_temp_db(admin_url: str, dbname: str) -> None:
    import asyncpg

    parsed = urlparse(admin_url)
    admin_dsn = urlunparse(parsed._replace(path="/postgres", query=""))
    conn = await asyncpg.connect(admin_dsn)
    try:
        # Terminate any leftover connections so DROP doesn't block.
        await conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            dbname,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
    finally:
        await conn.close()


def _run_alembic(temp_url: str, *args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = temp_url
    env.setdefault("ENVIRONMENT", "development")
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(_ALEMBIC_INI), *args],
        cwd=str(_BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"`alembic {' '.join(args)}` failed (exit {proc.returncode})\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )


def test_alembic_upgrade_head_then_downgrade_base_on_fresh_db() -> None:
    raw_url = os.environ.get("DATABASE_URL", "")
    if not raw_url:
        pytest.skip("DATABASE_URL not set")
    admin_url = _sync_url(raw_url)
    if not admin_url.startswith("postgresql://"):
        pytest.skip("Non-Postgres DATABASE_URL — skipping fresh-DB migration check")

    try:
        import asyncpg  # noqa: F401
    except ImportError:
        pytest.skip("asyncpg not installed")

    dbname = f"nassaq_mig_test_{uuid.uuid4().hex[:12]}"

    asyncio.run(_create_temp_db(admin_url, dbname))
    try:
        parsed = urlparse(admin_url)
        temp_url = urlunparse(parsed._replace(path=f"/{dbname}", query=""))

        # Forward path: every upgrade() must run cleanly on an empty DB.
        _run_alembic(temp_url, "upgrade", "head")
        # Reverse path: every downgrade() must run cleanly back to base.
        _run_alembic(temp_url, "downgrade", "base")
    finally:
        try:
            asyncio.run(_drop_temp_db(admin_url, dbname))
        except Exception:
            # Best-effort cleanup; the DB name is unique per run so a leftover
            # row won't break subsequent runs.
            pass
