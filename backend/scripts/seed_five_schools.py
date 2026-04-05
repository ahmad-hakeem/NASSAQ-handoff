"""
Seed 5 new schools with complete data:
- 25 classes, 25 teachers, 100 students, 1 admin, 1 sub-admin per school
"""
import asyncio
import sys
import os
import uuid
import random
from datetime import datetime, timezone, timedelta
import bcrypt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scripts.seed_db_helper import get_seed_db
PASSWORD = "NassaqAdmin2026!##$$HBJ"

SCHOOLS = [
    {
        "id": "school-noor-ahlia",
        "name_ar": "مدرسة النور الأهلية",
        "name_en": "Al-Noor Private School",
        "type": "primary",
        "city": "الرياض",
        "address": "حي الربوة، شارع الأمير سلطان",
        "phone": "+966114521100",
        "email": "info@noor-ahlia.edu.sa",
        "license": "EDU-2024-002",
        "stages": ["primary"],
        "grades_range": (1, 6),
        "sections_per_grade": [4, 4, 4, 4, 5, 4],
        "admin_email": "admin@noor-ahlia.edu.sa",
        "subadmin_email": "subadmin@noor-ahlia.edu.sa",
        "admin_name": "عبدالله محمد الشمري",
        "subadmin_name": "فاطمة أحمد العتيبي",
    },
    {
        "id": "school-fahad-secondary",
        "name_ar": "ثانوية الملك فهد",
        "name_en": "King Fahad Secondary School",
        "type": "secondary",
        "city": "جدة",
        "address": "حي الحمراء، طريق الملك عبدالعزيز",
        "phone": "+966122987654",
        "email": "info@fahad-secondary.edu.sa",
        "license": "EDU-2024-003",
        "stages": ["secondary"],
        "grades_range": (10, 12),
        "sections_per_grade": [8, 9, 8],
        "admin_email": "admin@fahad-secondary.edu.sa",
        "subadmin_email": "subadmin@fahad-secondary.edu.sa",
        "admin_name": "خالد عبدالرحمن القحطاني",
        "subadmin_name": "نورة سعد الغامدي",
    },
    {
        "id": "school-amal-middle",
        "name_ar": "متوسطة الأمل",
        "name_en": "Al-Amal Middle School",
        "type": "middle",
        "city": "الدمام",
        "address": "حي النزهة، شارع الملك سعود",
        "phone": "+966138876543",
        "email": "info@amal-middle.edu.sa",
        "license": "EDU-2024-004",
        "stages": ["middle"],
        "grades_range": (7, 9),
        "sections_per_grade": [8, 9, 8],
        "admin_email": "admin@amal-middle.edu.sa",
        "subadmin_email": "subadmin@amal-middle.edu.sa",
        "admin_name": "محمد إبراهيم الدوسري",
        "subadmin_name": "هيفاء عبدالله المطيري",
    },
    {
        "id": "school-falah-primary",
        "name_ar": "ابتدائية الفلاح",
        "name_en": "Al-Falah Primary School",
        "type": "primary",
        "city": "مكة المكرمة",
        "address": "حي العزيزية، شارع إبراهيم الخليل",
        "phone": "+966125543210",
        "email": "info@falah-primary.edu.sa",
        "license": "EDU-2024-005",
        "stages": ["primary"],
        "grades_range": (1, 6),
        "sections_per_grade": [4, 4, 4, 5, 4, 4],
        "admin_email": "admin@falah-primary.edu.sa",
        "subadmin_email": "subadmin@falah-primary.edu.sa",
        "admin_name": "سعود عبدالعزيز الزهراني",
        "subadmin_name": "منيرة محمد الحربي",
    },
    {
        "id": "school-tamayoz",
        "name_ar": "مدارس التميز العالمية",
        "name_en": "Al-Tamayoz International Schools",
        "type": "mixed",
        "city": "الرياض",
        "address": "حي الياسمين، طريق الملك خالد",
        "phone": "+966117765432",
        "email": "info@tamayoz.edu.sa",
        "license": "EDU-2024-006",
        "stages": ["primary", "middle", "secondary"],
        "grades_range": (1, 12),
        "sections_per_grade": [2, 2, 2, 2, 2, 2, 2, 2, 3, 2, 2, 2],
        "admin_email": "admin@tamayoz.edu.sa",
        "subadmin_email": "subadmin@tamayoz.edu.sa",
        "admin_name": "ناصر عبدالله العسيري",
        "subadmin_name": "رنا أحمد الشهري",
    },
]

MALE_FIRST_NAMES = ["محمد", "أحمد", "عبدالله", "عبدالرحمن", "خالد", "سعد", "فهد", "عمر", "علي", "إبراهيم",
                     "يوسف", "حمزة", "بندر", "فيصل", "طارق", "وليد", "زياد", "ماجد", "ياسر", "هاني",
                     "نايف", "سلطان", "راشد", "جاسم", "عادل", "كريم", "صالح", "عصام", "تركي", "مشاري"]
FEMALE_FIRST_NAMES = ["فاطمة", "نورة", "منيرة", "ريم", "هيفاء", "أميرة", "سارة", "لولوة", "خلود", "هند",
                       "رهف", "لمياء", "شيخة", "غادة", "عبير", "مريم", "وفاء", "دانة", "أسماء", "صفاء",
                       "نوف", "حصة", "عزة", "بتول", "زينب", "رانيا", "إيمان", "جواهر", "هنوف", "عائشة"]
FAMILY_NAMES = ["الشمري", "العتيبي", "القحطاني", "الغامدي", "الدوسري", "المطيري", "الزهراني", "الحربي",
                 "العسيري", "الشهري", "البقمي", "الرشيدي", "العجمي", "الهاجري", "البلوي", "السبيعي",
                 "الأحمدي", "السلمي", "الثبيتي", "الرويلي", "العمري", "الجهني", "الأنصاري", "الحمدان",
                 "آل سعود", "الفيفي", "الخثعمي", "الأزدي", "البشري", "الشريف"]

SUBJECTS_PRIMARY = [
    {"name_ar": "القرآن الكريم والدراسات الإسلامية", "name_en": "Quran & Islamic Studies", "weekly_hours": 5},
    {"name_ar": "اللغة العربية", "name_en": "Arabic Language", "weekly_hours": 8},
    {"name_ar": "الرياضيات", "name_en": "Mathematics", "weekly_hours": 6},
    {"name_ar": "العلوم", "name_en": "Science", "weekly_hours": 4},
    {"name_ar": "اللغة الإنجليزية", "name_en": "English Language", "weekly_hours": 4},
    {"name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies", "weekly_hours": 3},
    {"name_ar": "التربية الفنية", "name_en": "Art Education", "weekly_hours": 2},
    {"name_ar": "التربية البدنية", "name_en": "Physical Education", "weekly_hours": 3},
    {"name_ar": "المهارات الرقمية", "name_en": "Digital Skills", "weekly_hours": 2},
    {"name_ar": "المهارات الحياتية", "name_en": "Life Skills", "weekly_hours": 1},
]

SUBJECTS_MIDDLE = [
    {"name_ar": "القرآن الكريم والدراسات الإسلامية", "name_en": "Quran & Islamic Studies", "weekly_hours": 5},
    {"name_ar": "اللغة العربية", "name_en": "Arabic Language", "weekly_hours": 5},
    {"name_ar": "الرياضيات", "name_en": "Mathematics", "weekly_hours": 6},
    {"name_ar": "العلوم", "name_en": "Science", "weekly_hours": 4},
    {"name_ar": "اللغة الإنجليزية", "name_en": "English Language", "weekly_hours": 4},
    {"name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies", "weekly_hours": 3},
    {"name_ar": "التربية الفنية", "name_en": "Art Education", "weekly_hours": 2},
    {"name_ar": "التربية البدنية والدفاع عن النفس", "name_en": "PE & Self Defense", "weekly_hours": 2},
    {"name_ar": "المهارات الرقمية", "name_en": "Digital Skills", "weekly_hours": 2},
    {"name_ar": "التفكير الناقد", "name_en": "Critical Thinking", "weekly_hours": 2},
]

SUBJECTS_SECONDARY = [
    {"name_ar": "اللغة العربية والكفايات اللغوية", "name_en": "Arabic & Linguistic Competencies", "weekly_hours": 5},
    {"name_ar": "الرياضيات", "name_en": "Mathematics", "weekly_hours": 5},
    {"name_ar": "اللغة الإنجليزية", "name_en": "English Language", "weekly_hours": 5},
    {"name_ar": "الفيزياء", "name_en": "Physics", "weekly_hours": 4},
    {"name_ar": "الكيمياء", "name_en": "Chemistry", "weekly_hours": 4},
    {"name_ar": "الأحياء", "name_en": "Biology", "weekly_hours": 4},
    {"name_ar": "الدراسات الإسلامية", "name_en": "Islamic Studies", "weekly_hours": 3},
    {"name_ar": "التقنية الرقمية", "name_en": "Digital Technology", "weekly_hours": 3},
    {"name_ar": "التربية الصحية والبدنية", "name_en": "Health & Physical Education", "weekly_hours": 2},
    {"name_ar": "المهارات الحياتية", "name_en": "Life Skills", "weekly_hours": 1},
]

SECTIONS = ["أ", "ب", "ج", "د", "هـ", "و", "ز", "ح", "ط"]

GRADE_NAMES = {
    1: "الصف الأول", 2: "الصف الثاني", 3: "الصف الثالث",
    4: "الصف الرابع", 5: "الصف الخامس", 6: "الصف السادس",
    7: "الصف السابع (الأول متوسط)", 8: "الصف الثامن (الثاني متوسط)", 9: "الصف التاسع (الثالث متوسط)",
    10: "السنة الأولى الثانوية", 11: "السنة الثانية الثانوية", 12: "السنة الثالثة الثانوية",
}

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(12)).decode()

def rand_phone():
    prefixes = ["050", "053", "054", "055", "056", "057", "058", "059"]
    return "+" + "966" + random.choice(prefixes)[1:] + str(random.randint(1000000, 9999999))

def rand_date_born(min_age=6, max_age=18):
    days = random.randint(min_age * 365, max_age * 365)
    return (datetime(2026, 3, 14) - timedelta(days=days)).strftime("%Y-%m-%d")

def rand_date_join():
    days = random.randint(30, 730)
    return (datetime(2026, 3, 14) - timedelta(days=days)).strftime("%Y-%m-%d")

def gen_name(female=False, school_idx=0):
    first = random.choice(FEMALE_FIRST_NAMES if female else MALE_FIRST_NAMES)
    family = random.choice(FAMILY_NAMES)
    return f"{first} {family}"

async def seed():
    async with get_seed_db() as db:
        await _seed_impl(db)

async def _seed_impl(db):
    pw_hash = hash_password(PASSWORD)
    now = datetime.now(timezone.utc).isoformat()
    
    schools_created = []
    total_teachers = 0
    total_students = 0
    total_classes = 0
    total_users = 0
    
    for school in SCHOOLS:
        sid = school["id"]
        print(f"\n=== Creating school: {school['name_ar']} ({sid}) ===")
        
        # Check if already exists
        existing = await db.schools.find_one({"id": sid})
        if existing:
            print(f"  School {sid} already exists, skipping...")
            continue
        
        # Determine school type for subjects
        stype = school["type"]
        if stype == "primary":
            subj_list = SUBJECTS_PRIMARY
            stage_name = "المرحلة الابتدائية"
            stage_id = f"stage-primary-{sid}"
        elif stype == "middle":
            subj_list = SUBJECTS_MIDDLE
            stage_name = "المرحلة المتوسطة"
            stage_id = f"stage-middle-{sid}"
        elif stype == "secondary":
            subj_list = SUBJECTS_SECONDARY
            stage_name = "المرحلة الثانوية"
            stage_id = f"stage-secondary-{sid}"
        else:  # mixed
            subj_list = SUBJECTS_PRIMARY + SUBJECTS_MIDDLE[:3]
            stage_name = "المرحلة المختلطة"
            stage_id = f"stage-mixed-{sid}"
        
        # 1. Create school document
        school_doc = {
            "id": sid,
            "name_ar": school["name_ar"],
            "name_en": school["name_en"],
            "type": stype,
            "city": school["city"],
            "address": school["address"],
            "phone": school["phone"],
            "email": school["email"],
            "license_number": school["license"],
            "academic_year": "2024-2025",
            "status": "active",
            "subscription_plan": "standard",
            "student_count": 0,
            "teacher_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        await db.schools.insert_one(school_doc)
        print(f"  Created school document")
        
        # 2. Create academic stage
        stage_doc = {
            "id": stage_id,
            "school_id": sid,
            "name": stage_name,
            "name_ar": stage_name,
            "order": 1,
            "is_active": True,
            "created_at": now,
        }
        await db.academic_stages.insert_one(stage_doc)
        
        # 3. Create academic year & terms
        ay_id = f"ay-2024-2025-{sid}"
        await db.academic_years.insert_one({
            "id": ay_id,
            "school_id": sid,
            "year": "2024-2025",
            "name_ar": "العام الدراسي 2024-2025",
            "is_current": True,
            "start_date": "2024-09-01",
            "end_date": "2025-06-30",
            "created_at": now,
        })
        await db.academic_terms.insert_one({
            "id": f"term-1-{sid}",
            "school_id": sid,
            "academic_year_id": ay_id,
            "name_ar": "الفصل الدراسي الأول",
            "term_number": 1,
            "start_date": "2024-09-01",
            "end_date": "2025-01-31",
            "is_current": True,
            "created_at": now,
        })
        await db.academic_terms.insert_one({
            "id": f"term-2-{sid}",
            "school_id": sid,
            "academic_year_id": ay_id,
            "name_ar": "الفصل الدراسي الثاني",
            "term_number": 2,
            "start_date": "2025-02-01",
            "end_date": "2025-06-30",
            "is_current": False,
            "created_at": now,
        })
        
        # 4. Create school_settings
        await db.school_settings.insert_one({
            "school_id": sid,
            "academic_year": "2024-2025",
            "current_semester": "first",
            "working_days": {"sunday": True, "monday": True, "tuesday": True, "wednesday": True, "thursday": True, "friday": False, "saturday": False},
            "periods_per_day": 7,
            "period_duration": 45,
            "school_day_start": "07:00",
            "school_day_end": "13:15",
            "break_duration": 15,
            "prayer_time": "12:00",
            "created_at": now,
            "updated_at": now,
        })
        
        # 5. Create school_constraints
        await db.school_constraints.insert_one({
            "id": f"sc-{sid}",
            "school_id": sid,
            "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"],
            "periods_per_day": 7,
            "period_duration_minutes": 45,
            "break_after_period": 4,
            "prayer_after_period": 6,
            "start_time": "07:00",
            "is_active": True,
            "created_at": now,
        })
        
        # 6. Create grades
        g_start, g_end = school["grades_range"]
        sections_config = school["sections_per_grade"]
        grade_ids = {}
        for gi, gnum in enumerate(range(g_start, g_end + 1)):
            gid = f"grade-{gnum}-{sid}"
            stage_map = {"primary": "stage-primary", "middle": "stage-middle", "secondary": "stage-secondary", "mixed": "stage-primary"}
            stage_for_grade = "stage-primary"
            if gnum <= 6:
                stage_for_grade = f"stage-primary-{sid}" if stype in ["primary", "mixed"] else stage_id
            elif gnum <= 9:
                stage_for_grade = f"stage-middle-{sid}" if stype in ["middle", "mixed"] else stage_id
            else:
                stage_for_grade = f"stage-secondary-{sid}" if stype in ["secondary", "mixed"] else stage_id
            
            await db.grades.insert_one({
                "id": gid,
                "school_id": sid,
                "stage_id": stage_id,
                "name": GRADE_NAMES.get(gnum, f"الصف {gnum}"),
                "name_ar": GRADE_NAMES.get(gnum, f"الصف {gnum}"),
                "grade_number": gnum,
                "order": gi + 1,
                "is_active": True,
                "created_at": now,
            })
            grade_ids[gnum] = gid
        
        # 7. Create subjects
        subject_ids = []
        for si_idx, subj in enumerate(subj_list):
            sub_id = f"sub-{sid}-{si_idx+1}"
            await db.subjects.insert_one({
                "id": sub_id,
                "school_id": sid,
                "name_ar": subj["name_ar"],
                "name_en": subj["name_en"],
                "weekly_hours": subj["weekly_hours"],
                "is_active": True,
                "created_at": now,
            })
            subject_ids.append(sub_id)
        
        # 8. Create 25 classes
        classes_created = []
        class_counter = 0
        for gi, gnum in enumerate(range(g_start, g_end + 1)):
            num_sections = sections_config[gi] if gi < len(sections_config) else 2
            gid = grade_ids[gnum]
            for sec_idx in range(num_sections):
                if class_counter >= 25:
                    break
                section_letter = SECTIONS[sec_idx]
                class_id = f"cls-{sid}-g{gnum}-{section_letter}"
                class_doc = {
                    "id": class_id,
                    "school_id": sid,
                    "name": f"{GRADE_NAMES.get(gnum, f'الصف {gnum}')} ({section_letter})",
                    "name_ar": f"{GRADE_NAMES.get(gnum, f'الصف {gnum}')} ({section_letter})",
                    "grade_level": str(gnum),
                    "grade_id": gid,
                    "section": section_letter,
                    "student_count": 0,
                    "is_active": True,
                    "created_at": now,
                }
                await db.classes.insert_one(class_doc)
                classes_created.append(class_id)
                class_counter += 1
                
                # Link subjects to class
                for sub_id in subject_ids:
                    await db.class_subjects.insert_one({
                        "id": str(uuid.uuid4()),
                        "school_id": sid,
                        "class_id": class_id,
                        "subject_id": sub_id,
                        "created_at": now,
                    })
            if class_counter >= 25:
                break
        
        total_classes += len(classes_created)
        print(f"  Created {len(classes_created)} classes")
        
        # 9. Create 25 teachers
        teacher_ids = []
        teacher_subject_map = {}
        for t_idx in range(25):
            t_name = gen_name(female=(t_idx >= 15), school_idx=0)
            t_email = f"teacher{t_idx+1}@{school['email'].split('@')[1]}"
            tid = f"tch-{sid}-{t_idx+1}"
            primary_sub_idx = t_idx % len(subject_ids)
            primary_sub = subject_ids[primary_sub_idx]
            
            teacher_doc = {
                "id": tid,
                "school_id": sid,
                "name": t_name,
                "name_ar": t_name,
                "full_name": t_name,
                "full_name_ar": t_name,
                "email": t_email,
                "phone": rand_phone(),
                "specialization": primary_sub,
                "primary_subject_id": primary_sub,
                "subject_ids": [primary_sub],
                "max_periods_per_week": 24,
                "max_periods_per_day": 6,
                "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"],
                "rank": random.choice(["معلم", "معلم ممارس", "معلم متقدم"]),
                "qualification": random.choice(["بكالوريوس", "ماجستير"]),
                "hire_date": rand_date_join(),
                "is_active": True,
                "created_at": now,
            }
            await db.teachers.insert_one(teacher_doc)
            teacher_ids.append(tid)
            teacher_subject_map[tid] = primary_sub
            
            # Create teacher user
            teacher_user = {
                "id": str(uuid.uuid4()),
                "email": t_email,
                "role": "teacher",
                "full_name": t_name,
                "school_id": sid,
                "teacher_id": tid,
                "is_active": True,
                "must_change_password": False,
                "password_hash": pw_hash,
                "created_at": now,
                "updated_at": now,
                "tenant_id": sid,
            }
            await db.users.insert_one(teacher_user)
            
            # Create teacher_subjects
            await db.teacher_subjects.insert_one({
                "id": str(uuid.uuid4()),
                "school_id": sid,
                "teacher_id": tid,
                "subject_id": primary_sub,
                "created_at": now,
            })
        
        total_teachers += 25
        print(f"  Created 25 teachers")
        
        # 10. Create teacher_assignments (link teachers to classes via subjects)
        for t_idx, tid in enumerate(teacher_ids):
            sub_id = teacher_subject_map[tid]
            # Each teacher handles 1-3 classes
            num_classes = random.randint(1, 3)
            assigned_classes = random.sample(classes_created, min(num_classes, len(classes_created)))
            for cls_id in assigned_classes:
                await db.teacher_assignments.insert_one({
                    "id": str(uuid.uuid4()),
                    "school_id": sid,
                    "teacher_id": tid,
                    "class_id": cls_id,
                    "subject_id": sub_id,
                    "periods_per_week": subj_list[t_idx % len(subj_list)]["weekly_hours"],
                    "is_active": True,
                    "created_at": now,
                })
        
        # 11. Create grade_subjects
        for gnum, gid in grade_ids.items():
            for sub_id in subject_ids:
                await db.grade_subjects.insert_one({
                    "id": str(uuid.uuid4()),
                    "school_id": sid,
                    "grade_id": gid,
                    "subject_id": sub_id,
                    "weekly_hours": random.randint(2, 6),
                    "is_active": True,
                    "created_at": now,
                })
        
        # 12. Create 100 students (as users + linked to classes)
        student_ids = []
        students_per_class = {}
        for s_idx in range(100):
            # Distribute across classes
            cls_id = classes_created[s_idx % len(classes_created)]
            is_female = random.random() < 0.45
            s_name = gen_name(female=is_female)
            s_email = f"student{s_idx+1}@{school['email'].split('@')[1]}"
            student_id = str(uuid.uuid4())
            
            student_user = {
                "id": student_id,
                "email": s_email,
                "role": "student",
                "full_name": s_name,
                "school_id": sid,
                "class_id": cls_id,
                "grade_id": None,
                "date_of_birth": rand_date_born(6, 18),
                "enrollment_date": rand_date_join(),
                "phone": rand_phone(),
                "national_id": str(random.randint(1000000000, 2000000000)),
                "is_active": True,
                "must_change_password": False,
                "password_hash": pw_hash,
                "created_at": now,
                "updated_at": now,
                "tenant_id": sid,
            }
            await db.users.insert_one(student_user)
            student_ids.append(student_id)
            students_per_class[cls_id] = students_per_class.get(cls_id, 0) + 1
        
        # Update class student_counts
        for cls_id, count in students_per_class.items():
            await db.classes.update_one({"id": cls_id}, {"$set": {"student_count": count}})
        
        total_students += 100
        print(f"  Created 100 students")
        
        # 13. Create 1 parent per 5 students (20 parents)
        for p_idx in range(20):
            is_female = p_idx % 3 == 0
            p_name = gen_name(female=is_female)
            p_email = f"parent{p_idx+1}@{school['email'].split('@')[1]}"
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": p_email,
                "role": "parent",
                "full_name": p_name,
                "school_id": sid,
                "is_active": True,
                "must_change_password": False,
                "password_hash": pw_hash,
                "created_at": now,
                "updated_at": now,
                "tenant_id": sid,
            })
        
        # 14. Create school admin users
        admin_id = str(uuid.uuid4())
        await db.users.insert_one({
            "id": admin_id,
            "email": school["admin_email"],
            "role": "school_admin",
            "full_name": school["admin_name"],
            "school_id": sid,
            "is_active": True,
            "must_change_password": False,
            "password_hash": pw_hash,
            "created_at": now,
            "updated_at": now,
            "tenant_id": sid,
        })
        subadmin_id = str(uuid.uuid4())
        await db.users.insert_one({
            "id": subadmin_id,
            "email": school["subadmin_email"],
            "role": "school_sub_admin",
            "full_name": school["subadmin_name"],
            "school_id": sid,
            "is_active": True,
            "must_change_password": False,
            "password_hash": pw_hash,
            "created_at": now,
            "updated_at": now,
            "tenant_id": sid,
        })
        total_users += 2
        print(f"  Created admin ({school['admin_email']}) + sub-admin ({school['subadmin_email']})")
        
        # 15. Update school student/teacher counts
        await db.schools.update_one(
            {"id": sid},
            {"$set": {"student_count": 100, "teacher_count": 25, "class_count": len(classes_created)}}
        )
        
        # 16. Create some attendance records (last 30 days, sample)
        for day_offset in range(30):
            date = (datetime(2026, 3, 14) - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            weekday = (datetime(2026, 3, 14) - timedelta(days=day_offset)).weekday()
            if weekday >= 5:  # Skip Friday/Saturday (Islamic weekend)
                continue
            for s_id in random.sample(student_ids, min(50, len(student_ids))):
                is_absent = random.random() < 0.08
                await db.get_collection("attendance").insert_one({
                    "id": str(uuid.uuid4()),
                    "school_id": sid,
                    "student_id": s_id,
                    "date": date,
                    "status": "absent" if is_absent else "present",
                    "created_at": now,
                })
        
        # 17. Create some notifications
        notification_types = [
            {"type": "attendance", "message_ar": "تسجيل حضور ناجح لليوم الدراسي"},
            {"type": "assignment", "message_ar": "تم تسليم واجب جديد"},
            {"type": "grade", "message_ar": "تم رصد درجة جديدة"},
            {"type": "schedule", "message_ar": "تغيير في الجدول الدراسي"},
            {"type": "alert", "message_ar": "تنبيه: غياب متكرر لطالب"},
        ]
        for n_idx in range(15):
            notif = random.choice(notification_types)
            await db.get_collection("notifications").insert_one({
                "id": str(uuid.uuid4()),
                "school_id": sid,
                "type": notif["type"],
                "message_ar": notif["message_ar"],
                "is_read": random.random() < 0.6,
                "created_at": (datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 168))).isoformat(),
            })
        
        # 18. Create time_slots
        period_starts = ["07:00", "07:45", "08:30", "09:15", "10:15", "11:00", "11:45"]
        period_ends   = ["07:45", "08:30", "09:15", "10:00", "11:00", "11:45", "12:30"]
        for ts_idx in range(7):
            await db.time_slots.insert_one({
                "id": f"ts-{sid}-{ts_idx+1}",
                "school_id": sid,
                "period_number": ts_idx + 1,
                "start_time": period_starts[ts_idx],
                "end_time": period_ends[ts_idx],
                "is_break": ts_idx == 3,
                "is_prayer": ts_idx == 6,
                "created_at": now,
            })
        
        schools_created.append(school["name_ar"])
        print(f"  Done: {school['name_ar']}")
    
    print(f"\n========= SEED COMPLETE =========")
    print(f"Schools created: {len(schools_created)}")
    print(f"Total teachers: {total_teachers}")
    print(f"Total students: {total_students}")
    print(f"Total classes: {total_classes}")
    print(f"School admins+sub-admins: {total_users}")

if __name__ == "__main__":
    asyncio.run(seed())
