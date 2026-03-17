"""
Script to seed all reference data for NASSAQ school management system
This includes:
- Default school settings
- Academic structure (stages, grades, tracks)
- Subjects per stage/track
- Teacher ranks and teaching loads
- Administrative constraints
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
import uuid

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

# ============================================
# 1. DEFAULT SCHOOL SETTINGS
# ============================================

DEFAULT_SCHOOL_SETTINGS = {
    "working_days": {
        "sunday": True,
        "monday": True,
        "tuesday": True,
        "wednesday": True,
        "thursday": True,
        "friday": False,
        "saturday": False
    },
    "working_days_ar": ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس"],
    "working_days_en": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
    "weekend_days_ar": ["الجمعة", "السبت"],
    "weekend_days_en": ["Friday", "Saturday"],
    "periods_per_day": 7,
    "period_duration_minutes": 45,
    "break_duration_minutes": 20,
    "prayer_duration_minutes": 20,
    "school_day_start": "07:00",
    "school_day_end": "13:15",
    "time_slots": [
        {"slot_number": 1, "type": "period", "name_ar": "الحصة الأولى", "name_en": "First Period", "start_time": "07:00", "end_time": "07:45"},
        {"slot_number": 2, "type": "period", "name_ar": "الحصة الثانية", "name_en": "Second Period", "start_time": "07:45", "end_time": "08:30"},
        {"slot_number": 3, "type": "period", "name_ar": "الحصة الثالثة", "name_en": "Third Period", "start_time": "08:30", "end_time": "09:15"},
        {"slot_number": 4, "type": "break", "name_ar": "الاستراحة", "name_en": "Break", "start_time": "09:15", "end_time": "09:35"},
        {"slot_number": 5, "type": "period", "name_ar": "الحصة الرابعة", "name_en": "Fourth Period", "start_time": "09:35", "end_time": "10:20"},
        {"slot_number": 6, "type": "period", "name_ar": "الحصة الخامسة", "name_en": "Fifth Period", "start_time": "10:20", "end_time": "11:05"},
        {"slot_number": 7, "type": "prayer", "name_ar": "فترة الصلاة", "name_en": "Prayer Time", "start_time": "11:05", "end_time": "11:25"},
        {"slot_number": 8, "type": "period", "name_ar": "الحصة السادسة", "name_en": "Sixth Period", "start_time": "11:25", "end_time": "12:10"},
        {"slot_number": 9, "type": "period", "name_ar": "الحصة السابعة", "name_en": "Seventh Period", "start_time": "12:10", "end_time": "12:55"},
    ]
}

# ============================================
# 2. ACADEMIC STRUCTURE - STAGES
# ============================================

ACADEMIC_STAGES = [
    {
        "id": "stage-elementary",
        "name_ar": "المرحلة الابتدائية",
        "name_en": "Elementary Stage",
        "order": 1,
        "is_active": True
    },
    {
        "id": "stage-middle",
        "name_ar": "المرحلة المتوسطة",
        "name_en": "Middle Stage",
        "order": 2,
        "is_active": True
    },
    {
        "id": "stage-high",
        "name_ar": "المرحلة الثانوية",
        "name_en": "High School Stage",
        "order": 3,
        "is_active": True
    }
]

# ============================================
# 3. ACADEMIC STRUCTURE - GRADES
# ============================================

ACADEMIC_GRADES = [
    # Elementary - Lower Grades (1-3)
    {"id": "grade-1", "stage_id": "stage-elementary", "name_ar": "الصف الأول الابتدائي", "name_en": "Grade 1", "order": 1, "grade_level": 1, "is_lower_elementary": True, "is_active": True},
    {"id": "grade-2", "stage_id": "stage-elementary", "name_ar": "الصف الثاني الابتدائي", "name_en": "Grade 2", "order": 2, "grade_level": 2, "is_lower_elementary": True, "is_active": True},
    {"id": "grade-3", "stage_id": "stage-elementary", "name_ar": "الصف الثالث الابتدائي", "name_en": "Grade 3", "order": 3, "grade_level": 3, "is_lower_elementary": True, "is_active": True},
    # Elementary - Upper Grades (4-6)
    {"id": "grade-4", "stage_id": "stage-elementary", "name_ar": "الصف الرابع الابتدائي", "name_en": "Grade 4", "order": 4, "grade_level": 4, "is_lower_elementary": False, "is_active": True},
    {"id": "grade-5", "stage_id": "stage-elementary", "name_ar": "الصف الخامس الابتدائي", "name_en": "Grade 5", "order": 5, "grade_level": 5, "is_lower_elementary": False, "is_active": True},
    {"id": "grade-6", "stage_id": "stage-elementary", "name_ar": "الصف السادس الابتدائي", "name_en": "Grade 6", "order": 6, "grade_level": 6, "is_lower_elementary": False, "is_active": True},
    # Middle School (7-9)
    {"id": "grade-7", "stage_id": "stage-middle", "name_ar": "الصف الأول المتوسط", "name_en": "Grade 7", "order": 7, "grade_level": 7, "is_lower_elementary": False, "is_active": True},
    {"id": "grade-8", "stage_id": "stage-middle", "name_ar": "الصف الثاني المتوسط", "name_en": "Grade 8", "order": 8, "grade_level": 8, "is_lower_elementary": False, "is_active": True},
    {"id": "grade-9", "stage_id": "stage-middle", "name_ar": "الصف الثالث المتوسط", "name_en": "Grade 9", "order": 9, "grade_level": 9, "is_lower_elementary": False, "is_active": True},
    # High School (10-12)
    {"id": "grade-10", "stage_id": "stage-high", "name_ar": "الصف الأول الثانوي", "name_en": "Grade 10", "order": 10, "grade_level": 10, "is_lower_elementary": False, "is_active": True},
    {"id": "grade-11", "stage_id": "stage-high", "name_ar": "الصف الثاني الثانوي", "name_en": "Grade 11", "order": 11, "grade_level": 11, "is_lower_elementary": False, "is_active": True},
    {"id": "grade-12", "stage_id": "stage-high", "name_ar": "الصف الثالث الثانوي", "name_en": "Grade 12", "order": 12, "grade_level": 12, "is_lower_elementary": False, "is_active": True},
]

# ============================================
# 4. EDUCATION TRACKS
# ============================================

EDUCATION_TRACKS = [
    {
        "id": "track-general",
        "name_ar": "التعليم العام",
        "name_en": "General Education",
        "code": "general",
        "is_quran_track": False,
        "is_active": True
    },
    {
        "id": "track-quran",
        "name_ar": "مدارس تحفيظ القرآن الكريم",
        "name_en": "Quran Memorization Schools",
        "code": "quran_memorization",
        "is_quran_track": True,
        "is_active": True
    }
]

# ============================================
# 5. SUBJECTS
# ============================================

# Base subjects for all
BASE_SUBJECTS = [
    {"id": "subj-arabic", "name_ar": "لغتي", "name_en": "Arabic Language", "code": "arabic", "color": "#3B82F6"},
    {"id": "subj-arabic-eternal", "name_ar": "لغتي الخالدة", "name_en": "Arabic Language (Eternal)", "code": "arabic_eternal", "color": "#3B82F6"},
    {"id": "subj-math", "name_ar": "الرياضيات", "name_en": "Mathematics", "code": "math", "color": "#10B981"},
    {"id": "subj-science", "name_ar": "العلوم", "name_en": "Science", "code": "science", "color": "#8B5CF6"},
    {"id": "subj-islamic", "name_ar": "الدراسات الإسلامية", "name_en": "Islamic Studies", "code": "islamic", "color": "#059669"},
    {"id": "subj-quran", "name_ar": "القرآن الكريم", "name_en": "Holy Quran", "code": "quran", "color": "#047857"},
    {"id": "subj-social", "name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies", "code": "social", "color": "#F59E0B"},
    {"id": "subj-english", "name_ar": "اللغة الإنجليزية", "name_en": "English Language", "code": "english", "color": "#EF4444"},
    {"id": "subj-digital", "name_ar": "المهارات الرقمية", "name_en": "Digital Skills", "code": "digital", "color": "#6366F1"},
    {"id": "subj-art", "name_ar": "التربية الفنية", "name_en": "Art Education", "code": "art", "color": "#EC4899"},
    {"id": "subj-pe", "name_ar": "التربية البدنية", "name_en": "Physical Education", "code": "pe", "color": "#14B8A6"},
    {"id": "subj-life", "name_ar": "المهارات الحياتية والأسرية", "name_en": "Life & Family Skills", "code": "life_skills", "color": "#F97316"},
]

# Subject mappings per stage/track
SUBJECT_MAPPINGS = [
    # Elementary Lower (1-3) - General
    {"stage_id": "stage-elementary", "grade_ids": ["grade-1", "grade-2", "grade-3"], "track_id": "track-general", 
     "subjects": ["subj-arabic", "subj-math", "subj-science", "subj-islamic", "subj-english", "subj-digital", "subj-art", "subj-pe", "subj-life"]},
    # Elementary Lower (1-3) - Quran
    {"stage_id": "stage-elementary", "grade_ids": ["grade-1", "grade-2", "grade-3"], "track_id": "track-quran", 
     "subjects": ["subj-arabic", "subj-math", "subj-science", "subj-islamic", "subj-quran", "subj-english", "subj-digital", "subj-art", "subj-pe", "subj-life"]},
    # Elementary Upper (4-6) - General
    {"stage_id": "stage-elementary", "grade_ids": ["grade-4", "grade-5", "grade-6"], "track_id": "track-general", 
     "subjects": ["subj-arabic", "subj-math", "subj-science", "subj-islamic", "subj-social", "subj-english", "subj-digital", "subj-art", "subj-pe", "subj-life"]},
    # Elementary Upper (4-6) - Quran
    {"stage_id": "stage-elementary", "grade_ids": ["grade-4", "grade-5", "grade-6"], "track_id": "track-quran", 
     "subjects": ["subj-arabic", "subj-math", "subj-science", "subj-islamic", "subj-quran", "subj-social", "subj-english", "subj-digital", "subj-art", "subj-pe", "subj-life"]},
    # Middle School - General
    {"stage_id": "stage-middle", "grade_ids": ["grade-7", "grade-8", "grade-9"], "track_id": "track-general", 
     "subjects": ["subj-arabic-eternal", "subj-math", "subj-science", "subj-islamic", "subj-social", "subj-english", "subj-digital", "subj-art", "subj-pe", "subj-life"]},
    # Middle School - Quran
    {"stage_id": "stage-middle", "grade_ids": ["grade-7", "grade-8", "grade-9"], "track_id": "track-quran", 
     "subjects": ["subj-arabic-eternal", "subj-math", "subj-science", "subj-islamic", "subj-quran", "subj-social", "subj-english", "subj-digital", "subj-art", "subj-pe", "subj-life"]},
    # High School - General (using same subjects as middle for now)
    {"stage_id": "stage-high", "grade_ids": ["grade-10", "grade-11", "grade-12"], "track_id": "track-general", 
     "subjects": ["subj-arabic-eternal", "subj-math", "subj-science", "subj-islamic", "subj-social", "subj-english", "subj-digital", "subj-art", "subj-pe", "subj-life"]},
    # High School - Quran
    {"stage_id": "stage-high", "grade_ids": ["grade-10", "grade-11", "grade-12"], "track_id": "track-quran", 
     "subjects": ["subj-arabic-eternal", "subj-math", "subj-science", "subj-islamic", "subj-quran", "subj-social", "subj-english", "subj-digital", "subj-art", "subj-pe", "subj-life"]},
]

# ============================================
# 6. TEACHER RANKS
# ============================================

TEACHER_RANKS = [
    {"id": "rank-teacher", "name_ar": "المعلم", "name_en": "Teacher", "code": "teacher", "weekly_periods": 24, "order": 1, "is_special_education": False},
    {"id": "rank-practitioner", "name_ar": "المعلم الممارس", "name_en": "Practitioner Teacher", "code": "practitioner", "weekly_periods": 24, "order": 2, "is_special_education": False},
    {"id": "rank-advanced", "name_ar": "المعلم المتقدم", "name_en": "Advanced Teacher", "code": "advanced", "weekly_periods": 22, "order": 3, "is_special_education": False},
    {"id": "rank-expert", "name_ar": "المعلم الخبير", "name_en": "Expert Teacher", "code": "expert", "weekly_periods": 18, "order": 4, "is_special_education": False},
    {"id": "rank-sped-practitioner", "name_ar": "معلم تربية خاصة - معلم ممارس", "name_en": "Special Ed - Practitioner", "code": "sped_practitioner", "weekly_periods": 18, "order": 5, "is_special_education": True},
    {"id": "rank-sped-advanced", "name_ar": "معلم تربية خاصة - معلم متقدم", "name_en": "Special Ed - Advanced", "code": "sped_advanced", "weekly_periods": 16, "order": 6, "is_special_education": True},
    {"id": "rank-sped-expert", "name_ar": "معلم تربية خاصة - معلم خبير", "name_en": "Special Ed - Expert", "code": "sped_expert", "weekly_periods": 14, "order": 7, "is_special_education": True},
]

# ============================================
# 7. ADMINISTRATIVE CONSTRAINTS
# ============================================

ADMIN_CONSTRAINTS = [
    {
        "id": "constraint-teacher-conflict",
        "name_ar": "لا يسمح بإسناد المعلم إلى حصتين في نفس الوقت",
        "name_en": "Teacher cannot be assigned to two periods at the same time",
        "code": "no_teacher_conflict",
        "type": "hard",
        "is_active": True
    },
    {
        "id": "constraint-class-conflict",
        "name_ar": "لا يسمح بإسناد الفصل إلى حصتين في نفس الوقت",
        "name_en": "Class cannot be assigned to two periods at the same time",
        "code": "no_class_conflict",
        "type": "hard",
        "is_active": True
    },
    {
        "id": "constraint-consecutive-subjects",
        "name_ar": "لا يسمح بوضع أكثر من حصتين متتاليتين لنفس المادة في اليوم نفسه لنفس الفصل",
        "name_en": "No more than 2 consecutive periods of same subject per day per class",
        "code": "max_consecutive_subject",
        "type": "soft",
        "max_consecutive": 2,
        "is_active": True
    },
    {
        "id": "constraint-pe-first-period",
        "name_ar": "لا يسمح بوضع التربية البدنية في الحصة الأولى",
        "name_en": "Physical Education not allowed in first period",
        "code": "no_pe_first_period",
        "type": "soft",
        "subject_code": "pe",
        "blocked_periods": [1],
        "is_active": True
    },
    {
        "id": "constraint-english-lower-elementary",
        "name_ar": "لا يسمح بوضع اللغة الإنجليزية في الحصة الأولى للصفوف الأولية",
        "name_en": "English not allowed in first period for lower elementary",
        "code": "no_english_first_lower",
        "type": "soft",
        "subject_code": "english",
        "blocked_periods": [1],
        "applies_to_grades": ["grade-1", "grade-2", "grade-3"],
        "is_active": True
    },
    {
        "id": "constraint-islamic-last-period",
        "name_ar": "لا يسمح بوضع الدراسات الإسلامية أو القرآن الكريم في الحصة السابعة",
        "name_en": "Islamic Studies or Quran not allowed in 7th period",
        "code": "no_islamic_last_period",
        "type": "soft",
        "subject_codes": ["islamic", "quran"],
        "blocked_periods": [7],
        "is_active": True
    },
]

# ============================================
# 8. DEFAULT TEACHER AVAILABILITY
# ============================================

DEFAULT_TEACHER_AVAILABILITY = {
    "sunday": [1, 2, 3, 4, 5, 6, 7],
    "monday": [1, 2, 3, 4, 5, 6, 7],
    "tuesday": [1, 2, 3, 4, 5, 6, 7],
    "wednesday": [1, 2, 3, 4, 5, 6, 7],
    "thursday": [1, 2, 3, 4, 5, 6, 7],
    "friday": [],
    "saturday": []
}


async def seed_reference_data():
    """Main function to seed all reference data"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    now = datetime.now(timezone.utc)
    
    print("=" * 60)
    print("Starting NASSAQ Reference Data Seeding")
    print("=" * 60)
    
    # 1. Seed Academic Stages
    print("\n[1/8] Seeding Academic Stages...")
    for stage in ACADEMIC_STAGES:
        stage['created_at'] = now
        stage['updated_at'] = now
        await db.academic_stages.update_one(
            {"id": stage["id"]},
            {"$set": stage},
            upsert=True
        )
    print(f"  ✓ {len(ACADEMIC_STAGES)} stages seeded")
    
    # 2. Seed Academic Grades
    print("\n[2/8] Seeding Academic Grades...")
    for grade in ACADEMIC_GRADES:
        grade['created_at'] = now
        grade['updated_at'] = now
        await db.academic_grades.update_one(
            {"id": grade["id"]},
            {"$set": grade},
            upsert=True
        )
    print(f"  ✓ {len(ACADEMIC_GRADES)} grades seeded")
    
    # 3. Seed Education Tracks
    print("\n[3/8] Seeding Education Tracks...")
    for track in EDUCATION_TRACKS:
        track['created_at'] = now
        track['updated_at'] = now
        await db.education_tracks.update_one(
            {"id": track["id"]},
            {"$set": track},
            upsert=True
        )
    print(f"  ✓ {len(EDUCATION_TRACKS)} tracks seeded")
    
    # 4. Seed Subjects
    print("\n[4/8] Seeding Subjects...")
    for subject in BASE_SUBJECTS:
        subject['created_at'] = now
        subject['updated_at'] = now
        subject['is_active'] = True
        await db.subjects.update_one(
            {"id": subject["id"]},
            {"$set": subject},
            upsert=True
        )
    print(f"  ✓ {len(BASE_SUBJECTS)} subjects seeded")
    
    # 5. Seed Subject Mappings
    print("\n[5/8] Seeding Subject Mappings...")
    for mapping in SUBJECT_MAPPINGS:
        mapping['id'] = f"mapping-{mapping['stage_id']}-{mapping['track_id']}-{'-'.join(mapping['grade_ids'])}"
        mapping['created_at'] = now
        mapping['updated_at'] = now
        await db.subject_mappings.update_one(
            {"id": mapping["id"]},
            {"$set": mapping},
            upsert=True
        )
    print(f"  ✓ {len(SUBJECT_MAPPINGS)} subject mappings seeded")
    
    # 6. Seed Teacher Ranks
    print("\n[6/8] Seeding Teacher Ranks...")
    for rank in TEACHER_RANKS:
        rank['created_at'] = now
        rank['updated_at'] = now
        rank['is_active'] = True
        await db.teacher_ranks.update_one(
            {"id": rank["id"]},
            {"$set": rank},
            upsert=True
        )
    print(f"  ✓ {len(TEACHER_RANKS)} teacher ranks seeded")
    
    # 7. Seed Administrative Constraints
    print("\n[7/8] Seeding Administrative Constraints...")
    for constraint in ADMIN_CONSTRAINTS:
        constraint['created_at'] = now
        constraint['updated_at'] = now
        await db.admin_constraints.update_one(
            {"id": constraint["id"]},
            {"$set": constraint},
            upsert=True
        )
    print(f"  ✓ {len(ADMIN_CONSTRAINTS)} constraints seeded")
    
    # 8. Seed Default School Settings Template
    print("\n[8/8] Seeding Default School Settings Template...")
    settings_template = {
        "id": "default-school-settings",
        "name_ar": "الإعدادات الافتراضية للمدارس",
        "name_en": "Default School Settings",
        **DEFAULT_SCHOOL_SETTINGS,
        "default_teacher_availability": DEFAULT_TEACHER_AVAILABILITY,
        "created_at": now,
        "updated_at": now
    }
    await db.default_settings.update_one(
        {"id": "default-school-settings"},
        {"$set": settings_template},
        upsert=True
    )
    print("  ✓ Default school settings template seeded")
    
    print("\n" + "=" * 60)
    print("Reference Data Seeding Complete!")
    print("=" * 60)
    
    return True


async def apply_settings_to_existing_schools():
    """Apply default settings to all existing schools"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    now = datetime.now(timezone.utc)
    
    print("\n" + "=" * 60)
    print("Applying Default Settings to Existing Schools")
    print("=" * 60)
    
    # Get default settings
    default_settings = await db.default_settings.find_one({"id": "default-school-settings"})
    if not default_settings:
        print("ERROR: Default settings not found!")
        return False
    
    # Get all schools
    schools = await db.schools.find({}).to_list(None)
    
    for school in schools:
        school_id = school.get('id')
        
        # Create school-specific settings
        school_settings = {
            "id": f"settings-{school_id}",
            "school_id": school_id,
            "working_days": default_settings.get("working_days"),
            "working_days_ar": default_settings.get("working_days_ar"),
            "working_days_en": default_settings.get("working_days_en"),
            "weekend_days_ar": default_settings.get("weekend_days_ar"),
            "weekend_days_en": default_settings.get("weekend_days_en"),
            "periods_per_day": default_settings.get("periods_per_day"),
            "period_duration_minutes": default_settings.get("period_duration_minutes"),
            "break_duration_minutes": default_settings.get("break_duration_minutes"),
            "prayer_duration_minutes": default_settings.get("prayer_duration_minutes"),
            "school_day_start": default_settings.get("school_day_start"),
            "school_day_end": default_settings.get("school_day_end"),
            "time_slots": default_settings.get("time_slots"),
            "education_track": "track-general",  # Default to general education
            "created_at": now,
            "updated_at": now
        }
        
        await db.school_settings.update_one(
            {"school_id": school_id},
            {"$set": school_settings},
            upsert=True
        )
        print(f"  ✓ Settings applied to: {school.get('name')}")
    
    print(f"\n  Total: {len(schools)} schools updated")
    return True


if __name__ == "__main__":
    async def main():
        await seed_reference_data()
        await apply_settings_to_existing_schools()
    
    asyncio.run(main())
