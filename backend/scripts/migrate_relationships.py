"""
Migration script: Convert user_relationships from old schema to new schema
Old: user_id_1, user_id_2 (no entity types)
New: from_entity_type, from_entity_id, to_entity_type, to_entity_id, status
"""
import asyncio
import sys
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_upsert
sys.path.insert(0, "/home/runner/workspace/backend")

from datetime import datetime, timezone

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from scripts.seed_db_helper import get_seed_db

RELATIONSHIP_TYPE_MAP = {
    "parent_child": {
        "from_entity_type": "parent",
        "to_entity_type": "student",
        "new_type": "parent_of"
    },
    "sibling": {
        "from_entity_type": "student",
        "to_entity_type": "student",
        "new_type": "sibling"
    },
    "teacher_class": {
        "from_entity_type": "teacher",
        "to_entity_type": "class",
        "new_type": "teaches_class"
    },
    "teacher_subject": {
        "from_entity_type": "teacher",
        "to_entity_type": "subject",
        "new_type": "teaches_subject"
    },
    "enrolled_in_school": {
        "from_entity_type": "student",
        "to_entity_type": "school",
        "new_type": "enrolled_in_school"
    },
    "belongs_to_class": {
        "from_entity_type": "student",
        "to_entity_type": "class",
        "new_type": "belongs_to_class"
    },
    "belongs_to_grade": {
        "from_entity_type": "student",
        "to_entity_type": "grade",
        "new_type": "belongs_to_grade"
    },
    "employed_at": {
        "from_entity_type": "teacher",
        "to_entity_type": "school",
        "new_type": "employed_at"
    },
    "manages_school": {
        "from_entity_type": "principal",
        "to_entity_type": "school",
        "new_type": "manages_school"
    },
    "principal_school": {
        "from_entity_type": "principal",
        "to_entity_type": "school",
        "new_type": "manages_school"
    },
}


async def migrate():
    async with get_seed_db() as db:

        total = await gd_count(db.session, "user_relationships", {})
        print(f"Total user_relationships: {total}")

        already_migrated = await gd_count(db.session, "user_relationships", {"from_entity_id": {"$exists": True, "$ne": None}})
        print(f"Already migrated: {already_migrated}")

        needs_migration = await gd_count(db.session, "user_relationships", {
            "$or": [
                {"from_entity_id": {"$exists": False}},
                {"from_entity_id": None}
            ]
        })
        print(f"Needs migration: {needs_migration}")

        if needs_migration == 0:
            print("All records already migrated!")
            return

        now = datetime.now(timezone.utc).isoformat()
        migrated = 0
        errors = 0

        docs = await gd_find(db.session, "user_relationships", {
            "$or": [
                {"from_entity_id": None}
            ]
        }, limit=10000)

        for doc in docs:
            rel_type = doc.get("relationship_type", "")
            mapping = RELATIONSHIP_TYPE_MAP.get(rel_type)

            if not mapping:
                errors += 1
                continue

            update_fields = {
                "from_entity_type": mapping["from_entity_type"],
                "from_entity_id": doc.get("user_id_1"),
                "to_entity_type": mapping["to_entity_type"],
                "to_entity_id": doc.get("user_id_2"),
                "relationship_type": mapping["new_type"],
                "status": "active" if doc.get("is_active", True) else "inactive",
                "updated_at": now
            }

            await gd_update_one(db.session, "user_relationships", {"id": doc["id"]}, update_fields)
            migrated += 1

            if migrated % 500 == 0:
                print(f"  Migrated batch: {migrated}/{needs_migration}")

        print(f"\nMigration complete: {migrated} migrated, {errors} errors")

        # Verify
        still_broken = await gd_count(db.session, "user_relationships", {
            "$or": [
                {"from_entity_type": None},
                {"from_entity_type": {"$exists": False}}
            ]
        })
        print(f"Still broken (null entity types): {still_broken}")

        # Print distribution
        pipeline = [
            {"$group": {"_id": "$relationship_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        print("\nRelationship types after migration:")
        async for doc in db.user_relationships.aggregate(pipeline):
            print(f"  {doc['_id']}: {doc['count']}")
if __name__ == "__main__":
    asyncio.run(migrate())
