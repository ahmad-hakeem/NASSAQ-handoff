"""
Master Seed Script - Official Curriculum Complete
سكريبت تثبيت المنهج الرسمي الكامل

This script runs all seed scripts in the correct order to populate
the official curriculum data.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

# Add the scripts directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seed_official_curriculum_complete import seed_official_curriculum
from seed_subject_details_part1 import seed_subject_details_part1
from seed_subject_details_secondary import seed_subject_details_secondary

# Database connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

async def verify_seed_data():
    """Verify the seeded data and print statistics"""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("\n" + "=" * 60)
    print("إحصائيات البيانات المُثبتة")
    print("Seeded Data Statistics")
    print("=" * 60)
    
    try:
        # Count documents in each collection
        stages_count = await db.official_curriculum_stages.count_documents({})
        tracks_count = await db.official_curriculum_tracks.count_documents({})
        grades_count = await db.official_curriculum_grades.count_documents({})
        subjects_count = await db.official_curriculum_subjects.count_documents({})
        details_count = await db.official_curriculum_subject_details.count_documents({})
        ranks_count = await db.official_teacher_rank_loads.count_documents({})
        
        print(f"\n📊 المراحل الدراسية (Stages): {stages_count}")
        print(f"📊 المسارات التعليمية (Tracks): {tracks_count}")
        print(f"📊 الصفوف والسنوات (Grades): {grades_count}")
        print(f"📊 المواد الدراسية (Subjects): {subjects_count}")
        print(f"📊 توزيع المواد (Subject Details): {details_count}")
        print(f"📊 رتب المعلمين (Teacher Ranks): {ranks_count}")
        
        # Calculate total annual periods by stage
        print("\n" + "-" * 40)
        print("توزيع المواد حسب المرحلة:")
        
        stages = await db.official_curriculum_stages.find({}).to_list(length=10)
        for stage in stages:
            stage_grades = await db.official_curriculum_grades.find(
                {"stage_id": stage["id"]}
            ).to_list(length=50)
            
            grade_ids = [g["id"] for g in stage_grades]
            details = await db.official_curriculum_subject_details.find(
                {"grade_id": {"$in": grade_ids}}
            ).to_list(length=1000)
            
            total_details = len(details)
            print(f"  • {stage['name_ar']}: {len(stage_grades)} صف/سنة، {total_details} توزيعة")
        
        print("\n" + "=" * 60)
        print("✅ تم التحقق من البيانات بنجاح!")
        print("=" * 60)
        
    finally:
        client.close()

async def run_all_seeds():
    """Run all seed scripts in order"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "تثبيت بيانات المنهج الرسمي الكامل" + " " * 11 + "║")
    print("║" + " " * 10 + "Official Curriculum Complete Seed" + " " * 12 + "║")
    print("╚" + "═" * 58 + "╝")
    print(f"\nتاريخ التنفيذ: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    try:
        # Step 1: Seed base curriculum data
        print("\n" + "=" * 60)
        print("[الخطوة 1/4] تثبيت البيانات الأساسية...")
        print("=" * 60)
        await seed_official_curriculum()
        
        # Step 2: Seed primary and middle school subject details
        print("\n" + "=" * 60)
        print("[الخطوة 2/4] تثبيت توزيع مواد المرحلة الابتدائية والمتوسطة...")
        print("=" * 60)
        await seed_subject_details_part1()
        
        # Step 3: Seed secondary school subject details
        print("\n" + "=" * 60)
        print("[الخطوة 3/4] تثبيت توزيع مواد المرحلة الثانوية...")
        print("=" * 60)
        await seed_subject_details_secondary()
        
        # Step 4: Verify all data
        print("\n" + "=" * 60)
        print("[الخطوة 4/4] التحقق من البيانات...")
        print("=" * 60)
        await verify_seed_data()
        
        print("\n")
        print("╔" + "═" * 58 + "╗")
        print("║" + " " * 15 + "✅ اكتمل التثبيت بنجاح!" + " " * 17 + "║")
        print("║" + " " * 15 + "✅ Seed Complete!" + " " * 22 + "║")
        print("╚" + "═" * 58 + "╝")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ خطأ أثناء التثبيت: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_all_seeds())
