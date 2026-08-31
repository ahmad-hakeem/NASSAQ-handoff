"""
NASSAQ Platform — Comprehensive Test Data Seed
================================================
Two fully isolated Arabic-named school tenants with all roles,
academic structure, timetables, and 4 weeks of operational data.

Usage:
    cd backend
    python scripts/seed_test_data.py

Safe to re-run: checks for existing data before inserting.
"""
import asyncio
import os
import sys
import uuid
import random
from datetime import datetime, timezone, timedelta, date

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import async_session_factory
from engines.sql_utils import gd_find_one, gd_insert, gd_insert_many, gd_count
from dependencies import hash_password

# ─── Constants ────────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000/api"
DEFAULT_PASSWORD = "Test@1234"
ACADEMIC_YEAR = "2026-2027"

SCHOOLS = [
    {
        "code": "FARABI-001",
        "name": "مدرسة الفارابي للتعليم الأساسي",
        "name_en": "Al-Farabi School",
        "city": "الرياض",
        "region": "الرياض",
        "school_type": "public",
        "student_prefix": "FAR",
        "email_domain": "faarabi.edu",
        "status": "active",
    },
    {
        "code": "IBNSINA-001",
        "name": "أكاديمية ابن سينا الدولية",
        "name_en": "Ibn Sina International Academy",
        "city": "جدة",
        "region": "مكة المكرمة",
        "school_type": "private",
        "student_prefix": "IBN",
        "email_domain": "ibnsina.edu",
        "status": "active",
    },
]

MALE_FIRST = [
    "أحمد", "محمد", "خالد", "عبدالله", "سعد", "عمر", "يوسف", "إبراهيم",
    "علي", "حسن", "فهد", "ناصر", "سلطان", "طارق", "وليد", "ماجد",
    "رائد", "بلال", "زياد", "أنس",
]

FEMALE_FIRST = [
    "فاطمة", "نورة", "سارة", "ريم", "هند", "لطيفة", "منيرة", "أميرة",
    "شيماء", "دانة", "رهف", "لمى", "غادة", "أسماء", "هيا", "ليلى",
    "مها", "سلمى", "وفاء", "إيمان",
]

FAMILY_NAMES = [
    "الرشيدي", "العتيبي", "القحطاني", "الشمري", "الزهراني", "الدوسري",
    "الحربي", "العنزي", "المطيري", "الغامدي", "السبيعي", "البقمي",
    "الرويلي", "العجمي", "الصاعدي", "المالكي", "الجهني", "الوادعي",
    "التميمي", "الأحمدي",
]

# (name_ar, name_en, code, category, default_periods_per_week)
SUBJECTS_DATA = [
    ("اللغة العربية",      "Arabic Language",    "AR",   "core",      6),
    ("اللغة الإنجليزية",  "English Language",   "EN",   "core",      5),
    ("الرياضيات",          "Mathematics",        "MATH", "core",      6),
    ("العلوم",             "Science",            "SCI",  "core",      4),
    ("التربية الإسلامية",  "Islamic Studies",    "IS",   "core",      4),
    ("الدراسات الاجتماعية","Social Studies",     "SS",   "core",      3),
    ("التربية البدنية",    "Physical Education", "PE",   "elective",  2),
    ("التربية الفنية",     "Art",                "ART",  "elective",  2),
    ("الحاسوب",            "Computer Science",   "CS",   "elective",  2),
    ("التاريخ",            "History",            "HIS",  "core",      2),
    ("الجغرافيا",          "Geography",          "GEO",  "core",      2),
    ("الكيمياء",           "Chemistry",          "CHEM", "secondary", 3),
    ("الفيزياء",           "Physics",            "PHY",  "secondary", 3),
    ("الأحياء",            "Biology",            "BIO",  "secondary", 3),
]

WORK_DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]

# (slot_number, name_ar, start, end, is_break)
TIME_SLOTS_DATA = [
    (1, "الحصة الأولى",  "07:30", "08:15", False),
    (2, "الحصة الثانية", "08:15", "09:00", False),
    (3, "الحصة الثالثة", "09:00", "09:45", False),
    (4, "الحصة الرابعة", "09:45", "10:30", False),
    (5, "الاستراحة",     "10:30", "10:50", True),
    (6, "الحصة الخامسة", "10:50", "11:35", False),
    (7, "الحصة السادسة", "11:35", "12:20", False),
    (8, "الحصة السابعة", "12:20", "13:05", False),
]

PRODUCT_ISSUES = [
    {"title": "بطء في تحميل جدول الحصص",            "issue_type": "performance_issue",       "page": "الجداول والمواعيد",     "priority": "high",     "status": "open"},
    {"title": "خطأ عند تسجيل الغياب الجماعي",        "issue_type": "bug",                     "page": "الحضور والغياب",        "priority": "critical", "status": "open"},
    {"title": "لا تظهر درجات الطلاب في بوابة الأهل", "issue_type": "bug",                     "page": "بوابة ولي الأمر",       "priority": "high",     "status": "in_progress"},
    {"title": "إضافة تقرير أسبوعي للحضور",           "issue_type": "feature_request",         "page": "التقارير",             "priority": "medium",   "status": "open"},
    {"title": "خطأ في حساب نسبة الحضور",             "issue_type": "bug",                     "page": "الحضور والغياب",        "priority": "high",     "status": "in_progress"},
    {"title": "تحسين واجهة قائمة الطلاب",            "issue_type": "improvement_suggestion",  "page": "إدارة المستخدمين",     "priority": "low",      "status": "open"},
    {"title": "إشعارات الأهل لا تصل أحياناً",        "issue_type": "bug",                     "page": "التواصل",              "priority": "medium",   "status": "in_progress"},
    {"title": "إضافة تصدير PDF لجدول الحصص",         "issue_type": "feature_request",         "page": "الجداول والمواعيد",     "priority": "medium",   "status": "resolved"},
    {"title": "خطأ في صلاحيات المعلم البديل",        "issue_type": "permission_issue",        "page": "إدارة المستخدمين",     "priority": "high",     "status": "resolved"},
    {"title": "تحسين سرعة البحث في سجلات الطلاب",   "issue_type": "performance_issue",       "page": "إدارة المستخدمين",     "priority": "low",      "status": "resolved"},
]

POSITIVE_BEHAVIOURS = [
    ("positive", "academic", 10, "تميّز في الأداء الأكاديمي وحصل على أعلى درجة في الاختبار"),
    ("positive", "social",   5,  "أظهر روح التعاون مع زملائه خلال العمل الجماعي"),
    ("positive", "conduct",  5,  "التزام مثالي بقواعد المدرسة طوال الأسبوع"),
    ("positive", "academic", 10, "قدّم مشروعاً استثنائياً في مادة العلوم"),
    ("positive", "social",   5,  "ساعد زميله في فهم المادة الدراسية"),
]
NEGATIVE_BEHAVIOURS = [
    ("negative", "conduct",  -5, "التأخر عن الحصة الأولى بدون عذر"),
    ("negative", "academic", -5, "إهمال الواجب المنزلي لأسبوع كامل"),
    ("negative", "social",   -3, "إزعاج الزملاء خلال وقت الدراسة"),
    ("negative", "conduct",  -5, "استخدام الهاتف خلال وقت الدراسة"),
]

GRADE_NAMES = {
    1:  "الصف الأول",
    2:  "الصف الثاني",
    3:  "الصف الثالث",
    4:  "الصف الرابع",
    5:  "الصف الخامس",
    6:  "الصف السادس",
    7:  "الصف السابع",
    8:  "الصف الثامن",
    9:  "الصف التاسع",
    10: "الصف العاشر",
    11: "الصف الحادي عشر",
    12: "الصف الثاني عشر",
}

TEACHER_SPECIALIZATIONS = [
    "اللغة العربية", "اللغة العربية",
    "اللغة الإنجليزية", "اللغة الإنجليزية",
    "الرياضيات", "الرياضيات",
    "العلوم", "العلوم",
    "التربية الإسلامية", "الدراسات الاجتماعية",
    "التربية البدنية", "التربية الفنية",
    "الحاسوب", "التاريخ", "الجغرافيا",
    "الكيمياء", "الفيزياء", "الأحياء",
]

# Pre-compute bcrypt hash once — reused for all accounts (same password)
print("Pre-computing password hash...", flush=True)
_HASHED_DEFAULT = hash_password(DEFAULT_PASSWORD)
print("Done.\n", flush=True)


# ─── Transliteration ──────────────────────────────────────────────────────────

_TRANS = {
    "أ": "a", "ا": "a", "إ": "i", "آ": "a", "ب": "b", "ت": "t", "ث": "th",
    "ج": "j", "ح": "h", "خ": "kh", "د": "d", "ذ": "dh", "ر": "r", "ز": "z",
    "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "a",
    "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n",
    "ه": "h", "و": "w", "ي": "y", "ى": "a", "ة": "a", "ء": "", "ئ": "y",
    "ؤ": "w", " ": "_",
}


def _uid() -> str:
    return str(uuid.uuid4())


def _transliterate(text: str) -> str:
    return "".join(_TRANS.get(ch, ch) for ch in text)


def _arabic_name(gender: str) -> tuple:
    """Return (full_name_ar, email_slug) for a random Arabic person."""
    first = random.choice(MALE_FIRST if gender == "male" else FEMALE_FIRST)
    family = random.choice(FAMILY_NAMES)
    full_ar = f"{first} {family}"
    slug = f"{_transliterate(first)}.{_transliterate(family)}".lower().replace("_", "")
    return full_ar, slug


# ─── DB Session Helper ────────────────────────────────────────────────────────

class SeedDB:
    """Thin async context manager wrapping SQLAlchemy async session."""

    def __init__(self):
        self._session = None
        self.session = None

    async def __aenter__(self):
        self._session = async_session_factory()
        self.session = await self._session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            await self.session.commit()
        await self._session.__aexit__(exc_type, exc_val, exc_tb)

    async def find_one(self, collection: str, filters: dict):
        return await gd_find_one(self.session, collection, filters)

    async def insert(self, collection: str, data: dict) -> dict:
        """Insert a record and return the full data dict (gd_insert only returns the ID)."""
        inserted_id = await gd_insert(self.session, collection, data)
        return {**data, "id": inserted_id}

    async def count(self, collection: str, filters: dict) -> int:
        return await gd_count(self.session, collection, filters)

    async def upsert(self, collection: str, lookup: dict, data: dict) -> dict:
        """Return existing record if found, otherwise insert and return the full data dict."""
        existing = await self.find_one(collection, lookup)
        if existing:
            return existing
        merged = {}
        merged.update(lookup)
        merged.update(data)
        return await self.insert(collection, merged)


# ─── Step 1: Schools ──────────────────────────────────────────────────────────

async def seed_schools(db: SeedDB) -> dict:
    """Create both school tenant records. Returns {code: school_record}."""
    results = {}
    for s in SCHOOLS:
        record = await db.upsert(
            "schools",
            {"code": s["code"]},
            {
                "id": _uid(),
                "name": s["name"],
                "name_en": s["name_en"],
                "city": s["city"],
                "region": s["region"],
                "country": "SA",
                "school_type": s["school_type"],
                "status": "active",
                "language": "ar",
                "calendar_system": "hijri_gregorian",
                "student_capacity": 300,
                "tenant_type": "production",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        results[s["code"]] = {**record, **s}
        print(f"  ✓ School: {s['name_en']} ({s['code']})")
    return results


# ─── Step 2: Platform Admin ───────────────────────────────────────────────────

async def seed_platform_admin(db: SeedDB) -> dict:
    user = await db.upsert(
        "users",
        {"email": "admin@nassaq.com"},
        {
            "id": _uid(),
            "full_name": "مدير المنصة",
            "full_name_en": "Platform Administrator",
            "password_hash": _HASHED_DEFAULT,
            "role": "platform_admin",
            "linked_roles": ["platform_admin"],
            "status": "active",
            "is_active": True,
            "must_change_password": False,
            "preferred_language": "ar",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    )
    print(f"  ✓ Platform Admin: admin@nassaq.com")
    return user


# ─── Step 3: School Admins & Teachers ────────────────────────────────────────

async def seed_school_users(db: SeedDB, school: dict) -> dict:
    """
    Creates 2 school admins and 18 teachers for a school.
    Returns {"admins": [...user_records], "teachers": [{"user":..,"teacher":..,"email":..}]}
    """
    domain = school["email_domain"]
    school_id = school["id"]
    result = {"admins": [], "teachers": []}

    # 2 school admins
    admin_specs = [
        ("mudeer", "مدير المدرسة", "School Director"),
        ("naeb",   "نائب المدير",  "Deputy Director"),
    ]
    for slug, name_ar, name_en in admin_specs:
        email = f"{slug}@{domain}"
        user = await db.upsert(
            "users",
            {"email": email},
            {
                "id": _uid(),
                "full_name": name_ar,
                "full_name_en": name_en,
                "password_hash": _HASHED_DEFAULT,
                "role": "school_admin",
                "linked_roles": ["school_admin"],
                "tenant_id": school_id,
                "primary_tenant_id": school_id,
                "status": "active",
                "is_active": True,
                "must_change_password": False,
                "preferred_language": "ar",
                "email_verified": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        result["admins"].append(user)

    # 18 teachers
    used_emails: set = set()
    for i, spec in enumerate(TEACHER_SPECIALIZATIONS):
        gender = "female" if i % 3 == 0 else "male"
        name_ar, slug = _arabic_name(gender)
        email = f"{slug}@{domain}"
        counter = 2
        while email in used_emails:
            email = f"{slug}{counter}@{domain}"
            counter += 1
        used_emails.add(email)

        user = await db.upsert(
            "users",
            {"email": email},
            {
                "id": _uid(),
                "full_name": name_ar,
                "password_hash": _HASHED_DEFAULT,
                "role": "teacher",
                "linked_roles": ["teacher"],
                "tenant_id": school_id,
                "primary_tenant_id": school_id,
                "status": "active",
                "is_active": True,
                "must_change_password": False,
                "preferred_language": "ar",
                "email_verified": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )

        national_id = f"1{random.randint(10000000, 99999999)}"
        teacher = await db.upsert(
            "teachers",
            {"user_id": user["id"], "school_id": school_id},
            {
                "id": _uid(),
                "full_name": name_ar,
                "email": email,
                "school_id": school_id,
                "specialization": spec,
                "subject": spec,
                "rank": "معلم أول",
                "qualification": "بكالوريوس تربية",
                "years_of_experience": random.randint(3, 20),
                "gender": gender,
                "national_id": national_id,
                "weekly_periods": 24,
                "max_daily_periods": 6,
                "user_id": user["id"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        result["teachers"].append({"user": user, "teacher": teacher, "email": email})

    print(f"  ✓ {len(result['admins'])} admins, {len(result['teachers'])} teachers — {school['name_en']}")
    return result


# ─── Step 4: Classes & Subjects ───────────────────────────────────────────────

async def seed_classes_and_subjects(db: SeedDB, school: dict, teachers: list) -> dict:
    """
    Creates 18 classes (grades 1-6 have 2 sections, 7-12 have 1) and 14 subjects.
    Returns {"classes": [...], "subjects": [...]}
    """
    school_id = school["id"]
    classes = []
    subjects = []
    teacher_objs = [t["teacher"] for t in teachers]
    teacher_idx = 0

    for grade in range(1, 13):
        sections = ["أ", "ب"] if grade <= 6 else ["أ"]
        for section in sections:
            name = f"{GRADE_NAMES[grade]} {section}"
            homeroom = teacher_objs[teacher_idx % len(teacher_objs)]
            teacher_idx += 1

            cls = await db.upsert(
                "classes",
                {"name": name, "school_id": school_id},
                {
                    "id": _uid(),
                    "name": name,
                    "name_en": f"Grade {grade} {section}",
                    "school_id": school_id,
                    "grade_level": str(grade),
                    "section": section,
                    "capacity": 30,
                    "current_students": 0,
                    "homeroom_teacher_id": homeroom["id"],
                    "homeroom_teacher_name": homeroom["full_name"],
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            classes.append({**cls, "grade_number": grade})

    for name_ar, name_en, code, category, periods in SUBJECTS_DATA:
        subj = await db.upsert(
            "subjects",
            {"code": code, "school_id": school_id},
            {
                "id": _uid(),
                "name": name_ar,
                "name_ar": name_ar,
                "name_en": name_en,
                "code": code,
                "school_id": school_id,
                "category": category,
                "default_periods_per_week": periods,
                "is_active": True,
                "is_global": False,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        subjects.append(subj)

    print(f"  ✓ {len(classes)} classes, {len(subjects)} subjects — {school['name_en']}")
    return {"classes": classes, "subjects": subjects}


# ─── Step 5: Students & Parents ───────────────────────────────────────────────

async def seed_students_and_parents(db: SeedDB, school: dict, classes: list) -> dict:
    """
    Creates ~14 students per class, each with a linked parent + parent user.
    Returns {"students": [...], "parents": [...]}
    """
    school_id = school["id"]
    prefix = school["student_prefix"]
    domain = school["email_domain"]
    all_students = []
    all_parents = []
    student_counter = 1
    used_parent_emails: set = set()

    for cls in classes:
        for i in range(14):
            gender = "male" if i % 2 == 0 else "female"
            name_ar, _ = _arabic_name(gender)
            student_number = f"{prefix}-{student_counter:03d}"
            student_counter += 1

            # Generate unique parent email
            parent_name_ar, parent_slug = _arabic_name("male")
            parent_email = f"{parent_slug}.w{student_counter}@gmail.com"
            while parent_email in used_parent_emails:
                parent_email = f"{parent_slug}.w{student_counter}x@gmail.com"
            used_parent_emails.add(parent_email)
            parent_phone = f"05{random.randint(10000000, 99999999)}"

            parent = await db.upsert(
                "parents",
                {"email": parent_email},
                {
                    "id": _uid(),
                    "full_name": parent_name_ar,
                    "email": parent_email,
                    "phone": parent_phone,
                    "national_id": f"2{random.randint(10000000, 99999999)}",
                    "student_ids": [],
                    "school_id": school_id,
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
            )

            parent_user = await db.upsert(
                "users",
                {"email": parent_email},
                {
                    "id": _uid(),
                    "full_name": parent_name_ar,
                    "password_hash": _HASHED_DEFAULT,
                    "role": "parent",
                    "linked_roles": ["parent"],
                    "tenant_id": school_id,
                    "primary_tenant_id": school_id,
                    "status": "active",
                    "is_active": True,
                    "must_change_password": False,
                    "preferred_language": "ar",
                    "email_verified": True,
                    "parent_id": parent["id"],
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
            )

            student = await db.upsert(
                "students",
                {"student_number": student_number, "school_id": school_id},
                {
                    "id": _uid(),
                    "full_name": name_ar,
                    "school_id": school_id,
                    "class_id": cls["id"],
                    "student_number": student_number,
                    "grade": cls["grade_level"],
                    "gender": gender,
                    "parent_id": parent["id"],
                    "parent_name": parent_name_ar,
                    "parent_email": parent_email,
                    "parent_phone": parent_phone,
                    "national_id": f"3{random.randint(10000000, 99999999)}",
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            all_students.append(student)
            all_parents.append({"parent": parent, "user": parent_user, "email": parent_email})

    print(f"  ✓ {len(all_students)} students, {len(all_parents)} parents — {school['name_en']}")
    return {"students": all_students, "parents": all_parents}


# ─── Step 6: Time Slots ───────────────────────────────────────────────────────

async def seed_time_slots(db: SeedDB, school: dict) -> list:
    """Create 8 time slots (7 periods + 1 break) for a school."""
    school_id = school["id"]
    slots = []
    for number, name_ar, start, end, is_break in TIME_SLOTS_DATA:
        slot = await db.upsert(
            "time_slots",
            {"school_id": school_id, "slot_number": number},
            {
                "id": _uid(),
                "school_id": school_id,
                "name": name_ar,
                "name_en": f"Period {number}" if not is_break else "Break",
                "start_time": start,
                "end_time": end,
                "slot_number": number,
                "duration_minutes": 45 if not is_break else 20,
                "is_break": is_break,
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
            },
        )
        slots.append(slot)
    print(f"  ✓ {len(slots)} time slots — {school['name_en']}")
    return slots


# ─── Step 7: Teacher Assignments ─────────────────────────────────────────────

async def seed_teacher_assignments(
    db: SeedDB, school: dict, teachers: list, classes: list, subjects: list
) -> list:
    """Assign each teacher to classes matching their specialization."""
    school_id = school["id"]
    subj_by_name = {s["name_ar"]: s for s in subjects}
    assignments = []

    for i, teacher_info in enumerate(teachers):
        teacher = teacher_info["teacher"]
        spec_name = TEACHER_SPECIALIZATIONS[i % len(TEACHER_SPECIALIZATIONS)]
        subject = subj_by_name.get(spec_name)
        if not subject:
            continue

        is_secondary = subject["category"] == "secondary"

        for cls in classes:
            grade_num = int(cls.get("grade_level", cls.get("grade_number", 1)))
            if is_secondary and grade_num < 10:
                continue

            asn = await db.upsert(
                "teacher_assignments",
                {
                    "teacher_id": teacher["id"],
                    "class_id": cls["id"],
                    "subject_id": subject["id"],
                    "school_id": school_id,
                },
                {
                    "id": _uid(),
                    "school_id": school_id,
                    "teacher_id": teacher["id"],
                    "class_id": cls["id"],
                    "subject_id": subject["id"],
                    "weekly_sessions": subject["default_periods_per_week"],
                    "periods_per_week": subject["default_periods_per_week"],
                    "academic_year": ACADEMIC_YEAR,
                    "semester": 1,
                    "priority": "primary",
                    "teacher_name": teacher["full_name"],
                    "class_name": cls["name"],
                    "subject_name": subject["name_ar"],
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            assignments.append(asn)

    print(f"  ✓ {len(assignments)} teacher assignments — {school['name_en']}")
    return assignments


# ─── Step 8: Timetable & Schedule Sessions ────────────────────────────────────

async def seed_timetable(
    db: SeedDB, school: dict, classes: list, assignments: list, time_slots: list
) -> dict:
    """
    Creates one Timetable header and ScheduleSession for each
    class × day × non-break time_slot.
    Returns {"timetable": ..., "sessions": [...]}
    """
    school_id = school["id"]
    active_slots = [s for s in time_slots if not s["is_break"]]

    timetable = await db.upsert(
        "timetables",
        {"school_id": school_id, "academic_year": ACADEMIC_YEAR, "semester": 1},
        {
            "id": _uid(),
            "school_id": school_id,
            "name": f"جدول الفصل الأول {ACADEMIC_YEAR}",
            "name_en": f"Semester 1 Timetable {ACADEMIC_YEAR}",
            "academic_year": ACADEMIC_YEAR,
            "semester": 1,
            "effective_from": "2026-09-01",
            "effective_to": "2027-01-31",
            "working_days": WORK_DAYS,
            "status": "active",
            "version": 1,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    )

    # Build class → assignments map
    class_assignments: dict = {}
    for asn in assignments:
        class_assignments.setdefault(asn["class_id"], []).append(asn)

    sessions = []
    for cls in classes:
        cls_asns = class_assignments.get(cls["id"], [])
        if not cls_asns:
            continue

        shuffled = cls_asns[:]
        random.shuffle(shuffled)
        asn_idx = 0

        for day in WORK_DAYS:
            for slot in active_slots:
                if asn_idx >= len(shuffled):
                    asn_idx = 0
                asn = shuffled[asn_idx]
                asn_idx += 1

                existing = await db.find_one(
                    "schedule_sessions",
                    {
                        "school_id": school_id,
                        "schedule_id": timetable["id"],
                        "class_id": cls["id"],
                        "day_of_week": day,
                        "time_slot_id": slot["id"],
                    },
                )
                if existing:
                    sessions.append(existing)
                    continue

                sess = await db.insert(
                    "schedule_sessions",
                    {
                        "id": _uid(),
                        "school_id": school_id,
                        "schedule_id": timetable["id"],
                        "assignment_id": asn["id"],
                        "teacher_id": asn["teacher_id"],
                        "class_id": cls["id"],
                        "subject_id": asn["subject_id"],
                        "day_of_week": day,
                        "day": day,
                        "time_slot_id": slot["id"],
                        "slot_number": slot["slot_number"],
                        "status": "scheduled",
                        "teacher_name": asn["teacher_name"],
                        "class_name": asn["class_name"],
                        "subject_name": asn["subject_name"],
                        "time_slot_name": slot["name"],
                        "start_time": slot["start_time"],
                        "end_time": slot["end_time"],
                        "created_at": datetime.now(timezone.utc),
                    },
                )
                sessions.append(sess)

    print(f"  ✓ Timetable with {len(sessions)} sessions — {school['name_en']}")
    return {"timetable": timetable, "sessions": sessions}


# ─── API Helper ───────────────────────────────────────────────────────────────

async def get_api_token(email: str, password: str) -> str:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        resp = await client.post("/auth/login", json={"email": email, "password": password})
        resp.raise_for_status()
        return resp.json()["access_token"]


# ─── Step 9: Attendance ───────────────────────────────────────────────────────

async def seed_attendance(
    school: dict, db: "SeedDB", students: list, classes: list, sessions: list, teachers: list
) -> int:
    """Insert 4 weeks of attendance (Sun–Thu) for every class directly via ORM."""
    from pg_models import Attendance
    total = 0
    school_id = school["id"]

    class_students: dict = {}
    for s in students:
        class_students.setdefault(s["class_id"], []).append(s)

    # Map teacher profile id → user id (recorded_by must be a users.id FK)
    teacher_profile_to_user: dict = {}
    for t in teachers:
        teacher_profile_to_user[t["teacher"]["id"]] = t["user"]["id"]

    # Map class_id → a teacher user_id via sessions
    class_recorder: dict = {}
    for sess in sessions:
        cid = sess["class_id"]
        if cid not in class_recorder and sess.get("teacher_id"):
            uid = teacher_profile_to_user.get(sess["teacher_id"])
            if uid:
                class_recorder[cid] = uid

    # Fallback: if no session teacher found, use first teacher's user id
    fallback_user_id = teachers[0]["user"]["id"] if teachers else None

    today = date.today()
    start = today - timedelta(weeks=4)
    status_weights = ["present"] * 85 + ["absent"] * 10 + ["late"] * 5
    now_dt = datetime.now(timezone.utc)

    current = start
    while current <= today:
        weekday = current.weekday()  # Mon=0 … Sun=6
        if weekday not in (6, 0, 1, 2, 3):  # Sun-Thu only
            current += timedelta(days=1)
            continue

        day_dt = datetime(current.year, current.month, current.day, tzinfo=timezone.utc)

        for cls in classes:
            studs = class_students.get(cls["id"], [])
            if not studs:
                continue
            recorder_id = class_recorder.get(cls["id"], fallback_user_id)

            for s in studs:
                rec = Attendance(
                    id=_uid(),
                    school_id=school_id,
                    class_id=cls["id"],
                    student_id=s["id"],
                    session_id=None,
                    date=day_dt,
                    status=random.choice(status_weights),
                    recorded_by=recorder_id,
                    notes=None,
                    is_excused=False,
                    excuse_reason=None,
                )
                db.session.add(rec)
                total += 1

        current += timedelta(days=1)

    print(f"  ✓ {total} attendance records — {school['name_en']}")
    return total


# ─── Step 10a: Behaviour Records ─────────────────────────────────────────────

async def seed_behaviour_records(
    school: dict, db: "SeedDB", students: list, teachers: list
) -> int:
    from pg_models import BehaviourRecord
    total = 0
    school_id = school["id"]
    teacher_ids = [t["teacher"]["id"] for t in teachers]

    for student in students:
        count = random.randint(3, 5)
        for _ in range(count):
            is_positive = random.random() < 0.6
            templates = POSITIVE_BEHAVIOURS if is_positive else NEGATIVE_BEHAVIOURS
            btype, category, points, description = random.choice(templates)
            days_ago = random.randint(1, 28)
            record_date = datetime.now(timezone.utc) - timedelta(days=days_ago)

            rec = BehaviourRecord(
                id=_uid(),
                school_id=school_id,
                student_id=student["id"],
                class_id=student.get("class_id"),
                teacher_id=random.choice(teacher_ids),
                type=btype,
                category=category,
                severity="low" if is_positive else "medium",
                points=points,
                description=description,
                date=record_date,
                parent_notified=is_positive,
            )
            db.session.add(rec)
            total += 1

    print(f"  ✓ {total} behaviour records — {school['name_en']}")
    return total


# ─── Step 10b: Product Hub Issues ────────────────────────────────────────────

async def seed_product_hub_issues(school: dict, db: "SeedDB", admin_user: dict, issue_number_offset: int = 0) -> int:
    """Insert product hub issues directly via ORM (ProductIssue table)."""
    from pg_models import ProductIssue
    now = datetime.now(timezone.utc)
    admin_id = admin_user.get("id")
    admin_name = admin_user.get("full_name", "مدير المدرسة")
    total = 0

    for idx, issue_tmpl in enumerate(PRODUCT_ISSUES, start=1):
        issue_id = _uid()
        priority = issue_tmpl["priority"]

        issue = ProductIssue(
            id=issue_id,
            issue_number=issue_number_offset + idx,
            title=issue_tmpl["title"],
            issue_type=issue_tmpl["issue_type"],
            status=issue_tmpl.get("status", "new"),
            priority=priority,
            ai_suggested_priority=priority,
            page=issue_tmpl["page"],
            current_behavior=f"المشكلة الموصوفة: {issue_tmpl['title']}",
            expected_behavior="يجب أن يعمل النظام بشكل صحيح دون أخطاء",
            account_type="school_admin",
            employee_name=admin_name,
            employee_id=None,
            section=None,
            created_by=admin_id,
            created_by_name=admin_name,
            created_by_role="school_admin",
            is_deleted=False,
            context={
                "account_type": "school_admin",
                "platform": "web",
                "section": None,
                "page": issue_tmpl["page"],
                "url": None,
                "device": "Desktop",
                "browser": "Chrome",
                "user_id": admin_id,
            },
            description={
                "current_behavior": f"المشكلة الموصوفة: {issue_tmpl['title']}",
                "expected_behavior": "يجب أن يعمل النظام بشكل صحيح دون أخطاء",
                "reproduction_steps": [],
                "reproducible": None,
            },
            impact=[],
            technical={"error_message": None, "related_to": []},
            business={"affected_users_count": None, "user_type_weight": None, "impact_score": None},
            assignment={"assigned_to": None, "team": None, "due_date": None},
            ai={
                "suggested_title": issue_tmpl["title"],
                "duplicate_detected": False,
                "duplicate_candidates": [],
                "suggested_team": None,
                "generated_prompt": None,
                "priority_reasoning": None,
                "team_reasoning": None,
                "technical_notes": None,
                "impact_assessment": None,
            },
            attachments=[],
            submission_metadata={
                "employee_name": admin_name,
                "employee_id": None,
                "user_id": admin_id,
                "created_at": now.isoformat(),
                "created_date": now.strftime("%Y-%m-%d"),
                "created_time": now.strftime("%H:%M:%S"),
            },
            visibility={"prompt_visible_to_admin_only": True},
            system={
                "created_by": admin_id,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "last_status_changed_at": now.isoformat(),
            },
            hakim_analysis={},
            generated_prompt=None,
            sla_deadline=None,
            sla_status="on_track",
        )
        db.session.add(issue)
        total += 1

    print(f"  ✓ {total} product hub issues — {school['name_en']}")
    return total


# ─── Step 11: Write TEST_CREDENTIALS.md ──────────────────────────────────────

def write_credentials_file(
    schools: dict,
    platform_admin: dict,
    school_users: dict,
    school_populations: dict,
) -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_path = os.path.join(project_root, "TEST_CREDENTIALS.md")

    lines = [
        "# NASSAQ — Test Credentials",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> Default password for **ALL** accounts: `{DEFAULT_PASSWORD}`",
        "",
        "---",
        "",
        "## Platform Admin (cross-school access)",
        "",
        "| Role | Email | Password |",
        "|---|---|---|",
        f"| Platform Admin | admin@nassaq.com | {DEFAULT_PASSWORD} |",
        "",
        "---",
        "",
    ]

    for code, school in schools.items():
        users = school_users[code]
        pops = school_populations[code]

        lines += [
            f"## {school['name_en']} — {school['name']}",
            f"**Code:** `{code}` | **City:** {school['city']} | **Type:** {school['school_type']}",
            "",
            "### Administrators",
            "| Role | Email | Password |",
            "|---|---|---|",
        ]
        role_labels = ["School Admin (Primary)", "School Admin (Deputy)"]
        for idx, admin in enumerate(users["admins"]):
            label = role_labels[idx] if idx < len(role_labels) else "School Admin"
            lines.append(f"| {label} | {admin['email']} | {DEFAULT_PASSWORD} |")

        lines += [
            "",
            "### Teachers (all accounts)",
            "| Name | Email | Specialization | Password |",
            "|---|---|---|---|",
        ]
        for t in users["teachers"]:
            lines.append(
                f"| {t['teacher']['full_name']} | {t['email']} | {t['teacher']['specialization']} | {DEFAULT_PASSWORD} |"
            )

        lines += [
            "",
            "### Parents (sample — first 10)",
            "| Name | Email | Password |",
            "|---|---|---|",
        ]
        for p in pops["parents"][:10]:
            lines.append(f"| {p['parent']['full_name']} | {p['email']} | {DEFAULT_PASSWORD} |")
        remaining = len(pops["parents"]) - 10
        if remaining > 0:
            lines.append(f"| *(+{remaining} more)* | | |")

        lines += [
            "",
            f"**Total students:** {len(pops['students'])}  ",
            f"**Total parents:** {len(pops['parents'])}  ",
            f"**Total teachers:** {len(users['teachers'])}  ",
            "",
            "---",
            "",
        ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  ✓ TEST_CREDENTIALS.md → {out_path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("\n" + "=" * 60)
    print("NASSAQ — Comprehensive Test Data Seed")
    print("=" * 60 + "\n")

    schools = {}
    platform_admin = {}
    school_users = {}
    school_academics = {}
    school_populations = {}
    school_slots = {}
    school_assignments = {}
    school_timetables = {}

    # Each step uses its own DB transaction so no single commit is too large
    print("[1/9] Seeding schools & platform admin...")
    async with SeedDB() as db:
        schools = await seed_schools(db)
        platform_admin = await seed_platform_admin(db)

    print("\n[2/9] Seeding school admins & teachers...")
    async with SeedDB() as db:
        for code, school in schools.items():
            school_users[code] = await seed_school_users(db, school)

    print("\n[3/9] Seeding classes & subjects...")
    async with SeedDB() as db:
        for code, school in schools.items():
            teachers = school_users[code]["teachers"]
            school_academics[code] = await seed_classes_and_subjects(db, school, teachers)

    print("\n[4/9] Seeding students & parents (School A)...")
    code_a = list(schools.keys())[0]
    async with SeedDB() as db:
        school_populations[code_a] = await seed_students_and_parents(
            db, schools[code_a], school_academics[code_a]["classes"]
        )

    print("\n[5/9] Seeding students & parents (School B)...")
    code_b = list(schools.keys())[1]
    async with SeedDB() as db:
        school_populations[code_b] = await seed_students_and_parents(
            db, schools[code_b], school_academics[code_b]["classes"]
        )

    print("\n[6/9] Seeding time slots & teacher assignments...")
    async with SeedDB() as db:
        for code, school in schools.items():
            school_slots[code] = await seed_time_slots(db, school)
        for code, school in schools.items():
            teachers = school_users[code]["teachers"]
            classes = school_academics[code]["classes"]
            subjects = school_academics[code]["subjects"]
            school_assignments[code] = await seed_teacher_assignments(
                db, school, teachers, classes, subjects
            )

    print("\n[7/9] Seeding timetables (School A)...")
    async with SeedDB() as db:
        school_timetables[code_a] = await seed_timetable(
            db, schools[code_a],
            school_academics[code_a]["classes"],
            school_assignments[code_a],
            school_slots[code_a],
        )

    print("\n[8/9] Seeding timetables (School B)...")
    async with SeedDB() as db:
        school_timetables[code_b] = await seed_timetable(
            db, schools[code_b],
            school_academics[code_b]["classes"],
            school_assignments[code_b],
            school_slots[code_b],
        )

    # Clean up previous operational data to ensure idempotency
    print("\n[cleanup] Clearing previous operational data...")
    from sqlalchemy import text as _sql_text2, bindparam
    school_ids = [s["id"] for s in schools.values()]
    async with SeedDB() as db:
        await db.session.execute(
            _sql_text2("DELETE FROM attendance WHERE school_id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"ids": school_ids},
        )
        await db.session.execute(
            _sql_text2("DELETE FROM behaviour_records WHERE school_id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"ids": school_ids},
        )
    print("  ✓ Cleared attendance and behaviour records")

    # Behaviour records — DB-direct (split per school to avoid large transactions)
    print("\n[9a/9] Seeding behaviour records (DB)...")
    for code, school in schools.items():
        students = school_populations[code]["students"]
        teachers = school_users[code]["teachers"]
        async with SeedDB() as db:
            await seed_behaviour_records(school, db, students, teachers)

    # Attendance records — DB-direct (split per school to keep transactions manageable)
    print("\n[9b/9] Seeding attendance records (DB)...")
    for code, school in schools.items():
        students = school_populations[code]["students"]
        classes = school_academics[code]["classes"]
        sessions = school_timetables[code]["sessions"]
        teachers = school_users[code]["teachers"]
        async with SeedDB() as db:
            await seed_attendance(school, db, students, classes, sessions, teachers)

    # Product hub issues — DB-direct (find current max issue_number to avoid conflicts)
    print("\n[9c/9] Seeding product hub issues (DB)...")
    from sqlalchemy import text as _sql_text
    async with SeedDB() as db:
        row = (await db.session.execute(_sql_text("SELECT COALESCE(MAX(issue_number),0) FROM product_issues"))).scalar()
        current_max_issue_number = int(row)
    for i, (code, school) in enumerate(schools.items()):
        admin_record = school_users[code]["admins"][0] if school_users[code]["admins"] else {}
        async with SeedDB() as db:
            await seed_product_hub_issues(
                school, db, admin_record,
                issue_number_offset=current_max_issue_number + i * len(PRODUCT_ISSUES)
            )

    # Write credentials reference file
    print("\n[✓] Writing TEST_CREDENTIALS.md...")
    write_credentials_file(schools, platform_admin, school_users, school_populations)

    # Summary
    print("\n" + "=" * 60)
    print("Seed Complete — Summary")
    print("=" * 60)
    for code, school in schools.items():
        pops = school_populations.get(code, {})
        academics = school_academics.get(code, {})
        timetable_info = school_timetables.get(code, {})
        print(f"\n{school['name_en']} ({code}):")
        print(f"  Students  : {len(pops.get('students', []))}")
        print(f"  Parents   : {len(pops.get('parents', []))}")
        print(f"  Teachers  : {len(school_users.get(code, {}).get('teachers', []))}")
        print(f"  Classes   : {len(academics.get('classes', []))}")
        print(f"  Subjects  : {len(academics.get('subjects', []))}")
        print(f"  Sessions  : {len(timetable_info.get('sessions', []))}")

    print(f"\nDefault password for all accounts: {DEFAULT_PASSWORD}")
    print("Full credentials list: TEST_CREDENTIALS.md\n")


if __name__ == "__main__":
    asyncio.run(main())
