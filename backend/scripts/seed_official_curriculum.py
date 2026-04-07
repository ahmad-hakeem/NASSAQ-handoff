"""
Seed Official Saudi Curriculum Data into PostgreSQL
Read-only reference data - cannot be modified by school principals
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

import sys as _sys
import os as _os
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_upsert
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from scripts.seed_db_helper import get_seed_db

# ============ STAGES ============
STAGES = [
    {"id": "ocs-primary", "name_ar": "المرحلة الابتدائية", "name_en": "Primary Stage", "order": 1, "grade_range": [1,6]},
    {"id": "ocs-middle", "name_ar": "المرحلة المتوسطة", "name_en": "Middle Stage", "order": 2, "grade_range": [7,9]},
    {"id": "ocs-secondary", "name_ar": "المرحلة الثانوية", "name_en": "Secondary Stage", "order": 3, "grade_range": [10,12]},
]

# ============ TRACKS ============
TRACKS = [
    {"id": "oct-primary-general", "stage_id": "ocs-primary", "name_ar": "التعليم العام", "name_en": "General Education", "order": 1},
    {"id": "oct-primary-quran", "stage_id": "ocs-primary", "name_ar": "تحفيظ القرآن الكريم", "name_en": "Quran Memorization", "order": 2},
    {"id": "oct-middle-general", "stage_id": "ocs-middle", "name_ar": "التعليم العام", "name_en": "General Education", "order": 1},
    {"id": "oct-middle-quran", "stage_id": "ocs-middle", "name_ar": "تحفيظ القرآن الكريم", "name_en": "Quran Memorization", "order": 2},
    {"id": "oct-secondary-common", "stage_id": "ocs-secondary", "name_ar": "مسار مشترك (السنة الأولى)", "name_en": "Common Track (Year 1)", "order": 1},
    {"id": "oct-secondary-general", "stage_id": "ocs-secondary", "name_ar": "المسار العام", "name_en": "General Track", "order": 2},
    {"id": "oct-secondary-cs", "stage_id": "ocs-secondary", "name_ar": "مسار علوم الحاسب والهندسة", "name_en": "CS & Engineering Track", "order": 3},
    {"id": "oct-secondary-health", "stage_id": "ocs-secondary", "name_ar": "مسار الصحة والحياة", "name_en": "Health & Life Track", "order": 4},
    {"id": "oct-secondary-business", "stage_id": "ocs-secondary", "name_ar": "مسار إدارة الأعمال", "name_en": "Business Administration Track", "order": 5},
    {"id": "oct-secondary-sharia", "stage_id": "ocs-secondary", "name_ar": "المسار الشرعي", "name_en": "Sharia Track", "order": 6},
]

# ============ OFFICIAL GRADES ============
GRADES = [
    # Primary - General
    {"id": "ocg-p1-gen", "stage_id": "ocs-primary", "track_id": "oct-primary-general", "name_ar": "الصف الأول الابتدائي", "grade_number": 1, "year_number": 1},
    {"id": "ocg-p2-gen", "stage_id": "ocs-primary", "track_id": "oct-primary-general", "name_ar": "الصف الثاني الابتدائي", "grade_number": 2, "year_number": 2},
    {"id": "ocg-p3-gen", "stage_id": "ocs-primary", "track_id": "oct-primary-general", "name_ar": "الصف الثالث الابتدائي", "grade_number": 3, "year_number": 3},
    {"id": "ocg-p4-gen", "stage_id": "ocs-primary", "track_id": "oct-primary-general", "name_ar": "الصف الرابع الابتدائي", "grade_number": 4, "year_number": 4},
    {"id": "ocg-p5-gen", "stage_id": "ocs-primary", "track_id": "oct-primary-general", "name_ar": "الصف الخامس الابتدائي", "grade_number": 5, "year_number": 5},
    {"id": "ocg-p6-gen", "stage_id": "ocs-primary", "track_id": "oct-primary-general", "name_ar": "الصف السادس الابتدائي", "grade_number": 6, "year_number": 6},
    # Primary - Quran
    {"id": "ocg-p1-qr", "stage_id": "ocs-primary", "track_id": "oct-primary-quran", "name_ar": "الصف الأول الابتدائي (تحفيظ القرآن الكريم)", "grade_number": 1, "year_number": 1},
    {"id": "ocg-p2-qr", "stage_id": "ocs-primary", "track_id": "oct-primary-quran", "name_ar": "الصف الثاني الابتدائي (تحفيظ القرآن الكريم)", "grade_number": 2, "year_number": 2},
    {"id": "ocg-p3-qr", "stage_id": "ocs-primary", "track_id": "oct-primary-quran", "name_ar": "الصف الثالث الابتدائي (تحفيظ القرآن الكريم)", "grade_number": 3, "year_number": 3},
    {"id": "ocg-p4-qr", "stage_id": "ocs-primary", "track_id": "oct-primary-quran", "name_ar": "الصف الرابع الابتدائي (تحفيظ القرآن الكريم)", "grade_number": 4, "year_number": 4},
    {"id": "ocg-p5-qr", "stage_id": "ocs-primary", "track_id": "oct-primary-quran", "name_ar": "الصف الخامس الابتدائي (تحفيظ القرآن الكريم)", "grade_number": 5, "year_number": 5},
    {"id": "ocg-p6-qr", "stage_id": "ocs-primary", "track_id": "oct-primary-quran", "name_ar": "الصف السادس الابتدائي (تحفيظ القرآن الكريم)", "grade_number": 6, "year_number": 6},
    # Middle - General
    {"id": "ocg-m1-gen", "stage_id": "ocs-middle", "track_id": "oct-middle-general", "name_ar": "الصف الأول المتوسط (التعليم العام)", "grade_number": 7, "year_number": 1},
    {"id": "ocg-m2-gen", "stage_id": "ocs-middle", "track_id": "oct-middle-general", "name_ar": "الصف الثاني المتوسط (التعليم العام)", "grade_number": 8, "year_number": 2},
    {"id": "ocg-m3-gen", "stage_id": "ocs-middle", "track_id": "oct-middle-general", "name_ar": "الصف الثالث المتوسط (التعليم العام)", "grade_number": 9, "year_number": 3},
    # Middle - Quran
    {"id": "ocg-m1-qr", "stage_id": "ocs-middle", "track_id": "oct-middle-quran", "name_ar": "الصف الأول المتوسط (تحفيظ القرآن الكريم)", "grade_number": 7, "year_number": 1},
    {"id": "ocg-m2-qr", "stage_id": "ocs-middle", "track_id": "oct-middle-quran", "name_ar": "الصف الثاني المتوسط (تحفيظ القرآن الكريم)", "grade_number": 8, "year_number": 2},
    {"id": "ocg-m3-qr", "stage_id": "ocs-middle", "track_id": "oct-middle-quran", "name_ar": "الصف الثالث المتوسط (تحفيظ القرآن الكريم)", "grade_number": 9, "year_number": 3},
    # Secondary
    {"id": "ocg-s1-com", "stage_id": "ocs-secondary", "track_id": "oct-secondary-common", "name_ar": "السنة الأولى (الثانوية العامة - مسار مشترك)", "grade_number": 10, "year_number": 1},
    {"id": "ocg-s2-gen", "stage_id": "ocs-secondary", "track_id": "oct-secondary-general", "name_ar": "السنة الثانية (الثانوية العامة - المسار العام)", "grade_number": 11, "year_number": 2},
    {"id": "ocg-s3-gen", "stage_id": "ocs-secondary", "track_id": "oct-secondary-general", "name_ar": "السنة الثالثة (الثانوية العامة - المسار العام)", "grade_number": 12, "year_number": 3},
    {"id": "ocg-s2-cs", "stage_id": "ocs-secondary", "track_id": "oct-secondary-cs", "name_ar": "السنة الثانية (الثانوية العامة - مسار علوم الحاسب والهندسة)", "grade_number": 11, "year_number": 2},
    {"id": "ocg-s3-cs", "stage_id": "ocs-secondary", "track_id": "oct-secondary-cs", "name_ar": "السنة الثالثة (الثانوية العامة - مسار علوم الحاسب والهندسة)", "grade_number": 12, "year_number": 3},
    {"id": "ocg-s2-health", "stage_id": "ocs-secondary", "track_id": "oct-secondary-health", "name_ar": "السنة الثانية (الثانوية العامة - مسار الصحة والحياة)", "grade_number": 11, "year_number": 2},
    {"id": "ocg-s3-health", "stage_id": "ocs-secondary", "track_id": "oct-secondary-health", "name_ar": "السنة الثالثة (الثانوية العامة - مسار الصحة والحياة)", "grade_number": 12, "year_number": 3},
    {"id": "ocg-s2-biz", "stage_id": "ocs-secondary", "track_id": "oct-secondary-business", "name_ar": "السنة الثانية (الثانوية العامة - مسار إدارة الأعمال)", "grade_number": 11, "year_number": 2},
    {"id": "ocg-s3-biz", "stage_id": "ocs-secondary", "track_id": "oct-secondary-business", "name_ar": "السنة الثالثة (الثانوية العامة - مسار إدارة الأعمال)", "grade_number": 12, "year_number": 3},
    {"id": "ocg-s2-sha", "stage_id": "ocs-secondary", "track_id": "oct-secondary-sharia", "name_ar": "السنة الثانية (الثانوية العامة - المسار الشرعي)", "grade_number": 11, "year_number": 2},
    {"id": "ocg-s3-sha", "stage_id": "ocs-secondary", "track_id": "oct-secondary-sharia", "name_ar": "السنة الثالثة (الثانوية العامة - المسار الشرعي)", "grade_number": 12, "year_number": 3},
]

# ============ GRADE-SUBJECT MAPPINGS ============
# Format: (grade_id, subject_name_ar, annual_sessions, item_type)
# item_type: "class_period" | "non_class_period" | "optional_pool"
GRADE_SUBJECTS = {
    "ocg-p1-gen": [
        ("القرآن الكريم والدراسات الإسلامية", 180, "class_period"),
        ("اللغة العربية", 288, "class_period"),
        ("الرياضيات", 180, "class_period"),
        ("العلوم", 108, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("التربية الفنية", 72, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 108, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 108, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p2-gen": [
        ("القرآن الكريم والدراسات الإسلامية", 180, "class_period"),
        ("اللغة العربية", 252, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 108, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("التربية الفنية", 72, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 108, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 108, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p3-gen": [
        ("القرآن الكريم والدراسات الإسلامية", 180, "class_period"),
        ("اللغة العربية", 216, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("التربية الفنية", 72, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 108, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 108, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p4-gen": [
        ("القرآن الكريم والدراسات الإسلامية", 180, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 36, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 72, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p5-gen": [
        ("القرآن الكريم والدراسات الإسلامية", 180, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 36, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 72, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p6-gen": [
        ("القرآن الكريم والدراسات الإسلامية", 180, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 36, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 72, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p1-qr": [
        ("القرآن الكريم والدراسات الإسلامية", 324, "class_period"),
        ("اللغة العربية", 288, "class_period"),
        ("الرياضيات", 180, "class_period"),
        ("العلوم", 108, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("التربية الفنية", 72, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 108, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 101, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p2-qr": [
        ("القرآن الكريم والدراسات الإسلامية", 324, "class_period"),
        ("اللغة العربية", 252, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 108, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("التربية الفنية", 72, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 108, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 101, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p3-qr": [
        ("القرآن الكريم والدراسات الإسلامية", 324, "class_period"),
        ("اللغة العربية", 216, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("التربية الفنية", 72, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 108, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 101, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p4-qr": [
        ("القرآن الكريم والدراسات الإسلامية", 288, "class_period"),
        ("التجويد", 36, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 36, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 72, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 67, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p5-qr": [
        ("القرآن الكريم والدراسات الإسلامية", 288, "class_period"),
        ("التجويد", 36, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 36, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 72, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 67, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-p6-qr": [
        ("القرآن الكريم والدراسات الإسلامية", 288, "class_period"),
        ("التجويد", 36, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 108, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 36, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 72, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("النشاط", 67, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-m1-gen": [
        ("القرآن الكريم والدراسات الإسلامية", 180, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 108, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 72, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 72, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("التفكير الناقد", 0, "class_period"),
        ("النشاط", 36, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-m2-gen": [
        ("القرآن الكريم والدراسات الإسلامية", 180, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 108, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 72, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 72, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("التفكير الناقد", 0, "class_period"),
        ("النشاط", 36, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-m3-gen": [
        ("القرآن الكريم والدراسات الإسلامية", 180, "class_period"),
        ("اللغة العربية", 144, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 72, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 72, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("التفكير الناقد", 72, "class_period"),
        ("النشاط", 36, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-m1-qr": [
        ("القرآن الكريم والدراسات الإسلامية", 288, "class_period"),
        ("التجويد", 36, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 36, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 36, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("التفكير الناقد", 0, "class_period"),
        ("النشاط", 67, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-m2-qr": [
        ("القرآن الكريم والدراسات الإسلامية", 288, "class_period"),
        ("التجويد", 36, "class_period"),
        ("اللغة العربية", 180, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 36, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 36, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("التفكير الناقد", 0, "class_period"),
        ("النشاط", 67, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    "ocg-m3-qr": [
        ("القرآن الكريم والدراسات الإسلامية", 252, "class_period"),
        ("التجويد", 36, "class_period"),
        ("اللغة العربية", 144, "class_period"),
        ("الدراسات الاجتماعية", 72, "class_period"),
        ("الرياضيات", 216, "class_period"),
        ("العلوم", 144, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("المهارات الرقمية", 72, "class_period"),
        ("التربية الفنية", 36, "class_period"),
        ("التربية البدنية والدفاع عن النفس", 36, "class_period"),
        ("المهارات الحياتية والأسرية", 36, "class_period"),
        ("التفكير الناقد", 72, "class_period"),
        ("النشاط", 68, "class_period"),
        ("الفترات اللاصفية", 240, "non_class_period"),
    ],
    # Secondary Common (Year 1)
    "ocg-s1-com": [
        ("القرآن الكريم وتفسيره", 60, "class_period"),
        ("الرياضيات", 180, "class_period"),
        ("اللغة الإنجليزية", 180, "class_period"),
        ("التقنية الرقمية", 108, "class_period"),
        ("الأحياء", 60, "class_period"),
        ("الكيمياء", 60, "class_period"),
        ("الفيزياء", 60, "class_period"),
        ("علم البيئة", 36, "class_period"),
        ("الكفايات اللغوية", 120, "class_period"),
        ("الحديث", 36, "class_period"),
        ("المعرفة المالية", 36, "class_period"),
        ("الدراسات الاجتماعية", 60, "class_period"),
        ("التفكير الناقد", 48, "class_period"),
        ("التربية المهنية", 36, "class_period"),
        ("التربية الصحية والبدنية", 72, "class_period"),
        ("النشاط", 60, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # Secondary General Track Year 2
    "ocg-s2-gen": [
        ("الرياضيات", 180, "class_period"),
        ("اللغة الإنجليزية", 180, "class_period"),
        ("الكيمياء", 180, "class_period"),
        ("الأحياء", 144, "class_period"),
        ("الفيزياء", 60, "class_period"),
        ("التوحيد", 36, "class_period"),
        ("الكفايات اللغوية", 72, "class_period"),
        ("التقنية الرقمية", 72, "class_period"),
        ("التاريخ", 60, "class_period"),
        ("الفنون", 36, "class_period"),
        ("اللياقة والثقافة الصحية", 60, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # Secondary General Track Year 3
    "ocg-s3-gen": [
        ("الرياضيات", 144, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("الكيمياء", 60, "class_period"),
        ("الفيزياء", 180, "class_period"),
        ("علوم الأرض والفضاء", 96, "class_period"),
        ("الفقه", 36, "class_period"),
        ("الدراسات الأدبية", 36, "class_period"),
        ("الدراسات النفسية والاجتماعية", 36, "class_period"),
        ("التقنية الرقمية", 36, "class_period"),
        ("المواطنة الرقمية", 36, "class_period"),
        ("الجغرافيا", 36, "class_period"),
        ("المهارات الحياتية", 36, "class_period"),
        ("التربية الصحية والبدنية", 48, "class_period"),
        ("البحث ومصادر المعلومات", 36, "class_period"),
        ("المجال الاختياري", 120, "optional_pool"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # CS & Engineering Year 2
    "ocg-s2-cs": [
        ("الرياضيات", 180, "class_period"),
        ("اللغة الإنجليزية", 180, "class_period"),
        ("الكيمياء", 180, "class_period"),
        ("الأحياء", 144, "class_period"),
        ("الفيزياء", 60, "class_period"),
        ("التوحيد", 36, "class_period"),
        ("الكفايات اللغوية", 72, "class_period"),
        ("علم البيانات", 36, "class_period"),
        ("إنترنت الأشياء", 72, "class_period"),
        ("الهندسة", 60, "class_period"),
        ("اللياقة والثقافة الصحية", 60, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # CS & Engineering Year 3
    "ocg-s3-cs": [
        ("الرياضيات", 144, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("الكيمياء", 60, "class_period"),
        ("الفيزياء", 180, "class_period"),
        ("علوم الأرض والفضاء", 96, "class_period"),
        ("الفقه", 36, "class_period"),
        ("الدراسات الأدبية", 36, "class_period"),
        ("الذكاء الاصطناعي", 84, "class_period"),
        ("الأمن السيبراني", 36, "class_period"),
        ("هندسة البرمجيات", 60, "class_period"),
        ("التصميم الهندسي", 48, "class_period"),
        ("المهارات الحياتية", 36, "class_period"),
        ("التربية الصحية والبدنية", 48, "class_period"),
        ("البحث ومصادر المعلومات", 36, "class_period"),
        ("مشروع التخرج", 36, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # Health & Life Year 2
    "ocg-s2-health": [
        ("الرياضيات", 180, "class_period"),
        ("اللغة الإنجليزية", 180, "class_period"),
        ("الكيمياء", 180, "class_period"),
        ("الأحياء", 144, "class_period"),
        ("الفيزياء", 60, "class_period"),
        ("التوحيد", 36, "class_period"),
        ("الكفايات اللغوية", 72, "class_period"),
        ("التقنية الرقمية", 72, "class_period"),
        ("مبادئ العلوم الصحية", 96, "class_period"),
        ("اللياقة والثقافة الصحية", 60, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # Health & Life Year 3
    "ocg-s3-health": [
        ("الرياضيات", 144, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("الكيمياء", 60, "class_period"),
        ("الفيزياء", 180, "class_period"),
        ("علوم الأرض والفضاء", 96, "class_period"),
        ("الفقه", 36, "class_period"),
        ("الدراسات الأدبية", 36, "class_period"),
        ("الرعاية الصحية", 108, "class_period"),
        ("أنظمة جسم الإنسان", 84, "class_period"),
        ("الإحصاء", 36, "class_period"),
        ("المهارات الحياتية", 36, "class_period"),
        ("التربية الصحية والبدنية", 48, "class_period"),
        ("البحث ومصادر المعلومات", 36, "class_period"),
        ("مشروع التخرج", 36, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # Business Administration Year 2
    "ocg-s2-biz": [
        ("اللغة الإنجليزية", 180, "class_period"),
        ("التوحيد", 36, "class_period"),
        ("التفسير", 36, "class_period"),
        ("الكفايات اللغوية", 72, "class_period"),
        ("الدراسات اللغوية", 60, "class_period"),
        ("صناعة القرار في الأعمال", 156, "class_period"),
        ("مقدمة في الأعمال", 120, "class_period"),
        ("مبادئ الاقتصاد", 48, "class_period"),
        ("الإدارة المالية", 108, "class_period"),
        ("التقنية الرقمية", 72, "class_period"),
        ("التاريخ", 60, "class_period"),
        ("الفنون", 36, "class_period"),
        ("اللياقة والثقافة الصحية", 60, "class_period"),
        ("النشاط", 108, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # Business Administration Year 3
    "ocg-s3-biz": [
        ("اللغة الإنجليزية", 144, "class_period"),
        ("الفقه", 36, "class_period"),
        ("الدراسات الأدبية", 36, "class_period"),
        ("الدراسات النفسية والاجتماعية", 36, "class_period"),
        ("الدراسات البلاغية والنقدية", 48, "class_period"),
        ("مبادئ الإدارة", 60, "class_period"),
        ("إدارة الفعاليات", 120, "class_period"),
        ("تخطيط الحملات التسويقية", 120, "class_period"),
        ("السكرتارية والإدارة المكتبية", 60, "class_period"),
        ("مبادئ القانون", 120, "class_period"),
        ("تطبيقات في القانون", 36, "class_period"),
        ("المواطنة الرقمية", 36, "class_period"),
        ("الإحصاء", 36, "class_period"),
        ("الجغرافيا", 36, "class_period"),
        ("المهارات الحياتية", 36, "class_period"),
        ("التربية الصحية والبدنية", 48, "class_period"),
        ("البحث ومصادر المعلومات", 36, "class_period"),
        ("مشروع التخرج", 36, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # Sharia Track Year 2
    "ocg-s2-sha": [
        ("القرآن الكريم", 180, "class_period"),
        ("اللغة الإنجليزية", 180, "class_period"),
        ("التوحيد 1", 36, "class_period"),
        ("التوحيد 2", 36, "class_period"),
        ("الحديث", 36, "class_period"),
        ("القراءات 1", 60, "class_period"),
        ("القراءات 2", 60, "class_period"),
        ("علوم القرآن", 60, "class_period"),
        ("التفسير", 36, "class_period"),
        ("الكفايات اللغوية", 72, "class_period"),
        ("الدراسات اللغوية", 60, "class_period"),
        ("التقنية الرقمية", 72, "class_period"),
        ("التاريخ", 60, "class_period"),
        ("الفنون", 36, "class_period"),
        ("اللياقة والثقافة الصحية", 60, "class_period"),
        ("النشاط", 108, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
    # Sharia Track Year 3
    "ocg-s3-sha": [
        ("القرآن الكريم", 180, "class_period"),
        ("اللغة الإنجليزية", 144, "class_period"),
        ("التفسير", 36, "class_period"),
        ("الفقه 1", 36, "class_period"),
        ("الفقه 2", 60, "class_period"),
        ("أصول الفقه", 36, "class_period"),
        ("مصطلح الحديث", 36, "class_period"),
        ("الفرائض", 48, "class_period"),
        ("الدراسات الأدبية", 36, "class_period"),
        ("الدراسات النفسية والاجتماعية", 36, "class_period"),
        ("الدراسات البلاغية والنقدية", 48, "class_period"),
        ("مبادئ القانون", 120, "class_period"),
        ("تطبيقات في القانون", 36, "class_period"),
        ("المواطنة الرقمية", 36, "class_period"),
        ("الجغرافيا", 36, "class_period"),
        ("المهارات الحياتية", 36, "class_period"),
        ("التربية الصحية والبدنية", 48, "class_period"),
        ("البحث ومصادر المعلومات", 36, "class_period"),
        ("مشروع التخرج", 36, "class_period"),
        ("النشاط", 72, "class_period"),
        ("الفترات اللاصفية", 216, "non_class_period"),
    ],
}

# Official Teacher Rank Loads
TEACHER_RANK_LOADS = [
    {"rank_ar": "معلم", "rank_en": "Teacher", "weekly_load": 24, "is_special_ed": False, "notes_ar": "النصاب الرسمي للمعلم والمعلم الممارس"},
    {"rank_ar": "معلم ممارس", "rank_en": "Practicing Teacher", "weekly_load": 24, "is_special_ed": False, "notes_ar": "النصاب الرسمي للمعلم الممارس"},
    {"rank_ar": "معلم ممارس (تربية خاصة)", "rank_en": "Practicing Teacher (Special Ed)", "weekly_load": 18, "is_special_ed": True, "notes_ar": "النصاب الرسمي لمعلم ممارس التربية الخاصة"},
    {"rank_ar": "معلم متقدم", "rank_en": "Advanced Teacher", "weekly_load": 22, "is_special_ed": False, "notes_ar": "النصاب الرسمي للمعلم المتقدم"},
    {"rank_ar": "معلم متقدم (تربية خاصة)", "rank_en": "Advanced Teacher (Special Ed)", "weekly_load": 16, "is_special_ed": True, "notes_ar": "النصاب الرسمي لمعلم متقدم التربية الخاصة"},
    {"rank_ar": "معلم خبير", "rank_en": "Expert Teacher", "weekly_load": 18, "is_special_ed": False, "notes_ar": "النصاب الرسمي للمعلم الخبير"},
    {"rank_ar": "معلم خبير (تربية خاصة)", "rank_en": "Expert Teacher (Special Ed)", "weekly_load": 14, "is_special_ed": True, "notes_ar": "النصاب الرسمي لمعلم خبير التربية الخاصة"},
]

# Optional Subject Pool (Year 3 General Track)
OPTIONAL_POOLS = [
    {
        "id": "oop-y3-general",
        "grade_id": "ocg-s3-gen",
        "name_ar": "المجال الاختياري - السنة الثالثة (المسار العام)",
        "total_sessions": 120,
        "items": [
            {"name_ar": "التصميم الرقمي", "learning_type": "حضوري"},
            {"name_ar": "المهارات الإدارية", "learning_type": "حضوري"},
            {"name_ar": "التنمية المستدامة", "learning_type": "حضوري"},
            {"name_ar": "الكتابة الوظيفية والإبداعية", "learning_type": "حضوري"},
            {"name_ar": "فن تصميم الأزياء", "learning_type": "حضوري"},
            {"name_ar": "الإسعافات الأولية", "learning_type": "حضوري"},
            {"name_ar": "الأمن السيبراني", "learning_type": "إلكتروني ذاتي التعلم"},
            {"name_ar": "السياحة والضيافة", "learning_type": "إلكتروني ذاتي التعلم"},
            {"name_ar": "الذكاء الاصطناعي", "learning_type": "إلكتروني ذاتي التعلم"},
        ]
    }
]

async def seed():
    async with get_seed_db() as db:
        now = datetime.now(timezone.utc).isoformat()

        print("Clearing existing official curriculum data...")
        for col in ["official_curriculum_stages", "official_curriculum_tracks", "official_curriculum_grades",
                     "official_curriculum_subjects", "official_curriculum_grade_subjects",
                     "official_teacher_rank_loads", "official_optional_subject_pools", "official_optional_subject_pool_items"]:
            await db[col].drop()

        print("Seeding stages...")
        for stage in STAGES:
            await gd_insert(db.session, "official_curriculum_stages", {**stage, "is_official": True, "is_read_only": True, "created_at": now})

        print("Seeding tracks...")
        for track in TRACKS:
            await gd_insert(db.session, "official_curriculum_tracks", {**track, "is_official": True, "is_read_only": True, "created_at": now})

        print("Seeding grades...")
        for grade in GRADES:
            await gd_insert(db.session, "official_curriculum_grades", {**grade, "is_official": True, "is_read_only": True, "created_at": now})

        print("Seeding subjects and grade-subject mappings...")
        # Collect all unique subject names
        all_subjects = {}
        for grade_id, subjects in GRADE_SUBJECTS.items():
            for (subj_name, sessions, item_type) in subjects:
                if subj_name not in all_subjects:
                    sub_id = "ocs-" + subj_name.replace(" ", "-").replace("(", "").replace(")", "")[:30]
                    all_subjects[subj_name] = sub_id
                    await gd_insert(db.session, "official_curriculum_subjects", {
                        "id": sub_id,
                        "name_ar": subj_name,
                        "name_en": subj_name,
                        "is_official": True,
                        "is_read_only": True,
                        "created_at": now,
                    })

        print(f"  Created {len(all_subjects)} unique subjects")

        # Grade-subject mappings
        total_mappings = 0
        for grade_id, subjects in GRADE_SUBJECTS.items():
            for order, (subj_name, sessions, item_type) in enumerate(subjects):
                sub_id = all_subjects[subj_name]
                grade = next((g for g in GRADES if g["id"] == grade_id), None)
                if grade:
                    await gd_insert(db.session, "official_curriculum_grade_subjects", {
                        "id": str(uuid.uuid4()),
                        "grade_id": grade_id,
                        "stage_id": grade["stage_id"],
                        "track_id": grade["track_id"],
                        "subject_id": sub_id,
                        "subject_name_ar": subj_name,
                        "annual_sessions": sessions,
                        "item_type": item_type,
                        "is_official": True,
                        "is_read_only": True,
                        "display_order": order + 1,
                        "created_at": now,
                    })
                    total_mappings += 1

        print(f"  Created {total_mappings} grade-subject mappings")

        print("Seeding teacher rank loads...")
        for rank in TEACHER_RANK_LOADS:
            await gd_insert(db.session, "official_teacher_rank_loads", {
                "id": str(uuid.uuid4()),
                **rank,
                "is_official": True,
                "is_read_only": True,
                "created_at": now,
            })

        print("Seeding optional subject pools...")
        for pool in OPTIONAL_POOLS:
            pool_id = pool["id"]
            await gd_insert(db.session, "official_optional_subject_pools", {
                "id": pool_id,
                "grade_id": pool["grade_id"],
                "name_ar": pool["name_ar"],
                "total_sessions": pool["total_sessions"],
                "is_official": True,
                "is_read_only": True,
                "created_at": now,
            })
            for item in pool["items"]:
                await gd_insert(db.session, "official_optional_subject_pool_items", {
                    "id": str(uuid.uuid4()),
                    "pool_id": pool_id,
                    "name_ar": item["name_ar"],
                    "learning_type": item["learning_type"],
                    "is_official": True,
                    "is_read_only": True,
                    "created_at": now,
                })

        # Create indexes
        pass  # index handled by PostgreSQL
        pass  # index handled by PostgreSQL
        pass  # index handled by PostgreSQL
        pass  # index handled by PostgreSQL, ("subject_id", 1)])

        print("\n========= CURRICULUM SEED COMPLETE =========")
        print(f"Stages: {len(STAGES)}")
        print(f"Tracks: {len(TRACKS)}")
        print(f"Grades: {len(GRADES)}")
        print(f"Subjects: {len(all_subjects)}")
        print(f"Grade-Subject mappings: {total_mappings}")
        print(f"Teacher rank loads: {len(TEACHER_RANK_LOADS)}")
if __name__ == "__main__":
    asyncio.run(seed())
