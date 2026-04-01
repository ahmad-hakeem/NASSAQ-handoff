"""
NASSAQ - نَسَّق
نظام إدارة المدارس الذكي المتعدد المستأجرين
Smart Multi-Tenant School Management System

Architecture (Phase 8 Modularized):
- /dependencies.py - Shared db, auth, engines, helpers
- /routes/*_mod.py - Consolidated route modules (extracted from server.py)
- /routes/*.py - Factory-pattern route modules (pre-existing)
- /engines - Core business engines
- server.py - Thin orchestrator (app init, CORS, router registration)
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("nassaq")

from fastapi import FastAPI, APIRouter, Depends, Request
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Any, Union
from datetime import datetime, timezone
from enum import Enum
import uuid
import jwt

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    generate_secure_password, generate_student_qr_code,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, smart_scheduling_engine, hakim_engine,
    reporting_engine, export_engine, session_engine,
)

from engines.session_engine import TeacherSessionEngine, session_router

app = FastAPI(
    title="NASSAQ - نَسَّق",
    description="نظام إدارة المدارس الذكي المتعدد المستأجرين",
    version="3.0.0"
)

from middleware.rate_limiter import RateLimitMiddleware
from middleware.error_handler import ErrorHandlerMiddleware
from middleware.nosql_sanitizer import NoSQLSanitizerMiddleware
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(NoSQLSanitizerMiddleware)
app.add_middleware(RateLimitMiddleware)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

from config import config as _cfg
_cors_origins = _cfg.CORS_ORIGINS
_allow_creds = _cors_origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

from routes.monitoring_routes import router as monitoring_router
app.include_router(monitoring_router)


async def _seed_platform_admins():
    admins = [
        {
            "full_name": "Dr. Ahmad Zalat",
            "email": "zalat@nassaqapp.com",
            "password": "h38xaHBJ",
            "role": "platform_admin",
        },
        {
            "full_name": "Ahmed Hakim",
            "email": "hakim@nassaqapp.com",
            "password": "Hakimnassaqapp2026$$",
            "role": "platform_admin",
        },
    ]
    for admin in admins:
        existing = await db.users.find_one({"email": admin["email"]})
        if not existing:
            user_doc = {
                "id": str(uuid.uuid4()),
                "email": admin["email"],
                "full_name": admin["full_name"],
                "password_hash": hash_password(admin["password"]),
                "role": admin["role"],
                "is_active": True,
                "tenant_id": None,
                "phone": None,
                "avatar_url": None,
                "preferred_language": "ar",
                "preferred_theme": "light",
                "must_change_password": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.users.insert_one(user_doc)
            logger.info(f"Seeded platform admin: {admin['email']}")
        else:
            if existing.get("role") != "platform_admin":
                await db.users.update_one({"email": admin["email"]}, {"$set": {"role": "platform_admin"}})
                logger.info(f"Updated role to platform_admin: {admin['email']}")


@app.on_event("startup")
async def startup_tasks():
    from config import config
    issues = config.validate()
    if issues:
        for issue in issues:
            logger.warning(f"Config issue: {issue}")
    logger.info(f"NASSAQ v{config.VERSION} starting in {config.ENVIRONMENT} mode")

    from db_indexes import create_indexes
    try:
        await create_indexes()
        logger.info("Database indexes verified on startup")
    except Exception as e:
        logger.warning(f"Index creation on startup: {e}")

    from engines.approval_engine import approval_engine
    from engines.approval_handlers import TeacherApprovalHandler, SchoolApprovalHandler
    approval_engine.register(TeacherApprovalHandler())
    approval_engine.register(SchoolApprovalHandler())
    logger.info(f"Approval engine initialized with {len(approval_engine.get_registered_types())} handler(s)")

    await _seed_platform_admins()

    from seeds.timetable_hard_constraints import seed_hard_constraints
    try:
        result = await seed_hard_constraints(db)
        logger.info(f"Timetable hard constraints: {result}")
    except Exception as e:
        logger.warning(f"Hard constraints seeding: {e}")

    from seeds.timetable_soft_constraints import seed_soft_constraints
    try:
        result = await seed_soft_constraints(db)
        logger.info(f"Timetable soft constraints: {result}")
    except Exception as e:
        logger.warning(f"Soft constraints seeding: {e}")


# ============== SHARED PYDANTIC MODELS ==============

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    full_name_en: Optional[str] = None
    role: UserRole
    tenant_id: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    preferred_language: str = "ar"
    preferred_theme: str = "light"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    full_name_en: Optional[str] = None
    role: UserRole
    tenant_id: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    full_name: str
    full_name_en: Optional[str] = None
    title: Optional[str] = None
    role: UserRole
    tenant_id: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    must_change_password: bool = False
    preferred_language: str = "ar"
    preferred_theme: str = "light"
    created_at: str
    teacher_id: Optional[str] = None
    student_id: Optional[str] = None
    parent_id: Optional[str] = None
    is_switched: bool = False
    original_role: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class SchoolBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    code: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: str = "SA"
    logo_url: Optional[str] = None
    status: SchoolStatus = SchoolStatus.PENDING
    student_capacity: int = 0
    current_students: int = 0
    current_teachers: int = 0

class SchoolCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    code: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: str = "SA"
    student_capacity: int = 500
    language: Optional[str] = "ar"
    calendar_system: Optional[str] = "hijri_gregorian"
    school_type: Optional[str] = "public"
    stage: Optional[str] = "primary"
    principal_name: Optional[str] = None
    principal_email: Optional[EmailStr] = None
    principal_phone: Optional[str] = None

class SchoolResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    name_en: Optional[str] = None
    code: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: str
    logo_url: Optional[str] = None
    status: SchoolStatus
    student_capacity: int
    current_students: int
    current_teachers: int
    created_at: str

class HakimMessage(BaseModel):
    message: str
    context: Optional[str] = None
    user_role: Optional[str] = None
    tenant_id: Optional[str] = None

class HakimResponse(BaseModel):
    response: str
    suggestions: List[str] = []

class DashboardStats(BaseModel):
    total_schools: int = 0
    total_students: int = 0
    total_teachers: int = 0
    total_classes: int = 0
    total_lessons_today: int = 0
    active_schools: int = 0
    pending_schools: int = 0
    suspended_schools: int = 0
    setup_schools: int = 0
    total_users: int = 0
    pending_requests: int = 0
    active_users: int = 0
    active_users_today: int = 0
    total_subjects: int = 0
    total_operations: int = 0
    teachers_without_classes: int = 0
    incomplete_schedules: int = 0
    schools_without_principal: int = 0
    students_missing_data: int = 0
    teachers_without_rank: int = 0
    student_attendance_rate: float = 0.0
    teacher_attendance_rate: float = 0.0
    waiting_sessions: int = 0
    lessons_today: int = 0
    last_updated: str = ""

class SuperAdminDashboardStats(BaseModel):
    total_schools: int = 0
    total_students: int = 0
    total_teachers: int = 0
    total_classes: int = 0
    total_lessons_today: int = 0
    active_users_today: int = 0
    student_attendance_percentage: float = 0.0
    teacher_attendance_percentage: float = 0.0
    waiting_sessions: int = 0
    active_schools: int = 0
    suspended_schools: int = 0
    pending_schools: int = 0
    students_present_today: int = 0
    students_absent_today: int = 0
    teachers_present_today: int = 0
    teachers_absent_today: int = 0
    schools_growth_rate: float = 0.0
    students_growth_rate: float = 0.0
    teachers_growth_rate: float = 0.0
    last_updated: str = ""

class AIOperationResult(BaseModel):
    success: bool
    message: str
    message_en: str
    health_score: Optional[int] = None
    issues_found: int = 0
    recommendations: int = 0
    details: Optional[dict] = None

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class RegistrationRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MORE_INFO_REQUESTED = "more_info_requested"
    PENDING_REVIEW = "pending_review"

class RegistrationRequest(BaseModel):
    full_name: str
    phone: str
    account_type: str
    status: RegistrationRequestStatus = RegistrationRequestStatus.PENDING
    email: Optional[str] = None
    national_id: Optional[str] = None
    school_name: Optional[str] = None
    school_email: Optional[str] = None
    school_phone: Optional[str] = None
    school_city: Optional[str] = None
    school_address: Optional[str] = None
    student_capacity: Optional[str] = None
    school_code: Optional[str] = None
    specialization: Optional[str] = None
    subject: Optional[str] = None
    educational_level: Optional[str] = None
    school_mentioned: Optional[str] = None
    country: Optional[str] = "السعودية"
    years_of_experience: Optional[str] = None

class RegistrationRequestResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    full_name: str
    phone: str
    account_type: str
    status: str
    email: Optional[str] = None
    national_id: Optional[str] = None
    school_name: Optional[str] = None
    school_email: Optional[str] = None
    school_phone: Optional[str] = None
    school_city: Optional[str] = None
    school_address: Optional[str] = None
    student_capacity: Optional[str] = None
    school_code: Optional[str] = None
    specialization: Optional[str] = None
    subject: Optional[str] = None
    educational_level: Optional[str] = None
    school_mentioned: Optional[str] = None
    country: Optional[str] = None
    years_of_experience: Optional[str] = None
    created_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None
    additional_info: Optional[str] = None

class ApproveRequestData(BaseModel):
    admin_note: Optional[str] = None

class RejectRequestData(BaseModel):
    reason: str

class RequestMoreInfoData(BaseModel):
    questions: str

class TeacherApprovalResult(BaseModel):
    success: bool
    message: str
    teacher_id: Optional[str] = None
    user_id: Optional[str] = None
    temp_password: Optional[str] = None
    school_id: Optional[str] = None
    school_name: Optional[str] = None

class TeacherCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    specialization: Optional[str] = None
    rank: Optional[str] = None
    subject: Optional[str] = None
    qualification: Optional[str] = None
    years_of_experience: Optional[int] = None

class TeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    specialization: Optional[str] = None
    rank: Optional[str] = None
    subject: Optional[str] = None
    qualification: Optional[str] = None
    years_of_experience: Optional[int] = None
    is_active: Optional[bool] = None

class TeacherResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    specialization: Optional[str] = None
    rank: Optional[str] = None
    subject: Optional[str] = None
    qualification: Optional[str] = None
    years_of_experience: Optional[int] = None
    school_id: str
    is_active: bool = True
    created_at: Optional[str] = None
    weekly_periods: Optional[int] = None
    max_daily_periods: Optional[int] = None

class StudentCreate(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    student_number: Optional[str] = None
    grade: Optional[str] = None
    class_id: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_email: Optional[EmailStr] = None
    parent_name: Optional[str] = None

class StudentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    student_number: Optional[str] = None
    grade: Optional[str] = None
    class_id: Optional[str] = None
    school_id: str
    parent_phone: Optional[str] = None
    parent_email: Optional[str] = None
    parent_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    qr_code: Optional[str] = None

class ClassCreate(BaseModel):
    name: str
    grade: Optional[str] = None
    section: Optional[str] = None
    capacity: int = 30
    class_teacher_id: Optional[str] = None
    grade_id: Optional[str] = None
    academic_year_id: Optional[str] = None

class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    student_number: Optional[str] = None
    grade: Optional[str] = None
    class_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_email: Optional[EmailStr] = None
    parent_name: Optional[str] = None
    is_active: Optional[bool] = None

class ClassUpdate(BaseModel):
    name: Optional[str] = None
    grade: Optional[str] = None
    section: Optional[str] = None
    capacity: Optional[int] = None
    class_teacher_id: Optional[str] = None
    grade_id: Optional[str] = None
    academic_year_id: Optional[str] = None

class ClassResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    grade: Optional[Union[int, str]] = None
    section: Optional[str] = None
    capacity: int = 30
    school_id: str
    class_teacher_id: Optional[str] = None
    grade_id: Optional[str] = None
    grade_level_id: Optional[str] = None
    academic_year_id: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    current_students: int = 0
    student_count: int = 0
    homeroom_teacher_id: Optional[str] = None
    homeroom_teacher_name: Optional[str] = None
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    class_type: Optional[str] = None

class SubjectCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    code: Optional[str] = None
    weekly_periods: int = 4
    description: Optional[str] = None
    grade_level: Optional[str] = None

class SubjectResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    name_en: Optional[str] = None
    code: Optional[str] = None
    weekly_periods: int = 4
    description: Optional[str] = None
    school_id: str
    is_active: bool = True
    created_at: Optional[str] = None

class TeacherRankEnum(str, Enum):
    TEACHER = "معلم"
    ADVANCED_TEACHER = "معلم متقدم"
    EXPERT_TEACHER = "معلم خبير"

class DayOfWeekEnum(str, Enum):
    SUNDAY = "الأحد"
    MONDAY = "الإثنين"
    TUESDAY = "الثلاثاء"
    WEDNESDAY = "الأربعاء"
    THURSDAY = "الخميس"

class SessionStatusEnum(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ScheduleStatusEnum(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ACTIVE = "active"
    ARCHIVED = "archived"

class TimeSlotCreate(BaseModel):
    period_number: int
    start_time: str
    end_time: str
    slot_type: str = "class"
    label: Optional[str] = None
    day: Optional[str] = None

class TimeSlotResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    period_number: int
    start_time: str
    end_time: str
    slot_type: str
    label: Optional[str] = None
    day: Optional[str] = None
    is_active: bool = True

class TeacherAssignmentCreate(BaseModel):
    teacher_id: str
    subject_id: str
    class_id: str
    periods_per_week: int = 1
    schedule_id: Optional[str] = None
    is_primary: bool = True

class TeacherAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    teacher_id: str
    subject_id: str
    class_id: str
    periods_per_week: int
    schedule_id: Optional[str] = None
    is_primary: bool = True
    is_active: bool = True
    created_at: Optional[str] = None

class SchoolScheduleCreate(BaseModel):
    name: str
    academic_year: Optional[str] = None
    semester: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "draft"

class SchoolScheduleResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    name: str
    academic_year: Optional[str] = None
    semester: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    created_by: Optional[str] = None

class ScheduleSessionCreate(BaseModel):
    schedule_id: str
    teacher_assignment_id: Optional[str] = None
    teacher_id: Optional[str] = None
    subject_id: Optional[str] = None
    class_id: Optional[str] = None
    day: str
    period_number: int
    time_slot_id: Optional[str] = None
    room: Optional[str] = None

class ScheduleSessionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    schedule_id: str
    teacher_assignment_id: Optional[str] = None
    teacher_id: Optional[str] = None
    subject_id: Optional[str] = None
    class_id: Optional[str] = None
    day: str
    period_number: int
    time_slot_id: Optional[str] = None
    room: Optional[str] = None
    status: str = "scheduled"
    created_at: Optional[str] = None
    teacher_name: Optional[str] = None
    subject_name: Optional[str] = None
    class_name: Optional[str] = None


# ============== REGISTER PHASE 8 MODULARIZED ROUTES ==============

from routes.auth_routes_mod import router as auth_mod_router
from routes.user_routes_mod import router as user_mod_router
from routes.school_routes_mod import router as school_mod_router
from routes.dashboard_routes_mod import router as dashboard_mod_router
from routes.ai_routes_mod import router as ai_mod_router
from routes.registration_routes_mod import router as registration_mod_router
from routes.academics_routes_mod import router as academics_mod_router
from routes.scheduling_routes_mod import router as scheduling_mod_router
from routes.attendance_routes_mod import router as attendance_mod_router
from routes.assessment_routes_mod import router as assessment_mod_router
from routes.behaviour_routes_mod import router as behaviour_mod_router
from routes.notification_routes_mod import router as notification_mod_router
from routes.platform_routes_mod import router as platform_mod_router
from routes.reporting_routes_mod import router as reporting_mod_router
from routes.role_dashboards_mod import router as role_dashboards_mod_router
from routes.admin_routes_mod import router as admin_mod_router
from routes.school_settings_mod import router as school_settings_mod_router
from routes.participation_routes_mod import router as participation_mod_router
from routes.search_directory_routes_mod import router as search_directory_mod_router
from routes.event_workflow_routes_mod import router as event_workflow_mod_router
from routes.relationship_routes_mod import router as relationship_mod_router
from routes.consent_privacy_routes_mod import router as consent_privacy_mod_router
from routes.activities_routes_mod import router as activities_mod_router
from routes.product_hub_routes import router as product_hub_router

api_router.include_router(auth_mod_router)
api_router.include_router(user_mod_router)
api_router.include_router(school_mod_router)
api_router.include_router(dashboard_mod_router)
api_router.include_router(ai_mod_router)
api_router.include_router(registration_mod_router)
api_router.include_router(academics_mod_router)

from routes.academic_structure_routes import router as academic_structure_router
api_router.include_router(academic_structure_router)
api_router.include_router(scheduling_mod_router)
api_router.include_router(attendance_mod_router)
api_router.include_router(assessment_mod_router)
api_router.include_router(behaviour_mod_router)
api_router.include_router(notification_mod_router)
api_router.include_router(participation_mod_router)
api_router.include_router(platform_mod_router)
api_router.include_router(reporting_mod_router)
api_router.include_router(role_dashboards_mod_router)
api_router.include_router(admin_mod_router)
api_router.include_router(school_settings_mod_router)
api_router.include_router(search_directory_mod_router)
api_router.include_router(event_workflow_mod_router)
api_router.include_router(relationship_mod_router)
api_router.include_router(consent_privacy_mod_router)
api_router.include_router(activities_mod_router)
api_router.include_router(product_hub_router)

from routes.principal_management_routes import router as principal_mgmt_router
api_router.include_router(principal_mgmt_router)

from routes.official_curriculum_routes import router as official_curriculum_router, set_database as set_official_curriculum_db
set_official_curriculum_db(db)
api_router.include_router(official_curriculum_router)

from routes.timetable_readiness_routes import router as timetable_readiness_router, set_database as set_readiness_db
set_readiness_db(db)
api_router.include_router(timetable_readiness_router)

from routes.principal_timetable_routes import (
    router as principal_timetable_router,
    set_db as set_principal_tt_db,
    set_engine as set_principal_tt_engine
)
set_principal_tt_db(db)
set_principal_tt_engine(smart_scheduling_engine)
api_router.include_router(principal_timetable_router)

# ============== REGISTER PRE-EXISTING FACTORY ROUTES ==============

from routes.scheduling_routes import create_scheduling_router
from routes.attendance_routes import create_attendance_router
from routes.assessment_routes import create_assessment_router
from routes.audit_routes import create_audit_router
from routes.teacher_registration_routes import create_teacher_registration_router
from routes.student_management_routes import create_student_routes
from routes.teacher_management_routes import create_teacher_management_routes
from routes.class_management_routes import create_class_management_routes
from routes.notification_routes import create_notification_routes
from routes.schedule_management_routes import create_schedule_management_routes

scheduling_router = create_scheduling_router(db, get_current_user, require_roles, UserRole)
attendance_router = create_attendance_router(db, get_current_user, require_roles, UserRole)
assessment_router = create_assessment_router(db, get_current_user, require_roles, UserRole)
audit_router = create_audit_router(db, get_current_user, require_roles, UserRole)
teacher_registration_router = create_teacher_registration_router(db, get_current_user, require_roles, UserRole)
student_routes = create_student_routes(db, get_current_user)
teacher_management_routes = create_teacher_management_routes(db, get_current_user)
class_management_routes = create_class_management_routes(db, get_current_user)
notification_routes = create_notification_routes(db, get_current_user)
schedule_management_routes = create_schedule_management_routes(db, get_current_user)

from routes.teacher_attendance_routes import create_teacher_attendance_routes
teacher_attendance_router = create_teacher_attendance_routes(db, get_current_user, require_roles, UserRole)

from routes.communication_routes import create_communication_routes
communication_router = create_communication_routes(db, get_current_user, require_roles, UserRole)

from routes.bulk_teacher_routes import create_bulk_teacher_routes
bulk_teacher_router = create_bulk_teacher_routes(db, get_current_user, require_roles, UserRole, hash_password, generate_secure_password)

from routes.student_creation_routes import create_student_creation_routes
student_creation_router = create_student_creation_routes(db, get_current_user, require_roles, UserRole, hash_password, generate_secure_password)

from routes.admin_dashboard_routes import setup_admin_routes
admin_dashboard_router = setup_admin_routes(db, get_current_user, require_roles, UserRole)

from routes.security_routes import setup_security_routes
security_router = setup_security_routes(db, get_current_user, require_roles, UserRole)

from routes.audit_routes import setup_audit_routes
audit_router = setup_audit_routes(db, get_current_user, require_roles, UserRole)

from routes.settings_routes import setup_settings_routes
settings_router = setup_settings_routes(db, get_current_user, require_roles, UserRole)

from routes.user_roles_routes import setup_user_roles_routes
user_roles_router = setup_user_roles_routes(db, get_current_user, require_roles, UserRole, create_access_token)

from routes.websocket_routes import create_websocket_routes, get_connection_manager, send_realtime_notification

def decode_token_for_ws(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
        return None

websocket_router, ws_manager = create_websocket_routes(db, decode_token_for_ws)

from routes.bulk_import_export_routes import setup_bulk_routes, setup_import_tracking_routes
bulk_routes = setup_bulk_routes(db, get_current_user, require_roles, UserRole)
import_tracking_routes = setup_import_tracking_routes(db, get_current_user, require_roles, UserRole)

from routes.student_portal_routes import setup_student_portal_routes
student_portal_routes = setup_student_portal_routes(db, get_current_user, require_roles, UserRole)

from routes.parent_portal_routes import setup_parent_portal_routes
parent_portal_routes = setup_parent_portal_routes(db, get_current_user, require_roles, UserRole)

api_router.include_router(scheduling_router)
api_router.include_router(attendance_router)
api_router.include_router(assessment_router)
api_router.include_router(audit_router)
api_router.include_router(teacher_registration_router)
api_router.include_router(student_routes)
api_router.include_router(teacher_management_routes)
api_router.include_router(class_management_routes)
api_router.include_router(notification_routes)
api_router.include_router(schedule_management_routes)
api_router.include_router(teacher_attendance_router)
api_router.include_router(communication_router)
api_router.include_router(bulk_teacher_router)
api_router.include_router(student_creation_router)
api_router.include_router(admin_dashboard_router)
api_router.include_router(security_router)
api_router.include_router(audit_router)
api_router.include_router(settings_router)
api_router.include_router(user_roles_router)
api_router.include_router(websocket_router)
api_router.include_router(bulk_routes)
api_router.include_router(import_tracking_routes)
api_router.include_router(student_portal_routes)
api_router.include_router(parent_portal_routes)

app.include_router(api_router)
app.include_router(session_router)

import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

FRONTEND_BUILD = Path(__file__).parent.parent / "frontend" / "build"
if FRONTEND_BUILD.exists() and (FRONTEND_BUILD / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD / "static")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        file_path = FRONTEND_BUILD / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_BUILD / "index.html"))
