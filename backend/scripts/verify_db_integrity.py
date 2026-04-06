"""
NASSAQ Database Integrity Verification
Verifies FK constraints, unique constraints, indexes, data counts,
and query latency on the Replit co-located PostgreSQL instance.
Run: cd backend && python scripts/verify_db_integrity.py
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def verify():
    import asyncpg
    from urllib.parse import urlparse, parse_qs

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL not set")
        return False

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    sslmode = params.get("sslmode", [None])[0]
    ssl_arg = "require" if sslmode and sslmode != "disable" else False

    conn = await asyncpg.connect(url, ssl=ssl_arg)

    print("=" * 60)
    print("NASSAQ Database Integrity Verification")
    print("=" * 60)

    db_name = await conn.fetchval("SELECT current_database()")
    print(f"\nDatabase: {db_name}")

    latencies = []
    for _ in range(10):
        start = time.perf_counter()
        await conn.fetchval("SELECT 1")
        latencies.append((time.perf_counter() - start) * 1000)
    avg_ms = sum(latencies) / len(latencies)
    print(f"Latency: {avg_ms:.2f}ms avg (min={min(latencies):.2f}ms, max={max(latencies):.2f}ms)")

    fk_count = await conn.fetchval(
        "SELECT count(*) FROM information_schema.table_constraints "
        "WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public'"
    )
    uq_count = await conn.fetchval(
        "SELECT count(*) FROM information_schema.table_constraints "
        "WHERE constraint_type = 'UNIQUE' AND table_schema = 'public'"
    )
    idx_count = await conn.fetchval(
        "SELECT count(*) FROM pg_indexes WHERE schemaname = 'public'"
    )
    print(f"\nConstraints:")
    print(f"  FK constraints: {fk_count}")
    print(f"  Unique constraints: {uq_count}")
    print(f"  Indexes: {idx_count}")

    alembic_ver = await conn.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
    print(f"  Alembic version: {alembic_ver}")

    print(f"\nData counts:")
    tables = [
        "users", "schools", "students", "teachers", "classes", "subjects",
        "audit_logs", "counters", "generic_documents", "timetable_constraints",
        "product_issues", "notifications", "school_settings",
    ]
    all_ok = True
    for t in tables:
        count = await conn.fetchval(f'SELECT count(*) FROM "{t}"')
        print(f"  {t}: {count}")

    critical_fks = await conn.fetch("""
        SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name IN ('users', 'teachers', 'students', 'classes', 'subjects', 'attendance')
        ORDER BY tc.table_name, kcu.column_name
    """)
    print(f"\nCritical FK constraints ({len(critical_fks)}):")
    for fk in critical_fks:
        print(f"  {fk['table_name']}.{fk['column_name']} → {fk['foreign_table']}")

    print(f"\n{'=' * 60}")
    ok = fk_count >= 90 and uq_count >= 3 and idx_count >= 200 and avg_ms < 10
    print(f"RESULT: {'ALL CHECKS PASSED' if ok else 'CHECKS FAILED'}")
    print(f"{'=' * 60}")

    await conn.close()
    return ok


if __name__ == "__main__":
    result = asyncio.run(verify())
    sys.exit(0 if result else 1)
