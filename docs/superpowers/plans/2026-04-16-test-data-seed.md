# Test Data Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `backend/scripts/seed_test_data.py` — an idempotent script that populates NASSAQ with two fully isolated Arabic-named school tenants covering all roles, academic structure, schedules, and 4 weeks of operational data.

**Architecture:** Hybrid seeding — SQLAlchemy direct writes for structural data (schools, users, classes, subjects, timetables), then httpx API calls against `http://localhost:8000` for operational data (attendance, behaviour, product hub issues). All data is idempotent: checks for existence before inserting. Produces `TEST_CREDENTIALS.md` at project root on completion.

**Tech Stack:** Python asyncio, SQLAlchemy async, httpx (async), bcrypt (via `backend/dependencies.py`), existing `backend/scripts/seed_db_helper.py` pattern.

---

## File Structure

- **Create:** `backend/scripts/seed_test_data.py` — the single seed script (all tasks contribute to this file)
- **Create:** `TEST_CREDENTIALS.md` — generated at runtime, written to project root

---

## Task 1: Script Skeleton — Imports, Constants, Name Banks

**Files:**
- Create: `backend/scripts/seed_test_data.py`

- [ ] **Step 1: Create the file with all imports and data constants**

```python
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

# ─── Constants ───────────────────────────────────────────────────────────────

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

# Arabic male first names
MALE_FIRST = [
    "أحمد", "محمد", "خالد", "عبدالله", "سعد", "عمر", "يوسف", "إبراهيم",
    "علي", "حسن", "فهد", "ناصر", "سلطان", "طارق", "وليد", "ماجد",
    "رائد", "بلال", "زياد", "أنس",
]

# Arabic female first names
FEMALE_FIRST = [
    "فاطمة", "نورة", "سارة", "ريم", "هند", "لطيفة", "منيرة", "أميرة",
    "شيماء", "دانة", "رهف", "لمى", "غادة", "أسماء", "هيا", "ليلى",
    "مها", "سلمى", "وفاء", "إيمان",
]

# Arabic family names
FAMILY_NAMES = [
    "الرشيدي", "العتيبي", "القحطاني", "الشمري", "الزهراني", "الدوسري",
    "الحربي", "العنزي", "المطيري", "الغامدي", "السبيعي", "البقمي",
    "الرويلي", "العجمي", "الصاعدي", "المالكي", "الجهني", "الوادعي",
    "التميمي", "الأحمدي",
]

# Subjects: (name_ar, name_en, code, category, default_periods_per_week)
SUBJECTS_DATA = [
    ("اللغة العربية",     "Arabic Language",    "AR",   "core",     6),
    ("اللغة الإنجليزية", "English Language",   "EN",   "core",     5),
    ("الرياضيات",         "Mathematics",        "MATH", "core",     6),
    ("العلوم",            "Science",            "SCI",  "core",     4),
    ("التربية الإسلامية", "Islamic Studies",    "IS",   "core",     4),
    ("الدراسات الاجتماعية","Social Studies",    "SS",   "core",     3),
    ("التربية البدنية",   "Physical Education", "PE",   "elective", 2),
    ("التربية الفنية",    "Art",                "ART",  "elective", 2),
    ("الحاسوب",           "Computer Science",   "CS",   "elective", 2),
    ("التاريخ",           "History",            "HIS",  "core",     2),
    ("الجغرافيا",         "Geography",          "GEO",  "core",     2),
    ("الكيمياء",          "Chemistry",          "CHEM", "secondary",3),
    ("الفيزياء",          "Physics",            "PHY",  "secondary",3),
    ("الأحياء",           "Biology",            "BIO",  "secondary",3),
]

# Gulf work-week days
WORK_DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]

# Time slots: (slot_number, name_ar, start, end, is_break)
TIME_SLOTS_DATA = [
    (1,  "الحصة الأولى",   "07:30", "08:15", False),
    (2,  "الحصة الثانية",  "08:15", "09:00", False),
    (3,  "الحصة الثالثة",  "09:00", "09:45", False),
    (4,  "الحصة الرابعة",  "09:45", "10:30", False),
    (5,  "الاستراحة",      "10:30", "10:50", True),
    (6,  "الحصة الخامسة",  "10:50", "11:35", False),
    (7,  "الحصة السادسة",  "11:35", "12:20", False),
    (8,  "الحصة السابعة",  "12:20", "13:05", False),
]

# Product hub issues to create per school
PRODUCT_ISSUES = [
    {"title": "بطء في تحميل جدول الحصص",             "issue_type": "performance", "priority": "high",     "status": "open"},
    {"title": "خطأ عند تسجيل الغياب الجماعي",         "issue_type": "bug",         "priority": "critical", "status": "open"},
    {"title": "لا تظهر درجات الطلاب في بوابة الأهل",  "issue_type": "bug",         "priority": "high",     "status": "in_progress"},
    {"title": "إضافة تقرير أسبوعي للحضور",            "issue_type": "feature",     "priority": "medium",   "status": "open"},
    {"title": "خطأ في حساب نسبة الحضور",              "issue_type": "bug",         "priority": "high",     "status": "in_progress"},
    {"title": "تحسين واجهة قائمة الطلاب",             "issue_type": "improvement", "priority": "low",      "status": "open"},
    {"title": "إشعارات الأهل لا تصل أحياناً",         "issue_type": "bug",         "priority": "medium",   "status": "in_progress"},
    {"title": "إضافة تصدير PDF لجدول الحصص",          "issue_type": "feature",     "priority": "medium",   "status": "resolved"},
    {"title": "خطأ في صلاحيات المعلم البديل",         "issue_type": "bug",         "priority": "high",     "status": "resolved"},
    {"title": "تحسين سرعة البحث في سجلات الطلاب",    "issue_type": "performance", "priority": "low",      "status": "resolved"},
]

# Behaviour records templates
POSITIVE_BEHAVIOURS = [
    ("positive", "academic",  10, "تميّز في الأداء الأكاديمي وحصل على أعلى درجة في الاختبار"),
    ("positive", "social",    5,  "أظهر روح التعاون مع زملائه خلال العمل الجماعي"),
    ("positive", "conduct",   5,  "التزام مثالي بقواعد المدرسة طوال الأسبوع"),
    ("positive", "academic",  10, "قدّم مشروعاً استثنائياً في مادة العلوم"),
    ("positive", "social",    5,  "ساعد زميله في فهم المادة الدراسية"),
]
NEGATIVE_BEHAVIOURS = [
    ("negative", "conduct",  -5,  "التأخر عن الحصة الأولى بدون عذر"),
    ("negative", "academic", -5,  "إهمال الواجب المنزلي لأسبوع كامل"),
    ("negative", "social",   -3,  "إزعاج الزملاء خلال وقت الدراسة"),
    ("negative", "conduct",  -5,  "استخدام الهاتف خلال وقت الدراسة"),
]


def _uid() -> str:
    return str(uuid.uuid4())


def _arabic_name(gender: str) -> tuple[str, str]:
    """Return (full_name_ar, slug_en) for a random Arabic person."""
    first = random.choice(MALE_FIRST if gender == "male" else FEMALE_FIRST)
    family = random.choice(FAMILY_NAMES)
    full_ar = f"{first} {family}"
    # Create an ASCII slug for email
    slug = f"{_transliterate(first)}.{_transliterate(family)}".lower().replace(" ", "")
    return full_ar, slug


_TRANS = {
    "أ":"a","ا":"a","إ":"i","آ":"a","ب":"b","ت":"t","ث":"th","ج":"j",
    "ح":"h","خ":"kh","د":"d","ذ":"dh","ر":"r","ز":"z","س":"s","ش":"sh",
    "ص":"s","ض":"d","ط":"t","ظ":"z","ع":"a","غ":"gh","ف":"f","ق":"q",
    "ك":"k","ل":"l","م":"m","ن":"n","ه":"h","و":"w","ي":"y","ى":"a",
    "ة":"a","ء":"","ئ":"y","ؤ":"w","لا":"la",
}


def _transliterate(text: str) -> str:
    out = []
    for ch in text:
        out.append(_TRANS.get(ch, ch))
    return "".join(out)
```

- [ ] **Step 2: Verify the file is syntactically valid**

```bash
cd backend && python -c "import scripts.seed_test_data" && echo "OK"
```
Expected output: `OK`

---

## Task 2: DB Session Helper

**Files:**
- Modify: `backend/scripts/seed_test_data.py` (append)

- [ ] **Step 1: Add the async DB context manager**

Append to `backend/scripts/seed_test_data.py`:

```python
# ─── DB Session Helper ────────────────────────────────────────────────────────

class SeedDB:
    """Thin async context manager giving direct SQLAlchemy session access."""
    def __init__(self):
        self._session = None

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
        return await gd_insert(self.session, collection, data)

    async def insert_many(self, collection: str, records: list) -> list:
        return await gd_insert_many(self.session, collection, records)

    async def count(self, collection: str, filters: dict) -> int:
        return await gd_count(self.session, collection, filters)

    async def upsert(self, collection: str, lookup: dict, data: dict) -> dict:
        """Insert if not found, return existing record if found."""
        existing = await self.find_one(collection, lookup)
        if existing:
            return existing
        return await self.insert(collection, {**lookup, **data})
```

- [ ] **Step 2: Verify import chain still works**

```bash
cd backend && python -c "import scripts.seed_test_data; print('OK')"
```
Expected: `OK`

---

## Task 3: Seed Schools

**Files:**
- Modify: `backend/scripts/seed_test_data.py` (append)

- [ ] **Step 1: Add `seed_schools()` function**

Append to `backend/scripts/seed_test_data.py`:

```python
# ─── Step 1: Schools ─────────────────────────────────────────────────────────

async def seed_schools(db: SeedDB) -> dict[str, dict]:
    """
    Create both school tenants. Returns {code: school_record}.
    Safe to re-run: skips schools that already have the given code.
    """
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
                "setup_completed": True,
                "tenant_type": "production",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        results[s["code"]] = {**record, **s}
        print(f"  ✓ School: {s['name_en']} ({s['code']})")
    return results
```

- [ ] **Step 2: Add a minimal `main()` stub to test this task in isolation**

Append to `backend/scripts/seed_test_data.py`:

```python
# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("\n=== NASSAQ Test Data Seed ===\n")
    async with SeedDB() as db:
        print("[1/10] Seeding schools...")
        schools = await seed_schools(db)
        print(f"       {len(schools)} schools ready.\n")
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Run and verify schools are created**

```bash
cd backend && python scripts/seed_test_data.py
```
Expected output contains:
```
✓ School: Al-Farabi School (FARABI-001)
✓ School: Ibn Sina International Academy (IBNSINA-001)
2 schools ready.
```

---

## Task 4: Seed Users — Platform Admin, School Admins, Teachers, Parents

**Files:**
- Modify: `backend/scripts/seed_test_data.py`

- [ ] **Step 1: Add `seed_platform_admin()` function — insert before `main()`**

```python
# ─── Step 2: Platform Admin ───────────────────────────────────────────────────

async def seed_platform_admin(db: SeedDB) -> dict:
    user = await db.upsert(
        "users",
        {"email": "admin@nassaq.com"},
        {
            "id": _uid(),
            "full_name": "مدير المنصة",
            "full_name_en": "Platform Administrator",
            "password_hash": hash_password(DEFAULT_PASSWORD),
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
```

- [ ] **Step 2: Add `seed_school_users()` — creates 2 admins + 18 teachers + parents per school**

```python
# ─── Step 3: School Users ─────────────────────────────────────────────────────

async def seed_school_users(db: SeedDB, school: dict) -> dict:
    """
    Returns {
      "admins": [user_record, ...],
      "teachers": [{"user": ..., "teacher": ...}, ...],
      "parents": [{"user": ..., "parent": ...}, ...],
    }
    """
    domain = school["email_domain"]
    school_id = school["id"]
    result = {"admins": [], "teachers": [], "parents": []}

    # ── 2 school admins ────────────────────────────────────────────────────────
    admin_specs = [
        ("mudeer", "مدير المدرسة",   "School Director",  "male"),
        ("naeb",   "نائب المدير",    "Deputy Director",  "male"),
    ]
    for slug, name_ar, name_en, gender in admin_specs:
        email = f"{slug}@{domain}"
        user = await db.upsert(
            "users",
            {"email": email},
            {
                "id": _uid(),
                "full_name": name_ar,
                "full_name_en": name_en,
                "password_hash": hash_password(DEFAULT_PASSWORD),
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

    # ── 18 teachers ────────────────────────────────────────────────────────────
    used_emails: set[str] = set()
    teacher_specializations = [
        "اللغة العربية", "اللغة العربية", "اللغة الإنجليزية", "اللغة الإنجليزية",
        "الرياضيات", "الرياضيات", "العلوم", "العلوم",
        "التربية الإسلامية", "الدراسات الاجتماعية", "التربية البدنية",
        "التربية الفنية", "الحاسوب", "التاريخ", "الجغرافيا",
        "الكيمياء", "الفيزياء", "الأحياء",
    ]
    for i, spec in enumerate(teacher_specializations):
        gender = "male" if i % 3 != 0 else "female"
        name_ar, slug = _arabic_name(gender)
        # Ensure unique email
        base_email = f"{slug}@{domain}"
        email = base_email
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
                "password_hash": hash_password(DEFAULT_PASSWORD),
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
                "national_id": f"1{random.randint(10000000, 99999999)}",
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

    # ── Parents (seeded later, after students so we can link them) ─────────────
    return result
```

- [ ] **Step 3: Update `main()` to call these functions**

Replace the existing `main()` with:

```python
async def main():
    print("\n=== NASSAQ Test Data Seed ===\n")
    async with SeedDB() as db:
        print("[1/10] Seeding schools...")
        schools = await seed_schools(db)

        print("[2/10] Seeding platform admin...")
        platform_admin = await seed_platform_admin(db)

        print("[3/10] Seeding school users (admins + teachers)...")
        school_users = {}
        for code, school in schools.items():
            school_users[code] = await seed_school_users(db, school)

    print("\nDone (partial — more tasks to come).")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run and verify user counts**

```bash
cd backend && python scripts/seed_test_data.py
```
Expected output contains lines like:
```
✓ Platform Admin: admin@nassaq.com
✓ 2 admins, 18 teachers — Al-Farabi School
✓ 2 admins, 18 teachers — Ibn Sina International Academy
```

---

## Task 5: Seed Classes, Subjects, and Students

**Files:**
- Modify: `backend/scripts/seed_test_data.py`

- [ ] **Step 1: Add `seed_classes_and_subjects()` — insert before `main()`**

```python
# ─── Step 4: Classes & Subjects ───────────────────────────────────────────────

GRADE_NAMES = {
    1: "الصف الأول",    2: "الصف الثاني",   3: "الصف الثالث",
    4: "الصف الرابع",   5: "الصف الخامس",   6: "الصف السادس",
    7: "الصف السابع",   8: "الصف الثامن",   9: "الصف التاسع",
    10: "الصف العاشر",  11: "الصف الحادي عشر", 12: "الصف الثاني عشر",
}
SECTIONS = ["أ", "ب"]  # Two sections for grades 1-6, one for 7-12


async def seed_classes_and_subjects(
    db: SeedDB, school: dict, teachers: list
) -> dict:
    """
    Returns {"classes": [...], "subjects": [...]}
    Each class record has extra key "grade_number" for convenience.
    """
    school_id = school["id"]
    classes = []
    subjects = []

    # Assign homeroom teachers round-robin
    teacher_objs = [t["teacher"] for t in teachers]

    teacher_idx = 0
    for grade in range(1, 13):
        sections = SECTIONS if grade <= 6 else ["أ"]
        for section in sections:
            name = f"{GRADE_NAMES[grade]} {section}"
            homeroom_teacher = teacher_objs[teacher_idx % len(teacher_objs)]
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
                    "homeroom_teacher_id": homeroom_teacher["id"],
                    "homeroom_teacher_name": homeroom_teacher["full_name"],
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            classes.append({**cls, "grade_number": grade, "section": section})

    # Create subjects
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
```

- [ ] **Step 2: Add `seed_students_and_parents()` — insert before `main()`**

```python
# ─── Step 5: Students & Parents ───────────────────────────────────────────────

async def seed_students_and_parents(
    db: SeedDB, school: dict, classes: list
) -> dict:
    """
    ~175 students across 18 classes, each linked to a parent.
    Returns {"students": [...], "parents": [...]}
    """
    school_id = school["id"]
    prefix = school["student_prefix"]
    domain = school["email_domain"]
    all_students = []
    all_parents = []

    student_counter = 1
    for cls in classes:
        # ~14 students per class (totals ~175 across 13 classes for grades 1-6 with 2 sections)
        count = 14
        class_students = []

        for i in range(count):
            gender = "male" if i % 2 == 0 else "female"
            name_ar, slug = _arabic_name(gender)
            student_number = f"{prefix}-{student_counter:03d}"
            student_counter += 1

            # Create parent first (or find existing by phone pattern)
            parent_phone = f"05{random.randint(10000000, 99999999)}"
            parent_name_ar, parent_slug = _arabic_name("male")
            parent_email = f"{parent_slug}.parent{student_counter}@gmail.com"

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

            # Create parent User account
            parent_user = await db.upsert(
                "users",
                {"email": parent_email},
                {
                    "id": _uid(),
                    "full_name": parent_name_ar,
                    "password_hash": hash_password(DEFAULT_PASSWORD),
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

            # Create student
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
            class_students.append(student)
            all_students.append(student)
            all_parents.append({"parent": parent, "user": parent_user, "email": parent_email})

        all_students.extend(class_students)

    # Deduplicate (class_students were added twice — remove duplicates)
    seen_ids = set()
    unique_students = []
    for s in all_students:
        if s["id"] not in seen_ids:
            seen_ids.add(s["id"])
            unique_students.append(s)

    print(f"  ✓ {len(unique_students)} students, {len(all_parents)} parents — {school['name_en']}")
    return {"students": unique_students, "parents": all_parents}
```

- [ ] **Step 3: Update `main()` to call these new functions**

Replace `main()`:

```python
async def main():
    print("\n=== NASSAQ Test Data Seed ===\n")

    seed_state = {}  # Holds all seeded objects for cross-step access

    async with SeedDB() as db:
        print("[1/10] Seeding schools...")
        schools = await seed_schools(db)

        print("[2/10] Seeding platform admin...")
        platform_admin = await seed_platform_admin(db)

        print("[3/10] Seeding school users (admins + teachers)...")
        school_users = {}
        for code, school in schools.items():
            school_users[code] = await seed_school_users(db, school)

        print("[4/10] Seeding classes & subjects...")
        school_academics = {}
        for code, school in schools.items():
            teachers = school_users[code]["teachers"]
            school_academics[code] = await seed_classes_and_subjects(db, school, teachers)

        print("[5/10] Seeding students & parents...")
        school_populations = {}
        for code, school in schools.items():
            classes = school_academics[code]["classes"]
            school_populations[code] = await seed_students_and_parents(db, school, classes)

    seed_state = {
        "schools": schools,
        "platform_admin": platform_admin,
        "school_users": school_users,
        "school_academics": school_academics,
        "school_populations": school_populations,
    }
    print("\nDone (tasks 1-5 complete).")
    return seed_state

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run and check output**

```bash
cd backend && python scripts/seed_test_data.py
```
Expected output contains:
```
[4/10] Seeding classes & subjects...
  ✓ 18 classes, 14 subjects — Al-Farabi School
  ✓ 18 classes, 14 subjects — Ibn Sina International Academy
[5/10] Seeding students & parents...
  ✓ 252 students, 252 parents — Al-Farabi School
```
(252 = 18 classes × 14 students)

---

## Task 6: Seed Time Slots, Teacher Assignments, and Timetable

**Files:**
- Modify: `backend/scripts/seed_test_data.py`

- [ ] **Step 1: Add `seed_time_slots()` — insert before `main()`**

```python
# ─── Step 6: Time Slots ───────────────────────────────────────────────────────

async def seed_time_slots(db: SeedDB, school: dict) -> list:
    """Create 8 time slots (including 1 break) per school."""
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
```

- [ ] **Step 2: Add `seed_teacher_assignments()` — insert before `main()`**

```python
# ─── Step 7: Teacher Assignments ─────────────────────────────────────────────

async def seed_teacher_assignments(
    db: SeedDB, school: dict, teachers: list, classes: list, subjects: list
) -> list:
    """
    Assign each teacher to 1-3 subjects across classes they cover.
    Returns list of assignment records.
    """
    school_id = school["id"]

    # Build a subject lookup by code
    subj_by_name = {s["name_ar"]: s for s in subjects}

    # Teacher → subject mapping (matches teacher_specializations order from Task 4)
    teacher_subject_map = [
        "اللغة العربية", "اللغة العربية", "اللغة الإنجليزية", "اللغة الإنجليزية",
        "الرياضيات", "الرياضيات", "العلوم", "العلوم",
        "التربية الإسلامية", "الدراسات الاجتماعية", "التربية البدنية",
        "التربية الفنية", "الحاسوب", "التاريخ", "الجغرافيا",
        "الكيمياء", "الفيزياء", "الأحياء",
    ]

    assignments = []
    # Assign each teacher to all classes (or a subset for secondary subjects)
    for i, teacher_info in enumerate(teachers):
        teacher = teacher_info["teacher"]
        spec_name = teacher_subject_map[i % len(teacher_subject_map)]
        subject = subj_by_name.get(spec_name)
        if not subject:
            continue

        # Secondary subjects only apply to grades 10-12
        is_secondary = subject["category"] == "secondary"

        for cls in classes:
            grade_num = int(cls["grade_level"])
            if is_secondary and grade_num < 10:
                continue
            if not is_secondary and grade_num >= 10 and subject["category"] == "elective":
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
```

- [ ] **Step 3: Add `seed_timetable()` — creates timetable + schedule sessions**

```python
# ─── Step 8: Timetable & Schedule Sessions ────────────────────────────────────

async def seed_timetable(
    db: SeedDB, school: dict, classes: list, assignments: list, time_slots: list
) -> dict:
    """
    Creates one Timetable record and populates ScheduleSession for each
    class × day × non-break time_slot combination.
    Returns {"timetable": ..., "sessions": [...]}
    """
    school_id = school["id"]
    active_slots = [s for s in time_slots if not s["is_break"]]

    # Create timetable header
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

    # Build assignment lookup: class_id → list of assignments
    class_assignments: dict[str, list] = {}
    for asn in assignments:
        class_assignments.setdefault(asn["class_id"], []).append(asn)

    sessions = []
    for cls in classes:
        cls_assignments = class_assignments.get(cls["id"], [])
        if not cls_assignments:
            continue

        # Rotate assignments across days/slots to avoid conflicts
        asn_cycle = cls_assignments[:]
        random.shuffle(asn_cycle)
        asn_idx = 0

        for day in WORK_DAYS:
            for slot in active_slots:
                if asn_idx >= len(asn_cycle):
                    asn_idx = 0

                asn = asn_cycle[asn_idx]
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
```

- [ ] **Step 4: Update `main()` to call tasks 6–8**

Inside the `async with SeedDB() as db:` block, add after step 5:

```python
        print("[6/10] Seeding time slots...")
        school_slots = {}
        for code, school in schools.items():
            school_slots[code] = await seed_time_slots(db, school)

        print("[7/10] Seeding teacher assignments...")
        school_assignments = {}
        for code, school in schools.items():
            teachers = school_users[code]["teachers"]
            classes = school_academics[code]["classes"]
            subjects = school_academics[code]["subjects"]
            school_assignments[code] = await seed_teacher_assignments(
                db, school, teachers, classes, subjects
            )

        print("[8/10] Seeding timetables...")
        school_timetables = {}
        for code, school in schools.items():
            classes = school_academics[code]["classes"]
            assignments = school_assignments[code]
            time_slots = school_slots[code]
            school_timetables[code] = await seed_timetable(
                db, school, classes, assignments, time_slots
            )
```

Also add these to the `seed_state` dict:
```python
    seed_state["school_slots"] = school_slots
    seed_state["school_assignments"] = school_assignments
    seed_state["school_timetables"] = school_timetables
```

- [ ] **Step 5: Run and check session count**

```bash
cd backend && python scripts/seed_test_data.py
```
Expected output includes:
```
[8/10] Seeding timetables...
  ✓ Timetable with 630 sessions — Al-Farabi School
  ✓ Timetable with 630 sessions — Ibn Sina International Academy
```
(18 classes × 7 periods × 5 days = 630)

---

## Task 7: API-Driven Attendance Records

**Files:**
- Modify: `backend/scripts/seed_test_data.py`

- [ ] **Step 1: Add `get_api_token()` helper — insert before `main()`**

```python
# ─── API Helper ───────────────────────────────────────────────────────────────

async def get_api_token(email: str, password: str) -> str:
    """Authenticate against the live API and return a Bearer token."""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        resp = await client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]
```

- [ ] **Step 2: Add `seed_attendance()` — insert before `main()`**

```python
# ─── Step 9: Attendance ───────────────────────────────────────────────────────

async def seed_attendance(
    school: dict,
    token: str,
    students: list,
    classes: list,
    sessions: list,
) -> int:
    """
    POST 4 weeks of bulk attendance (Sun–Thu) for every class.
    Returns total records created.
    """
    headers = {"Authorization": f"Bearer {token}"}
    total = 0

    # Build class → students mapping
    class_students: dict[str, list] = {}
    for s in students:
        class_students.setdefault(s["class_id"], []).append(s)

    # Build class → first teacher_id from sessions
    class_teacher: dict[str, str] = {}
    for sess in sessions:
        if sess["class_id"] not in class_teacher and sess.get("teacher_id"):
            class_teacher[sess["class_id"]] = sess["teacher_id"]

    # 4 weeks back from today
    today = date.today()
    start = today - timedelta(weeks=4)

    status_weights = ["present"] * 85 + ["absent"] * 10 + ["late"] * 5

    async with httpx.AsyncClient(base_url=API_BASE, timeout=60) as client:
        current = start
        while current <= today:
            weekday = current.weekday()  # Mon=0, Sun=6
            # Gulf work week: Sun(6), Mon(0), Tue(1), Wed(2), Thu(3)
            if weekday not in (6, 0, 1, 2, 3):
                current += timedelta(days=1)
                continue

            for cls in classes:
                studs = class_students.get(cls["id"], [])
                if not studs:
                    continue
                teacher_id = class_teacher.get(cls["id"], "")

                records = [
                    {
                        "student_id": s["id"],
                        "status": random.choice(status_weights),
                        "notes": None,
                    }
                    for s in studs
                ]

                payload = {
                    "class_id": cls["id"],
                    "date": current.isoformat(),
                    "records": records,
                }

                try:
                    resp = await client.post(
                        "/attendance/bulk",
                        json=payload,
                        headers=headers,
                    )
                    if resp.status_code in (200, 201):
                        total += len(records)
                    else:
                        # Don't abort — log and continue
                        print(f"    ! Attendance warn {resp.status_code}: {resp.text[:80]}")
                except Exception as e:
                    print(f"    ! Attendance error: {e}")

            current += timedelta(days=1)

    print(f"  ✓ ~{total} attendance records — {school['name_en']}")
    return total
```

- [ ] **Step 3: Wire into `main()` — add after the `async with SeedDB()` block**

```python
    print("[9/10] Seeding operational data via API...")
    for code, school in schools.items():
        admin_email = f"mudeer@{school['email_domain']}"
        try:
            token = await get_api_token(admin_email, DEFAULT_PASSWORD)
        except Exception as e:
            print(f"  ! Could not get token for {admin_email}: {e}")
            continue

        students = school_populations[code]["students"]
        classes = school_academics[code]["classes"]
        sessions = school_timetables[code]["sessions"]

        await seed_attendance(school, token, students, classes, sessions)
```

- [ ] **Step 4: Run with live backend and verify**

Ensure Backend API workflow is running, then:
```bash
cd backend && python scripts/seed_test_data.py
```
Expected:
```
[9/10] Seeding operational data via API...
  ✓ ~xxxxx attendance records — Al-Farabi School
```

---

## Task 8: API-Driven Behaviour Records and Product Hub Issues

**Files:**
- Modify: `backend/scripts/seed_test_data.py`

- [ ] **Step 1: Add `seed_behaviour_records()` — insert before `main()`**

```python
# ─── Step 10a: Behaviour Records ─────────────────────────────────────────────

async def seed_behaviour_records(
    school: dict, token: str, students: list, teachers: list
) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    total = 0
    teacher_ids = [t["teacher"]["id"] for t in teachers]

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        for student in students:
            count = random.randint(3, 5)
            for _ in range(count):
                is_positive = random.random() < 0.6
                templates = POSITIVE_BEHAVIOURS if is_positive else NEGATIVE_BEHAVIOURS
                btype, category, points, description = random.choice(templates)

                days_ago = random.randint(1, 28)
                record_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

                payload = {
                    "student_id": student["id"],
                    "class_id": student["class_id"],
                    "teacher_id": random.choice(teacher_ids),
                    "type": btype,
                    "category": category,
                    "severity": "low" if is_positive else "medium",
                    "points": points,
                    "description": description,
                    "date": record_date,
                    "parent_notified": is_positive,
                }
                try:
                    resp = await client.post("/behaviour", json=payload, headers=headers)
                    if resp.status_code in (200, 201):
                        total += 1
                    else:
                        print(f"    ! Behaviour warn {resp.status_code}: {resp.text[:80]}")
                except Exception as e:
                    print(f"    ! Behaviour error: {e}")

    print(f"  ✓ ~{total} behaviour records — {school['name_en']}")
    return total
```

- [ ] **Step 2: Add `seed_product_hub_issues()` — insert before `main()`**

```python
# ─── Step 10b: Product Hub Issues ────────────────────────────────────────────

async def seed_product_hub_issues(
    school: dict, token: str, admin_user: dict
) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    total = 0

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        for issue_tmpl in PRODUCT_ISSUES:
            payload = {
                "title": issue_tmpl["title"],
                "issue_type": issue_tmpl["issue_type"],
                "priority": issue_tmpl["priority"],
                "status": issue_tmpl["status"],
                "current_behavior": f"المشكلة: {issue_tmpl['title']}",
                "expected_behavior": "يجب أن يعمل النظام بشكل صحيح",
                "section": "الجدول الدراسي",
                "account_type": "school_admin",
                "employee_name": admin_user.get("full_name", "مدير المدرسة"),
                "device": "Desktop",
                "browser": "Chrome",
            }
            try:
                resp = await client.post("/product-hub/issues", json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    total += 1
                else:
                    print(f"    ! Product hub warn {resp.status_code}: {resp.text[:80]}")
            except Exception as e:
                print(f"    ! Product hub error: {e}")

    print(f"  ✓ {total} product hub issues — {school['name_en']}")
    return total
```

- [ ] **Step 3: Wire both into `main()` — extend the operational data loop**

In `main()`, inside the `for code, school in schools.items():` loop under step 9, add after `seed_attendance(...)`:

```python
        teachers = school_users[code]["teachers"]
        admin_record = school_users[code]["admins"][0] if school_users[code]["admins"] else {}
        await seed_behaviour_records(school, token, students, teachers)
        await seed_product_hub_issues(school, token, admin_record)
```

- [ ] **Step 4: Run and verify**

```bash
cd backend && python scripts/seed_test_data.py
```
Expected output includes:
```
  ✓ ~xxxx behaviour records — Al-Farabi School
  ✓ 10 product hub issues — Al-Farabi School
```

---

## Task 9: Write TEST_CREDENTIALS.md

**Files:**
- Modify: `backend/scripts/seed_test_data.py`

- [ ] **Step 1: Add `write_credentials_file()` — insert before `main()`**

```python
# ─── Step 11: Credentials File ───────────────────────────────────────────────

def write_credentials_file(
    schools: dict,
    platform_admin: dict,
    school_users: dict,
    school_populations: dict,
) -> None:
    """Write TEST_CREDENTIALS.md to the project root."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_path = os.path.join(project_root, "TEST_CREDENTIALS.md")

    lines = [
        "# NASSAQ — Test Credentials",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> Default password for ALL accounts: `{DEFAULT_PASSWORD}`",
        "",
        "---",
        "",
        "## Platform Admin (cross-school)",
        "",
        f"| Role | Email | Password |",
        f"|---|---|---|",
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
            f"**School Code:** `{code}` | **City:** {school['city']}",
            "",
            "### Administrators",
            "| Role | Email | Password |",
            "|---|---|---|",
        ]
        for admin in users["admins"]:
            lines.append(f"| School Admin | {admin['email']} | {DEFAULT_PASSWORD} |")

        lines += [
            "",
            "### Teachers (sample — first 5)",
            "| Name | Email | Specialization | Password |",
            "|---|---|---|---|",
        ]
        for t in users["teachers"][:5]:
            lines.append(
                f"| {t['teacher']['full_name']} | {t['email']} | {t['teacher']['specialization']} | {DEFAULT_PASSWORD} |"
            )
        lines.append(f"| *(+{len(users['teachers']) - 5} more teachers)* | ... | | |")

        lines += [
            "",
            "### Parents (sample — first 5)",
            "| Name | Email | Password |",
            "|---|---|---|",
        ]
        for p in pops["parents"][:5]:
            lines.append(f"| {p['parent']['full_name']} | {p['email']} | {DEFAULT_PASSWORD} |")
        lines.append(f"| *(+{len(pops['parents']) - 5} more parents)* | ... | | |")

        lines += [
            "",
            f"**Total students:** {len(pops['students'])}",
            f"**Total parents:** {len(pops['parents'])}",
            "",
            "---",
            "",
        ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  ✓ TEST_CREDENTIALS.md written to {out_path}")
```

- [ ] **Step 2: Call it from `main()` — add after the operational data loop**

```python
    print("[10/10] Writing TEST_CREDENTIALS.md...")
    write_credentials_file(schools, platform_admin, school_users, school_populations)
```

- [ ] **Step 3: Run and check the file exists**

```bash
cd backend && python scripts/seed_test_data.py && ls -la ../TEST_CREDENTIALS.md
```
Expected: file exists with non-zero size.

---

## Task 10: Final Summary Print and Full End-to-End Run

**Files:**
- Modify: `backend/scripts/seed_test_data.py`

- [ ] **Step 1: Add summary block to end of `main()`**

After `write_credentials_file(...)`:

```python
    # Summary
    print("\n" + "=" * 60)
    print("NASSAQ Test Data Seed — Complete")
    print("=" * 60)
    for code, school in schools.items():
        pops = school_populations[code]
        academics = school_academics[code]
        timetable_info = school_timetables[code]
        print(f"\n{school['name_en']} ({code}):")
        print(f"  Students : {len(pops['students'])}")
        print(f"  Parents  : {len(pops['parents'])}")
        print(f"  Teachers : {len(school_users[code]['teachers'])}")
        print(f"  Classes  : {len(academics['classes'])}")
        print(f"  Subjects : {len(academics['subjects'])}")
        print(f"  Sessions : {len(timetable_info['sessions'])}")
    print(f"\nLogin with any account using password: {DEFAULT_PASSWORD}")
    print("See TEST_CREDENTIALS.md for the full list.\n")
```

- [ ] **Step 2: Do a full clean run against the live backend**

Ensure Backend API workflow is running (`http://localhost:8000/api/health` or similar returns 200).

```bash
cd backend && python scripts/seed_test_data.py 2>&1 | tee /tmp/seed_run.log
```

- [ ] **Step 3: Verify success criteria from the spec**

```bash
# Check school count
cd backend && python -c "
import asyncio
from scripts.seed_db_helper import get_seed_db
from engines.sql_utils import gd_count

async def check():
    async with get_seed_db() as db:
        schools = await gd_count(db.session, 'schools', {'status': 'active'})
        teachers = await gd_count(db.session, 'teachers', {})
        students = await gd_count(db.session, 'students', {})
        parents = await gd_count(db.session, 'parents', {})
        sessions = await gd_count(db.session, 'schedule_sessions', {})
        print(f'Schools: {schools}')
        print(f'Teachers: {teachers}')
        print(f'Students: {students}')
        print(f'Parents: {parents}')
        print(f'Schedule sessions: {sessions}')

asyncio.run(check())
"
```

Expected output:
```
Schools: 2       (at minimum — may include pre-existing schools)
Teachers: 36     (18 per school)
Students: 504    (252 per school)
Parents: 504
Schedule sessions: 1260   (630 per school)
```

- [ ] **Step 4: Verify TEST_CREDENTIALS.md is readable and correct**

```bash
head -40 TEST_CREDENTIALS.md
```
Expected: Shows platform admin credentials, then School A and School B sections with admin and teacher emails.

---

## Self-Review Checklist

- [x] Two schools created with distinct codes, regions, types — **Task 3**
- [x] All 5 roles covered: platform_admin, school_admin, teacher, parent, (student via parent) — **Task 4–5**
- [x] 18 classes per school (12 grades, grades 1-6 have 2 sections) — **Task 5**
- [x] 14 subjects with correct categories — **Task 5**
- [x] 8 time slots including break, Gulf work week — **Task 6**
- [x] Teacher assignments covering all classes — **Task 6**
- [x] Timetable + 630 schedule sessions per school — **Task 6**
- [x] 4 weeks of bulk attendance via API — **Task 7**
- [x] 3–5 behaviour records per student via API — **Task 8**
- [x] 10 product hub issues per school via API — **Task 8**
- [x] TEST_CREDENTIALS.md written — **Task 9**
- [x] Idempotency: all inserts use `upsert()` — **Task 2**
- [x] Summary statistics printed — **Task 10**
