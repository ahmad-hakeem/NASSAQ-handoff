"""
Master Seed Script - Official Curriculum Complete

This script runs all seed scripts in the correct order to populate
the official curriculum data.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from seed_official_curriculum_complete import seed_official_curriculum
from seed_subject_details_part1 import seed_subject_details_part1
from seed_subject_details_secondary import seed_subject_details_secondary
from scripts.seed_db_helper import get_seed_db


async def verify_seed_data():
    async with get_seed_db() as db:
        print("\n" + "=" * 60)
        print("Seeded Data Statistics")
        print("=" * 60)

        stages_count = await db.official_curriculum_stages.count_documents({})
        tracks_count = await db.official_curriculum_tracks.count_documents({})
        grades_count = await db.official_curriculum_grades.count_documents({})
        subjects_count = await db.official_curriculum_subjects.count_documents({})
        details_count = await db.official_curriculum_subject_details.count_documents({})
        ranks_count = await db.official_teacher_rank_loads.count_documents({})

        print(f"\nStages: {stages_count}")
        print(f"Tracks: {tracks_count}")
        print(f"Grades: {grades_count}")
        print(f"Subjects: {subjects_count}")
        print(f"Subject Details: {details_count}")
        print(f"Teacher Ranks: {ranks_count}")

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
            print(f"  {stage['name_ar']}: {len(stage_grades)} grades, {total_details} details")

        print("\n" + "=" * 60)


async def run_all_seeds():
    print(f"\nOfficial Curriculum Complete Seed")
    print(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    try:
        print("\n[Step 1/4] Seeding base curriculum data...")
        await seed_official_curriculum()

        print("\n[Step 2/4] Seeding primary & middle school subject details...")
        await seed_subject_details_part1()

        print("\n[Step 3/4] Seeding secondary school subject details...")
        await seed_subject_details_secondary()

        print("\n[Step 4/4] Verifying data...")
        await verify_seed_data()

        print("\nSeed Complete!")

    except Exception as e:
        print(f"\nError during seed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_all_seeds())
