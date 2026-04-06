"""
NASSAQ Pre-Deployment Database Backup
Creates a JSON snapshot of all critical table counts and sample IDs
for verification after deployment.

Usage: python scripts/backup_db.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def create_backup_snapshot():
    from db import engine
    from sqlalchemy import text

    tables = [
        "users", "schools", "students", "teachers", "classes",
        "subjects", "attendance", "audit_logs", "sessions",
        "timetable_constraints", "notifications", "product_issues",
    ]

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "tables": {},
    }

    async with engine.connect() as conn:
        for table in tables:
            try:
                result = await conn.execute(text(f"SELECT count(*) FROM {table}"))
                count = result.scalar()
                id_result = await conn.execute(text(f"SELECT id FROM {table} ORDER BY id LIMIT 3"))
                sample_ids = [row[0] for row in id_result.fetchall()]
                snapshot["tables"][table] = {
                    "count": count,
                    "sample_ids": sample_ids,
                }
            except Exception:
                await conn.rollback()
                snapshot["tables"][table] = {"count": 0, "note": "table not found or empty"}

        try:
            version_result = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            snapshot["alembic_version"] = version_result.scalar()
        except Exception:
            await conn.rollback()
            snapshot["alembic_version"] = "unknown"

    await engine.dispose()

    backup_dir = os.path.join(os.path.dirname(__file__), "..", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(backup_dir, f"snapshot_{ts}.json")
    with open(filepath, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    print(f"Backup snapshot saved: {filepath}")
    print(json.dumps(snapshot, indent=2, default=str))
    return snapshot


async def verify_against_snapshot(snapshot_path: str):
    with open(snapshot_path) as f:
        old = json.load(f)

    current = await create_backup_snapshot()

    print("\n=== DEPLOYMENT VERIFICATION ===")
    all_ok = True
    for table, old_data in old["tables"].items():
        if "error" in old_data:
            continue
        new_data = current["tables"].get(table, {})
        if "error" in new_data:
            print(f"  FAIL  {table}: table missing or error")
            all_ok = False
            continue
        old_count = old_data["count"]
        new_count = new_data["count"]
        if new_count < old_count:
            print(f"  FAIL  {table}: {old_count} → {new_count} (DATA LOSS DETECTED)")
            all_ok = False
        else:
            print(f"  PASS  {table}: {old_count} → {new_count}")

    print(f"\nFINAL: {'ALL PASS' if all_ok else 'DATA LOSS DETECTED'}")
    return all_ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        if len(sys.argv) < 3:
            print("Usage: python backup_db.py verify <snapshot_file>")
            sys.exit(1)
        ok = asyncio.run(verify_against_snapshot(sys.argv[2]))
        sys.exit(0 if ok else 1)
    else:
        asyncio.run(create_backup_snapshot())
