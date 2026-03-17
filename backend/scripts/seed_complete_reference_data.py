"""
سكريبت تثبيت البيانات المرجعية الأساسية الكاملة
يشمل: الهيكل الأكاديمي، المواد، رتب المعلمين، النصاب، القيود الإدارية، الإعدادات الافتراضية
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
import uuid

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

# ============================================
# 1. المراحل الدراسية
# ============================================
STAGES = [
    {"id": "STAGE-001", "name_ar": "المرحلة الابتدائية", "name_en": "Elementary Stage", "order": 1, "grades_count": 6},
    {"id": "STAGE-002", "name_ar": "المرحلة المتوسطة", "name_en": "Middle Stage", "order": 2, "grades_count": 3},
    {"id": "STAGE-003", "name_ar": "المرحلة الثانوية", "name_en": "High Stage", "order": 3, "grades_count": 3},
]

# ============================================
# 2. الصفوف الدراسية - 12 صف
# ============================================
GRADES = [
    # المرحلة الابتدائية
    {"id": "GRADE-01", "stage_id": "STAGE-001", "name_ar": "الصف الأول الابتدائي", "name_en": "Grade 1", "order": 1, "is_lower_grades": True},
    {"id": "GRADE-02", "stage_id": "STAGE-001", "name_ar": "الصف الثاني الابتدائي", "name_en": "Grade 2", "order": 2, "is_lower_grades": True},
    {"id": "GRADE-03", "stage_id": "STAGE-001", "name_ar": "الصف الثالث الابتدائي", "name_en": "Grade 3", "order": 3, "is_lower_grades": True},
    {"id": "GRADE-04", "stage_id": "STAGE-001", "name_ar": "الصف الرابع الابتدائي", "name_en": "Grade 4", "order": 4, "is_lower_grades": False},
    {"id": "GRADE-05", "stage_id": "STAGE-001", "name_ar": "الصف الخامس الابتدائي", "name_en": "Grade 5", "order": 5, "is_lower_grades": False},
    {"id": "GRADE-06", "stage_id": "STAGE-001", "name_ar": "الصف السادس الابتدائي", "name_en": "Grade 6", "order": 6, "is_lower_grades": False},
    # المرحلة المتوسطة
    {"id": "GRADE-07", "stage_id": "STAGE-002", "name_ar": "الصف الأول المتوسط", "name_en": "Grade 7", "order": 7, "is_lower_grades": False},
    {"id": "GRADE-08", "stage_id": "STAGE-002", "name_ar": "الصف الثاني المتوسط", "name_en": "Grade 8", "order": 8, "is_lower_grades": False},
    {"id": "GRADE-09", "stage_id": "STAGE-002", "name_ar": "الصف الثالث المتوسط", "name_en": "Grade 9", "order": 9, "is_lower_grades": False},
    # المرحلة الثانوية
    {"id": "GRADE-10", "stage_id": "STAGE-003", "name_ar": "الصف الأول الثانوي", "name_en": "Grade 10", "order": 10, "is_lower_grades": False},
    {"id": "GRADE-11", "stage_id": "STAGE-003", "name_ar": "الصف الثاني الثانوي", "name_en": "Grade 11", "order": 11, "is_lower_grades": False},
    {"id": "GRADE-12", "stage_id": "STAGE-003", "name_ar": "الصف الثالث الثانوي", "name_en": "Grade 12", "order": 12, "is_lower_grades": False},
]

# ============================================
# 3. المسارات التعليمية
# ============================================
TRACKS = [
    {"id": "TRACK-001", "name_ar": "التعليم العام", "name_en": "General Education", "code": "general", "is_quran_track": False},
    {"id": "TRACK-002", "name_ar": "مدارس تحفيظ القرآن الكريم", "name_en": "Quran Memorization", "code": "quran_memorization", "is_quran_track": True},
]

# ============================================
# 4. المواد الدراسية - حسب المرحلة والمسار
# ============================================
def get_subjects():
    subjects = []
    subject_id = 1
    
    # المواد الأساسية المشتركة
    common_subjects = [
        {"name_ar": "لغتي", "name_en": "Arabic Language", "category": "language", "weekly_periods": 6},
        {"name_ar": "الرياضيات", "name_en": "Mathematics", "category": "science", "weekly_periods": 5},
        {"name_ar": "العلوم", "name_en": "Science", "category": "science", "weekly_periods": 4},
        {"name_ar": "الدراسات الإسلامية", "name_en": "Islamic Studies", "category": "islamic", "weekly_periods": 3},
        {"name_ar": "اللغة الإنجليزية", "name_en": "English Language", "category": "language", "weekly_periods": 4},
        {"name_ar": "المهارات الرقمية", "name_en": "Digital Skills", "category": "technology", "weekly_periods": 2},
        {"name_ar": "التربية الفنية", "name_en": "Art Education", "category": "activity", "weekly_periods": 2},
        {"name_ar": "التربية البدنية", "name_en": "Physical Education", "category": "activity", "weekly_periods": 2},
        {"name_ar": "المهارات الحياتية والأسرية", "name_en": "Life Skills", "category": "skills", "weekly_periods": 2},
    ]
    
    # مواد إضافية للصفوف العليا
    upper_additional = [
        {"name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies", "category": "social", "weekly_periods": 2},
    ]
    
    # مواد تحفيظ القرآن
    quran_subjects = [
        {"name_ar": "القرآن الكريم", "name_en": "Holy Quran", "category": "islamic", "weekly_periods": 6},
    ]
    
    # مواد المرحلة المتوسطة والثانوية
    secondary_subjects = [
        {"name_ar": "لغتي الخالدة", "name_en": "Arabic Literature", "category": "language", "weekly_periods": 5},
    ]
    
    # إنشاء المواد لكل مرحلة ومسار
    for grade in GRADES:
        grade_id = grade["id"]
        stage_id = grade["stage_id"]
        is_lower = grade.get("is_lower_grades", False)
        grade_order = grade["order"]
        
        # المواد الأساسية
        base_subjects = common_subjects.copy()
        
        # إضافة الدراسات الاجتماعية للصفوف العليا والمتوسطة والثانوية
        if not is_lower:
            base_subjects.extend(upper_additional)
        
        # تغيير "لغتي" إلى "لغتي الخالدة" للمتوسطة والثانوية
        if stage_id in ["STAGE-002", "STAGE-003"]:
            base_subjects = [s for s in base_subjects if s["name_ar"] != "لغتي"]
            base_subjects.extend(secondary_subjects)
        
        # مسار التعليم العام
        for subj in base_subjects:
            subjects.append({
                "id": f"SUBJ-{subject_id:03d}",
                "name_ar": subj["name_ar"],
                "name_en": subj["name_en"],
                "category": subj["category"],
                "weekly_periods": subj["weekly_periods"],
                "stage_id": stage_id,
                "grade_id": grade_id,
                "track_id": "TRACK-001",
                "is_quran_track": False,
                "is_active": True,
            })
            subject_id += 1
        
        # مسار تحفيظ القرآن (نفس المواد + القرآن الكريم)
        for subj in base_subjects:
            subjects.append({
                "id": f"SUBJ-{subject_id:03d}",
                "name_ar": subj["name_ar"],
                "name_en": subj["name_en"],
                "category": subj["category"],
                "weekly_periods": subj["weekly_periods"],
                "stage_id": stage_id,
                "grade_id": grade_id,
                "track_id": "TRACK-002",
                "is_quran_track": True,
                "is_active": True,
            })
            subject_id += 1
        
        # إضافة القرآن الكريم لمسار التحفيظ
        for subj in quran_subjects:
            subjects.append({
                "id": f"SUBJ-{subject_id:03d}",
                "name_ar": subj["name_ar"],
                "name_en": subj["name_en"],
                "category": subj["category"],
                "weekly_periods": subj["weekly_periods"],
                "stage_id": stage_id,
                "grade_id": grade_id,
                "track_id": "TRACK-002",
                "is_quran_track": True,
                "is_active": True,
            })
            subject_id += 1
    
    return subjects

# ============================================
# 5. رتب المعلمين والنصاب التدريسي
# ============================================
TEACHER_RANKS = [
    {"id": "RANK-001", "name_ar": "المعلم", "name_en": "Teacher", "weekly_periods": 24, "daily_max": 6, "order": 1, "is_special_education": False},
    {"id": "RANK-002", "name_ar": "المعلم الممارس", "name_en": "Practitioner Teacher", "weekly_periods": 24, "daily_max": 6, "order": 2, "is_special_education": False},
    {"id": "RANK-003", "name_ar": "المعلم المتقدم", "name_en": "Advanced Teacher", "weekly_periods": 22, "daily_max": 5, "order": 3, "is_special_education": False},
    {"id": "RANK-004", "name_ar": "المعلم الخبير", "name_en": "Expert Teacher", "weekly_periods": 18, "daily_max": 4, "order": 4, "is_special_education": False},
    {"id": "RANK-005", "name_ar": "معلم تربية خاصة - معلم ممارس", "name_en": "Special Ed - Practitioner", "weekly_periods": 18, "daily_max": 4, "order": 5, "is_special_education": True},
    {"id": "RANK-006", "name_ar": "معلم تربية خاصة - معلم متقدم", "name_en": "Special Ed - Advanced", "weekly_periods": 16, "daily_max": 4, "order": 6, "is_special_education": True},
    {"id": "RANK-007", "name_ar": "معلم تربية خاصة - معلم خبير", "name_en": "Special Ed - Expert", "weekly_periods": 14, "daily_max": 3, "order": 7, "is_special_education": True},
]

# ============================================
# 6. القيود الإدارية الأساسية
# ============================================
ADMIN_CONSTRAINTS = [
    {
        "id": "CONST-001",
        "name_ar": "تعارض المعلم",
        "name_en": "Teacher Conflict",
        "description_ar": "لا يسمح بإسناد المعلم إلى حصتين في نفس الوقت",
        "description_en": "Teacher cannot be assigned to two sessions at the same time",
        "constraint_type": "conflict",
        "priority": "critical",
        "is_active": True,
    },
    {
        "id": "CONST-002",
        "name_ar": "تعارض الفصل",
        "name_en": "Class Conflict",
        "description_ar": "لا يسمح بإسناد الفصل إلى حصتين في نفس الوقت",
        "description_en": "Class cannot have two sessions at the same time",
        "constraint_type": "conflict",
        "priority": "critical",
        "is_active": True,
    },
    {
        "id": "CONST-003",
        "name_ar": "الحد الأقصى للحصص المتتالية",
        "name_en": "Max Consecutive Sessions",
        "description_ar": "لا يسمح بوضع أكثر من حصتين متتاليتين لنفس المادة في اليوم نفسه لنفس الفصل",
        "description_en": "Max 2 consecutive sessions of same subject per day per class",
        "constraint_type": "balance",
        "priority": "high",
        "is_active": True,
    },
    {
        "id": "CONST-004",
        "name_ar": "التربية البدنية",
        "name_en": "Physical Education",
        "description_ar": "لا يسمح بوضع التربية البدنية في الحصة الأولى",
        "description_en": "Physical Education not allowed in first period",
        "constraint_type": "subject_time",
        "priority": "medium",
        "is_active": True,
        "subject_category": "activity",
        "restricted_periods": [1],
    },
    {
        "id": "CONST-005",
        "name_ar": "اللغة الإنجليزية للصفوف الأولية",
        "name_en": "English for Lower Grades",
        "description_ar": "لا يسمح بوضع اللغة الإنجليزية في الحصة الأولى للصفوف الأولية",
        "description_en": "English not allowed in first period for lower grades",
        "constraint_type": "subject_time",
        "priority": "medium",
        "is_active": True,
        "subject_category": "language",
        "restricted_periods": [1],
        "applies_to_lower_grades": True,
    },
    {
        "id": "CONST-006",
        "name_ar": "الدراسات الإسلامية والقرآن",
        "name_en": "Islamic Studies & Quran",
        "description_ar": "لا يسمح بوضع الدراسات الإسلامية أو القرآن الكريم في الحصة السابعة",
        "description_en": "Islamic Studies or Quran not allowed in 7th period",
        "constraint_type": "subject_time",
        "priority": "medium",
        "is_active": True,
        "subject_category": "islamic",
        "restricted_periods": [7],
    },
]

# ============================================
# 7. الإعدادات الافتراضية للمدارس
# ============================================
DEFAULT_SCHOOL_SETTINGS = {
    "id": "default-school-settings",
    "name": "الإعدادات الافتراضية للمدارس",
    "name_en": "Default School Settings",
    
    # أيام العمل
    "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"],
    "working_days_ar": ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس"],
    "working_days_en": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
    "weekend_days": ["friday", "saturday"],
    "weekend_days_ar": ["الجمعة", "السبت"],
    "weekend_days_en": ["Friday", "Saturday"],
    
    # الإطار الزمني
    "school_day_start": "07:00",
    "school_day_end": "13:15",
    "periods_per_day": 7,
    "period_duration_minutes": 45,
    "break_duration_minutes": 20,
    "prayer_duration_minutes": 20,
    
    # الفترات الزمنية
    "time_slots": [
        {"slot_number": 1, "type": "period", "name_ar": "الحصة الأولى", "name_en": "Period 1", "start_time": "07:00", "end_time": "07:45", "duration": 45},
        {"slot_number": 2, "type": "period", "name_ar": "الحصة الثانية", "name_en": "Period 2", "start_time": "07:45", "end_time": "08:30", "duration": 45},
        {"slot_number": 3, "type": "period", "name_ar": "الحصة الثالثة", "name_en": "Period 3", "start_time": "08:30", "end_time": "09:15", "duration": 45},
        {"slot_number": 4, "type": "break", "name_ar": "الاستراحة", "name_en": "Break", "start_time": "09:15", "end_time": "09:35", "duration": 20},
        {"slot_number": 5, "type": "period", "name_ar": "الحصة الرابعة", "name_en": "Period 4", "start_time": "09:35", "end_time": "10:20", "duration": 45},
        {"slot_number": 6, "type": "period", "name_ar": "الحصة الخامسة", "name_en": "Period 5", "start_time": "10:20", "end_time": "11:05", "duration": 45},
        {"slot_number": 7, "type": "prayer", "name_ar": "فترة الصلاة", "name_en": "Prayer Time", "start_time": "11:05", "end_time": "11:25", "duration": 20},
        {"slot_number": 8, "type": "period", "name_ar": "الحصة السادسة", "name_en": "Period 6", "start_time": "11:25", "end_time": "12:10", "duration": 45},
        {"slot_number": 9, "type": "period", "name_ar": "الحصة السابعة", "name_en": "Period 7", "start_time": "12:10", "end_time": "12:55", "duration": 45},
    ],
    
    # التوافر الافتراضي
    "default_availability": {
        "sunday": [1, 2, 3, 4, 5, 6, 7],
        "monday": [1, 2, 3, 4, 5, 6, 7],
        "tuesday": [1, 2, 3, 4, 5, 6, 7],
        "wednesday": [1, 2, 3, 4, 5, 6, 7],
        "thursday": [1, 2, 3, 4, 5, 6, 7],
    },
    
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


async def seed_all_reference_data():
    """تثبيت جميع البيانات المرجعية"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("=" * 60)
    print("🚀 بدء تثبيت البيانات المرجعية الكاملة")
    print("=" * 60)
    
    # 1. المراحل الدراسية
    print("\n📚 تثبيت المراحل الدراسية...")
    await db.reference_stages.delete_many({})
    for stage in STAGES:
        stage["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.reference_stages.insert_many(STAGES)
    print(f"   ✓ تم تثبيت {len(STAGES)} مراحل دراسية")
    
    # 2. الصفوف الدراسية
    print("\n📖 تثبيت الصفوف الدراسية...")
    await db.reference_grades.delete_many({})
    for grade in GRADES:
        grade["created_at"] = datetime.now(timezone.utc).isoformat()
        # إضافة اسم المرحلة
        stage = next((s for s in STAGES if s["id"] == grade["stage_id"]), None)
        if stage:
            grade["stage_name_ar"] = stage["name_ar"]
            grade["stage_name_en"] = stage["name_en"]
    await db.reference_grades.insert_many(GRADES)
    print(f"   ✓ تم تثبيت {len(GRADES)} صف دراسي")
    
    # 3. المسارات التعليمية
    print("\n🛤️ تثبيت المسارات التعليمية...")
    await db.reference_tracks.delete_many({})
    for track in TRACKS:
        track["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.reference_tracks.insert_many(TRACKS)
    print(f"   ✓ تم تثبيت {len(TRACKS)} مسار تعليمي")
    
    # 4. المواد الدراسية
    print("\n📕 تثبيت المواد الدراسية...")
    subjects = get_subjects()
    await db.reference_subjects.delete_many({})
    for subj in subjects:
        subj["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.reference_subjects.insert_many(subjects)
    print(f"   ✓ تم تثبيت {len(subjects)} مادة دراسية")
    
    # 5. رتب المعلمين
    print("\n👨‍🏫 تثبيت رتب المعلمين...")
    await db.reference_teacher_ranks.delete_many({})
    for rank in TEACHER_RANKS:
        rank["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.reference_teacher_ranks.insert_many(TEACHER_RANKS)
    print(f"   ✓ تم تثبيت {len(TEACHER_RANKS)} رتبة معلم")
    
    # 6. القيود الإدارية
    print("\n🚫 تثبيت القيود الإدارية...")
    await db.reference_admin_constraints.delete_many({})
    for const in ADMIN_CONSTRAINTS:
        const["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.reference_admin_constraints.insert_many(ADMIN_CONSTRAINTS)
    print(f"   ✓ تم تثبيت {len(ADMIN_CONSTRAINTS)} قيد إداري")
    
    # 7. الإعدادات الافتراضية
    print("\n⚙️ تثبيت الإعدادات الافتراضية...")
    await db.default_school_settings.delete_many({})
    await db.default_school_settings.insert_one(DEFAULT_SCHOOL_SETTINGS)
    print("   ✓ تم تثبيت الإعدادات الافتراضية للمدارس")
    
    # 8. تطبيق الإعدادات على المدارس الحالية
    print("\n🏫 تطبيق الإعدادات على المدارس الحالية...")
    schools = await db.schools.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(None)
    for school in schools:
        school_id = school["id"]
        
        # تحديث أو إنشاء إعدادات المدرسة
        existing = await db.school_settings.find_one({"school_id": school_id})
        if not existing:
            school_settings = {
                "school_id": school_id,
                **{k: v for k, v in DEFAULT_SCHOOL_SETTINGS.items() if k not in ["id", "name", "name_en"]},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.school_settings.insert_one(school_settings)
        else:
            # تحديث الإعدادات الحالية
            await db.school_settings.update_one(
                {"school_id": school_id},
                {"$set": {
                    "time_slots": DEFAULT_SCHOOL_SETTINGS["time_slots"],
                    "default_availability": DEFAULT_SCHOOL_SETTINGS["default_availability"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
        print(f"   ✓ تم تحديث إعدادات: {school['name']}")
    
    # 9. إنشاء time_slots للمدارس
    print("\n⏰ تثبيت الفترات الزمنية للمدارس...")
    for school in schools:
        school_id = school["id"]
        await db.time_slots.delete_many({"school_id": school_id})
        
        time_slots = []
        for slot in DEFAULT_SCHOOL_SETTINGS["time_slots"]:
            time_slots.append({
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "name": slot["name_ar"],
                "name_en": slot["name_en"],
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "slot_number": slot["slot_number"],
                "duration_minutes": slot["duration"],
                "is_break": slot["type"] in ["break", "prayer"],
                "slot_type": slot["type"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        
        if time_slots:
            await db.time_slots.insert_many(time_slots)
        print(f"   ✓ تم تثبيت {len(time_slots)} فترة زمنية لـ {school['name']}")
    
    print("\n" + "=" * 60)
    print("✅ تم تثبيت جميع البيانات المرجعية بنجاح!")
    print("=" * 60)
    
    # ملخص
    print("\n📊 ملخص البيانات:")
    print(f"   • المراحل: {len(STAGES)}")
    print(f"   • الصفوف: {len(GRADES)}")
    print(f"   • المسارات: {len(TRACKS)}")
    print(f"   • المواد: {len(subjects)}")
    print(f"   • رتب المعلمين: {len(TEACHER_RANKS)}")
    print(f"   • القيود الإدارية: {len(ADMIN_CONSTRAINTS)}")
    print(f"   • المدارس المحدّثة: {len(schools)}")


if __name__ == "__main__":
    asyncio.run(seed_all_reference_data())
