"""
Official Subject Details Seed Script - Part 3
سكريبت تثبيت توزيع المواد للمرحلة الثانوية

This script seeds all subject distributions for secondary stage
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
        "weekly_periods": round(annual_periods / 36, 1),  # 36 weeks
        "period_type": period_type,
        "is_official": True,
        "is_locked": True,
        "order": order
    }

# ============================================
# المرحلة الثانوية - السنة الأولى المشتركة
# ============================================

GRADE_S1_COMMON = [
    create_subject_detail("grade-s1-common", "subj-quran-tafseer", 60, "class_period", 1),
    create_subject_detail("grade-s1-common", "subj-math", 180, "class_period", 2),
    create_subject_detail("grade-s1-common", "subj-english", 180, "class_period", 3),
    create_subject_detail("grade-s1-common", "subj-digital-tech", 108, "class_period", 4),
    create_subject_detail("grade-s1-common", "subj-biology", 60, "class_period", 5),
    create_subject_detail("grade-s1-common", "subj-chemistry", 60, "class_period", 6),
    create_subject_detail("grade-s1-common", "subj-physics", 60, "class_period", 7),
    create_subject_detail("grade-s1-common", "subj-environment", 36, "class_period", 8),
    create_subject_detail("grade-s1-common", "subj-kifayat", 120, "class_period", 9),
    create_subject_detail("grade-s1-common", "subj-hadith", 36, "class_period", 10),
    create_subject_detail("grade-s1-common", "subj-financial-literacy", 36, "class_period", 11),
    create_subject_detail("grade-s1-common", "subj-social", 60, "class_period", 12),
    create_subject_detail("grade-s1-common", "subj-critical-thinking", 48, "class_period", 13),
    create_subject_detail("grade-s1-common", "subj-vocational", 36, "class_period", 14),
    create_subject_detail("grade-s1-common", "subj-pe-health", 72, "class_period", 15),
    create_subject_detail("grade-s1-common", "subj-activity", 60, "class_period", 16),
    create_subject_detail("grade-s1-common", "subj-non-class", 216, "non_class_period", 17),
]

# ============================================
# المرحلة الثانوية - المسار العام
# ============================================

GRADE_S2_GENERAL = [  # السنة الثانية - المسار العام
    create_subject_detail("grade-s2-general", "subj-math", 180, "class_period", 1),
    create_subject_detail("grade-s2-general", "subj-english", 180, "class_period", 2),
    create_subject_detail("grade-s2-general", "subj-chemistry", 180, "class_period", 3),
    create_subject_detail("grade-s2-general", "subj-biology", 144, "class_period", 4),
    create_subject_detail("grade-s2-general", "subj-physics", 60, "class_period", 5),
    create_subject_detail("grade-s2-general", "subj-tawheed", 36, "class_period", 6),
    create_subject_detail("grade-s2-general", "subj-kifayat", 72, "class_period", 7),
    create_subject_detail("grade-s2-general", "subj-digital-tech", 72, "class_period", 8),
    create_subject_detail("grade-s2-general", "subj-history", 60, "class_period", 9),
    create_subject_detail("grade-s2-general", "subj-arts", 36, "class_period", 10),
    create_subject_detail("grade-s2-general", "subj-fitness", 60, "class_period", 11),
    create_subject_detail("grade-s2-general", "subj-activity", 72, "class_period", 12),
    create_subject_detail("grade-s2-general", "subj-non-class", 216, "non_class_period", 13),
]

GRADE_S3_GENERAL = [  # السنة الثالثة - المسار العام
    create_subject_detail("grade-s3-general", "subj-math", 144, "class_period", 1),
    create_subject_detail("grade-s3-general", "subj-english", 144, "class_period", 2),
    create_subject_detail("grade-s3-general", "subj-chemistry", 60, "class_period", 3),
    create_subject_detail("grade-s3-general", "subj-physics", 180, "class_period", 4),
    create_subject_detail("grade-s3-general", "subj-earth-space", 96, "class_period", 5),
    create_subject_detail("grade-s3-general", "subj-fiqh", 36, "class_period", 6),
    create_subject_detail("grade-s3-general", "subj-literary-studies", 36, "class_period", 7),
    create_subject_detail("grade-s3-general", "subj-psychology", 36, "class_period", 8),
    create_subject_detail("grade-s3-general", "subj-digital-tech", 36, "class_period", 9),
    create_subject_detail("grade-s3-general", "subj-digital-citizenship", 36, "class_period", 10),
    create_subject_detail("grade-s3-general", "subj-geography", 36, "class_period", 11),
    create_subject_detail("grade-s3-general", "subj-life-skills-sec", 36, "class_period", 12),
    create_subject_detail("grade-s3-general", "subj-pe-health", 48, "class_period", 13),
    create_subject_detail("grade-s3-general", "subj-research", 36, "class_period", 14),
    create_subject_detail("grade-s3-general", "subj-optional", 120, "optional", 15),
    create_subject_detail("grade-s3-general", "subj-activity", 72, "class_period", 16),
    create_subject_detail("grade-s3-general", "subj-non-class", 216, "non_class_period", 17),
]

# ============================================
# المرحلة الثانوية - مسار علوم الحاسب والهندسة
# ============================================

GRADE_S2_CS_ENG = [  # السنة الثانية - مسار علوم الحاسب والهندسة
    create_subject_detail("grade-s2-cs-eng", "subj-math", 180, "class_period", 1),
    create_subject_detail("grade-s2-cs-eng", "subj-english", 180, "class_period", 2),
    create_subject_detail("grade-s2-cs-eng", "subj-chemistry", 180, "class_period", 3),
    create_subject_detail("grade-s2-cs-eng", "subj-biology", 144, "class_period", 4),
    create_subject_detail("grade-s2-cs-eng", "subj-physics", 60, "class_period", 5),
    create_subject_detail("grade-s2-cs-eng", "subj-tawheed", 36, "class_period", 6),
    create_subject_detail("grade-s2-cs-eng", "subj-kifayat", 72, "class_period", 7),
    create_subject_detail("grade-s2-cs-eng", "subj-data-science", 36, "class_period", 8),
    create_subject_detail("grade-s2-cs-eng", "subj-iot", 72, "class_period", 9),
    create_subject_detail("grade-s2-cs-eng", "subj-engineering", 60, "class_period", 10),
    create_subject_detail("grade-s2-cs-eng", "subj-fitness", 60, "class_period", 11),
    create_subject_detail("grade-s2-cs-eng", "subj-activity", 72, "class_period", 12),
    create_subject_detail("grade-s2-cs-eng", "subj-non-class", 216, "non_class_period", 13),
]

GRADE_S3_CS_ENG = [  # السنة الثالثة - مسار علوم الحاسب والهندسة
    create_subject_detail("grade-s3-cs-eng", "subj-math", 144, "class_period", 1),
    create_subject_detail("grade-s3-cs-eng", "subj-english", 144, "class_period", 2),
    create_subject_detail("grade-s3-cs-eng", "subj-chemistry", 60, "class_period", 3),
    create_subject_detail("grade-s3-cs-eng", "subj-physics", 180, "class_period", 4),
    create_subject_detail("grade-s3-cs-eng", "subj-earth-space", 96, "class_period", 5),
    create_subject_detail("grade-s3-cs-eng", "subj-fiqh", 36, "class_period", 6),
    create_subject_detail("grade-s3-cs-eng", "subj-literary-studies", 36, "class_period", 7),
    create_subject_detail("grade-s3-cs-eng", "subj-ai", 84, "class_period", 8),
    create_subject_detail("grade-s3-cs-eng", "subj-cybersecurity", 36, "class_period", 9),
    create_subject_detail("grade-s3-cs-eng", "subj-software-eng", 60, "class_period", 10),
    create_subject_detail("grade-s3-cs-eng", "subj-eng-design", 48, "class_period", 11),
    create_subject_detail("grade-s3-cs-eng", "subj-life-skills-sec", 36, "class_period", 12),
    create_subject_detail("grade-s3-cs-eng", "subj-pe-health", 48, "class_period", 13),
    create_subject_detail("grade-s3-cs-eng", "subj-research", 36, "class_period", 14),
    create_subject_detail("grade-s3-cs-eng", "subj-graduation", 36, "class_period", 15),
    create_subject_detail("grade-s3-cs-eng", "subj-activity", 72, "class_period", 16),
    create_subject_detail("grade-s3-cs-eng", "subj-non-class", 216, "non_class_period", 17),
]

# ============================================
# المرحلة الثانوية - مسار الصحة والحياة
# ============================================

GRADE_S2_HEALTH = [  # السنة الثانية - مسار الصحة والحياة
    create_subject_detail("grade-s2-health", "subj-math", 180, "class_period", 1),
    create_subject_detail("grade-s2-health", "subj-english", 180, "class_period", 2),
    create_subject_detail("grade-s2-health", "subj-chemistry", 180, "class_period", 3),
    create_subject_detail("grade-s2-health", "subj-biology", 144, "class_period", 4),
    create_subject_detail("grade-s2-health", "subj-physics", 60, "class_period", 5),
    create_subject_detail("grade-s2-health", "subj-tawheed", 36, "class_period", 6),
    create_subject_detail("grade-s2-health", "subj-kifayat", 72, "class_period", 7),
    create_subject_detail("grade-s2-health", "subj-digital-tech", 72, "class_period", 8),
    create_subject_detail("grade-s2-health", "subj-health-principles", 96, "class_period", 9),
    create_subject_detail("grade-s2-health", "subj-fitness", 60, "class_period", 10),
    create_subject_detail("grade-s2-health", "subj-activity", 72, "class_period", 11),
    create_subject_detail("grade-s2-health", "subj-non-class", 216, "non_class_period", 12),
]

GRADE_S3_HEALTH = [  # السنة الثالثة - مسار الصحة والحياة
    create_subject_detail("grade-s3-health", "subj-math", 144, "class_period", 1),
    create_subject_detail("grade-s3-health", "subj-english", 144, "class_period", 2),
    create_subject_detail("grade-s3-health", "subj-chemistry", 60, "class_period", 3),
    create_subject_detail("grade-s3-health", "subj-physics", 180, "class_period", 4),
    create_subject_detail("grade-s3-health", "subj-earth-space", 96, "class_period", 5),
    create_subject_detail("grade-s3-health", "subj-fiqh", 36, "class_period", 6),
    create_subject_detail("grade-s3-health", "subj-literary-studies", 36, "class_period", 7),
    create_subject_detail("grade-s3-health", "subj-health-care", 108, "class_period", 8),
    create_subject_detail("grade-s3-health", "subj-human-systems", 84, "class_period", 9),
    create_subject_detail("grade-s3-health", "subj-statistics", 36, "class_period", 10),
    create_subject_detail("grade-s3-health", "subj-life-skills-sec", 36, "class_period", 11),
    create_subject_detail("grade-s3-health", "subj-pe-health", 48, "class_period", 12),
    create_subject_detail("grade-s3-health", "subj-research", 36, "class_period", 13),
    create_subject_detail("grade-s3-health", "subj-graduation", 36, "class_period", 14),
    create_subject_detail("grade-s3-health", "subj-activity", 72, "class_period", 15),
    create_subject_detail("grade-s3-health", "subj-non-class", 216, "non_class_period", 16),
]

# ============================================
# المرحلة الثانوية - مسار إدارة الأعمال
# ============================================

GRADE_S2_BUSINESS = [  # السنة الثانية - مسار إدارة الأعمال
    create_subject_detail("grade-s2-business", "subj-english", 180, "class_period", 1),
    create_subject_detail("grade-s2-business", "subj-tawheed", 36, "class_period", 2),
    create_subject_detail("grade-s2-business", "subj-tafseer", 36, "class_period", 3),
    create_subject_detail("grade-s2-business", "subj-kifayat", 72, "class_period", 4),
    create_subject_detail("grade-s2-business", "subj-linguistic-studies", 60, "class_period", 5),
    create_subject_detail("grade-s2-business", "subj-business-decision", 156, "class_period", 6),
    create_subject_detail("grade-s2-business", "subj-business-intro", 120, "class_period", 7),
    create_subject_detail("grade-s2-business", "subj-economics", 48, "class_period", 8),
    create_subject_detail("grade-s2-business", "subj-financial-mgmt", 108, "class_period", 9),
    create_subject_detail("grade-s2-business", "subj-digital-tech", 72, "class_period", 10),
    create_subject_detail("grade-s2-business", "subj-history", 60, "class_period", 11),
    create_subject_detail("grade-s2-business", "subj-arts", 36, "class_period", 12),
    create_subject_detail("grade-s2-business", "subj-fitness", 60, "class_period", 13),
    create_subject_detail("grade-s2-business", "subj-activity", 108, "class_period", 14),
    create_subject_detail("grade-s2-business", "subj-non-class", 216, "non_class_period", 15),
]

GRADE_S3_BUSINESS = [  # السنة الثالثة - مسار إدارة الأعمال
    create_subject_detail("grade-s3-business", "subj-english", 144, "class_period", 1),
    create_subject_detail("grade-s3-business", "subj-fiqh", 36, "class_period", 2),
    create_subject_detail("grade-s3-business", "subj-literary-studies", 36, "class_period", 3),
    create_subject_detail("grade-s3-business", "subj-psychology", 36, "class_period", 4),
    create_subject_detail("grade-s3-business", "subj-rhetoric", 48, "class_period", 5),
    create_subject_detail("grade-s3-business", "subj-admin-principles", 60, "class_period", 6),
    create_subject_detail("grade-s3-business", "subj-events-mgmt", 120, "class_period", 7),
    create_subject_detail("grade-s3-business", "subj-marketing", 120, "class_period", 8),
    create_subject_detail("grade-s3-business", "subj-secretary", 60, "class_period", 9),
    create_subject_detail("grade-s3-business", "subj-law-principles", 120, "class_period", 10),
    create_subject_detail("grade-s3-business", "subj-law-applications", 36, "class_period", 11),
    create_subject_detail("grade-s3-business", "subj-digital-citizenship", 36, "class_period", 12),
    create_subject_detail("grade-s3-business", "subj-statistics", 36, "class_period", 13),
    create_subject_detail("grade-s3-business", "subj-geography", 36, "class_period", 14),
    create_subject_detail("grade-s3-business", "subj-life-skills-sec", 36, "class_period", 15),
    create_subject_detail("grade-s3-business", "subj-pe-health", 48, "class_period", 16),
    create_subject_detail("grade-s3-business", "subj-research", 36, "class_period", 17),
    create_subject_detail("grade-s3-business", "subj-graduation", 36, "class_period", 18),
    create_subject_detail("grade-s3-business", "subj-activity", 72, "class_period", 19),
    create_subject_detail("grade-s3-business", "subj-non-class", 216, "non_class_period", 20),
]

# ============================================
# المرحلة الثانوية - المسار الشرعي
# ============================================

GRADE_S2_ISLAMIC = [  # السنة الثانية - المسار الشرعي
    create_subject_detail("grade-s2-islamic", "subj-quran", 180, "class_period", 1),
    create_subject_detail("grade-s2-islamic", "subj-english", 180, "class_period", 2),
    create_subject_detail("grade-s2-islamic", "subj-tawheed1", 36, "class_period", 3),
    create_subject_detail("grade-s2-islamic", "subj-tawheed2", 36, "class_period", 4),
    create_subject_detail("grade-s2-islamic", "subj-hadith", 36, "class_period", 5),
    create_subject_detail("grade-s2-islamic", "subj-qiraat1", 60, "class_period", 6),
    create_subject_detail("grade-s2-islamic", "subj-qiraat2", 60, "class_period", 7),
    create_subject_detail("grade-s2-islamic", "subj-quran-sciences", 60, "class_period", 8),
    create_subject_detail("grade-s2-islamic", "subj-tafseer", 36, "class_period", 9),
    create_subject_detail("grade-s2-islamic", "subj-kifayat", 72, "class_period", 10),
    create_subject_detail("grade-s2-islamic", "subj-linguistic-studies", 60, "class_period", 11),
    create_subject_detail("grade-s2-islamic", "subj-digital-tech", 72, "class_period", 12),
    create_subject_detail("grade-s2-islamic", "subj-history", 60, "class_period", 13),
    create_subject_detail("grade-s2-islamic", "subj-arts", 36, "class_period", 14),
    create_subject_detail("grade-s2-islamic", "subj-fitness", 60, "class_period", 15),
    create_subject_detail("grade-s2-islamic", "subj-activity", 108, "class_period", 16),
    create_subject_detail("grade-s2-islamic", "subj-non-class", 216, "non_class_period", 17),
]

GRADE_S3_ISLAMIC = [  # السنة الثالثة - المسار الشرعي
    create_subject_detail("grade-s3-islamic", "subj-quran", 180, "class_period", 1),
    create_subject_detail("grade-s3-islamic", "subj-english", 144, "class_period", 2),
    create_subject_detail("grade-s3-islamic", "subj-tafseer", 36, "class_period", 3),
    create_subject_detail("grade-s3-islamic", "subj-fiqh1", 36, "class_period", 4),
    create_subject_detail("grade-s3-islamic", "subj-fiqh2", 60, "class_period", 5),
    create_subject_detail("grade-s3-islamic", "subj-usul-fiqh", 36, "class_period", 6),
    create_subject_detail("grade-s3-islamic", "subj-hadith-term", 36, "class_period", 7),
    create_subject_detail("grade-s3-islamic", "subj-faraid", 48, "class_period", 8),
    create_subject_detail("grade-s3-islamic", "subj-literary-studies", 36, "class_period", 9),
    create_subject_detail("grade-s3-islamic", "subj-psychology", 36, "class_period", 10),
    create_subject_detail("grade-s3-islamic", "subj-rhetoric", 48, "class_period", 11),
    create_subject_detail("grade-s3-islamic", "subj-law-principles", 120, "class_period", 12),
    create_subject_detail("grade-s3-islamic", "subj-law-applications", 36, "class_period", 13),
    create_subject_detail("grade-s3-islamic", "subj-digital-citizenship", 36, "class_period", 14),
    create_subject_detail("grade-s3-islamic", "subj-geography", 36, "class_period", 15),
    create_subject_detail("grade-s3-islamic", "subj-life-skills-sec", 36, "class_period", 16),
    create_subject_detail("grade-s3-islamic", "subj-pe-health", 48, "class_period", 17),
    create_subject_detail("grade-s3-islamic", "subj-research", 36, "class_period", 18),
    create_subject_detail("grade-s3-islamic", "subj-graduation", 36, "class_period", 19),
    create_subject_detail("grade-s3-islamic", "subj-activity", 72, "class_period", 20),
    create_subject_detail("grade-s3-islamic", "subj-non-class", 216, "non_class_period", 21),
]

# Combine all secondary school details
ALL_SUBJECT_DETAILS_SECONDARY = (
    GRADE_S1_COMMON +
    GRADE_S2_GENERAL + GRADE_S3_GENERAL +
    GRADE_S2_CS_ENG + GRADE_S3_CS_ENG +
    GRADE_S2_HEALTH + GRADE_S3_HEALTH +
    GRADE_S2_BUSINESS + GRADE_S3_BUSINESS +
    GRADE_S2_ISLAMIC + GRADE_S3_ISLAMIC
)

async def seed_subject_details_secondary():
    """Seed subject details for secondary schools"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("=" * 60)
    print("تثبيت توزيع المواد - المرحلة الثانوية")
    print("=" * 60)
    
    try:
        count = 0
        for detail in ALL_SUBJECT_DETAILS_SECONDARY:
            detail["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.official_curriculum_subject_details.update_one(
                {"id": detail["id"]},
                {"$set": detail},
                upsert=True
            )
            count += 1
        
        print(f"✓ تم تثبيت {count} توزيعة للمرحلة الثانوية")
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(seed_subject_details_secondary())
