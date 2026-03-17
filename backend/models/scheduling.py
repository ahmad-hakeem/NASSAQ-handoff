"""
Scheduling Engine Models for NASSAQ Platform
نماذج محرك الجدولة لمنصة نَسَّق

This module contains all data models for:
- Teacher Ranks (رتب المعلمين)
- Teacher Workload (نصاب المعلم)
- Class-Subject-Teacher Assignments (إسناد المعلمين للفصول والمواد)
- Time Slots (الفترات الزمنية)
- Schedule Sessions (حصص الجدول)
- School Schedules (الجداول المدرسية)
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from enum import Enum
from datetime import datetime, timezone


# ============== ENUMS ==============

class TeacherRank(str, Enum):
    """رتب المعلمين - Teacher Ranks"""
    EXPERT = "expert"           # معلم خبير
    ADVANCED = "advanced"       # معلم متقدم
    PRACTITIONER = "practitioner"  # معلم ممارس
    ASSISTANT = "assistant"     # معلم / مساعد معلم


class DayOfWeek(str, Enum):
    """أيام الأسبوع"""
    SUNDAY = "sunday"       # الأحد
    MONDAY = "monday"       # الاثنين
    TUESDAY = "tuesday"     # الثلاثاء
    WEDNESDAY = "wednesday" # الأربعاء
    THURSDAY = "thursday"   # الخميس
    FRIDAY = "friday"       # الجمعة
    SATURDAY = "saturday"   # السبت


class SessionStatus(str, Enum):
    """حالة الحصة"""
    SCHEDULED = "scheduled"     # مجدولة
    CANCELLED = "cancelled"     # ملغية
    COMPLETED = "completed"     # منتهية
    RESCHEDULED = "rescheduled" # مُعاد جدولتها


class ScheduleStatus(str, Enum):
    """حالة الجدول"""
    DRAFT = "draft"         # مسودة
    PUBLISHED = "published" # منشور
    ARCHIVED = "archived"   # مؤرشف


# ============== TEACHER WORKLOAD CONFIG ==============

class TeacherWorkloadConfig(BaseModel):
    """
    تكوين نصاب المعلم حسب الرتبة
    Teacher workload configuration by rank
    """
    rank: TeacherRank
    weekly_hours_min: int = Field(default=18, description="الحد الأدنى للنصاب الأسبوعي")
    weekly_hours_max: int = Field(default=24, description="الحد الأقصى للنصاب الأسبوعي")
    daily_sessions_max: int = Field(default=6, description="الحد الأقصى للحصص اليومية")
    consecutive_sessions_max: int = Field(default=3, description="الحد الأقصى للحصص المتتالية")


# Default workload configs by rank
DEFAULT_WORKLOAD_CONFIGS = {
    TeacherRank.EXPERT: TeacherWorkloadConfig(
        rank=TeacherRank.EXPERT,
        weekly_hours_min=12,
        weekly_hours_max=18,
        daily_sessions_max=4,
        consecutive_sessions_max=2
    ),
    TeacherRank.ADVANCED: TeacherWorkloadConfig(
        rank=TeacherRank.ADVANCED,
        weekly_hours_min=16,
        weekly_hours_max=20,
        daily_sessions_max=5,
        consecutive_sessions_max=3
    ),
    TeacherRank.PRACTITIONER: TeacherWorkloadConfig(
        rank=TeacherRank.PRACTITIONER,
        weekly_hours_min=18,
        weekly_hours_max=24,
        daily_sessions_max=6,
        consecutive_sessions_max=3
    ),
    TeacherRank.ASSISTANT: TeacherWorkloadConfig(
        rank=TeacherRank.ASSISTANT,
        weekly_hours_min=20,
        weekly_hours_max=26,
        daily_sessions_max=7,
        consecutive_sessions_max=4
    ),
}


# ============== TIME SLOT MODELS ==============

class TimeSlotCreate(BaseModel):
    """إنشاء فترة زمنية"""
    school_id: str
    name: str = Field(..., description="اسم الفترة مثل: الحصة الأولى")
    name_en: Optional[str] = None
    start_time: str = Field(..., description="وقت البداية HH:MM")
    end_time: str = Field(..., description="وقت النهاية HH:MM")
    slot_number: int = Field(..., ge=1, description="ترتيب الفترة في اليوم")
    duration_minutes: int = Field(default=45, description="مدة الفترة بالدقائق")
    is_break: bool = Field(default=False, description="هل هي فترة استراحة")


class TimeSlotResponse(BaseModel):
    """استجابة الفترة الزمنية"""
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    name: str
    name_en: Optional[str] = None
    start_time: str
    end_time: str
    slot_number: int
    duration_minutes: int
    is_break: bool
    is_active: bool
    created_at: str


# ============== TEACHER-CLASS-SUBJECT ASSIGNMENT ==============

class AssignmentPriority(str, Enum):
    """أولوية الإسناد"""
    PRIMARY = "primary"       # أساسي
    BACKUP = "backup"         # احتياطي


class TeacherAssignmentCreate(BaseModel):
    """
    إسناد معلم لفصل ومادة
    Teacher-Class-Subject Assignment
    """
    school_id: str
    teacher_id: str
    class_id: str
    subject_id: str
    weekly_sessions: int = Field(default=4, ge=1, le=10, description="عدد الحصص الأسبوعية")
    academic_year: str = Field(default="2026-2027", description="العام الدراسي")
    semester: int = Field(default=1, ge=1, le=2, description="الفصل الدراسي")
    priority: AssignmentPriority = Field(default=AssignmentPriority.PRIMARY, description="أساسي أم احتياطي")


class TeacherAssignmentResponse(BaseModel):
    """استجابة إسناد المعلم"""
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    teacher_id: str
    teacher_name: Optional[str] = None
    class_id: str
    class_name: Optional[str] = None
    subject_id: str
    subject_name: Optional[str] = None
    weekly_sessions: int
    academic_year: str
    semester: int
    priority: str = "primary"
    is_active: bool
    created_at: str


# ============== SCHEDULE SESSION ==============

class ScheduleSessionCreate(BaseModel):
    """
    إنشاء حصة في الجدول
    Create a schedule session
    """
    school_id: str
    schedule_id: str
    assignment_id: str  # Teacher-Class-Subject Assignment ID
    day_of_week: DayOfWeek
    time_slot_id: str
    room_id: Optional[str] = None  # للتطوير المستقبلي


class ScheduleSessionResponse(BaseModel):
    """استجابة حصة الجدول"""
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    schedule_id: str
    assignment_id: str
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    subject_id: Optional[str] = None
    subject_name: Optional[str] = None
    day_of_week: DayOfWeek
    time_slot_id: str
    time_slot_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room_id: Optional[str] = None
    status: SessionStatus
    created_at: str


# ============== SCHOOL SCHEDULE ==============

class SchoolScheduleCreate(BaseModel):
    """إنشاء جدول مدرسي"""
    school_id: str
    name: str = Field(..., description="اسم الجدول")
    name_en: Optional[str] = None
    academic_year: str = Field(default="2026-2027")
    semester: int = Field(default=1, ge=1, le=2)
    effective_from: str = Field(..., description="تاريخ بدء العمل بالجدول YYYY-MM-DD")
    effective_to: Optional[str] = None
    working_days: List[DayOfWeek] = Field(
        default=[DayOfWeek.SUNDAY, DayOfWeek.MONDAY, DayOfWeek.TUESDAY, 
                 DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY]
    )


class SchoolScheduleResponse(BaseModel):
    """استجابة الجدول المدرسي"""
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    name: str
    name_en: Optional[str] = None
    academic_year: str
    semester: int
    effective_from: str
    effective_to: Optional[str] = None
    working_days: List[DayOfWeek]
    status: ScheduleStatus
    total_sessions: int = 0
    created_at: str
    updated_at: str


# ============== SCHEDULE CONFLICT ==============

class ScheduleConflict(BaseModel):
    """تعارض في الجدول"""
    conflict_type: str  # teacher_double_booking, class_double_booking, room_double_booking
    message: str
    message_ar: str
    day: DayOfWeek
    time_slot_id: str
    conflicting_sessions: List[str] = []  # Session IDs
    severity: str = "error"  # error, warning


# ============== SCHEDULE GENERATION REQUEST ==============

class ScheduleGenerationRequest(BaseModel):
    """طلب توليد جدول آلي"""
    school_id: str
    schedule_id: str
    respect_teacher_workload: bool = True
    avoid_consecutive_heavy_subjects: bool = True
    distribute_subjects_evenly: bool = True
    max_iterations: int = Field(default=1000, ge=100, le=10000)


class ScheduleGenerationResult(BaseModel):
    """نتيجة توليد الجدول"""
    success: bool
    schedule_id: str
    sessions_created: int = 0
    conflicts: List[ScheduleConflict] = []
    warnings: List[str] = []
    message: str
    message_ar: str
