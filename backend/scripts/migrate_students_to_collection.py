"""
Migration: Copy student users from users collection to students collection
The /api/students endpoint reads from db.students, not db.users
"""
import asyncio
import uuid
from datetime import datetime, timezone

import sys as _sys
import os as _os
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_upsert
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from scripts.seed_db_helper import get_seed_db

async def migrate():
    async with get_seed_db() as db:
        now = datetime.now(timezone.utc).isoformat()

        print("=== MIGRATING STUDENTS to students collection ===")

        # Get all student users
        student_users = await gd_find(db.session, "users", {"role": "student"}, {"_id": 0}, limit=10000)
        print(f"Found {len(student_users)} student users in users collection")

        existing_students = await gd_count(db.session, "students", {})
        print(f"Students currently in students collection: {existing_students}")

        # Get class map
        classes = await gd_find(db.session, "classes", {}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1, "grade_level": 1, "school_id": 1}, limit=5000)
        class_map = {c["id"]: c for c in classes}

        created = 0
        skipped = 0

        for user in student_users:
            # Check if already exists in students collection
            existing = await db.students.find_one({"$or": [
                {"id": user.get("id")},
                {"user_id": user.get("id")},
                {"email": user.get("email")}
            ]})

            if existing:
                skipped += 1
                continue

            class_id = user.get("class_id")
            class_info = class_map.get(class_id, {}) if class_id else {}

            student_doc = {
                "id": user.get("id") or str(uuid.uuid4()),
                "user_id": user.get("id"),
                "full_name": user.get("full_name") or user.get("name") or "طالب",
                "full_name_en": user.get("full_name_en"),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "school_id": user.get("school_id") or user.get("tenant_id"),
                "class_id": class_id,
                "class_name": class_info.get("name") or class_info.get("name_ar"),
                "grade_level": class_info.get("grade_level"),
                "student_number": f"STU-{str(uuid.uuid4())[:6].upper()}",
                "date_of_birth": user.get("date_of_birth"),
                "national_id": user.get("national_id"),
                "gender": user.get("gender"),
                "parent_phone": user.get("parent_phone"),
                "parent_name": user.get("parent_name"),
                "enrollment_date": user.get("enrollment_date"),
                "is_active": user.get("is_active", True),
                "created_at": user.get("created_at") or now,
                "updated_at": user.get("updated_at") or now,
            }

            await gd_insert(db.session, "students", student_doc)
            created += 1

            if created % 50 == 0:
                print(f"  Created {created} students so far...")

        # Create indexes
        pass  # index handled by PostgreSQL
        pass  # index handled by PostgreSQL
        pass  # index handled by PostgreSQL

        print(f"\n=== MIGRATION COMPLETE ===")
        print(f"Created: {created} student records in students collection")
        print(f"Skipped: {skipped} (already existed)")

        # Verify counts per school
        schools = await gd_find(db.session, "schools", {}, {"id": 1, "name_ar": 1}, limit=10)
        for school in schools:
            count = await gd_count(db.session, "students", {"school_id": school["id"]})
            print(f"  {school['id']}: {count} students")
if __name__ == "__main__":
    asyncio.run(migrate())
