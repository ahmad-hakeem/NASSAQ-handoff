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


async def cleanup():
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
