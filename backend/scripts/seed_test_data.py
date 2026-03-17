"""
Script to seed test data for NASSAQ school management system
This includes:
- Test teachers with proper ranks
- Test students with proper grades
- Test classes linked to academic structure
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
import uuid
import bcrypt

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# ============================================
# TEST DATA
# ============================================

# Schools to use (using existing ones)
TARGET_SCHOOLS = [
    {"id": "school-nor-001", "name": "مدرسة النور"},
    {"id": "school-aml-001", "name": "مدرسة الأمل"}
]

# Test Teachers
TEST_TEACHERS = [
    # مدرسة النور - 5 معلمين
    {
        "school_id": "school-nor-001",
        "full_name_ar": "أحمد محمد العتيبي",
        "full_name_en": "Ahmed Mohammed Al-Otaibi",
        "email": "ahmed.otaibi@nor.edu.sa",
        "phone": "+966501234567",
        "rank_id": "rank-advanced",
        "subjects": ["subj-arabic", "subj-arabic-eternal"],
        "gender": "male"
    },
    {
        "school_id": "school-nor-001",
        "full_name_ar": "فاطمة علي الغامدي",
        "full_name_en": "Fatima Ali Al-Ghamdi",
        "email": "fatima.ghamdi@nor.edu.sa",
        "phone": "+966502234567",
        "rank_id": "rank-practitioner",
        "subjects": ["subj-math"],
        "gender": "female"
    },
    {
        "school_id": "school-nor-001",
        "full_name_ar": "خالد سعد القحطاني",
        "full_name_en": "Khalid Saad Al-Qahtani",
        "email": "khalid.qahtani@nor.edu.sa",
        "phone": "+966503234567",
        "rank_id": "rank-expert",
        "subjects": ["subj-science"],
        "gender": "male"
    },
    {
        "school_id": "school-nor-001",
        "full_name_ar": "نورة عبدالله الشمري",
        "full_name_en": "Noura Abdullah Al-Shammari",
        "email": "noura.shammari@nor.edu.sa",
        "phone": "+966504234567",
        "rank_id": "rank-teacher",
        "subjects": ["subj-english"],
        "gender": "female"
    },
    {
        "school_id": "school-nor-001",
        "full_name_ar": "محمد عبدالرحمن الدوسري",
        "full_name_en": "Mohammed Abdulrahman Al-Dosari",
        "email": "mohammed.dosari@nor.edu.sa",
        "phone": "+966505234567",
        "rank_id": "rank-practitioner",
        "subjects": ["subj-islamic", "subj-quran"],
        "gender": "male"
    },
    # مدرسة الأمل - 4 معلمين
    {
        "school_id": "school-aml-001",
        "full_name_ar": "سارة محمد الحربي",
        "full_name_en": "Sara Mohammed Al-Harbi",
        "email": "sara.harbi@aml.edu.sa",
        "phone": "+966506234567",
        "rank_id": "rank-advanced",
        "subjects": ["subj-arabic", "subj-arabic-eternal"],
        "gender": "female"
    },
    {
        "school_id": "school-aml-001",
        "full_name_ar": "عبدالله فهد المطيري",
        "full_name_en": "Abdullah Fahd Al-Mutairi",
        "email": "abdullah.mutairi@aml.edu.sa",
        "phone": "+966507234567",
        "rank_id": "rank-practitioner",
        "subjects": ["subj-math", "subj-science"],
        "gender": "male"
    },
    {
        "school_id": "school-aml-001",
        "full_name_ar": "هند سالم العنزي",
        "full_name_en": "Hind Salem Al-Anazi",
        "email": "hind.anazi@aml.edu.sa",
        "phone": "+966508234567",
        "rank_id": "rank-teacher",
        "subjects": ["subj-english", "subj-social"],
        "gender": "female"
    },
    {
        "school_id": "school-aml-001",
        "full_name_ar": "يوسف أحمد الزهراني",
        "full_name_en": "Youssef Ahmed Al-Zahrani",
        "email": "youssef.zahrani@aml.edu.sa",
        "phone": "+966509234567",
        "rank_id": "rank-expert",
        "subjects": ["subj-pe", "subj-art"],
        "gender": "male"
    },
]

# Test Classes (Sections)
TEST_CLASSES = [
    # مدرسة النور - 6 فصول
    {"school_id": "school-nor-001", "grade_id": "grade-1", "section": "أ", "capacity": 25},
    {"school_id": "school-nor-001", "grade_id": "grade-1", "section": "ب", "capacity": 25},
    {"school_id": "school-nor-001", "grade_id": "grade-4", "section": "أ", "capacity": 30},
    {"school_id": "school-nor-001", "grade_id": "grade-7", "section": "أ", "capacity": 30},
    {"school_id": "school-nor-001", "grade_id": "grade-7", "section": "ب", "capacity": 30},
    {"school_id": "school-nor-001", "grade_id": "grade-10", "section": "أ", "capacity": 28},
    # مدرسة الأمل - 4 فصول
    {"school_id": "school-aml-001", "grade_id": "grade-2", "section": "أ", "capacity": 25},
    {"school_id": "school-aml-001", "grade_id": "grade-5", "section": "أ", "capacity": 28},
    {"school_id": "school-aml-001", "grade_id": "grade-8", "section": "أ", "capacity": 30},
    {"school_id": "school-aml-001", "grade_id": "grade-11", "section": "أ", "capacity": 25},
]

# Sample student names (Arabic)
MALE_FIRST_NAMES = ["محمد", "أحمد", "عبدالله", "خالد", "سعد", "فهد", "ناصر", "سلطان", "عمر", "يوسف", "علي", "حسن", "إبراهيم", "عبدالرحمن", "ماجد"]
FEMALE_FIRST_NAMES = ["فاطمة", "نورة", "سارة", "هند", "منى", "ريم", "لمى", "دانة", "جود", "لين", "ملاك", "شهد", "رغد", "وجدان", "أسماء"]
LAST_NAMES = ["العتيبي", "الغامدي", "القحطاني", "الشمري", "الدوسري", "الحربي", "المطيري", "العنزي", "الزهراني", "السبيعي", "البلوي", "الشهري", "الجهني", "العمري", "الحارثي"]

def generate_student_name(gender: str, index: int):
    """Generate a student name based on gender and index"""
    first_names = MALE_FIRST_NAMES if gender == "male" else FEMALE_FIRST_NAMES
    first_name = first_names[index % len(first_names)]
    last_name = LAST_NAMES[index % len(LAST_NAMES)]
    return f"{first_name} {last_name}"


async def seed_test_data():
    """Main function to seed test data"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    now = datetime.now(timezone.utc)
    password_hash = hash_password("Teacher@123")
    student_password_hash = hash_password("Student@123")
    
    print("=" * 60)
    print("Starting NASSAQ Test Data Seeding")
    print("=" * 60)
    
    # Get grade info for reference
    grades = {g['id']: g async for g in db.academic_grades.find({})}
    ranks = {r['id']: r async for r in db.teacher_ranks.find({})}
    
    # 1. Seed Teachers
    print("\n[1/4] Seeding Test Teachers...")
    teacher_count = 0
    for teacher_data in TEST_TEACHERS:
        teacher_id = str(uuid.uuid4())
        rank = ranks.get(teacher_data['rank_id'], {})
        
        # Create user account
        user = {
            "id": teacher_id,
            "email": teacher_data['email'],
            "password": password_hash,
            "full_name": teacher_data['full_name_ar'],
            "full_name_en": teacher_data['full_name_en'],
            "phone": teacher_data['phone'],
            "role": "teacher",
            "tenant_id": teacher_data['school_id'],
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }
        await db.users.update_one(
            {"email": teacher_data['email']},
            {"$set": user},
            upsert=True
        )
        
        # Create teacher profile
        teacher = {
            "id": teacher_id,
            "user_id": teacher_id,
            "school_id": teacher_data['school_id'],
            "full_name_ar": teacher_data['full_name_ar'],
            "full_name_en": teacher_data['full_name_en'],
            "email": teacher_data['email'],
            "phone": teacher_data['phone'],
            "rank_id": teacher_data['rank_id'],
            "rank_name_ar": rank.get('name_ar', ''),
            "rank_name_en": rank.get('name_en', ''),
            "weekly_periods": rank.get('weekly_periods', 24),
            "subjects": teacher_data['subjects'],
            "gender": teacher_data['gender'],
            "availability": {
                "sunday": [1, 2, 3, 4, 5, 6, 7],
                "monday": [1, 2, 3, 4, 5, 6, 7],
                "tuesday": [1, 2, 3, 4, 5, 6, 7],
                "wednesday": [1, 2, 3, 4, 5, 6, 7],
                "thursday": [1, 2, 3, 4, 5, 6, 7],
            },
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }
        await db.teachers.update_one(
            {"email": teacher_data['email']},
            {"$set": teacher},
            upsert=True
        )
        teacher_count += 1
        print(f"  ✓ Teacher: {teacher_data['full_name_ar']} ({teacher_data['school_id']})")
    
    print(f"\n  Total: {teacher_count} teachers created")
    
    # 2. Seed Classes
    print("\n[2/4] Seeding Test Classes...")
    class_count = 0
    created_classes = []
    for class_data in TEST_CLASSES:
        grade = grades.get(class_data['grade_id'], {})
        class_id = f"{class_data['school_id']}-{class_data['grade_id']}-{class_data['section']}"
        
        class_doc = {
            "id": class_id,
            "school_id": class_data['school_id'],
            "grade_id": class_data['grade_id'],
            "grade_name_ar": grade.get('name_ar', ''),
            "grade_name_en": grade.get('name_en', ''),
            "stage_id": grade.get('stage_id', ''),
            "section": class_data['section'],
            "name_ar": f"{grade.get('name_ar', '')} - {class_data['section']}",
            "name_en": f"{grade.get('name_en', '')} - {class_data['section']}",
            "capacity": class_data['capacity'],
            "current_students": 0,  # Will be updated after adding students
            "education_track": "track-general",
            "is_active": True,
            "academic_year": "2025-2026",
            "created_at": now,
            "updated_at": now
        }
        await db.classes.update_one(
            {"id": class_id},
            {"$set": class_doc},
            upsert=True
        )
        created_classes.append(class_doc)
        class_count += 1
        print(f"  ✓ Class: {class_doc['name_ar']} ({class_data['school_id']})")
    
    print(f"\n  Total: {class_count} classes created")
    
    # 3. Seed Students (15 per class)
    print("\n[3/4] Seeding Test Students...")
    student_count = 0
    students_per_class = 15
    
    for class_doc in created_classes:
        class_students = 0
        for i in range(students_per_class):
            gender = "male" if i % 2 == 0 else "female"
            student_name = generate_student_name(gender, student_count)
            student_id = str(uuid.uuid4())
            email = f"student{student_count + 1}@{class_doc['school_id'].replace('school-', '').replace('-001', '')}.edu.sa"
            
            # Create user account
            user = {
                "id": student_id,
                "email": email,
                "password": student_password_hash,
                "full_name": student_name,
                "role": "student",
                "tenant_id": class_doc['school_id'],
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            await db.users.update_one(
                {"email": email},
                {"$set": user},
                upsert=True
            )
            
            # Create student profile
            student = {
                "id": student_id,
                "user_id": student_id,
                "school_id": class_doc['school_id'],
                "class_id": class_doc['id'],
                "grade_id": class_doc['grade_id'],
                "full_name_ar": student_name,
                "email": email,
                "gender": gender,
                "student_number": f"STU{str(student_count + 1).zfill(5)}",
                "enrollment_date": now.strftime("%Y-%m-%d"),
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            await db.students.update_one(
                {"email": email},
                {"$set": student},
                upsert=True
            )
            
            student_count += 1
            class_students += 1
        
        # Update class student count
        await db.classes.update_one(
            {"id": class_doc['id']},
            {"$set": {"current_students": class_students}}
        )
        print(f"  ✓ {class_students} students added to: {class_doc['name_ar']}")
    
    print(f"\n  Total: {student_count} students created")
    
    # 4. Update school statistics
    print("\n[4/4] Updating School Statistics...")
    for school in TARGET_SCHOOLS:
        school_id = school['id']
        
        # Count students and teachers
        student_count_school = await db.students.count_documents({"school_id": school_id})
        teacher_count_school = await db.teachers.count_documents({"school_id": school_id})
        class_count_school = await db.classes.count_documents({"school_id": school_id})
        
        await db.schools.update_one(
            {"id": school_id},
            {"$set": {
                "current_students": student_count_school,
                "current_teachers": teacher_count_school,
                "current_classes": class_count_school,
                "updated_at": now
            }}
        )
        print(f"  ✓ {school['name']}: {student_count_school} students, {teacher_count_school} teachers, {class_count_school} classes")
    
    print("\n" + "=" * 60)
    print("Test Data Seeding Complete!")
    print("=" * 60)
    
    # Print summary
    print("\n📊 Summary:")
    print(f"  - Teachers: {len(TEST_TEACHERS)}")
    print(f"  - Classes: {len(TEST_CLASSES)}")
    print(f"  - Students: {len(TEST_CLASSES) * students_per_class}")
    print("\n🔑 Test Credentials:")
    print("  - Teachers: [email]@nor.edu.sa or [email]@aml.edu.sa / Teacher@123")
    print("  - Students: student[N]@nor.edu.sa or student[N]@aml.edu.sa / Student@123")
    
    return True


if __name__ == "__main__":
    asyncio.run(seed_test_data())
