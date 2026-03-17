"""
NASSAQ Database Index Management
Creates compound indexes on key collections for query optimization.
Run at startup or via CLI: python db_indexes.py
"""
import asyncio
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from pymongo import IndexModel, ASCENDING, DESCENDING

load_dotenv(Path(__file__).parent / '.env')
logger = logging.getLogger("nassaq.indexes")

INDEXES = {
    "users": [
        IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email"),
        IndexModel([("role", ASCENDING), ("tenant_id", ASCENDING)], name="idx_users_role_tenant"),
        IndexModel([("tenant_id", ASCENDING), ("is_active", ASCENDING)], name="idx_users_tenant_active"),
        IndexModel([("id", ASCENDING)], unique=True, sparse=True, name="idx_users_id"),
    ],
    "schools": [
        IndexModel([("id", ASCENDING)], unique=True, name="idx_schools_id"),
        IndexModel([("code", ASCENDING)], unique=True, name="idx_schools_code"),
        IndexModel([("status", ASCENDING)], name="idx_schools_status"),
        IndexModel([("city", ASCENDING)], name="idx_schools_city"),
    ],
    "teachers": [
        IndexModel([("school_id", ASCENDING), ("is_active", ASCENDING)], name="idx_teachers_school_active"),
        IndexModel([("email", ASCENDING)], name="idx_teachers_email"),
        IndexModel([("id", ASCENDING)], unique=True, name="idx_teachers_id"),
    ],
    "students": [
        IndexModel([("school_id", ASCENDING), ("class_id", ASCENDING)], name="idx_students_school_class"),
        IndexModel([("school_id", ASCENDING), ("is_active", ASCENDING)], name="idx_students_school_active"),
        IndexModel([("email", ASCENDING)], sparse=True, name="idx_students_email"),
        IndexModel([("student_number", ASCENDING), ("school_id", ASCENDING)], name="idx_students_number_school"),
        IndexModel([("id", ASCENDING)], unique=True, name="idx_students_id"),
    ],
    "classes": [
        IndexModel([("school_id", ASCENDING), ("is_active", ASCENDING)], name="idx_classes_school_active"),
        IndexModel([("school_id", ASCENDING), ("grade_id", ASCENDING)], name="idx_classes_school_grade"),
        IndexModel([("id", ASCENDING)], unique=True, name="idx_classes_id"),
    ],
    "subjects": [
        IndexModel([("school_id", ASCENDING)], name="idx_subjects_school"),
        IndexModel([("id", ASCENDING)], unique=True, name="idx_subjects_id"),
    ],
    "attendance": [
        IndexModel([("school_id", ASCENDING), ("date", DESCENDING)], name="idx_attendance_school_date"),
        IndexModel([("student_id", ASCENDING), ("date", DESCENDING)], name="idx_attendance_student_date"),
        IndexModel([("class_id", ASCENDING), ("date", DESCENDING)], name="idx_attendance_class_date"),
        IndexModel([("school_id", ASCENDING), ("class_id", ASCENDING), ("date", DESCENDING)], name="idx_attendance_school_class_date"),
    ],
    "assessments": [
        IndexModel([("school_id", ASCENDING), ("class_id", ASCENDING)], name="idx_assessments_school_class"),
        IndexModel([("teacher_id", ASCENDING)], name="idx_assessments_teacher"),
        IndexModel([("id", ASCENDING)], unique=True, name="idx_assessments_id"),
    ],
    "assessment_submissions": [
        IndexModel([("assessment_id", ASCENDING), ("student_id", ASCENDING)], name="idx_submissions_assessment_student"),
        IndexModel([("student_id", ASCENDING)], name="idx_submissions_student"),
    ],
    "behaviour_records": [
        IndexModel([("school_id", ASCENDING), ("student_id", ASCENDING)], name="idx_behaviour_school_student"),
        IndexModel([("school_id", ASCENDING), ("created_at", DESCENDING)], name="idx_behaviour_school_date"),
    ],
    "notifications": [
        IndexModel([("user_id", ASCENDING), ("is_read", ASCENDING), ("created_at", DESCENDING)], name="idx_notifications_user_read_date"),
        IndexModel([("tenant_id", ASCENDING), ("created_at", DESCENDING)], name="idx_notifications_tenant_date"),
    ],
    "audit_logs": [
        IndexModel([("school_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_audit_school_time"),
        IndexModel([("entity_type", ASCENDING), ("entity_id", ASCENDING)], name="idx_audit_entity"),
        IndexModel([("performed_by", ASCENDING), ("timestamp", DESCENDING)], name="idx_audit_user_time"),
    ],
    "schedule_sessions": [
        IndexModel([("school_id", ASCENDING), ("schedule_id", ASCENDING), ("day", ASCENDING)], name="idx_sessions_school_sched_day"),
        IndexModel([("teacher_id", ASCENDING), ("day", ASCENDING)], name="idx_sessions_teacher_day"),
        IndexModel([("class_id", ASCENDING), ("day", ASCENDING)], name="idx_sessions_class_day"),
    ],
    "teacher_assignments": [
        IndexModel([("school_id", ASCENDING), ("teacher_id", ASCENDING)], name="idx_assigns_school_teacher"),
        IndexModel([("school_id", ASCENDING), ("class_id", ASCENDING)], name="idx_assigns_school_class"),
        IndexModel(
            [("teacher_id", ASCENDING), ("subject_id", ASCENDING), ("school_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"is_active": True},
            name="idx_assigns_teacher_subject_unique"
        ),
    ],
    "school_settings": [
        IndexModel([("school_id", ASCENDING)], unique=True, name="idx_school_settings_school"),
    ],
    "registration_requests": [
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="idx_requests_status_date"),
    ],
    "teacher_sessions": [
        IndexModel([("school_id", ASCENDING), ("session_date", DESCENDING)], name="idx_teacher_sessions_school_date"),
        IndexModel([("teacher_id", ASCENDING), ("session_date", DESCENDING)], name="idx_teacher_sessions_teacher_date"),
        IndexModel([("class_id", ASCENDING), ("session_date", DESCENDING)], name="idx_teacher_sessions_class_date"),
    ],
    "hakim_insights": [
        IndexModel([("school_id", ASCENDING), ("created_at", DESCENDING)], name="idx_hakim_school_date"),
    ],
    "platform_settings": [
        IndexModel([("type", ASCENDING)], unique=True, name="idx_platform_settings_type"),
    ],
    "time_slots": [
        IndexModel([("school_id", ASCENDING)], name="idx_time_slots_school"),
    ],
    "timetable_runs": [
        IndexModel([("school_id", ASCENDING), ("created_at", DESCENDING)], name="idx_timetable_runs_school_date"),
    ],
    "academic_years": [
        IndexModel([("school_id", ASCENDING)], name="idx_academic_years_school"),
    ],
    "academic_terms": [
        IndexModel([("school_id", ASCENDING)], name="idx_academic_terms_school"),
    ],
    "parents": [
        IndexModel([("email", ASCENDING)], sparse=True, name="idx_parents_email"),
        IndexModel([("id", ASCENDING)], unique=True, name="idx_parents_id"),
    ],
    "skills_types": [
        IndexModel([("id", ASCENDING)], unique=True, name="idx_skills_types_id"),
        IndexModel([("category", ASCENDING)], name="idx_skills_types_category"),
    ],
    "student_skills": [
        IndexModel([("student_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_student_skills_student"),
        IndexModel([("session_id", ASCENDING)], name="idx_student_skills_session"),
        IndexModel([("class_id", ASCENDING)], name="idx_student_skills_class"),
        IndexModel([("skill_type_id", ASCENDING)], name="idx_student_skills_type"),
    ],
    "session_interactions": [
        IndexModel([("session_id", ASCENDING)], name="idx_session_interactions_session"),
        IndexModel([("student_id", ASCENDING)], name="idx_session_interactions_student"),
        IndexModel([("interaction_type", ASCENDING)], name="idx_session_interactions_type"),
    ],
    "ai_insights": [
        IndexModel([("school_id", ASCENDING), ("type", ASCENDING)], name="idx_ai_insights_school_type"),
        IndexModel([("entity_id", ASCENDING), ("type", ASCENDING)], name="idx_ai_insights_entity_type"),
        IndexModel([("created_at", DESCENDING)], name="idx_ai_insights_created"),
    ],
    "ai_interventions": [
        IndexModel([("school_id", ASCENDING), ("status", ASCENDING)], name="idx_ai_interventions_school_status"),
        IndexModel([("student_id", ASCENDING), ("status", ASCENDING)], name="idx_ai_interventions_student_status"),
        IndexModel([("created_at", DESCENDING)], name="idx_ai_interventions_created"),
    ],
    "session_notes": [
        IndexModel([("session_id", ASCENDING)], name="idx_session_notes_session"),
        IndexModel([("teacher_id", ASCENDING)], name="idx_session_notes_teacher"),
        IndexModel([("student_id", ASCENDING)], name="idx_session_notes_student"),
    ],
    "session_event_log": [
        IndexModel([("session_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_session_events_session_time"),
        IndexModel([("event_type", ASCENDING)], name="idx_session_events_type"),
    ],
    "teacher_class_assignments": [
        IndexModel(
            [("school_id", ASCENDING), ("teacher_id", ASCENDING), ("class_id", ASCENDING)],
            unique=True,
            name="idx_tca_school_teacher_class_unique",
        ),
    ],
}


async def create_indexes():
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db_inst = client[os.environ['DB_NAME']]

    total = 0
    for collection_name, indexes in INDEXES.items():
        try:
            collection = db_inst[collection_name]
            result = await collection.create_indexes(indexes)
            total += len(result)
            logger.info(f"Created {len(result)} indexes on {collection_name}: {result}")
        except Exception as e:
            logger.warning(f"Index creation on {collection_name}: {e}")

    logger.info(f"Total indexes created/verified: {total}")
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(create_indexes())
    print(f"Done: {result} indexes created/verified")
