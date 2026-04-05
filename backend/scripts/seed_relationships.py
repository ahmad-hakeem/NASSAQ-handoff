"""
NASSAQ — Seed Relationship Graph, Identity, and Behaviour Data
Seeds:
  1. guardian_links for all students across all schools
  2. user_relationships (parent_child, sibling, teacher_class, teacher_subject, 
     enrolled_in_school, belongs_to_class, belongs_to_grade, employed_at, manages_school)
  3. user_identities and user_roles for all users
  4. linked_roles for multi-role users (teacher who is also parent)
  5. behaviour_records for noor-ahlia students
"""

import asyncio
import uuid
import random
from datetime import datetime, timezone, timedelta

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from scripts.seed_db_helper import get_seed_db


RELATIONSHIP_TYPES = [
    "parent_child", "sibling", "teacher_class", "teacher_subject",
    "enrolled_in_school", "belongs_to_class", "belongs_to_grade",
    "employed_at", "manages_school", "principal_school"
]

FULL_PERMISSIONS = {
    "can_pickup": True,
    "can_view_grades": True,
    "can_view_attendance": True,
    "can_communicate": True,
    "can_view_financial_data": False,
    "receive_notifications": True,
    "pickup_authorization": True,
}

BEHAVIOUR_POSITIVE = [
    "مشاركة متميزة في الفصل",
    "مساعدة زملائه في الفهم",
    "إنجاز الواجبات بانتظام",
    "التزام بالقواعد الصفية",
    "تفوق في الاختبار القصير",
    "مبادرة في الأنشطة المدرسية",
    "حسن التعامل مع المعلمين",
    "إبداع في المشروع الجماعي",
]

BEHAVIOUR_NEGATIVE = [
    "تأخر عن الحصة",
    "عدم إحضار الأدوات المدرسية",
    "التحدث أثناء الشرح",
    "عدم تسليم الواجب",
]

BEHAVIOUR_CATEGORIES = ["academic", "social", "behavioural", "attendance"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def main():
    async with get_seed_db() as db:

        print("=" * 60)
        print("NASSAQ — Relationship Graph & Identity Seeder")
        print("=" * 60)

        # ─── STEP 0: Clean broken data ───
        print("\n[0] Cleaning broken user_relationships...")
        deleted = await db.user_relationships.delete_many({
            "$or": [
                {"from_entity_type": None},
                {"user_id_1": None},
                {"relationship_type": None},
            ]
        })
        print(f"    Deleted {deleted.deleted_count} broken records")

        # ─── STEP 1: Load all data ───
        print("\n[1] Loading data...")
        all_students = await db.students.find({}, {"_id": 0}).to_list(2000)
        all_users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(2000)
        all_teachers = await db.teachers.find({}, {"_id": 0}).to_list(500)
        all_schools = await db.schools.find({}, {"_id": 0}).to_list(20)
        all_teacher_assignments = await db.teacher_assignments.find({}, {"_id": 0}).to_list(2000)
        all_teacher_class_assignments = await db.teacher_class_assignments.find({}, {"_id": 0}).to_list(2000)

        users_by_id = {u["id"]: u for u in all_users}
        users_by_role = {}
        for u in all_users:
            role = u.get("role", "")
            if role not in users_by_role:
                users_by_role[role] = []
            users_by_role[role].append(u)

        parent_users = users_by_role.get("parent", [])
        parent_users_by_school = {}
        for p in parent_users:
            tid = p.get("tenant_id", "")
            if tid not in parent_users_by_school:
                parent_users_by_school[tid] = []
            parent_users_by_school[tid].append(p)

        students_by_school = {}
        for s in all_students:
            sid = s.get("school_id", "")
            if sid not in students_by_school:
                students_by_school[sid] = []
            students_by_school[sid].append(s)

        teachers_by_school = {}
        for t in all_teachers:
            sid = t.get("school_id", "")
            if sid not in teachers_by_school:
                teachers_by_school[sid] = []
            teachers_by_school[sid].append(t)

        school_ids = list(students_by_school.keys())
        print(f"    Schools: {len(school_ids)}")
        print(f"    Students: {len(all_students)}")
        print(f"    Teachers: {len(all_teachers)}")
        print(f"    Parent users: {len(parent_users)}")
        print(f"    Teacher assignments: {len(all_teacher_assignments)}")

        # ─── STEP 2: Seed guardian_links for ALL students ───
        print("\n[2] Seeding guardian_links...")
        existing_links = await db.guardian_links.find({}, {"_id": 0, "student_id": 1, "parent_ref": 1}).to_list(5000)
        existing_link_keys = {(l["student_id"], l["parent_ref"]) for l in existing_links}

        guardian_links_to_insert = []
        parent_child_map = {}

        for school_id in school_ids:
            school_students = students_by_school.get(school_id, [])
            school_parents = parent_users_by_school.get(school_id, [])
            if not school_parents:
                continue

            for student in school_students:
                student_id = student.get("id")
                parent_user_id = student.get("parent_user_id")

                if parent_user_id and parent_user_id in users_by_id:
                    parent_user = users_by_id[parent_user_id]
                else:
                    parent_user = random.choice(school_parents)
                    parent_user_id = parent_user["id"]
                    await db.students.update_one(
                        {"id": student_id},
                        {"$set": {"parent_user_id": parent_user_id}}
                    )

                if (student_id, parent_user_id) in existing_link_keys:
                    if parent_user_id not in parent_child_map:
                        parent_child_map[parent_user_id] = []
                    parent_child_map[parent_user_id].append(student_id)
                    continue

                relationship = random.choice(["father", "mother"])
                guardian_links_to_insert.append({
                    "id": str(uuid.uuid4()),
                    "tenant_id": school_id,
                    "student_id": student_id,
                    "student_name": student.get("full_name", ""),
                    "parent_id": None,
                    "parent_user_id": parent_user_id,
                    "parent_ref": parent_user_id,
                    "parent_name": parent_user.get("full_name", ""),
                    "relationship": relationship,
                    "is_primary": True,
                    "is_active": True,
                    "permissions": FULL_PERMISSIONS.copy(),
                    "notes": None,
                    "linked_by": "system",
                    "linked_at": now_iso(),
                    "updated_at": now_iso(),
                })

                if parent_user_id not in parent_child_map:
                    parent_child_map[parent_user_id] = []
                parent_child_map[parent_user_id].append(student_id)

        if guardian_links_to_insert:
            await db.guardian_links.insert_many(guardian_links_to_insert)
        print(f"    Inserted {len(guardian_links_to_insert)} new guardian_links")
        total_links = await db.guardian_links.count_documents({})
        print(f"    Total guardian_links now: {total_links}")

        # ─── STEP 3: Update existing guardian_links permissions ───
        print("\n[3] Updating existing guardian_link permissions...")
        updated_perms = await db.guardian_links.update_many(
            {"permissions.can_view_financial_data": {"$exists": False}},
            {"$set": {
                "permissions.can_view_financial_data": False,
                "permissions.receive_notifications": True,
                "permissions.pickup_authorization": True,
            }}
        )
        print(f"    Updated {updated_perms.modified_count} links with new permission fields")

        # ─── STEP 4: Seed user_relationships ───
        print("\n[4] Seeding user_relationships...")
        await db.user_relationships.delete_many({})
        relationships_to_insert = []

        def make_rel(rel_type, uid1, uid2, tenant_id=None, metadata=None):
            doc = {
                "id": str(uuid.uuid4()),
                "relationship_type": rel_type,
                "user_id_1": uid1,
                "user_id_2": uid2,
                "tenant_id": tenant_id,
                "is_active": True,
                "is_verified": True,
                "detected_automatically": True,
                "detection_method": "system_seed",
                "created_at": now_iso(),
                "created_by": "system",
                "verified_by": "system",
                "verified_at": now_iso(),
            }
            if metadata:
                doc["metadata"] = metadata
            return doc

        # 4a: parent_child relationships
        print("    4a: parent_child...")
        parent_child_count = 0
        for parent_id, child_ids in parent_child_map.items():
            parent_user = users_by_id.get(parent_id)
            if not parent_user:
                continue
            tenant_id = parent_user.get("tenant_id")
            for child_id in child_ids:
                relationships_to_insert.append(
                    make_rel("parent_child", parent_id, child_id, tenant_id)
                )
                parent_child_count += 1
        print(f"        Created {parent_child_count} parent_child relationships")

        # 4b: sibling relationships
        print("    4b: sibling...")
        sibling_count = 0
        for parent_id, child_ids in parent_child_map.items():
            if len(child_ids) < 2:
                continue
            parent_user = users_by_id.get(parent_id)
            tenant_id = parent_user.get("tenant_id") if parent_user else None
            for i in range(len(child_ids)):
                for j in range(i + 1, len(child_ids)):
                    relationships_to_insert.append(
                        make_rel("sibling", child_ids[i], child_ids[j], tenant_id)
                    )
                    sibling_count += 1
        print(f"        Created {sibling_count} sibling relationships")

        # 4c: teacher_class relationships
        print("    4c: teacher_class...")
        tc_count = 0
        tc_seen = set()
        for tca in all_teacher_class_assignments:
            tid = tca.get("teacher_id")
            cid = tca.get("class_id")
            sid = tca.get("school_id")
            if not tid or not cid:
                continue
            key = (tid, cid)
            if key in tc_seen:
                continue
            tc_seen.add(key)
            relationships_to_insert.append(
                make_rel("teacher_class", tid, cid, sid,
                          metadata={"class_id": cid})
            )
            tc_count += 1
        print(f"        Created {tc_count} teacher_class relationships")

        # 4d: teacher_subject relationships
        print("    4d: teacher_subject...")
        ts_count = 0
        ts_seen = set()
        for ta in all_teacher_assignments:
            tid = ta.get("teacher_id")
            sub_id = ta.get("subject_id")
            sid = ta.get("school_id")
            if not tid or not sub_id:
                continue
            key = (tid, sub_id)
            if key in ts_seen:
                continue
            ts_seen.add(key)
            relationships_to_insert.append(
                make_rel("teacher_subject", tid, sub_id, sid,
                          metadata={"subject_id": sub_id})
            )
            ts_count += 1
        print(f"        Created {ts_count} teacher_subject relationships")

        # 4e: enrolled_in_school
        print("    4e: enrolled_in_school...")
        eis_count = 0
        for student in all_students:
            sid = student.get("id")
            school_id = student.get("school_id")
            if not school_id:
                continue
            relationships_to_insert.append(
                make_rel("enrolled_in_school", sid, school_id, school_id)
            )
            eis_count += 1
        print(f"        Created {eis_count} enrolled_in_school relationships")

        # 4f: belongs_to_class
        print("    4f: belongs_to_class...")
        btc_count = 0
        for student in all_students:
            sid = student.get("id")
            cid = student.get("class_id")
            school_id = student.get("school_id")
            if not cid:
                continue
            relationships_to_insert.append(
                make_rel("belongs_to_class", sid, cid, school_id,
                          metadata={"class_id": cid, "class_name": student.get("class_name", "")})
            )
            btc_count += 1
        print(f"        Created {btc_count} belongs_to_class relationships")

        # 4g: belongs_to_grade
        print("    4g: belongs_to_grade...")
        btg_count = 0
        for student in all_students:
            sid = student.get("id")
            grade = student.get("grade_level") or student.get("grade_id")
            school_id = student.get("school_id")
            if not grade:
                continue
            relationships_to_insert.append(
                make_rel("belongs_to_grade", sid, grade, school_id,
                          metadata={"grade": grade})
            )
            btg_count += 1
        print(f"        Created {btg_count} belongs_to_grade relationships")

        # 4h: employed_at (teachers)
        print("    4h: employed_at...")
        ea_count = 0
        teacher_users = users_by_role.get("teacher", [])
        for tu in teacher_users:
            tenant = tu.get("tenant_id")
            if not tenant:
                continue
            relationships_to_insert.append(
                make_rel("employed_at", tu["id"], tenant, tenant)
            )
            ea_count += 1
        print(f"        Created {ea_count} employed_at relationships")

        # 4i: manages_school (school admins)
        print("    4i: manages_school...")
        ms_count = 0
        admin_users = [u for u in all_users if u.get("role") in ("school_admin", "school_principal")]
        for admin in admin_users:
            tenant = admin.get("tenant_id")
            if not tenant:
                continue
            relationships_to_insert.append(
                make_rel("manages_school", admin["id"], tenant, tenant)
            )
            ms_count += 1
        # Also principal_school
        for admin in admin_users:
            tenant = admin.get("tenant_id")
            if not tenant:
                continue
            relationships_to_insert.append(
                make_rel("principal_school", admin["id"], tenant, tenant)
            )
        print(f"        Created {ms_count} manages_school + {ms_count} principal_school relationships")

        # Bulk insert
        if relationships_to_insert:
            batch_size = 1000
            for i in range(0, len(relationships_to_insert), batch_size):
                batch = relationships_to_insert[i:i + batch_size]
                await db.user_relationships.insert_many(batch)
        total_rels = await db.user_relationships.count_documents({})
        print(f"\n    Total user_relationships: {total_rels}")

        # ─── STEP 5: Populate user_identities ───
        print("\n[5] Populating user_identities...")
        await db.user_identities.delete_many({})
        identities = []
        for user in all_users:
            identities.append({
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "identity_type": "primary",
                "role": user.get("role", ""),
                "tenant_id": user.get("tenant_id"),
                "display_name": user.get("full_name", ""),
                "email": user.get("email", ""),
                "phone": user.get("phone"),
                "is_active": user.get("is_active", True),
                "created_at": user.get("created_at", now_iso()),
                "updated_at": now_iso(),
            })
        if identities:
            await db.user_identities.insert_many(identities)
        print(f"    Created {len(identities)} user_identities")

        # ─── STEP 6: Populate user_roles ───
        print("\n[6] Populating user_roles...")
        await db.user_roles.delete_many({})
        role_records = []
        for user in all_users:
            role_records.append({
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "role": user.get("role", ""),
                "tenant_id": user.get("tenant_id"),
                "is_primary": True,
                "is_active": user.get("is_active", True),
                "assigned_at": user.get("created_at", now_iso()),
                "assigned_by": "system",
            })
        if role_records:
            await db.user_roles.insert_many(role_records)
        print(f"    Created {len(role_records)} user_roles")

        # ─── STEP 7: Detect and link multi-role users ───
        print("\n[7] Detecting multi-role users (teacher who is also parent)...")
        multi_role_count = 0
        teacher_emails = {u.get("email"): u for u in teacher_users if u.get("email")}
        parent_emails = {u.get("email"): u for u in parent_users if u.get("email")}

        teacher_phones = {}
        for u in teacher_users:
            if u.get("phone"):
                teacher_phones[u["phone"]] = u
        parent_phones = {}
        for u in parent_users:
            if u.get("phone"):
                parent_phones[u["phone"]] = u

        teacher_names_by_school = {}
        for u in teacher_users:
            key = (u.get("full_name", "").strip(), u.get("tenant_id"))
            teacher_names_by_school[key] = u

        for parent in parent_users:
            matched_teacher = None
            if parent.get("phone") and parent["phone"] in teacher_phones:
                matched_teacher = teacher_phones[parent["phone"]]
            elif parent.get("email") and parent["email"] in teacher_emails:
                matched_teacher = teacher_emails[parent["email"]]
            else:
                key = (parent.get("full_name", "").strip(), parent.get("tenant_id"))
                if key in teacher_names_by_school:
                    matched_teacher = teacher_names_by_school[key]

            if matched_teacher and matched_teacher["id"] != parent["id"]:
                linked_roles = parent.get("linked_roles", [])
                already_linked = any(
                    lr.get("role") == "teacher" and lr.get("tenant_id") == matched_teacher.get("tenant_id")
                    for lr in linked_roles
                )
                if not already_linked:
                    new_role = {
                        "role": "teacher",
                        "tenant_id": matched_teacher.get("tenant_id"),
                        "scope_id": matched_teacher.get("id"),
                        "is_active": True,
                        "assigned_at": now_iso(),
                        "assigned_by": "system",
                    }
                    await db.users.update_one(
                        {"id": parent["id"]},
                        {"$push": {"linked_roles": new_role}}
                    )
                    role_records_extra = {
                        "id": str(uuid.uuid4()),
                        "user_id": parent["id"],
                        "role": "teacher",
                        "tenant_id": matched_teacher.get("tenant_id"),
                        "is_primary": False,
                        "is_active": True,
                        "assigned_at": now_iso(),
                        "assigned_by": "system",
                    }
                    await db.user_roles.insert_one(role_records_extra)
                    multi_role_count += 1

        # Also set linked_roles for all users who have empty linked_roles but a valid tenant
        updated_lr = await db.users.update_many(
            {
                "tenant_id": {"$ne": None},
                "$or": [
                    {"linked_roles": {"$exists": False}},
                    {"linked_roles": []},
                    {"linked_roles": None},
                ]
            },
            [
                {"$set": {
                    "linked_roles": [{
                        "role": "$role",
                        "tenant_id": "$tenant_id",
                        "scope_id": None,
                        "is_active": True,
                        "assigned_at": now_iso(),
                        "assigned_by": "system",
                    }]
                }}
            ]
        )
        print(f"    Detected {multi_role_count} multi-role users (teacher+parent)")
        print(f"    Set linked_roles for {updated_lr.modified_count} users who had empty linked_roles")

        # ─── STEP 8: Seed behaviour records ───
        print("\n[8] Seeding behaviour records for noor-ahlia...")
        noor_students = students_by_school.get("school-noor-ahlia", [])
        noor_teachers = teachers_by_school.get("school-noor-ahlia", [])

        behaviour_records = []
        if noor_students and noor_teachers:
            sample_students = random.sample(noor_students, min(30, len(noor_students)))
            for student in sample_students:
                num_records = random.randint(1, 4)
                for _ in range(num_records):
                    is_positive = random.random() < 0.7
                    teacher = random.choice(noor_teachers)
                    days_ago = random.randint(1, 90)
                    record_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")

                    behaviour_records.append({
                        "id": str(uuid.uuid4()),
                        "student_id": student["id"],
                        "student_name": student.get("full_name", ""),
                        "school_id": "school-noor-ahlia",
                        "class_id": student.get("class_id"),
                        "teacher_id": teacher.get("id"),
                        "teacher_name": teacher.get("full_name", ""),
                        "type": "positive" if is_positive else "negative",
                        "category": random.choice(BEHAVIOUR_CATEGORIES),
                        "description": random.choice(BEHAVIOUR_POSITIVE if is_positive else BEHAVIOUR_NEGATIVE),
                        "points": random.randint(1, 5) if is_positive else -random.randint(1, 3),
                        "date": record_date,
                        "created_at": now_iso(),
                        "created_by": teacher.get("id"),
                    })

        if behaviour_records:
            await db.behaviour_records.insert_many(behaviour_records)
        print(f"    Created {len(behaviour_records)} behaviour records")

        # ─── STEP 9: Create indexes ───
        print("\n[9] Creating indexes...")
        await db.guardian_links.create_index([("tenant_id", 1), ("student_id", 1)])
        await db.guardian_links.create_index([("parent_ref", 1)])
        await db.guardian_links.create_index([("parent_user_id", 1)])
        await db.user_relationships.create_index([("user_id_1", 1), ("relationship_type", 1)])
        await db.user_relationships.create_index([("user_id_2", 1), ("relationship_type", 1)])
        await db.user_relationships.create_index([("tenant_id", 1), ("relationship_type", 1)])
        await db.user_identities.create_index([("user_id", 1)])
        await db.user_roles.create_index([("user_id", 1)])
        await db.behaviour_records.create_index([("student_id", 1)])
        await db.behaviour_records.create_index([("school_id", 1)])
        print("    Indexes created")

        # ─── FINAL SUMMARY ───
        print("\n" + "=" * 60)
        print("FINAL COUNTS:")
        print(f"  guardian_links:      {await db.guardian_links.count_documents({})}")
        print(f"  user_relationships:  {await db.user_relationships.count_documents({})}")
        print(f"  user_identities:     {await db.user_identities.count_documents({})}")
        print(f"  user_roles:          {await db.user_roles.count_documents({})}")
        print(f"  behaviour_records:   {await db.behaviour_records.count_documents({})}")

        rel_types = await db.user_relationships.aggregate([
            {"$group": {"_id": "$relationship_type", "count": {"$sum": 1}}}
        ]).to_list(20)
        print("\n  Relationship types:")
        for rt in sorted(rel_types, key=lambda x: x["_id"]):
            print(f"    {rt['_id']}: {rt['count']}")

        multi = await db.users.count_documents({"linked_roles.1": {"$exists": True}})
        print(f"\n  Users with 2+ linked_roles: {multi}")

        print("\n" + "=" * 60)
        print("DONE!")
    if __name__ == "__main__":
        asyncio.run(main())
