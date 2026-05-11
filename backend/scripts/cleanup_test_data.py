"""
Cleanup test data left behind by integration tests.
Removes schools matching 'Test School*' and all related entities.

Usage: python -m scripts.cleanup_test_data
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import async_session_factory
from sqlalchemy import text
from config import NassaqConfig as Config


def _assert_destructive_ops_allowed() -> None:
    """SECURITY (audit M-7): never let this script run outside dev.

    Even though it filters by `'Test School%'`, a fat-finger rename of a real
    school could match. Defense-in-depth: hard-fail with a loud message in
    any non-development environment.
    """
    if not Config.destructive_ops_allowed():
        env = os.environ.get("ENVIRONMENT") or os.environ.get("REPLIT_DEPLOYMENT", "unknown")
        sys.stderr.write(
            f"REFUSING TO RUN cleanup_test_data.py in environment={env!r}: "
            "destructive ops are blocked outside development.\n"
        )
        raise SystemExit(2)


async def cleanup():
    _assert_destructive_ops_allowed()
    try:
        await _run_cleanup()
    finally:
        # SECURITY (audit M-7): re-assert at exit. Defends against the case
        # where Config.ENVIRONMENT was mutated mid-run (e.g. by a misbehaving
        # plugin or a long-lived REPL that imported this module while still
        # in dev and then flipped to prod). Refusing to "succeed silently"
        # in prod is the safer failure mode.
        _assert_destructive_ops_allowed()


async def _run_cleanup():
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT id, name_en FROM schools WHERE name_en LIKE 'Test School%'")
        )
        test_schools = result.fetchall()

        if not test_schools:
            print("No test schools found. Nothing to clean up.")
            return

        school_ids = [row[0] for row in test_schools]
        print(f"Found {len(school_ids)} test school(s) to remove:")
        for row in test_schools:
            print(f"  - {row[1]} ({row[0]})")

        placeholders = ", ".join(f":id_{i}" for i in range(len(school_ids)))
        params = {f"id_{i}": sid for i, sid in enumerate(school_ids)}

        delete_targets = [
            ("classes", "school_id"),
            ("teachers", "school_id"),
            ("students", "school_id"),
            ("users", "tenant_id"),
        ]
        for table, col in delete_targets:
            sql = "DELETE FROM {t} WHERE {c} IN ({p})".format(
                t=table, c=col, p=placeholders
            )
            r = await session.execute(text(sql), params)
            print(f"  Deleted {r.rowcount} rows from {table}")

        r = await session.execute(
            text("DELETE FROM schools WHERE id IN ({p})".format(p=placeholders)),
            params,
        )
        print(f"  Deleted {r.rowcount} schools")

        orphan_r = await session.execute(
            text(
                "DELETE FROM users WHERE tenant_id IS NULL "
                "AND role NOT IN ('platform_admin') "
                "AND email LIKE '%test%'"
            )
        )
        print(f"  Deleted {orphan_r.rowcount} orphaned test users")

        await session.commit()
        print("Cleanup complete.")


if __name__ == "__main__":
    asyncio.run(cleanup())
