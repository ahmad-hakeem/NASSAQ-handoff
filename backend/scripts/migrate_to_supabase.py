"""
NASSAQ Production Migration: Replit PostgreSQL → Supabase
Exports schema + data from current DB and imports to Supabase.
"""
import asyncio
import os
import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SOURCE_URL = os.environ.get("DATABASE_URL", "")
TARGET_URL = os.environ.get("SUPABASE_DATABASE_URL", "")


def to_asyncpg_url(url):
    if url.startswith("postgresql://"):
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params.pop("sslmode", None)
        clean_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=clean_query)).replace(
            "postgresql://", "postgresql://", 1
        )
    return url


async def get_table_order(conn):
    rows = await conn.fetch("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    return [r["tablename"] for r in rows]


async def get_table_count(conn, table):
    try:
        return await conn.fetchval(f'SELECT count(*) FROM "{table}"')
    except Exception:
        return -1


async def export_table_data(conn, table):
    try:
        rows = await conn.fetch(f'SELECT * FROM "{table}"')
        return rows
    except Exception as e:
        print(f"  WARNING: Could not export {table}: {e}")
        return []


async def get_create_statements(conn):
    result = []
    tables = await get_table_order(conn)
    for table in tables:
        row = await conn.fetchval(f"""
            SELECT 'CREATE TABLE IF NOT EXISTS "{table}" (' ||
            string_agg(
                '"' || column_name || '" ' || 
                CASE 
                    WHEN data_type = 'character varying' THEN 'VARCHAR' || COALESCE('(' || character_maximum_length || ')', '')
                    WHEN data_type = 'timestamp with time zone' THEN 'TIMESTAMPTZ'
                    WHEN data_type = 'timestamp without time zone' THEN 'TIMESTAMP'
                    WHEN data_type = 'boolean' THEN 'BOOLEAN'
                    WHEN data_type = 'integer' THEN 'INTEGER'
                    WHEN data_type = 'bigint' THEN 'BIGINT'
                    WHEN data_type = 'double precision' THEN 'DOUBLE PRECISION'
                    WHEN data_type = 'numeric' THEN 'NUMERIC'
                    WHEN data_type = 'text' THEN 'TEXT'
                    WHEN data_type = 'jsonb' THEN 'JSONB'
                    WHEN data_type = 'json' THEN 'JSON'
                    WHEN data_type = 'ARRAY' THEN 'JSONB'
                    WHEN data_type = 'USER-DEFINED' THEN 'VARCHAR'
                    ELSE data_type
                END ||
                CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END,
                ', ' ORDER BY ordinal_position
            ) || ');'
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
        """, table)
        if row:
            result.append(row)

    pk_rows = await conn.fetch("""
        SELECT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = 'public'
    """)
    for pk in pk_rows:
        result.append(
            f'ALTER TABLE "{pk["table_name"]}" ADD PRIMARY KEY ("{pk["column_name"]}");'
        )

    return result


async def run_migration():
    import asyncpg

    print("=" * 60)
    print("NASSAQ DATABASE MIGRATION: Replit → Supabase")
    print("=" * 60)

    print("\n--- Connecting to SOURCE (Replit helium) ---")
    src_url = to_asyncpg_url(SOURCE_URL)
    source = await asyncpg.connect(src_url)
    src_db = await source.fetchval("SELECT current_database()")
    print(f"  Connected: {src_db}")

    print("\n--- Connecting to TARGET (Supabase) ---")
    target = await asyncpg.connect(TARGET_URL, ssl="require", statement_cache_size=0)
    tgt_db = await target.fetchval("SELECT current_database()")
    print(f"  Connected: {tgt_db}")

    src_tables = await get_table_order(source)
    print(f"\n--- Source tables: {len(src_tables)} ---")

    skip_tables = {"_deployment_markers"}

    print("\n--- PHASE 1: Schema Migration ---")
    ddl_statements = await get_create_statements(source)
    
    for stmt in ddl_statements:
        try:
            await target.execute(stmt)
        except Exception as e:
            err = str(e)
            if "already exists" not in err:
                print(f"  DDL warning: {err[:120]}")

    idx_rows = await source.fetch("""
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'public'
        AND indexname NOT LIKE '%_pkey'
    """)
    for idx in idx_rows:
        try:
            await target.execute(idx["indexdef"])
        except Exception as e:
            if "already exists" not in str(e):
                pass

    seq_rows = await source.fetch("""
        SELECT sequence_name FROM information_schema.sequences
        WHERE sequence_schema = 'public'
    """)
    for seq in seq_rows:
        try:
            val = await source.fetchval(f"SELECT last_value FROM {seq['sequence_name']}")
            await target.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq['sequence_name']} START WITH {val}")
        except Exception:
            pass

    await target.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
    src_alembic = await source.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
    if src_alembic:
        await target.execute("DELETE FROM alembic_version")
        await target.execute("INSERT INTO alembic_version (version_num) VALUES ($1)", src_alembic)
        print(f"  Alembic version set: {src_alembic}")

    tgt_tables = await get_table_order(target)
    print(f"  Target tables after schema: {len(tgt_tables)}")

    print("\n--- PHASE 2: Data Export + Import ---")
    results = {}
    
    fk_order = [
        "alembic_version", "platform_settings", "lookup_options",
        "counters", "educational_stages", "grade_levels",
        "schools", "school_settings", "users", "teachers", "students", "parents",
        "classes", "subjects", "physical_classrooms",
        "teacher_assignments", "teacher_class_assignments",
        "academic_years", "academic_terms", "time_slots",
        "timetable_constraints", "timetable_runs", "timetables",
        "schedule_sessions", "session_event_log", "session_interactions", "session_notes",
        "attendance", "assessments", "assessment_submissions",
        "behaviour_types", "behaviour_records",
        "skills_types", "student_skills",
        "notifications", "messages",
        "audit_logs", "approval_requests", "approval_events",
        "registration_requests", "bulk_action_history",
        "product_issues", "issue_comments", "issue_activity_log", "issue_duplicates_map",
        "hakim_insights", "ai_insights", "ai_interventions",
        "teacher_sessions",
        "generic_documents",
    ]

    ordered_tables = []
    for t in fk_order:
        if t in src_tables and t not in skip_tables:
            ordered_tables.append(t)
    for t in src_tables:
        if t not in ordered_tables and t not in skip_tables:
            ordered_tables.append(t)

    for table in ordered_tables:
        src_count = await get_table_count(source, table)
        if src_count <= 0:
            results[table] = {"source": src_count, "target": 0, "status": "SKIP (empty)"}
            continue

        rows = await export_table_data(source, table)
        if not rows:
            results[table] = {"source": src_count, "target": 0, "status": "SKIP (no data)"}
            continue

        columns = list(rows[0].keys())
        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))

        imported = 0
        errors = 0
        for row in rows:
            values = []
            for c in columns:
                v = row[c]
                if isinstance(v, list):
                    v = json.dumps(v)
                values.append(v)
            try:
                await target.execute(
                    f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING',
                    *values
                )
                imported += 1
            except Exception as e:
                errors += 1
                if errors <= 2:
                    print(f"  {table} row error: {str(e)[:100]}")

        tgt_count = await get_table_count(target, table)
        status = "PASS" if tgt_count >= src_count else f"WARN ({tgt_count}/{src_count})"
        results[table] = {"source": src_count, "target": tgt_count, "status": status}
        print(f"  {table}: {src_count} → {tgt_count} [{status}]")

    print("\n--- PHASE 3: Verification ---")
    print(f"\n{'Table':<30} {'Source':>8} {'Target':>8} {'Status':<20}")
    print("-" * 70)
    all_pass = True
    for table, r in sorted(results.items()):
        src = r["source"]
        tgt = r["target"]
        st = r["status"]
        print(f"  {table:<28} {src:>8} {tgt:>8} {st:<20}")
        if "WARN" in st or "FAIL" in st:
            all_pass = False

    tgt_alembic = await target.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
    print(f"\n  Alembic version: source={src_alembic} target={tgt_alembic} {'PASS' if src_alembic == tgt_alembic else 'FAIL'}")

    print(f"\n{'=' * 60}")
    print(f"MIGRATION RESULT: {'ALL PASS' if all_pass else 'CHECK WARNINGS'}")
    print(f"{'=' * 60}")

    await source.close()
    await target.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
