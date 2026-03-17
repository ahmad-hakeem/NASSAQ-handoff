"""
Script to seed exact test data as specified by user
- 2 schools (مدرسة النور, مدرسة الأحساء)
- 5 teachers per school with specific availability exceptions
- 25 students per school distributed across 3 classes
- Administrative constraints per school
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
import bcrypt

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# Protected accounts (DO NOT DELETE)
PROTECTED_EMAILS = [
    'admin@nassaq.com',
    'principal1@nassaq.com',
    'principal4@nassaq.com',
    'teacher1@nor.edu.sa',
    'student1@nor.edu.sa',
    'parent1@nor.edu.sa'
]

# ============================================
# SCHOOL DATA
# ============================================

SCHOOLS = [
    {
        "id": "SCH-001",
        "name": "مدرسة النور",
        "name_en": "Al Noor School",
        "email": "principal1@nassaq.com",
        "phone": "0500001001",
        "city": "الرياض",
        "region": "الياسمين",
        "address": "حي الياسمين، الرياض، المملكة العربية السعودية",
        "country": "SA",
        "status": "active",
        "principal_email": "principal1@nassaq.com",
        "principal_name": "الأستاذ طلال أحمد",
        "code": "NSS-SA-26-0001"
    },
    {
        "id": "SCH-002",
        "name": "مدرسة الأحساء",
        "name_en": "Al Ahsa School",
        "email": "principal4@nassaq.com",
        "phone": "0500004004",
        "city": "الأحساء",
        "region": "الهفوف",
        "address": "حي الهفوف، الأحساء، المملكة العربية السعودية",
        "country": "SA",
        "status": "active",
        "principal_email": "principal4@nassaq.com",
        "principal_name": "الأستاذ محمد عبد العزيز",
        "code": "NSS-SA-26-0002"
    }
]

# ============================================
# CLASSES DATA
# ============================================

CLASSES = [
    # مدرسة النور
    {"id": "SCH-001-1A", "school_id": "SCH-001", "grade_id": "grade-1", "section": "أ", "name_ar": "الصف الأول الابتدائي - أ", "name_en": "Grade 1 - A", "capacity": 25},
    {"id": "SCH-001-2A", "school_id": "SCH-001", "grade_id": "grade-2", "section": "أ", "name_ar": "الصف الثاني الابتدائي - أ", "name_en": "Grade 2 - A", "capacity": 25},
    {"id": "SCH-001-7A", "school_id": "SCH-001", "grade_id": "grade-7", "section": "أ", "name_ar": "الصف الأول المتوسط - أ", "name_en": "Grade 7 - A", "capacity": 25},
    # مدرسة الأحساء
    {"id": "SCH-002-1A", "school_id": "SCH-002", "grade_id": "grade-1", "section": "أ", "name_ar": "الصف الأول الابتدائي - أ", "name_en": "Grade 1 - A", "capacity": 25},
    {"id": "SCH-002-2A", "school_id": "SCH-002", "grade_id": "grade-2", "section": "أ", "name_ar": "الصف الثاني الابتدائي - أ", "name_en": "Grade 2 - A", "capacity": 25},
    {"id": "SCH-002-7A", "school_id": "SCH-002", "grade_id": "grade-7", "section": "أ", "name_ar": "الصف الأول المتوسط - أ", "name_en": "Grade 7 - A", "capacity": 25},
]

# ============================================
# TEACHERS DATA
# ============================================

# Default full availability
DEFAULT_AVAILABILITY = {
    "sunday": [1, 2, 3, 4, 5, 6, 7],
    "monday": [1, 2, 3, 4, 5, 6, 7],
    "tuesday": [1, 2, 3, 4, 5, 6, 7],
    "wednesday": [1, 2, 3, 4, 5, 6, 7],
    "thursday": [1, 2, 3, 4, 5, 6, 7],
}

TEACHERS = [
    # معلمو مدرسة النور
    {
        "id": "TCH-N-001",
        "school_id": "SCH-001",
        "full_name_ar": "أحمد عبد الرحمن",
        "full_name_en": "Ahmed Abdulrahman",
        "email": "teacher1@nor.edu.sa",
        "phone": "+966501111001",
        "subjects": ["subj-arabic"],
        "subject_name": "لغتي / لغة عربية",
        "rank_id": "rank-practitioner",
        "rank_name": "المعلم الممارس",
        "weekly_periods": 24,
        "gender": "male",
        "availability": {
            "sunday": [2, 3, 4, 5, 6, 7],  # غير متاح الحصة الأولى يوم الأحد
            "monday": [1, 2, 3, 4, 5, 6, 7],
            "tuesday": [1, 2, 3, 4, 5, 6, 7],
            "wednesday": [1, 2, 3, 4, 5, 6, 7],
            "thursday": [1, 2, 3, 4, 5, 6, 7],
        }
    },
    {
        "id": "TCH-N-002",
        "school_id": "SCH-001",
        "full_name_ar": "منى علي",
        "full_name_en": "Muna Ali",
        "email": "teacher2@nor.edu.sa",
        "phone": "+966501111002",
        "subjects": ["subj-math"],
        "subject_name": "الرياضيات",
        "rank_id": "rank-teacher",
        "rank_name": "المعلم",
        "weekly_periods": 24,
        "gender": "female",
        "availability": DEFAULT_AVAILABILITY.copy()
    },
    {
        "id": "TCH-N-003",
        "school_id": "SCH-001",
        "full_name_ar": "خالد السبيعي",
        "full_name_en": "Khalid Al-Subaie",
        "email": "teacher3@nor.edu.sa",
        "phone": "+966501111003",
        "subjects": ["subj-science"],
        "subject_name": "العلوم",
        "rank_id": "rank-advanced",
        "rank_name": "المعلم المتقدم",
        "weekly_periods": 22,
        "gender": "male",
        "availability": DEFAULT_AVAILABILITY.copy()
    },
    {
        "id": "TCH-N-004",
        "school_id": "SCH-001",
        "full_name_ar": "سارة محمد",
        "full_name_en": "Sara Mohammed",
        "email": "teacher4@nor.edu.sa",
        "phone": "+966501111004",
        "subjects": ["subj-english"],
        "subject_name": "اللغة الإنجليزية",
        "rank_id": "rank-expert",
        "rank_name": "المعلم الخبير",
        "weekly_periods": 18,
        "gender": "female",
        "availability": {
            "sunday": [1, 2, 3, 4, 5, 6, 7],
            "monday": [1, 2, 3, 4, 5, 6, 7],
            "tuesday": [1, 2, 3, 4, 5, 6, 7],
            "wednesday": [1, 2, 3, 4, 5, 6],  # غير متاحة الحصة السابعة يوم الأربعاء
            "thursday": [1, 2, 3, 4, 5, 6, 7],
        }
    },
    {
        "id": "TCH-N-005",
        "school_id": "SCH-001",
        "full_name_ar": "عبد الله الحربي",
        "full_name_en": "Abdullah Al-Harbi",
        "email": "teacher5@nor.edu.sa",
        "phone": "+966501111005",
        "subjects": ["subj-islamic", "subj-quran"],
        "subject_name": "الدراسات الإسلامية / القرآن الكريم",
        "rank_id": "rank-practitioner",
        "rank_name": "المعلم الممارس",
        "weekly_periods": 24,
        "gender": "male",
        "availability": DEFAULT_AVAILABILITY.copy()
    },
    # معلمو مدرسة الأحساء
    {
        "id": "TCH-A-001",
        "school_id": "SCH-002",
        "full_name_ar": "يوسف عادل",
        "full_name_en": "Youssef Adel",
        "email": "teacher1@ahsa.edu.sa",
        "phone": "+966502222001",
        "subjects": ["subj-arabic"],
        "subject_name": "لغتي / لغة عربية",
        "rank_id": "rank-practitioner",
        "rank_name": "المعلم الممارس",
        "weekly_periods": 24,
        "gender": "male",
        "availability": {
            "sunday": [1, 2, 3, 4, 5, 6, 7],
            "monday": [2, 3, 4, 5, 6, 7],  # غير متاح الحصة الأولى يوم الإثنين
            "tuesday": [1, 2, 3, 4, 5, 6, 7],
            "wednesday": [1, 2, 3, 4, 5, 6, 7],
            "thursday": [1, 2, 3, 4, 5, 6, 7],
        }
    },
    {
        "id": "TCH-A-002",
        "school_id": "SCH-002",
        "full_name_ar": "هبة عبد العزيز",
        "full_name_en": "Heba Abdulaziz",
        "email": "teacher2@ahsa.edu.sa",
        "phone": "+966502222002",
        "subjects": ["subj-math"],
        "subject_name": "الرياضيات",
        "rank_id": "rank-teacher",
        "rank_name": "المعلم",
        "weekly_periods": 24,
        "gender": "female",
        "availability": DEFAULT_AVAILABILITY.copy()
    },
    {
        "id": "TCH-A-003",
        "school_id": "SCH-002",
        "full_name_ar": "إبراهيم حسن",
        "full_name_en": "Ibrahim Hassan",
        "email": "teacher3@ahsa.edu.sa",
        "phone": "+966502222003",
        "subjects": ["subj-science"],
        "subject_name": "العلوم",
        "rank_id": "rank-advanced",
        "rank_name": "المعلم المتقدم",
        "weekly_periods": 22,
        "gender": "male",
        "availability": DEFAULT_AVAILABILITY.copy()
    },
    {
        "id": "TCH-A-004",
        "school_id": "SCH-002",
        "full_name_ar": "آلاء كمال",
        "full_name_en": "Alaa Kamal",
        "email": "teacher4@ahsa.edu.sa",
        "phone": "+966502222004",
        "subjects": ["subj-english"],
        "subject_name": "اللغة الإنجليزية",
        "rank_id": "rank-expert",
        "rank_name": "المعلم الخبير",
        "weekly_periods": 18,
        "gender": "female",
        "availability": {
            "sunday": [1, 2, 3, 4, 5, 6, 7],
            "monday": [1, 2, 3, 4, 5, 6, 7],
            "tuesday": [3, 4, 5, 6, 7],  # غير متاحة الحصتين الأولى والثانية يوم الثلاثاء
            "wednesday": [1, 2, 3, 4, 5, 6, 7],
            "thursday": [1, 2, 3, 4, 5, 6, 7],
        }
    },
    {
        "id": "TCH-A-005",
        "school_id": "SCH-002",
        "full_name_ar": "محمد جابر",
        "full_name_en": "Mohammed Jaber",
        "email": "teacher5@ahsa.edu.sa",
        "phone": "+966502222005",
        "subjects": ["subj-islamic", "subj-quran"],
        "subject_name": "الدراسات الإسلامية / القرآن الكريم",
        "rank_id": "rank-practitioner",
        "rank_name": "المعلم الممارس",
        "weekly_periods": 24,
        "gender": "male",
        "availability": DEFAULT_AVAILABILITY.copy()
    },
]

# ============================================
# STUDENTS DATA
# ============================================

STUDENTS = [
    # مدرسة النور - الصف الأول الابتدائي (10 طلاب)
    {"id": "STU-N-001", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "عبد الرحمن أحمد", "gender": "male"},
    {"id": "STU-N-002", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "محمد خالد", "gender": "male"},
    {"id": "STU-N-003", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "يوسف سامي", "gender": "male"},
    {"id": "STU-N-004", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "عمر ياسر", "gender": "male"},
    {"id": "STU-N-005", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "نايف سعد", "gender": "male"},
    {"id": "STU-N-006", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "لينا محمود", "gender": "female"},
    {"id": "STU-N-007", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "جود علي", "gender": "female"},
    {"id": "STU-N-008", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "ريم عادل", "gender": "female"},
    {"id": "STU-N-009", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "سارة إبراهيم", "gender": "female"},
    {"id": "STU-N-010", "school_id": "SCH-001", "class_id": "SCH-001-1A", "grade_id": "grade-1", "full_name_ar": "تالا فهد", "gender": "female"},
    # مدرسة النور - الصف الثاني الابتدائي (8 طلاب)
    {"id": "STU-N-011", "school_id": "SCH-001", "class_id": "SCH-001-2A", "grade_id": "grade-2", "full_name_ar": "فهد محمد", "gender": "male"},
    {"id": "STU-N-012", "school_id": "SCH-001", "class_id": "SCH-001-2A", "grade_id": "grade-2", "full_name_ar": "نورة علي", "gender": "female"},
    {"id": "STU-N-013", "school_id": "SCH-001", "class_id": "SCH-001-2A", "grade_id": "grade-2", "full_name_ar": "هيا خالد", "gender": "female"},
    {"id": "STU-N-014", "school_id": "SCH-001", "class_id": "SCH-001-2A", "grade_id": "grade-2", "full_name_ar": "ريان عبد الله", "gender": "male"},
    {"id": "STU-N-015", "school_id": "SCH-001", "class_id": "SCH-001-2A", "grade_id": "grade-2", "full_name_ar": "مشعل سعد", "gender": "male"},
    {"id": "STU-N-016", "school_id": "SCH-001", "class_id": "SCH-001-2A", "grade_id": "grade-2", "full_name_ar": "جنى ياسر", "gender": "female"},
    {"id": "STU-N-017", "school_id": "SCH-001", "class_id": "SCH-001-2A", "grade_id": "grade-2", "full_name_ar": "عبد العزيز فهد", "gender": "male"},
    {"id": "STU-N-018", "school_id": "SCH-001", "class_id": "SCH-001-2A", "grade_id": "grade-2", "full_name_ar": "لمى إبراهيم", "gender": "female"},
    # مدرسة النور - الصف الأول المتوسط (7 طلاب)
    {"id": "STU-N-019", "school_id": "SCH-001", "class_id": "SCH-001-7A", "grade_id": "grade-7", "full_name_ar": "عبد الملك سالم", "gender": "male"},
    {"id": "STU-N-020", "school_id": "SCH-001", "class_id": "SCH-001-7A", "grade_id": "grade-7", "full_name_ar": "ريتال محمد", "gender": "female"},
    {"id": "STU-N-021", "school_id": "SCH-001", "class_id": "SCH-001-7A", "grade_id": "grade-7", "full_name_ar": "أروى حسن", "gender": "female"},
    {"id": "STU-N-022", "school_id": "SCH-001", "class_id": "SCH-001-7A", "grade_id": "grade-7", "full_name_ar": "فيصل عادل", "gender": "male"},
    {"id": "STU-N-023", "school_id": "SCH-001", "class_id": "SCH-001-7A", "grade_id": "grade-7", "full_name_ar": "دانة خالد", "gender": "female"},
    {"id": "STU-N-024", "school_id": "SCH-001", "class_id": "SCH-001-7A", "grade_id": "grade-7", "full_name_ar": "راكان أحمد", "gender": "male"},
    {"id": "STU-N-025", "school_id": "SCH-001", "class_id": "SCH-001-7A", "grade_id": "grade-7", "full_name_ar": "تيم عبد الله", "gender": "male"},
    # مدرسة الأحساء - الصف الأول الابتدائي (10 طلاب)
    {"id": "STU-A-001", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "زياد سامر", "gender": "male"},
    {"id": "STU-A-002", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "أنس فهد", "gender": "male"},
    {"id": "STU-A-003", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "حاتم علي", "gender": "male"},
    {"id": "STU-A-004", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "طلال خالد", "gender": "male"},
    {"id": "STU-A-005", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "راما إبراهيم", "gender": "female"},
    {"id": "STU-A-006", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "جنى حسين", "gender": "female"},
    {"id": "STU-A-007", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "رفيف سعد", "gender": "female"},
    {"id": "STU-A-008", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "حور محمد", "gender": "female"},
    {"id": "STU-A-009", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "ديم عبد الله", "gender": "female"},
    {"id": "STU-A-010", "school_id": "SCH-002", "class_id": "SCH-002-1A", "grade_id": "grade-1", "full_name_ar": "تالا ياسر", "gender": "female"},
    # مدرسة الأحساء - الصف الثاني الابتدائي (8 طلاب)
    {"id": "STU-A-011", "school_id": "SCH-002", "class_id": "SCH-002-2A", "grade_id": "grade-2", "full_name_ar": "راشد أحمد", "gender": "male"},
    {"id": "STU-A-012", "school_id": "SCH-002", "class_id": "SCH-002-2A", "grade_id": "grade-2", "full_name_ar": "لجين فهد", "gender": "female"},
    {"id": "STU-A-013", "school_id": "SCH-002", "class_id": "SCH-002-2A", "grade_id": "grade-2", "full_name_ar": "بيان علي", "gender": "female"},
    {"id": "STU-A-014", "school_id": "SCH-002", "class_id": "SCH-002-2A", "grade_id": "grade-2", "full_name_ar": "عمر سامي", "gender": "male"},
    {"id": "STU-A-015", "school_id": "SCH-002", "class_id": "SCH-002-2A", "grade_id": "grade-2", "full_name_ar": "ميار خالد", "gender": "female"},
    {"id": "STU-A-016", "school_id": "SCH-002", "class_id": "SCH-002-2A", "grade_id": "grade-2", "full_name_ar": "شهد ناصر", "gender": "female"},
    {"id": "STU-A-017", "school_id": "SCH-002", "class_id": "SCH-002-2A", "grade_id": "grade-2", "full_name_ar": "يزن عبد الرحمن", "gender": "male"},
    {"id": "STU-A-018", "school_id": "SCH-002", "class_id": "SCH-002-2A", "grade_id": "grade-2", "full_name_ar": "تركي محمد", "gender": "male"},
    # مدرسة الأحساء - الصف الأول المتوسط (7 طلاب)
    {"id": "STU-A-019", "school_id": "SCH-002", "class_id": "SCH-002-7A", "grade_id": "grade-7", "full_name_ar": "جاسم فهد", "gender": "male"},
    {"id": "STU-A-020", "school_id": "SCH-002", "class_id": "SCH-002-7A", "grade_id": "grade-7", "full_name_ar": "ليان إبراهيم", "gender": "female"},
    {"id": "STU-A-021", "school_id": "SCH-002", "class_id": "SCH-002-7A", "grade_id": "grade-7", "full_name_ar": "رؤى خالد", "gender": "female"},
    {"id": "STU-A-022", "school_id": "SCH-002", "class_id": "SCH-002-7A", "grade_id": "grade-7", "full_name_ar": "عبد الرحمن عادل", "gender": "male"},
    {"id": "STU-A-023", "school_id": "SCH-002", "class_id": "SCH-002-7A", "grade_id": "grade-7", "full_name_ar": "مريم سامر", "gender": "female"},
    {"id": "STU-A-024", "school_id": "SCH-002", "class_id": "SCH-002-7A", "grade_id": "grade-7", "full_name_ar": "مهند عبد الله", "gender": "male"},
    {"id": "STU-A-025", "school_id": "SCH-002", "class_id": "SCH-002-7A", "grade_id": "grade-7", "full_name_ar": "نواف حسن", "gender": "male"},
]

# ============================================
# TEACHER CONSTRAINTS
# ============================================

TEACHER_CONSTRAINTS = [
    # مدرسة النور
    {
        "id": "tc-n-001",
        "school_id": "SCH-001",
        "teacher_id": "TCH-N-001",
        "teacher_name": "أحمد عبد الرحمن",
        "constraint_type": "unavailable",
        "day": "sunday",
        "periods": [1],
        "description_ar": "أحمد عبد الرحمن لا يبدأ الحصة الأولى يوم الأحد",
        "description_en": "Ahmed Abdulrahman not available for first period on Sunday"
    },
    {
        "id": "tc-n-002",
        "school_id": "SCH-001",
        "teacher_id": "TCH-N-004",
        "teacher_name": "سارة محمد",
        "constraint_type": "unavailable",
        "day": "wednesday",
        "periods": [7],
        "description_ar": "سارة محمد لا تعمل الحصة السابعة يوم الأربعاء",
        "description_en": "Sara Mohammed not available for 7th period on Wednesday"
    },
    # مدرسة الأحساء
    {
        "id": "tc-a-001",
        "school_id": "SCH-002",
        "teacher_id": "TCH-A-001",
        "teacher_name": "يوسف عادل",
        "constraint_type": "unavailable",
        "day": "monday",
        "periods": [1],
        "description_ar": "يوسف عادل لا يبدأ الحصة الأولى يوم الإثنين",
        "description_en": "Youssef Adel not available for first period on Monday"
    },
    {
        "id": "tc-a-002",
        "school_id": "SCH-002",
        "teacher_id": "TCH-A-004",
        "teacher_name": "آلاء كمال",
        "constraint_type": "unavailable",
        "day": "tuesday",
        "periods": [1, 2],
        "description_ar": "آلاء كمال لا تعمل الحصتين الأولى والثانية يوم الثلاثاء",
        "description_en": "Alaa Kamal not available for 1st and 2nd periods on Tuesday"
    },
]


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc)
    
    print("=" * 70)
    print("🚀 بدء تثبيت بيانات الاختبار - المرحلة الثالثة")
    print("=" * 70)
    
    # ============================================
    # STEP 1: Clean old data (except protected)
    # ============================================
    print("\n[1/7] 🧹 تنظيف البيانات القديمة...")
    
    # Delete old schools (except new ones)
    old_schools = await db.schools.delete_many({
        "id": {"$nin": ["SCH-001", "SCH-002"]}
    })
    print(f"  - حذف {old_schools.deleted_count} مدرسة قديمة")
    
    # Delete old school settings
    old_settings = await db.school_settings.delete_many({
        "school_id": {"$nin": ["SCH-001", "SCH-002"]}
    })
    print(f"  - حذف {old_settings.deleted_count} إعدادات قديمة")
    
    # Delete old teachers (except protected)
    protected_teacher_emails = ['teacher1@nor.edu.sa']
    old_teachers = await db.teachers.delete_many({
        "email": {"$nin": [t["email"] for t in TEACHERS]}
    })
    print(f"  - حذف {old_teachers.deleted_count} معلم قديم")
    
    # Delete old students
    old_students = await db.students.delete_many({
        "id": {"$nin": [s["id"] for s in STUDENTS]}
    })
    print(f"  - حذف {old_students.deleted_count} طالب قديم")
    
    # Delete old classes
    old_classes = await db.classes.delete_many({
        "id": {"$nin": [c["id"] for c in CLASSES]}
    })
    print(f"  - حذف {old_classes.deleted_count} فصل قديم")
    
    # Delete old users (except protected)
    new_emails = [t["email"] for t in TEACHERS] + PROTECTED_EMAILS
    old_users = await db.users.delete_many({
        "email": {"$nin": new_emails},
        "role": {"$in": ["teacher", "student", "parent", "school_principal"]}
    })
    print(f"  - حذف {old_users.deleted_count} مستخدم قديم")
    
    # ============================================
    # STEP 2: Create Schools
    # ============================================
    print("\n[2/7] 🏫 إنشاء المدارس...")
    
    for school in SCHOOLS:
        school_doc = {
            **school,
            "student_capacity": 500,
            "current_students": 0,
            "current_teachers": 0,
            "current_classes": 0,
            "language": "ar",
            "calendar_system": "hijri_gregorian",
            "school_type": "public",
            "stage": "all",
            "logo_url": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.schools.update_one(
            {"id": school["id"]},
            {"$set": school_doc},
            upsert=True
        )
        print(f"  ✓ {school['name']}")
    
    # ============================================
    # STEP 3: Apply default settings to schools
    # ============================================
    print("\n[3/7] ⚙️ تطبيق الإعدادات الافتراضية...")
    
    default_settings = await db.default_settings.find_one({"id": "default-school-settings"}, {"_id": 0})
    
    for school in SCHOOLS:
        school_settings = {
            "id": f"settings-{school['id']}",
            "school_id": school["id"],
            "working_days": default_settings.get("working_days") if default_settings else {},
            "working_days_ar": default_settings.get("working_days_ar", []) if default_settings else [],
            "working_days_en": default_settings.get("working_days_en", []) if default_settings else [],
            "weekend_days_ar": default_settings.get("weekend_days_ar", []) if default_settings else [],
            "weekend_days_en": default_settings.get("weekend_days_en", []) if default_settings else [],
            "periods_per_day": default_settings.get("periods_per_day", 7) if default_settings else 7,
            "period_duration_minutes": default_settings.get("period_duration_minutes", 45) if default_settings else 45,
            "break_duration_minutes": default_settings.get("break_duration_minutes", 20) if default_settings else 20,
            "prayer_duration_minutes": default_settings.get("prayer_duration_minutes", 20) if default_settings else 20,
            "school_day_start": default_settings.get("school_day_start", "07:00") if default_settings else "07:00",
            "school_day_end": default_settings.get("school_day_end", "13:15") if default_settings else "13:15",
            "time_slots": default_settings.get("time_slots", []) if default_settings else [],
            "education_track": "track-general",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.school_settings.update_one(
            {"school_id": school["id"]},
            {"$set": school_settings},
            upsert=True
        )
        print(f"  ✓ إعدادات {school['name']}")
    
    # ============================================
    # STEP 4: Create Classes
    # ============================================
    print("\n[4/7] 📚 إنشاء الفصول...")
    
    for cls in CLASSES:
        class_doc = {
            **cls,
            "stage_id": "stage-elementary" if cls["grade_id"] in ["grade-1", "grade-2"] else "stage-middle",
            "current_students": 0,
            "education_track": "track-general",
            "is_active": True,
            "academic_year": "2025-2026",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.classes.update_one(
            {"id": cls["id"]},
            {"$set": class_doc},
            upsert=True
        )
        school_name = "مدرسة النور" if cls["school_id"] == "SCH-001" else "مدرسة الأحساء"
        print(f"  ✓ {cls['name_ar']} ({school_name})")
    
    # ============================================
    # STEP 5: Create Teachers with User Accounts
    # ============================================
    print("\n[5/7] 👨‍🏫 إنشاء المعلمين...")
    
    teacher_password = hash_password("Teacher@123")
    
    for teacher in TEACHERS:
        # Create user account
        user_doc = {
            "id": teacher["id"],
            "email": teacher["email"],
            "password": teacher_password,
            "full_name": teacher["full_name_ar"],
            "full_name_en": teacher["full_name_en"],
            "phone": teacher["phone"],
            "role": "teacher",
            "tenant_id": teacher["school_id"],
            "is_active": True,
            "must_change_password": False,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.users.update_one(
            {"email": teacher["email"]},
            {"$set": user_doc},
            upsert=True
        )
        
        # Create teacher profile
        teacher_doc = {
            "id": teacher["id"],
            "user_id": teacher["id"],
            "school_id": teacher["school_id"],
            "full_name_ar": teacher["full_name_ar"],
            "full_name_en": teacher["full_name_en"],
            "email": teacher["email"],
            "phone": teacher["phone"],
            "rank_id": teacher["rank_id"],
            "rank_name_ar": teacher["rank_name"],
            "rank_name_en": teacher.get("rank_name_en", ""),
            "weekly_periods": teacher["weekly_periods"],
            "subjects": teacher["subjects"],
            "subject_name": teacher["subject_name"],
            "gender": teacher["gender"],
            "availability": teacher["availability"],
            "is_active": True,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.teachers.update_one(
            {"id": teacher["id"]},
            {"$set": teacher_doc},
            upsert=True
        )
        
        school_name = "مدرسة النور" if teacher["school_id"] == "SCH-001" else "مدرسة الأحساء"
        print(f"  ✓ {teacher['full_name_ar']} - {teacher['subject_name']} ({school_name})")
    
    # ============================================
    # STEP 6: Create Students with User Accounts
    # ============================================
    print("\n[6/7] 👨‍🎓 إنشاء الطلاب...")
    
    student_password = hash_password("Student@123")
    student_counter = {"SCH-001": 0, "SCH-002": 0}
    
    for student in STUDENTS:
        school_code = "nor" if student["school_id"] == "SCH-001" else "ahsa"
        student_counter[student["school_id"]] += 1
        email = f"student{student_counter[student['school_id']]}@{school_code}.edu.sa"
        
        # Create user account
        user_doc = {
            "id": student["id"],
            "email": email,
            "password": student_password,
            "full_name": student["full_name_ar"],
            "role": "student",
            "tenant_id": student["school_id"],
            "is_active": True,
            "preferred_language": "ar",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.users.update_one(
            {"email": email},
            {"$set": user_doc},
            upsert=True
        )
        
        # Create student profile
        student_doc = {
            "id": student["id"],
            "user_id": student["id"],
            "school_id": student["school_id"],
            "class_id": student["class_id"],
            "grade_id": student["grade_id"],
            "full_name_ar": student["full_name_ar"],
            "email": email,
            "gender": student["gender"],
            "student_number": student["id"],
            "enrollment_date": now.strftime("%Y-%m-%d"),
            "is_active": True,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.students.update_one(
            {"id": student["id"]},
            {"$set": student_doc},
            upsert=True
        )
    
    # Count per school
    nor_students = len([s for s in STUDENTS if s["school_id"] == "SCH-001"])
    ahsa_students = len([s for s in STUDENTS if s["school_id"] == "SCH-002"])
    print(f"  ✓ مدرسة النور: {nor_students} طالب")
    print(f"  ✓ مدرسة الأحساء: {ahsa_students} طالب")
    
    # ============================================
    # STEP 7: Create Teacher Constraints
    # ============================================
    print("\n[7/7] 🚫 إنشاء القيود الإدارية الخاصة...")
    
    for constraint in TEACHER_CONSTRAINTS:
        constraint_doc = {
            **constraint,
            "is_active": True,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.teacher_constraints.update_one(
            {"id": constraint["id"]},
            {"$set": constraint_doc},
            upsert=True
        )
        print(f"  ✓ {constraint['description_ar']}")
    
    # ============================================
    # Update school statistics
    # ============================================
    print("\n📊 تحديث إحصائيات المدارس...")
    
    for school in SCHOOLS:
        school_id = school["id"]
        students_count = await db.students.count_documents({"school_id": school_id})
        teachers_count = await db.teachers.count_documents({"school_id": school_id})
        classes_count = await db.classes.count_documents({"school_id": school_id})
        
        await db.schools.update_one(
            {"id": school_id},
            {"$set": {
                "current_students": students_count,
                "current_teachers": teachers_count,
                "current_classes": classes_count,
                "updated_at": now.isoformat()
            }}
        )
        print(f"  ✓ {school['name']}: {students_count} طالب، {teachers_count} معلم، {classes_count} فصل")
    
    # Update class student counts
    for cls in CLASSES:
        count = await db.students.count_documents({"class_id": cls["id"]})
        await db.classes.update_one(
            {"id": cls["id"]},
            {"$set": {"current_students": count}}
        )
    
    # ============================================
    # Create Principal Accounts
    # ============================================
    print("\n👔 إنشاء حسابات مديري المدارس...")
    
    principal_password = hash_password("Principal@123")
    
    principals = [
        {
            "id": "principal-001",
            "email": "principal1@nassaq.com",
            "full_name": "الأستاذ طلال أحمد",
            "tenant_id": "SCH-001"
        },
        {
            "id": "principal-004",
            "email": "principal4@nassaq.com",
            "full_name": "الأستاذ محمد عبد العزيز",
            "tenant_id": "SCH-002"
        }
    ]
    
    for principal in principals:
        user_doc = {
            "id": principal["id"],
            "email": principal["email"],
            "password": principal_password,
            "full_name": principal["full_name"],
            "role": "school_principal",
            "tenant_id": principal["tenant_id"],
            "is_active": True,
            "preferred_language": "ar",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        await db.users.update_one(
            {"email": principal["email"]},
            {"$set": user_doc},
            upsert=True
        )
        school_name = "مدرسة النور" if principal["tenant_id"] == "SCH-001" else "مدرسة الأحساء"
        print(f"  ✓ {principal['full_name']} ({school_name})")
    
    # ============================================
    # Summary
    # ============================================
    print("\n" + "=" * 70)
    print("✅ اكتمل تثبيت بيانات الاختبار بنجاح!")
    print("=" * 70)
    
    print("\n📊 ملخص البيانات:")
    print(f"  • المدارس: 2")
    print(f"  • الفصول: 6 (3 لكل مدرسة)")
    print(f"  • المعلمين: 10 (5 لكل مدرسة)")
    print(f"  • الطلاب: 50 (25 لكل مدرسة)")
    print(f"  • القيود الإدارية: 4")
    
    print("\n📝 توزيع الطلاب:")
    print("  مدرسة النور:")
    print("    - الصف الأول الابتدائي: 10 طلاب")
    print("    - الصف الثاني الابتدائي: 8 طلاب")
    print("    - الصف الأول المتوسط: 7 طلاب")
    print("  مدرسة الأحساء:")
    print("    - الصف الأول الابتدائي: 10 طلاب")
    print("    - الصف الثاني الابتدائي: 8 طلاب")
    print("    - الصف الأول المتوسط: 7 طلاب")
    
    print("\n🔑 بيانات الدخول:")
    print("  مدير المنصة: admin@nassaq.com / Admin@123")
    print("  مدير مدرسة النور: principal1@nassaq.com / Principal@123")
    print("  مدير مدرسة الأحساء: principal4@nassaq.com / Principal@123")
    print("  معلم (النور): teacher1@nor.edu.sa / Teacher@123")
    print("  معلم (الأحساء): teacher1@ahsa.edu.sa / Teacher@123")
    print("  طالب (النور): student1@nor.edu.sa / Student@123")
    print("  طالب (الأحساء): student1@ahsa.edu.sa / Student@123")


if __name__ == "__main__":
    asyncio.run(main())
