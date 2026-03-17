"""
Official Curriculum Seed Data Script
سكريبت تثبيت بيانات المنهج الرسمي الكامل

This script seeds all official curriculum data including:
- Stages (المراحل)
- Tracks (المسارات)
- Grades (الصفوف/السنوات)
- Subjects (المواد)
- Subject Details per Grade/Track (توزيع المواد)
- Teacher Rank Loads (النصاب الرسمي)

ALL DATA IS READ-ONLY AND CANNOT BE MODIFIED BY SCHOOL PRINCIPALS
"""

import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import uuid

# Database connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

# ============================================
# OFFICIAL STAGES - المراحل الدراسية الرسمية
# ============================================
OFFICIAL_STAGES = [
    {
        "id": "stage-primary",
        "name_ar": "المرحلة الابتدائية",
        "name_en": "Primary Stage",
        "order": 1,
        "grades_count": 6,
        "is_official": True,
        "is_locked": True
    },
    {
        "id": "stage-middle",
        "name_ar": "المرحلة المتوسطة",
        "name_en": "Middle Stage",
        "order": 2,
        "grades_count": 3,
        "is_official": True,
        "is_locked": True
    },
    {
        "id": "stage-secondary",
        "name_ar": "المرحلة الثانوية",
        "name_en": "Secondary Stage",
        "order": 3,
        "grades_count": 3,
        "is_official": True,
        "is_locked": True
    }
]

# ============================================
# OFFICIAL TRACKS - المسارات التعليمية الرسمية
# ============================================
OFFICIAL_TRACKS = [
    {
        "id": "track-general",
        "name_ar": "التعليم العام",
        "name_en": "General Education",
        "applicable_stages": ["stage-primary", "stage-middle"],
        "order": 1,
        "is_official": True,
        "is_locked": True
    },
    {
        "id": "track-quran",
        "name_ar": "تحفيظ القرآن الكريم",
        "name_en": "Quran Memorization",
        "applicable_stages": ["stage-primary", "stage-middle"],
        "order": 2,
        "is_official": True,
        "is_locked": True
    },
    {
        "id": "track-common-first-year",
        "name_ar": "السنة الأولى المشتركة",
        "name_en": "Common First Year",
        "applicable_stages": ["stage-secondary"],
        "order": 3,
        "is_official": True,
        "is_locked": True
    },
    {
        "id": "track-sec-general",
        "name_ar": "المسار العام",
        "name_en": "General Track",
        "applicable_stages": ["stage-secondary"],
        "order": 4,
        "is_official": True,
        "is_locked": True
    },
    {
        "id": "track-sec-cs-eng",
        "name_ar": "مسار علوم الحاسب والهندسة",
        "name_en": "Computer Science & Engineering Track",
        "applicable_stages": ["stage-secondary"],
        "order": 5,
        "is_official": True,
        "is_locked": True
    },
    {
        "id": "track-sec-health",
        "name_ar": "مسار الصحة والحياة",
        "name_en": "Health & Life Track",
        "applicable_stages": ["stage-secondary"],
        "order": 6,
        "is_official": True,
        "is_locked": True
    },
    {
        "id": "track-sec-business",
        "name_ar": "مسار إدارة الأعمال",
        "name_en": "Business Administration Track",
        "applicable_stages": ["stage-secondary"],
        "order": 7,
        "is_official": True,
        "is_locked": True
    },
    {
        "id": "track-sec-islamic",
        "name_ar": "المسار الشرعي",
        "name_en": "Islamic Studies Track",
        "applicable_stages": ["stage-secondary"],
        "order": 8,
        "is_official": True,
        "is_locked": True
    }
]

# ============================================
# OFFICIAL GRADES - الصفوف والسنوات الرسمية
# ============================================
OFFICIAL_GRADES = [
    # المرحلة الابتدائية - التعليم العام
    {"id": "grade-p1-gen", "stage_id": "stage-primary", "track_id": "track-general", "name_ar": "الصف الأول الابتدائي", "name_en": "Grade 1 Primary", "grade_number": 1, "order": 1},
    {"id": "grade-p2-gen", "stage_id": "stage-primary", "track_id": "track-general", "name_ar": "الصف الثاني الابتدائي", "name_en": "Grade 2 Primary", "grade_number": 2, "order": 2},
    {"id": "grade-p3-gen", "stage_id": "stage-primary", "track_id": "track-general", "name_ar": "الصف الثالث الابتدائي", "name_en": "Grade 3 Primary", "grade_number": 3, "order": 3},
    {"id": "grade-p4-gen", "stage_id": "stage-primary", "track_id": "track-general", "name_ar": "الصف الرابع الابتدائي", "name_en": "Grade 4 Primary", "grade_number": 4, "order": 4},
    {"id": "grade-p5-gen", "stage_id": "stage-primary", "track_id": "track-general", "name_ar": "الصف الخامس الابتدائي", "name_en": "Grade 5 Primary", "grade_number": 5, "order": 5},
    {"id": "grade-p6-gen", "stage_id": "stage-primary", "track_id": "track-general", "name_ar": "الصف السادس الابتدائي", "name_en": "Grade 6 Primary", "grade_number": 6, "order": 6},
    
    # المرحلة الابتدائية - تحفيظ القرآن الكريم
    {"id": "grade-p1-quran", "stage_id": "stage-primary", "track_id": "track-quran", "name_ar": "الصف الأول الابتدائي (تحفيظ)", "name_en": "Grade 1 Primary (Quran)", "grade_number": 1, "order": 7},
    {"id": "grade-p2-quran", "stage_id": "stage-primary", "track_id": "track-quran", "name_ar": "الصف الثاني الابتدائي (تحفيظ)", "name_en": "Grade 2 Primary (Quran)", "grade_number": 2, "order": 8},
    {"id": "grade-p3-quran", "stage_id": "stage-primary", "track_id": "track-quran", "name_ar": "الصف الثالث الابتدائي (تحفيظ)", "name_en": "Grade 3 Primary (Quran)", "grade_number": 3, "order": 9},
    {"id": "grade-p4-quran", "stage_id": "stage-primary", "track_id": "track-quran", "name_ar": "الصف الرابع الابتدائي (تحفيظ)", "name_en": "Grade 4 Primary (Quran)", "grade_number": 4, "order": 10},
    {"id": "grade-p5-quran", "stage_id": "stage-primary", "track_id": "track-quran", "name_ar": "الصف الخامس الابتدائي (تحفيظ)", "name_en": "Grade 5 Primary (Quran)", "grade_number": 5, "order": 11},
    {"id": "grade-p6-quran", "stage_id": "stage-primary", "track_id": "track-quran", "name_ar": "الصف السادس الابتدائي (تحفيظ)", "name_en": "Grade 6 Primary (Quran)", "grade_number": 6, "order": 12},
    
    # المرحلة المتوسطة - التعليم العام
    {"id": "grade-m1-gen", "stage_id": "stage-middle", "track_id": "track-general", "name_ar": "الصف الأول المتوسط", "name_en": "Grade 1 Middle", "grade_number": 1, "order": 13},
    {"id": "grade-m2-gen", "stage_id": "stage-middle", "track_id": "track-general", "name_ar": "الصف الثاني المتوسط", "name_en": "Grade 2 Middle", "grade_number": 2, "order": 14},
    {"id": "grade-m3-gen", "stage_id": "stage-middle", "track_id": "track-general", "name_ar": "الصف الثالث المتوسط", "name_en": "Grade 3 Middle", "grade_number": 3, "order": 15},
    
    # المرحلة المتوسطة - تحفيظ القرآن الكريم
    {"id": "grade-m1-quran", "stage_id": "stage-middle", "track_id": "track-quran", "name_ar": "الصف الأول المتوسط (تحفيظ)", "name_en": "Grade 1 Middle (Quran)", "grade_number": 1, "order": 16},
    {"id": "grade-m2-quran", "stage_id": "stage-middle", "track_id": "track-quran", "name_ar": "الصف الثاني المتوسط (تحفيظ)", "name_en": "Grade 2 Middle (Quran)", "grade_number": 2, "order": 17},
    {"id": "grade-m3-quran", "stage_id": "stage-middle", "track_id": "track-quran", "name_ar": "الصف الثالث المتوسط (تحفيظ)", "name_en": "Grade 3 Middle (Quran)", "grade_number": 3, "order": 18},
    
    # المرحلة الثانوية - السنة الأولى المشتركة
    {"id": "grade-s1-common", "stage_id": "stage-secondary", "track_id": "track-common-first-year", "name_ar": "السنة الأولى المشتركة", "name_en": "Year 1 Common", "grade_number": 1, "order": 19},
    
    # المرحلة الثانوية - المسار العام
    {"id": "grade-s2-general", "stage_id": "stage-secondary", "track_id": "track-sec-general", "name_ar": "السنة الثانية - المسار العام", "name_en": "Year 2 General Track", "grade_number": 2, "order": 20},
    {"id": "grade-s3-general", "stage_id": "stage-secondary", "track_id": "track-sec-general", "name_ar": "السنة الثالثة - المسار العام", "name_en": "Year 3 General Track", "grade_number": 3, "order": 21},
    
    # المرحلة الثانوية - مسار علوم الحاسب والهندسة
    {"id": "grade-s2-cs-eng", "stage_id": "stage-secondary", "track_id": "track-sec-cs-eng", "name_ar": "السنة الثانية - مسار علوم الحاسب والهندسة", "name_en": "Year 2 CS & Engineering", "grade_number": 2, "order": 22},
    {"id": "grade-s3-cs-eng", "stage_id": "stage-secondary", "track_id": "track-sec-cs-eng", "name_ar": "السنة الثالثة - مسار علوم الحاسب والهندسة", "name_en": "Year 3 CS & Engineering", "grade_number": 3, "order": 23},
    
    # المرحلة الثانوية - مسار الصحة والحياة
    {"id": "grade-s2-health", "stage_id": "stage-secondary", "track_id": "track-sec-health", "name_ar": "السنة الثانية - مسار الصحة والحياة", "name_en": "Year 2 Health & Life", "grade_number": 2, "order": 24},
    {"id": "grade-s3-health", "stage_id": "stage-secondary", "track_id": "track-sec-health", "name_ar": "السنة الثالثة - مسار الصحة والحياة", "name_en": "Year 3 Health & Life", "grade_number": 3, "order": 25},
    
    # المرحلة الثانوية - مسار إدارة الأعمال
    {"id": "grade-s2-business", "stage_id": "stage-secondary", "track_id": "track-sec-business", "name_ar": "السنة الثانية - مسار إدارة الأعمال", "name_en": "Year 2 Business Admin", "grade_number": 2, "order": 26},
    {"id": "grade-s3-business", "stage_id": "stage-secondary", "track_id": "track-sec-business", "name_ar": "السنة الثالثة - مسار إدارة الأعمال", "name_en": "Year 3 Business Admin", "grade_number": 3, "order": 27},
    
    # المرحلة الثانوية - المسار الشرعي
    {"id": "grade-s2-islamic", "stage_id": "stage-secondary", "track_id": "track-sec-islamic", "name_ar": "السنة الثانية - المسار الشرعي", "name_en": "Year 2 Islamic Studies", "grade_number": 2, "order": 28},
    {"id": "grade-s3-islamic", "stage_id": "stage-secondary", "track_id": "track-sec-islamic", "name_ar": "السنة الثالثة - المسار الشرعي", "name_en": "Year 3 Islamic Studies", "grade_number": 3, "order": 29},
]

# Add is_official and is_locked to all grades
for grade in OFFICIAL_GRADES:
    grade["is_official"] = True
    grade["is_locked"] = True

# ============================================
# OFFICIAL SUBJECTS - المواد الدراسية الرسمية
# ============================================
OFFICIAL_SUBJECTS = [
    # المواد الأساسية
    {"id": "subj-quran-islamic", "name_ar": "القرآن الكريم والدراسات الإسلامية", "name_en": "Quran & Islamic Studies", "category": "islamic"},
    {"id": "subj-quran", "name_ar": "القرآن الكريم", "name_en": "Holy Quran", "category": "islamic"},
    {"id": "subj-tajweed", "name_ar": "التجويد", "name_en": "Tajweed", "category": "islamic"},
    {"id": "subj-tawheed", "name_ar": "التوحيد", "name_en": "Tawheed", "category": "islamic"},
    {"id": "subj-tawheed1", "name_ar": "التوحيد 1", "name_en": "Tawheed 1", "category": "islamic"},
    {"id": "subj-tawheed2", "name_ar": "التوحيد 2", "name_en": "Tawheed 2", "category": "islamic"},
    {"id": "subj-fiqh", "name_ar": "الفقه", "name_en": "Fiqh", "category": "islamic"},
    {"id": "subj-fiqh1", "name_ar": "الفقه 1", "name_en": "Fiqh 1", "category": "islamic"},
    {"id": "subj-fiqh2", "name_ar": "الفقه 2", "name_en": "Fiqh 2", "category": "islamic"},
    {"id": "subj-hadith", "name_ar": "الحديث", "name_en": "Hadith", "category": "islamic"},
    {"id": "subj-tafseer", "name_ar": "التفسير", "name_en": "Tafseer", "category": "islamic"},
    {"id": "subj-qiraat1", "name_ar": "القراءات 1", "name_en": "Qiraat 1", "category": "islamic"},
    {"id": "subj-qiraat2", "name_ar": "القراءات 2", "name_en": "Qiraat 2", "category": "islamic"},
    {"id": "subj-quran-sciences", "name_ar": "علوم القرآن", "name_en": "Quran Sciences", "category": "islamic"},
    {"id": "subj-usul-fiqh", "name_ar": "أصول الفقه", "name_en": "Usul Al-Fiqh", "category": "islamic"},
    {"id": "subj-hadith-term", "name_ar": "مصطلح الحديث", "name_en": "Hadith Terminology", "category": "islamic"},
    {"id": "subj-faraid", "name_ar": "الفرائض", "name_en": "Islamic Inheritance", "category": "islamic"},
    {"id": "subj-quran-tafseer", "name_ar": "القرآن الكريم وتفسيره", "name_en": "Quran & Tafseer", "category": "islamic"},
    
    # اللغة العربية
    {"id": "subj-arabic", "name_ar": "اللغة العربية", "name_en": "Arabic Language", "category": "language"},
    {"id": "subj-kifayat", "name_ar": "الكفايات اللغوية", "name_en": "Language Competencies", "category": "language"},
    {"id": "subj-linguistic-studies", "name_ar": "الدراسات اللغوية", "name_en": "Linguistic Studies", "category": "language"},
    {"id": "subj-literary-studies", "name_ar": "الدراسات الأدبية", "name_en": "Literary Studies", "category": "language"},
    {"id": "subj-rhetoric", "name_ar": "الدراسات البلاغية والنقدية", "name_en": "Rhetoric & Criticism", "category": "language"},
    {"id": "subj-functional-writing", "name_ar": "الكتابة الوظيفية والإبداعية", "name_en": "Functional & Creative Writing", "category": "language"},
    
    # اللغة الإنجليزية
    {"id": "subj-english", "name_ar": "اللغة الإنجليزية", "name_en": "English Language", "category": "language"},
    
    # الرياضيات والعلوم
    {"id": "subj-math", "name_ar": "الرياضيات", "name_en": "Mathematics", "category": "science"},
    {"id": "subj-science", "name_ar": "العلوم", "name_en": "Science", "category": "science"},
    {"id": "subj-physics", "name_ar": "الفيزياء", "name_en": "Physics", "category": "science"},
    {"id": "subj-chemistry", "name_ar": "الكيمياء", "name_en": "Chemistry", "category": "science"},
    {"id": "subj-biology", "name_ar": "الأحياء", "name_en": "Biology", "category": "science"},
    {"id": "subj-environment", "name_ar": "علم البيئة", "name_en": "Environmental Science", "category": "science"},
    {"id": "subj-earth-space", "name_ar": "علوم الأرض والفضاء", "name_en": "Earth & Space Sciences", "category": "science"},
    {"id": "subj-statistics", "name_ar": "الإحصاء", "name_en": "Statistics", "category": "science"},
    
    # الدراسات الاجتماعية
    {"id": "subj-social", "name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies", "category": "social"},
    {"id": "subj-history", "name_ar": "التاريخ", "name_en": "History", "category": "social"},
    {"id": "subj-geography", "name_ar": "الجغرافيا", "name_en": "Geography", "category": "social"},
    {"id": "subj-psychology", "name_ar": "الدراسات النفسية والاجتماعية", "name_en": "Psychology & Sociology", "category": "social"},
    
    # التقنية والحاسب
    {"id": "subj-digital-skills", "name_ar": "المهارات الرقمية", "name_en": "Digital Skills", "category": "technology"},
    {"id": "subj-digital-tech", "name_ar": "التقنية الرقمية", "name_en": "Digital Technology", "category": "technology"},
    {"id": "subj-data-science", "name_ar": "علم البيانات", "name_en": "Data Science", "category": "technology"},
    {"id": "subj-iot", "name_ar": "إنترنت الأشياء", "name_en": "Internet of Things", "category": "technology"},
    {"id": "subj-ai", "name_ar": "الذكاء الاصطناعي", "name_en": "Artificial Intelligence", "category": "technology"},
    {"id": "subj-cybersecurity", "name_ar": "الأمن السيبراني", "name_en": "Cybersecurity", "category": "technology"},
    {"id": "subj-software-eng", "name_ar": "هندسة البرمجيات", "name_en": "Software Engineering", "category": "technology"},
    {"id": "subj-digital-citizenship", "name_ar": "المواطنة الرقمية", "name_en": "Digital Citizenship", "category": "technology"},
    {"id": "subj-digital-design", "name_ar": "التصميم الرقمي", "name_en": "Digital Design", "category": "technology"},
    
    # الهندسة
    {"id": "subj-engineering", "name_ar": "الهندسة", "name_en": "Engineering", "category": "engineering"},
    {"id": "subj-eng-design", "name_ar": "التصميم الهندسي", "name_en": "Engineering Design", "category": "engineering"},
    
    # الصحة والحياة
    {"id": "subj-health-principles", "name_ar": "مبادئ العلوم الصحية", "name_en": "Health Sciences Principles", "category": "health"},
    {"id": "subj-health-care", "name_ar": "الرعاية الصحية", "name_en": "Health Care", "category": "health"},
    {"id": "subj-human-systems", "name_ar": "أنظمة جسم الإنسان", "name_en": "Human Body Systems", "category": "health"},
    {"id": "subj-first-aid", "name_ar": "الإسعافات الأولية", "name_en": "First Aid", "category": "health"},
    
    # إدارة الأعمال
    {"id": "subj-business-intro", "name_ar": "مقدمة في الأعمال", "name_en": "Introduction to Business", "category": "business"},
    {"id": "subj-business-decision", "name_ar": "صناعة القرار في الأعمال", "name_en": "Business Decision Making", "category": "business"},
    {"id": "subj-economics", "name_ar": "مبادئ الاقتصاد", "name_en": "Principles of Economics", "category": "business"},
    {"id": "subj-financial-mgmt", "name_ar": "الإدارة المالية", "name_en": "Financial Management", "category": "business"},
    {"id": "subj-financial-literacy", "name_ar": "المعرفة المالية", "name_en": "Financial Literacy", "category": "business"},
    {"id": "subj-admin-principles", "name_ar": "مبادئ الإدارة", "name_en": "Principles of Management", "category": "business"},
    {"id": "subj-events-mgmt", "name_ar": "إدارة الفعاليات", "name_en": "Events Management", "category": "business"},
    {"id": "subj-marketing", "name_ar": "تخطيط الحملات التسويقية", "name_en": "Marketing Campaigns", "category": "business"},
    {"id": "subj-secretary", "name_ar": "السكرتارية والإدارة المكتبية", "name_en": "Secretarial & Office Admin", "category": "business"},
    {"id": "subj-admin-skills", "name_ar": "المهارات الإدارية", "name_en": "Administrative Skills", "category": "business"},
    {"id": "subj-tourism", "name_ar": "السياحة والضيافة", "name_en": "Tourism & Hospitality", "category": "business"},
    
    # القانون
    {"id": "subj-law-principles", "name_ar": "مبادئ القانون", "name_en": "Principles of Law", "category": "law"},
    {"id": "subj-law-applications", "name_ar": "تطبيقات في القانون", "name_en": "Law Applications", "category": "law"},
    
    # المهارات والتربية
    {"id": "subj-life-skills", "name_ar": "المهارات الحياتية والأسرية", "name_en": "Life & Family Skills", "category": "skills"},
    {"id": "subj-life-skills-sec", "name_ar": "المهارات الحياتية", "name_en": "Life Skills", "category": "skills"},
    {"id": "subj-critical-thinking", "name_ar": "التفكير الناقد", "name_en": "Critical Thinking", "category": "skills"},
    {"id": "subj-research", "name_ar": "البحث ومصادر المعلومات", "name_en": "Research & Information Sources", "category": "skills"},
    {"id": "subj-vocational", "name_ar": "التربية المهنية", "name_en": "Vocational Education", "category": "skills"},
    {"id": "subj-sustainable-dev", "name_ar": "التنمية المستدامة", "name_en": "Sustainable Development", "category": "skills"},
    
    # التربية البدنية والفنية
    {"id": "subj-pe", "name_ar": "التربية البدنية والدفاع عن النفس", "name_en": "PE & Self Defense", "category": "physical"},
    {"id": "subj-pe-health", "name_ar": "التربية الصحية والبدنية", "name_en": "Health & Physical Education", "category": "physical"},
    {"id": "subj-fitness", "name_ar": "اللياقة والثقافة الصحية", "name_en": "Fitness & Health Culture", "category": "physical"},
    {"id": "subj-art", "name_ar": "التربية الفنية", "name_en": "Art Education", "category": "arts"},
    {"id": "subj-arts", "name_ar": "الفنون", "name_en": "Arts", "category": "arts"},
    {"id": "subj-fashion", "name_ar": "فن تصميم الأزياء", "name_en": "Fashion Design", "category": "arts"},
    
    # النشاط والفترات اللاصفية
    {"id": "subj-activity", "name_ar": "النشاط", "name_en": "Activity", "category": "activity"},
    {"id": "subj-non-class", "name_ar": "الفترات اللاصفية", "name_en": "Non-Class Periods", "category": "non_class"},
    
    # مشروع التخرج والاختياري
    {"id": "subj-graduation", "name_ar": "مشروع التخرج", "name_en": "Graduation Project", "category": "project"},
    {"id": "subj-optional", "name_ar": "المجال الاختياري", "name_en": "Optional Field", "category": "optional"},
]

# Add is_official and is_locked to all subjects
for subj in OFFICIAL_SUBJECTS:
    subj["is_official"] = True
    subj["is_locked"] = True

# ============================================
# OFFICIAL TEACHER RANK LOADS - النصاب الرسمي
# ============================================
OFFICIAL_TEACHER_RANK_LOADS = [
    {
        "id": "rank-teacher",
        "rank_name_ar": "المعلم",
        "rank_name_en": "Teacher",
        "weekly_periods": 24,
        "is_special_ed": False,
        "is_official": True,
        "is_locked": True,
        "order": 1
    },
    {
        "id": "rank-practitioner",
        "rank_name_ar": "المعلم الممارس",
        "rank_name_en": "Practicing Teacher",
        "weekly_periods": 24,
        "is_special_ed": False,
        "is_official": True,
        "is_locked": True,
        "order": 2
    },
    {
        "id": "rank-advanced",
        "rank_name_ar": "المعلم المتقدم",
        "rank_name_en": "Advanced Teacher",
        "weekly_periods": 22,
        "is_special_ed": False,
        "is_official": True,
        "is_locked": True,
        "order": 3
    },
    {
        "id": "rank-expert",
        "rank_name_ar": "المعلم الخبير",
        "rank_name_en": "Expert Teacher",
        "weekly_periods": 18,
        "is_special_ed": False,
        "is_official": True,
        "is_locked": True,
        "order": 4
    },
    {
        "id": "rank-practitioner-sped",
        "rank_name_ar": "معلم تربية خاصة - ممارس",
        "rank_name_en": "Special Ed - Practicing",
        "weekly_periods": 18,
        "is_special_ed": True,
        "is_official": True,
        "is_locked": True,
        "order": 5
    },
    {
        "id": "rank-advanced-sped",
        "rank_name_ar": "معلم تربية خاصة - متقدم",
        "rank_name_en": "Special Ed - Advanced",
        "weekly_periods": 16,
        "is_special_ed": True,
        "is_official": True,
        "is_locked": True,
        "order": 6
    },
    {
        "id": "rank-expert-sped",
        "rank_name_ar": "معلم تربية خاصة - خبير",
        "rank_name_en": "Special Ed - Expert",
        "weekly_periods": 14,
        "is_special_ed": True,
        "is_official": True,
        "is_locked": True,
        "order": 7
    }
]

async def seed_official_curriculum():
    """Seed all official curriculum data into the database"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("=" * 60)
    print("بدء تثبيت بيانات المنهج الرسمي الكامل")
    print("Starting Official Curriculum Seed")
    print("=" * 60)
    
    try:
        # Drop existing official collections
        print("\n[1/6] حذف البيانات القديمة...")
        await db.official_curriculum_stages.drop()
        await db.official_curriculum_tracks.drop()
        await db.official_curriculum_grades.drop()
        await db.official_curriculum_subjects.drop()
        await db.official_curriculum_subject_details.drop()
        await db.official_teacher_rank_loads.drop()
        print("✓ تم حذف البيانات القديمة")
        
        # Insert stages
        print("\n[2/6] تثبيت المراحل الدراسية...")
        for stage in OFFICIAL_STAGES:
            stage["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.official_curriculum_stages.insert_one(stage)
        print(f"✓ تم تثبيت {len(OFFICIAL_STAGES)} مراحل")
        
        # Insert tracks
        print("\n[3/6] تثبيت المسارات التعليمية...")
        for track in OFFICIAL_TRACKS:
            track["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.official_curriculum_tracks.insert_one(track)
        print(f"✓ تم تثبيت {len(OFFICIAL_TRACKS)} مسارات")
        
        # Insert grades
        print("\n[4/6] تثبيت الصفوف والسنوات...")
        for grade in OFFICIAL_GRADES:
            grade["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.official_curriculum_grades.insert_one(grade)
        print(f"✓ تم تثبيت {len(OFFICIAL_GRADES)} صف/سنة")
        
        # Insert subjects
        print("\n[5/6] تثبيت المواد الدراسية...")
        for subj in OFFICIAL_SUBJECTS:
            subj["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.official_curriculum_subjects.insert_one(subj)
        print(f"✓ تم تثبيت {len(OFFICIAL_SUBJECTS)} مادة")
        
        # Insert teacher rank loads
        print("\n[6/6] تثبيت النصاب الرسمي للمعلمين...")
        for rank in OFFICIAL_TEACHER_RANK_LOADS:
            rank["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.official_teacher_rank_loads.insert_one(rank)
        print(f"✓ تم تثبيت {len(OFFICIAL_TEACHER_RANK_LOADS)} رتب")
        
        # Create indexes
        print("\n[*] إنشاء الفهارس...")
        await db.official_curriculum_stages.create_index("id", unique=True)
        await db.official_curriculum_tracks.create_index("id", unique=True)
        await db.official_curriculum_grades.create_index("id", unique=True)
        await db.official_curriculum_grades.create_index([("stage_id", 1), ("track_id", 1)])
        await db.official_curriculum_subjects.create_index("id", unique=True)
        await db.official_curriculum_subject_details.create_index("id", unique=True)
        await db.official_curriculum_subject_details.create_index([("grade_id", 1), ("subject_id", 1)])
        await db.official_teacher_rank_loads.create_index("id", unique=True)
        print("✓ تم إنشاء الفهارس")
        
        print("\n" + "=" * 60)
        print("✅ تم تثبيت جميع البيانات الأساسية بنجاح!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(seed_official_curriculum())
