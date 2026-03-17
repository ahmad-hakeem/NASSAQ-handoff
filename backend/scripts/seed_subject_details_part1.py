"""
Official Subject Details Seed Script - Part 2
سكريبت تثبيت توزيع المواد لكل صف

This script seeds all subject distributions per grade/track
"""

import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

# Database connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

# Helper function to create subject detail
def create_subject_detail(grade_id, subject_id, annual_periods, period_type="class_period", order=1):
    return {
        "id": f"detail-{grade_id}-{subject_id}",
        "grade_id": grade_id,
        "subject_id": subject_id,
        "annual_periods": annual_periods,
        "weekly_periods": round(annual_periods / 36, 1),  # Assuming 36 weeks (2 semesters × 18 weeks)
        "period_type": period_type,  # class_period, non_class_period, optional
        "is_official": True,
        "is_locked": True,
        "order": order
    }

# ============================================
# المرحلة الابتدائية - التعليم العام
# ============================================

GRADE_P1_GEN = [  # الصف الأول الابتدائي
    create_subject_detail("grade-p1-gen", "subj-quran-islamic", 180, "class_period", 1),
    create_subject_detail("grade-p1-gen", "subj-arabic", 288, "class_period", 2),
    create_subject_detail("grade-p1-gen", "subj-math", 180, "class_period", 3),
    create_subject_detail("grade-p1-gen", "subj-science", 108, "class_period", 4),
    create_subject_detail("grade-p1-gen", "subj-english", 108, "class_period", 5),
    create_subject_detail("grade-p1-gen", "subj-art", 72, "class_period", 6),
    create_subject_detail("grade-p1-gen", "subj-pe", 108, "class_period", 7),
    create_subject_detail("grade-p1-gen", "subj-life-skills", 36, "class_period", 8),
    create_subject_detail("grade-p1-gen", "subj-activity", 108, "class_period", 9),
    create_subject_detail("grade-p1-gen", "subj-non-class", 240, "non_class_period", 10),
]

GRADE_P2_GEN = [  # الصف الثاني الابتدائي
    create_subject_detail("grade-p2-gen", "subj-quran-islamic", 180, "class_period", 1),
    create_subject_detail("grade-p2-gen", "subj-arabic", 252, "class_period", 2),
    create_subject_detail("grade-p2-gen", "subj-math", 216, "class_period", 3),
    create_subject_detail("grade-p2-gen", "subj-science", 108, "class_period", 4),
    create_subject_detail("grade-p2-gen", "subj-english", 108, "class_period", 5),
    create_subject_detail("grade-p2-gen", "subj-art", 72, "class_period", 6),
    create_subject_detail("grade-p2-gen", "subj-pe", 108, "class_period", 7),
    create_subject_detail("grade-p2-gen", "subj-life-skills", 36, "class_period", 8),
    create_subject_detail("grade-p2-gen", "subj-activity", 108, "class_period", 9),
    create_subject_detail("grade-p2-gen", "subj-non-class", 240, "non_class_period", 10),
]

GRADE_P3_GEN = [  # الصف الثالث الابتدائي
    create_subject_detail("grade-p3-gen", "subj-quran-islamic", 180, "class_period", 1),
    create_subject_detail("grade-p3-gen", "subj-arabic", 216, "class_period", 2),
    create_subject_detail("grade-p3-gen", "subj-math", 216, "class_period", 3),
    create_subject_detail("grade-p3-gen", "subj-science", 144, "class_period", 4),
    create_subject_detail("grade-p3-gen", "subj-english", 108, "class_period", 5),
    create_subject_detail("grade-p3-gen", "subj-art", 72, "class_period", 6),
    create_subject_detail("grade-p3-gen", "subj-pe", 108, "class_period", 7),
    create_subject_detail("grade-p3-gen", "subj-life-skills", 36, "class_period", 8),
    create_subject_detail("grade-p3-gen", "subj-activity", 108, "class_period", 9),
    create_subject_detail("grade-p3-gen", "subj-non-class", 240, "non_class_period", 10),
]

GRADE_P4_GEN = [  # الصف الرابع الابتدائي
    create_subject_detail("grade-p4-gen", "subj-quran-islamic", 180, "class_period", 1),
    create_subject_detail("grade-p4-gen", "subj-arabic", 180, "class_period", 2),
    create_subject_detail("grade-p4-gen", "subj-social", 72, "class_period", 3),
    create_subject_detail("grade-p4-gen", "subj-math", 216, "class_period", 4),
    create_subject_detail("grade-p4-gen", "subj-science", 144, "class_period", 5),
    create_subject_detail("grade-p4-gen", "subj-english", 108, "class_period", 6),
    create_subject_detail("grade-p4-gen", "subj-digital-skills", 72, "class_period", 7),
    create_subject_detail("grade-p4-gen", "subj-art", 36, "class_period", 8),
    create_subject_detail("grade-p4-gen", "subj-pe", 72, "class_period", 9),
    create_subject_detail("grade-p4-gen", "subj-life-skills", 36, "class_period", 10),
    create_subject_detail("grade-p4-gen", "subj-activity", 72, "class_period", 11),
    create_subject_detail("grade-p4-gen", "subj-non-class", 240, "non_class_period", 12),
]

GRADE_P5_GEN = [  # الصف الخامس الابتدائي
    create_subject_detail("grade-p5-gen", "subj-quran-islamic", 180, "class_period", 1),
    create_subject_detail("grade-p5-gen", "subj-arabic", 180, "class_period", 2),
    create_subject_detail("grade-p5-gen", "subj-social", 72, "class_period", 3),
    create_subject_detail("grade-p5-gen", "subj-math", 216, "class_period", 4),
    create_subject_detail("grade-p5-gen", "subj-science", 144, "class_period", 5),
    create_subject_detail("grade-p5-gen", "subj-english", 108, "class_period", 6),
    create_subject_detail("grade-p5-gen", "subj-digital-skills", 72, "class_period", 7),
    create_subject_detail("grade-p5-gen", "subj-art", 36, "class_period", 8),
    create_subject_detail("grade-p5-gen", "subj-pe", 72, "class_period", 9),
    create_subject_detail("grade-p5-gen", "subj-life-skills", 36, "class_period", 10),
    create_subject_detail("grade-p5-gen", "subj-activity", 72, "class_period", 11),
    create_subject_detail("grade-p5-gen", "subj-non-class", 240, "non_class_period", 12),
]

GRADE_P6_GEN = [  # الصف السادس الابتدائي
    create_subject_detail("grade-p6-gen", "subj-quran-islamic", 180, "class_period", 1),
    create_subject_detail("grade-p6-gen", "subj-arabic", 180, "class_period", 2),
    create_subject_detail("grade-p6-gen", "subj-social", 72, "class_period", 3),
    create_subject_detail("grade-p6-gen", "subj-math", 216, "class_period", 4),
    create_subject_detail("grade-p6-gen", "subj-science", 144, "class_period", 5),
    create_subject_detail("grade-p6-gen", "subj-english", 108, "class_period", 6),
    create_subject_detail("grade-p6-gen", "subj-digital-skills", 72, "class_period", 7),
    create_subject_detail("grade-p6-gen", "subj-art", 36, "class_period", 8),
    create_subject_detail("grade-p6-gen", "subj-pe", 72, "class_period", 9),
    create_subject_detail("grade-p6-gen", "subj-life-skills", 36, "class_period", 10),
    create_subject_detail("grade-p6-gen", "subj-activity", 72, "class_period", 11),
    create_subject_detail("grade-p6-gen", "subj-non-class", 240, "non_class_period", 12),
]

# ============================================
# المرحلة الابتدائية - تحفيظ القرآن الكريم
# ============================================

GRADE_P1_QURAN = [  # الصف الأول الابتدائي (تحفيظ)
    create_subject_detail("grade-p1-quran", "subj-quran-islamic", 324, "class_period", 1),
    create_subject_detail("grade-p1-quran", "subj-arabic", 288, "class_period", 2),
    create_subject_detail("grade-p1-quran", "subj-math", 180, "class_period", 3),
    create_subject_detail("grade-p1-quran", "subj-science", 108, "class_period", 4),
    create_subject_detail("grade-p1-quran", "subj-english", 108, "class_period", 5),
    create_subject_detail("grade-p1-quran", "subj-art", 72, "class_period", 6),
    create_subject_detail("grade-p1-quran", "subj-pe", 108, "class_period", 7),
    create_subject_detail("grade-p1-quran", "subj-life-skills", 36, "class_period", 8),
    create_subject_detail("grade-p1-quran", "subj-activity", 101, "class_period", 9),
    create_subject_detail("grade-p1-quran", "subj-non-class", 240, "non_class_period", 10),
]

GRADE_P2_QURAN = [  # الصف الثاني الابتدائي (تحفيظ)
    create_subject_detail("grade-p2-quran", "subj-quran-islamic", 324, "class_period", 1),
    create_subject_detail("grade-p2-quran", "subj-arabic", 252, "class_period", 2),
    create_subject_detail("grade-p2-quran", "subj-math", 216, "class_period", 3),
    create_subject_detail("grade-p2-quran", "subj-science", 108, "class_period", 4),
    create_subject_detail("grade-p2-quran", "subj-english", 108, "class_period", 5),
    create_subject_detail("grade-p2-quran", "subj-art", 72, "class_period", 6),
    create_subject_detail("grade-p2-quran", "subj-pe", 108, "class_period", 7),
    create_subject_detail("grade-p2-quran", "subj-life-skills", 36, "class_period", 8),
    create_subject_detail("grade-p2-quran", "subj-activity", 101, "class_period", 9),
    create_subject_detail("grade-p2-quran", "subj-non-class", 240, "non_class_period", 10),
]

GRADE_P3_QURAN = [  # الصف الثالث الابتدائي (تحفيظ)
    create_subject_detail("grade-p3-quran", "subj-quran-islamic", 324, "class_period", 1),
    create_subject_detail("grade-p3-quran", "subj-arabic", 216, "class_period", 2),
    create_subject_detail("grade-p3-quran", "subj-math", 216, "class_period", 3),
    create_subject_detail("grade-p3-quran", "subj-science", 144, "class_period", 4),
    create_subject_detail("grade-p3-quran", "subj-english", 108, "class_period", 5),
    create_subject_detail("grade-p3-quran", "subj-art", 72, "class_period", 6),
    create_subject_detail("grade-p3-quran", "subj-pe", 108, "class_period", 7),
    create_subject_detail("grade-p3-quran", "subj-life-skills", 36, "class_period", 8),
    create_subject_detail("grade-p3-quran", "subj-activity", 101, "class_period", 9),
    create_subject_detail("grade-p3-quran", "subj-non-class", 240, "non_class_period", 10),
]

GRADE_P4_QURAN = [  # الصف الرابع الابتدائي (تحفيظ)
    create_subject_detail("grade-p4-quran", "subj-quran-islamic", 288, "class_period", 1),
    create_subject_detail("grade-p4-quran", "subj-tajweed", 36, "class_period", 2),
    create_subject_detail("grade-p4-quran", "subj-arabic", 180, "class_period", 3),
    create_subject_detail("grade-p4-quran", "subj-social", 72, "class_period", 4),
    create_subject_detail("grade-p4-quran", "subj-math", 216, "class_period", 5),
    create_subject_detail("grade-p4-quran", "subj-science", 144, "class_period", 6),
    create_subject_detail("grade-p4-quran", "subj-english", 108, "class_period", 7),
    create_subject_detail("grade-p4-quran", "subj-digital-skills", 72, "class_period", 8),
    create_subject_detail("grade-p4-quran", "subj-art", 36, "class_period", 9),
    create_subject_detail("grade-p4-quran", "subj-pe", 72, "class_period", 10),
    create_subject_detail("grade-p4-quran", "subj-life-skills", 36, "class_period", 11),
    create_subject_detail("grade-p4-quran", "subj-activity", 67, "class_period", 12),
    create_subject_detail("grade-p4-quran", "subj-non-class", 240, "non_class_period", 13),
]

GRADE_P5_QURAN = [  # الصف الخامس الابتدائي (تحفيظ)
    create_subject_detail("grade-p5-quran", "subj-quran-islamic", 288, "class_period", 1),
    create_subject_detail("grade-p5-quran", "subj-tajweed", 36, "class_period", 2),
    create_subject_detail("grade-p5-quran", "subj-arabic", 180, "class_period", 3),
    create_subject_detail("grade-p5-quran", "subj-social", 72, "class_period", 4),
    create_subject_detail("grade-p5-quran", "subj-math", 216, "class_period", 5),
    create_subject_detail("grade-p5-quran", "subj-science", 144, "class_period", 6),
    create_subject_detail("grade-p5-quran", "subj-english", 108, "class_period", 7),
    create_subject_detail("grade-p5-quran", "subj-digital-skills", 72, "class_period", 8),
    create_subject_detail("grade-p5-quran", "subj-art", 36, "class_period", 9),
    create_subject_detail("grade-p5-quran", "subj-pe", 72, "class_period", 10),
    create_subject_detail("grade-p5-quran", "subj-life-skills", 36, "class_period", 11),
    create_subject_detail("grade-p5-quran", "subj-activity", 67, "class_period", 12),
    create_subject_detail("grade-p5-quran", "subj-non-class", 240, "non_class_period", 13),
]

GRADE_P6_QURAN = [  # الصف السادس الابتدائي (تحفيظ)
    create_subject_detail("grade-p6-quran", "subj-quran-islamic", 288, "class_period", 1),
    create_subject_detail("grade-p6-quran", "subj-tajweed", 36, "class_period", 2),
    create_subject_detail("grade-p6-quran", "subj-arabic", 180, "class_period", 3),
    create_subject_detail("grade-p6-quran", "subj-social", 72, "class_period", 4),
    create_subject_detail("grade-p6-quran", "subj-math", 216, "class_period", 5),
    create_subject_detail("grade-p6-quran", "subj-science", 144, "class_period", 6),
    create_subject_detail("grade-p6-quran", "subj-english", 108, "class_period", 7),
    create_subject_detail("grade-p6-quran", "subj-digital-skills", 72, "class_period", 8),
    create_subject_detail("grade-p6-quran", "subj-art", 36, "class_period", 9),
    create_subject_detail("grade-p6-quran", "subj-pe", 72, "class_period", 10),
    create_subject_detail("grade-p6-quran", "subj-life-skills", 36, "class_period", 11),
    create_subject_detail("grade-p6-quran", "subj-activity", 67, "class_period", 12),
    create_subject_detail("grade-p6-quran", "subj-non-class", 240, "non_class_period", 13),
]

# ============================================
# المرحلة المتوسطة - التعليم العام
# ============================================

GRADE_M1_GEN = [  # الصف الأول المتوسط
    create_subject_detail("grade-m1-gen", "subj-quran-islamic", 180, "class_period", 1),
    create_subject_detail("grade-m1-gen", "subj-arabic", 180, "class_period", 2),
    create_subject_detail("grade-m1-gen", "subj-social", 108, "class_period", 3),
    create_subject_detail("grade-m1-gen", "subj-math", 216, "class_period", 4),
    create_subject_detail("grade-m1-gen", "subj-science", 144, "class_period", 5),
    create_subject_detail("grade-m1-gen", "subj-english", 144, "class_period", 6),
    create_subject_detail("grade-m1-gen", "subj-digital-skills", 72, "class_period", 7),
    create_subject_detail("grade-m1-gen", "subj-art", 72, "class_period", 8),
    create_subject_detail("grade-m1-gen", "subj-pe", 72, "class_period", 9),
    create_subject_detail("grade-m1-gen", "subj-life-skills", 36, "class_period", 10),
    create_subject_detail("grade-m1-gen", "subj-critical-thinking", 0, "class_period", 11),
    create_subject_detail("grade-m1-gen", "subj-activity", 36, "class_period", 12),
    create_subject_detail("grade-m1-gen", "subj-non-class", 240, "non_class_period", 13),
]

GRADE_M2_GEN = [  # الصف الثاني المتوسط
    create_subject_detail("grade-m2-gen", "subj-quran-islamic", 180, "class_period", 1),
    create_subject_detail("grade-m2-gen", "subj-arabic", 180, "class_period", 2),
    create_subject_detail("grade-m2-gen", "subj-social", 108, "class_period", 3),
    create_subject_detail("grade-m2-gen", "subj-math", 216, "class_period", 4),
    create_subject_detail("grade-m2-gen", "subj-science", 144, "class_period", 5),
    create_subject_detail("grade-m2-gen", "subj-english", 144, "class_period", 6),
    create_subject_detail("grade-m2-gen", "subj-digital-skills", 72, "class_period", 7),
    create_subject_detail("grade-m2-gen", "subj-art", 72, "class_period", 8),
    create_subject_detail("grade-m2-gen", "subj-pe", 72, "class_period", 9),
    create_subject_detail("grade-m2-gen", "subj-life-skills", 36, "class_period", 10),
    create_subject_detail("grade-m2-gen", "subj-critical-thinking", 0, "class_period", 11),
    create_subject_detail("grade-m2-gen", "subj-activity", 36, "class_period", 12),
    create_subject_detail("grade-m2-gen", "subj-non-class", 240, "non_class_period", 13),
]

GRADE_M3_GEN = [  # الصف الثالث المتوسط
    create_subject_detail("grade-m3-gen", "subj-quran-islamic", 180, "class_period", 1),
    create_subject_detail("grade-m3-gen", "subj-arabic", 144, "class_period", 2),
    create_subject_detail("grade-m3-gen", "subj-social", 72, "class_period", 3),
    create_subject_detail("grade-m3-gen", "subj-math", 216, "class_period", 4),
    create_subject_detail("grade-m3-gen", "subj-science", 144, "class_period", 5),
    create_subject_detail("grade-m3-gen", "subj-english", 144, "class_period", 6),
    create_subject_detail("grade-m3-gen", "subj-digital-skills", 72, "class_period", 7),
    create_subject_detail("grade-m3-gen", "subj-art", 72, "class_period", 8),
    create_subject_detail("grade-m3-gen", "subj-pe", 72, "class_period", 9),
    create_subject_detail("grade-m3-gen", "subj-life-skills", 36, "class_period", 10),
    create_subject_detail("grade-m3-gen", "subj-critical-thinking", 72, "class_period", 11),
    create_subject_detail("grade-m3-gen", "subj-activity", 36, "class_period", 12),
    create_subject_detail("grade-m3-gen", "subj-non-class", 240, "non_class_period", 13),
]

# ============================================
# المرحلة المتوسطة - تحفيظ القرآن الكريم
# ============================================

GRADE_M1_QURAN = [  # الصف الأول المتوسط (تحفيظ)
    create_subject_detail("grade-m1-quran", "subj-quran-islamic", 288, "class_period", 1),
    create_subject_detail("grade-m1-quran", "subj-tajweed", 36, "class_period", 2),
    create_subject_detail("grade-m1-quran", "subj-arabic", 180, "class_period", 3),
    create_subject_detail("grade-m1-quran", "subj-social", 72, "class_period", 4),
    create_subject_detail("grade-m1-quran", "subj-math", 216, "class_period", 5),
    create_subject_detail("grade-m1-quran", "subj-science", 144, "class_period", 6),
    create_subject_detail("grade-m1-quran", "subj-english", 144, "class_period", 7),
    create_subject_detail("grade-m1-quran", "subj-digital-skills", 72, "class_period", 8),
    create_subject_detail("grade-m1-quran", "subj-art", 36, "class_period", 9),
    create_subject_detail("grade-m1-quran", "subj-pe", 36, "class_period", 10),
    create_subject_detail("grade-m1-quran", "subj-life-skills", 36, "class_period", 11),
    create_subject_detail("grade-m1-quran", "subj-critical-thinking", 0, "class_period", 12),
    create_subject_detail("grade-m1-quran", "subj-activity", 67, "class_period", 13),
    create_subject_detail("grade-m1-quran", "subj-non-class", 240, "non_class_period", 14),
]

GRADE_M2_QURAN = [  # الصف الثاني المتوسط (تحفيظ)
    create_subject_detail("grade-m2-quran", "subj-quran-islamic", 288, "class_period", 1),
    create_subject_detail("grade-m2-quran", "subj-tajweed", 36, "class_period", 2),
    create_subject_detail("grade-m2-quran", "subj-arabic", 180, "class_period", 3),
    create_subject_detail("grade-m2-quran", "subj-social", 72, "class_period", 4),
    create_subject_detail("grade-m2-quran", "subj-math", 216, "class_period", 5),
    create_subject_detail("grade-m2-quran", "subj-science", 144, "class_period", 6),
    create_subject_detail("grade-m2-quran", "subj-english", 144, "class_period", 7),
    create_subject_detail("grade-m2-quran", "subj-digital-skills", 72, "class_period", 8),
    create_subject_detail("grade-m2-quran", "subj-art", 36, "class_period", 9),
    create_subject_detail("grade-m2-quran", "subj-pe", 36, "class_period", 10),
    create_subject_detail("grade-m2-quran", "subj-life-skills", 36, "class_period", 11),
    create_subject_detail("grade-m2-quran", "subj-critical-thinking", 0, "class_period", 12),
    create_subject_detail("grade-m2-quran", "subj-activity", 67, "class_period", 13),
    create_subject_detail("grade-m2-quran", "subj-non-class", 240, "non_class_period", 14),
]

GRADE_M3_QURAN = [  # الصف الثالث المتوسط (تحفيظ)
    create_subject_detail("grade-m3-quran", "subj-quran-islamic", 252, "class_period", 1),
    create_subject_detail("grade-m3-quran", "subj-tajweed", 36, "class_period", 2),
    create_subject_detail("grade-m3-quran", "subj-arabic", 144, "class_period", 3),
    create_subject_detail("grade-m3-quran", "subj-social", 72, "class_period", 4),
    create_subject_detail("grade-m3-quran", "subj-math", 216, "class_period", 5),
    create_subject_detail("grade-m3-quran", "subj-science", 144, "class_period", 6),
    create_subject_detail("grade-m3-quran", "subj-english", 144, "class_period", 7),
    create_subject_detail("grade-m3-quran", "subj-digital-skills", 72, "class_period", 8),
    create_subject_detail("grade-m3-quran", "subj-art", 36, "class_period", 9),
    create_subject_detail("grade-m3-quran", "subj-pe", 36, "class_period", 10),
    create_subject_detail("grade-m3-quran", "subj-life-skills", 36, "class_period", 11),
    create_subject_detail("grade-m3-quran", "subj-critical-thinking", 72, "class_period", 12),
    create_subject_detail("grade-m3-quran", "subj-activity", 68, "class_period", 13),
    create_subject_detail("grade-m3-quran", "subj-non-class", 240, "non_class_period", 14),
]

# Combine all primary and middle school details
ALL_SUBJECT_DETAILS_PART1 = (
    GRADE_P1_GEN + GRADE_P2_GEN + GRADE_P3_GEN + GRADE_P4_GEN + GRADE_P5_GEN + GRADE_P6_GEN +
    GRADE_P1_QURAN + GRADE_P2_QURAN + GRADE_P3_QURAN + GRADE_P4_QURAN + GRADE_P5_QURAN + GRADE_P6_QURAN +
    GRADE_M1_GEN + GRADE_M2_GEN + GRADE_M3_GEN +
    GRADE_M1_QURAN + GRADE_M2_QURAN + GRADE_M3_QURAN
)

async def seed_subject_details_part1():
    """Seed subject details for primary and middle schools"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("=" * 60)
    print("تثبيت توزيع المواد - الجزء الأول")
    print("المرحلة الابتدائية والمتوسطة")
    print("=" * 60)
    
    try:
        count = 0
        for detail in ALL_SUBJECT_DETAILS_PART1:
            detail["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.official_curriculum_subject_details.update_one(
                {"id": detail["id"]},
                {"$set": detail},
                upsert=True
            )
            count += 1
        
        print(f"✓ تم تثبيت {count} توزيعة للمرحلة الابتدائية والمتوسطة")
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(seed_subject_details_part1())
