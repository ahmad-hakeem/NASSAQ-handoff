"""
NASSAQ Shared Pydantic Models
All Pydantic models shared across route modules.
"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator, field_validator
import re


# FIX (C6): Single source of truth for the Saudi national ID format. Routes used
# inconsistent validation (some demanded exactly 10 chars, others accepted any
# string) which let invalid IDs slip into one path and rejected valid ones in
# another. Use `validate_saudi_national_id(value, required=...)` from any model.
_SAUDI_NATIONAL_ID_RE = re.compile(r"^[12]\d{9}$")


def validate_saudi_national_id(value, required: bool = True):
    """Return the cleaned ID or raise ValueError. Pass required=False to allow None/''."""
    if value is None or value == "":
        if required:
            raise ValueError("رقم الهوية الوطنية مطلوب")
        return None
    cleaned = str(value).strip()
    if not _SAUDI_NATIONAL_ID_RE.match(cleaned):
        raise ValueError("رقم الهوية الوطنية غير صالح: يجب أن يكون 10 أرقام ويبدأ بـ 1 أو 2")
    return cleaned
from typing import List, Optional, Any, Union
from datetime import datetime, timezone
from enum import Enum
import re as _re
import uuid

from dependencies import UserRole, SchoolStatus

_PHONE_RE = _re.compile(r"^\+?[0-9]{7,15}$")
_PASSWORD_MIN = 8
_PASSWORD_MAX = 128
_NAME_MIN = 2
_NAME_MAX = 100


def validate_password_complexity(password: str) -> str:
    if len(password) < _PASSWORD_MIN:
        raise ValueError(f"كلمة المرور يجب أن تكون {_PASSWORD_MIN} أحرف على الأقل")
    if len(password) > _PASSWORD_MAX:
        raise ValueError(f"كلمة المرور يجب ألا تتجاوز {_PASSWORD_MAX} حرفاً")
    if not _re.search(r"[A-Za-z]", password):
        raise ValueError("كلمة المرور يجب أن تحتوي على حرف واحد على الأقل")
    if not _re.search(r"[0-9]", password):
        raise ValueError("كلمة المرور يجب أن تحتوي على رقم واحد على الأقل")
    return password


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=_NAME_MIN, max_length=_NAME_MAX)
    full_name_en: Optional[str] = Field(None, max_length=_NAME_MAX)
    role: UserRole
    tenant_id: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    preferred_language: str = "ar"
    preferred_theme: str = "light"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "":
            cleaned = v.replace(" ", "").replace("-", "")
            if not _PHONE_RE.match(cleaned):
                raise ValueError("رقم الهاتف غير صالح — يجب أن يحتوي على 7-15 رقماً")
            return cleaned
        return v

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=_PASSWORD_MIN, max_length=_PASSWORD_MAX)
    full_name: str = Field(..., min_length=_NAME_MIN, max_length=_NAME_MAX)
    full_name_en: Optional[str] = Field(None, max_length=_NAME_MAX)
    role: UserRole
    tenant_id: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)

    @field_validator("full_name")
    @classmethod
    def check_full_name(cls, v: str) -> str:
        if v and v.strip() != v:
            v = v.strip()
        if len(v) < _NAME_MIN:
            raise ValueError(f"الاسم يجب أن يكون {_NAME_MIN} أحرف على الأقل")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "":
            cleaned = v.replace(" ", "").replace("-", "")
            if not _PHONE_RE.match(cleaned):
                raise ValueError("رقم الهاتف غير صالح — يجب أن يحتوي على 7-15 رقماً")
            return cleaned
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
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
    has_generic_name: Optional[bool] = False
    preferred_language: Optional[str] = "ar"
    preferred_theme: Optional[str] = "light"
    created_at: Optional[str] = None
    teacher_id: Optional[str] = None
    student_id: Optional[str] = None
    parent_id: Optional[str] = None
    is_switched: bool = False
    original_role: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
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
    principal_mobile: Optional[str] = None
    educational_pathway: Optional[str] = None

class SchoolResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
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
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class RegistrationRequestStatus(str, Enum):
    PENDING = "pending"
    PENDING_REVIEW = "pending_review"
    UNDER_VERIFICATION = "under_verification"
    APPROVED = "approved"
    REJECTED = "rejected"
    MORE_INFO_REQUESTED = "more_info_requested"

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
    model_config = ConfigDict(extra="ignore", from_attributes=True)
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
    message: str = ""
    questions: str = ""

    @model_validator(mode="after")
    def normalize_message(self):
        if not self.message and self.questions:
            self.message = self.questions
        return self

class TeacherApprovalResult(BaseModel):
    success: bool
    message: str
    teacher_id: Optional[str] = None
    user_id: Optional[str] = None
    temp_password: Optional[str] = None
    school_id: Optional[str] = None
    school_name: Optional[str] = None

class TeacherCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str
    full_name_en: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    school_id: Optional[str] = None
    specialization: Optional[str] = None
    rank: Optional[str] = None
    subject: Optional[str] = None
    qualification: Optional[str] = None
    years_of_experience: Optional[int] = None
    gender: Optional[str] = None

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
    model_config = ConfigDict(extra="ignore", from_attributes=True)
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
    model_config = ConfigDict(extra="ignore")
    full_name: str
    full_name_en: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    school_id: Optional[str] = None
    student_number: Optional[str] = None
    grade: Optional[str] = None
    class_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_email: Optional[EmailStr] = None
    parent_name: Optional[str] = None
    is_gifted: Optional[bool] = False
    talents: Optional[List[str]] = []
    character_traits: Optional[List[str]] = []

class StudentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    id: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    student_number: Optional[str] = None
    national_id: Optional[str] = None
    grade: Optional[str] = None
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    section: Optional[str] = None
    school_id: str
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    parent_id: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_email: Optional[str] = None
    parent_name: Optional[str] = None
    parent_relationship: Optional[str] = None
    is_gifted: Optional[bool] = False
    talents: Optional[List[str]] = []
    character_traits: Optional[List[str]] = []
    is_active: bool = True
    created_at: Optional[str] = None
    qr_code: Optional[str] = None
    nationality: Optional[str] = None
    enrollment_date: Optional[str] = None
    health_info: Optional[dict] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None

class ClassCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    name_en: Optional[str] = None
    school_id: Optional[str] = None
    grade: Optional[str] = None
    grade_level: Optional[str] = None
    section: Optional[str] = None
    capacity: int = 30
    class_teacher_id: Optional[str] = None
    homeroom_teacher_id: Optional[str] = None
    grade_id: Optional[str] = None
    academic_year_id: Optional[str] = None

class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    student_number: Optional[str] = None
    national_id: Optional[str] = None
    grade: Optional[str] = None
    class_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_email: Optional[EmailStr] = None
    parent_name: Optional[str] = None
    parent_relationship: Optional[str] = None
    is_gifted: Optional[bool] = None
    talents: Optional[List[str]] = None
    character_traits: Optional[List[str]] = None
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
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    id: str
    name: str
    grade: Optional[Union[int, str]] = None
    section: Optional[str] = None
    capacity: Optional[int] = 30
    school_id: str
    class_teacher_id: Optional[str] = None
    grade_id: Optional[str] = None
    grade_level_id: Optional[str] = None
    academic_year_id: Optional[str] = None
    is_active: Optional[bool] = True
    created_at: Optional[str] = None
    current_students: Optional[int] = 0
    student_count: Optional[int] = 0
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
    model_config = ConfigDict(extra="ignore", from_attributes=True)
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
    school_id: Optional[str] = None

class TimeSlotResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    id: str
    school_id: Optional[str] = None
    name: Optional[str] = None
    name_en: Optional[str] = None
    period_number: Optional[int] = None
    slot_number: Optional[int] = None
    start_time: str
    end_time: str
    duration_minutes: Optional[int] = 45
    slot_type: Optional[str] = "teaching"
    is_break: Optional[bool] = False
    is_prayer: Optional[bool] = False
    label: Optional[str] = None
    day: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class TeacherAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    teacher_id: str
    subject_id: str
    class_id: Optional[str] = None
    school_id: Optional[str] = None
    periods_per_week: Optional[int] = None
    weekly_sessions: Optional[int] = 4
    academic_year: Optional[str] = None
    semester: Optional[int] = 1
    schedule_id: Optional[str] = None
    is_primary: bool = True

class TeacherAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    id: str
    school_id: Optional[str] = None
    teacher_id: str
    subject_id: Optional[str] = None
    class_id: Optional[str] = None
    periods_per_week: Optional[int] = 0
    schedule_id: Optional[str] = None
    is_primary: bool = True
    is_active: bool = True
    created_at: Optional[str] = None
    teacher_name: Optional[str] = None
    class_name: Optional[str] = None
    subject_name: Optional[str] = None

class SchoolScheduleCreate(BaseModel):
    name: str
    academic_year: Optional[str] = None
    semester: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "draft"
    school_id: Optional[str] = None

class SchoolScheduleResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
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
    model_config = ConfigDict(extra="ignore", from_attributes=True)
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


