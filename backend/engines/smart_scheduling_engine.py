"""
NASSAQ Smart Scheduling Engine - محرك الجدولة الذكي
======================================================
نظام متقدم لتوليد الجداول الدراسية بالذكاء الاصطناعي

يتضمن:
- التحقق من جاهزية البيانات (Pre-Validation)
- تحميل إعدادات المدرسة
- بناء مصفوفة الطلب الأكاديمي
- بناء مصفوفة الموارد المتاحة
- تشغيل التحقق المسبق من التعارضات
- إنشاء مسودة الجدول
- تطبيق القيود أثناء التوزيع
- تحسين الجدول
- إنتاج النتائج

Database Schema (23 Tables):
- schools, academic_years, academic_terms, school_settings
- academic_stages, grades, classes, subjects, grade_subjects
- teachers, teacher_ranks, teacher_subjects, teacher_availability
- administrative_constraints, school_holidays
- timetable_runs, timetable_run_logs
- timetables, timetable_sessions, timetable_conflicts, timetable_unscheduled_demands
- timetable_approvals, audit_logs
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel, Field
import uuid
import logging
import random

logger = logging.getLogger(__name__)


# ============== ENUMS ==============

class TimetableRunStatus(str, Enum):
    """حالة تشغيل محرك الجدولة"""
    PENDING = "pending"           # في انتظار البدء
    VALIDATING = "validating"     # التحقق من البيانات
    LOADING = "loading"           # تحميل البيانات
    GENERATING = "generating"     # توليد الجدول
    OPTIMIZING = "optimizing"     # تحسين الجدول
    COMPLETED = "completed"       # اكتمل بنجاح
    FAILED = "failed"             # فشل
    PARTIAL = "partial"           # اكتمل جزئياً


class TimetableStatus(str, Enum):
    """حالة الجدول"""
    DRAFT = "draft"               # مسودة
    REVIEW = "review"             # قيد المراجعة
    APPROVED = "approved"         # معتمد
    PUBLISHED = "published"       # منشور
    ARCHIVED = "archived"         # مؤرشف


class SessionSourceType(str, Enum):
    """مصدر إنشاء الحصة"""
    AI_GENERATED = "ai_generated"     # توليد آلي
    MANUAL = "manual"                 # إدخال يدوي
    HYBRID_ADJUSTED = "hybrid_adjusted"  # معدّل


class SessionStatus(str, Enum):
    """حالة الحصة"""
    SCHEDULED = "scheduled"       # مجدولة
    CANCELLED = "cancelled"       # ملغاة
    SUBSTITUTE = "substitute"     # بديلة


class ConflictType(str, Enum):
    """نوع التعارض"""
    TEACHER_OVERLAP = "teacher_overlap"         # تعارض معلم
    CLASS_OVERLAP = "class_overlap"             # تعارض فصل
    SUBJECT_CONSECUTIVE = "subject_consecutive"  # مواد متتالية
    TEACHER_OVERLOAD = "teacher_overload"       # تجاوز نصاب
    AVAILABILITY = "availability"                # توافر
    CONSTRAINT_VIOLATION = "constraint_violation"  # انتهاك قيد


class ConflictSeverity(str, Enum):
    """شدة التعارض"""
    CRITICAL = "critical"         # حرج - يمنع النشر
    HIGH = "high"                 # عالي
    MEDIUM = "medium"             # متوسط
    LOW = "low"                   # منخفض


class DayOfWeek(str, Enum):
    """أيام الأسبوع"""
    SUNDAY = "sunday"
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"


# ============== PYDANTIC MODELS ==============

class ValidationIssue(BaseModel):
    """مشكلة في التحقق"""
    category: str           # teachers, classes, subjects, etc.
    severity: str           # critical, warning, info
    message_ar: str
    message_en: str
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None


class PreValidationResult(BaseModel):
    """نتيجة التحقق المسبق"""
    is_valid: bool
    can_proceed: bool
    issues: List[ValidationIssue] = []
    summary: Dict[str, Any] = {}


class AcademicDemand(BaseModel):
    """طلب أكاديمي - مصفوفة الطلب"""
    class_id: str
    class_name: str
    grade_id: str
    subjects: List[Dict[str, Any]]  # subject_id, weekly_periods, suitable_teachers
    total_periods_required: int


class ResourceAvailability(BaseModel):
    """توافر الموارد"""
    teacher_id: str
    teacher_name: str
    subject_ids: List[str]
    weekly_load: int
    current_load: int = 0
    availability: Dict[str, List[int]]  # day -> available_periods


class SchedulingCandidate(BaseModel):
    """مرشح للجدولة"""
    class_id: str
    subject_id: str
    teacher_id: str
    day: str
    period: int
    score: float = 0.0
    is_valid: bool = True
    violations: List[str] = []


class TimetableSession(BaseModel):
    """حصة في الجدول"""
    id: str
    timetable_id: str
    school_id: str
    class_id: str
    grade_id: str
    subject_id: str
    teacher_id: str
    day_of_week: str
    period_number: int
    start_time: str
    end_time: str
    session_type: str = "class"  # class, break, prayer
    source_type: str = "ai_generated"
    status: str = "scheduled"


class TimetableConflict(BaseModel):
    """تعارض في الجدول"""
    id: str
    run_id: str
    timetable_id: Optional[str] = None
    conflict_type: str
    class_id: Optional[str] = None
    teacher_id: Optional[str] = None
    subject_id: Optional[str] = None
    day_of_week: str
    period_number: int
    severity: str
    message_ar: str
    message_en: str
    is_resolved: bool = False


class UnscheduledDemand(BaseModel):
    """طلب غير مجدول"""
    id: str
    run_id: str
    school_id: str
    class_id: str
    grade_id: str
    subject_id: str
    required_periods: int
    scheduled_periods: int
    remaining_periods: int
    reason_ar: str
    reason_en: str


class TimetableRunLog(BaseModel):
    """سجل تشغيل المحرك"""
    id: str
    run_id: str
    log_level: str  # info, warning, error, debug
    message: str
    context: Dict[str, Any] = {}
    created_at: str


class GenerationResult(BaseModel):
    """نتيجة توليد الجدول"""
    success: bool
    timetable_id: Optional[str] = None
    run_id: str
    status: str
    completion_percentage: float
    total_sessions: int
    scheduled_sessions: int
    conflicts_count: int
    unscheduled_count: int
    optimization_score: float
    message_ar: str
    message_en: str


# ============== SMART SCHEDULING ENGINE ==============

class SmartSchedulingEngine:
    """
    محرك الجدولة الذكي - النظام الرئيسي
    Smart Scheduling Engine - Main System
    """
    
    def __init__(self, db):
        self.db = db
        # Collections
        self.schools = db.schools
        self.school_settings = db.school_settings
        self.academic_years = db.academic_years
        self.academic_terms = db.academic_terms
        self.stages = db.academic_stages
        self.grades = db.grades
        self.classes = db.classes
        self.subjects = db.subjects
        self.grade_subjects = db.grade_subjects
        self.teachers = db.teachers
        self.teacher_ranks = db.teacher_ranks
        self.teacher_subjects = db.teacher_subjects
        self.teacher_availability = db.teacher_availability
        self.constraints = db.administrative_constraints
        self.school_constraints = db.school_constraints
        self.hard_constraints = db.timetable_hard_constraints
        self.soft_constraints = db.timetable_soft_constraints
        self.holidays = db.school_holidays
        self.teacher_assignments = db.teacher_assignments
        # Timetable collections
        self.timetable_runs = db.timetable_runs
        self.timetable_run_logs = db.timetable_run_logs
        self.timetables = db.timetables
        self.timetable_sessions = db.timetable_sessions
        self.timetable_conflicts = db.timetable_conflicts
        self.unscheduled_demands = db.timetable_unscheduled_demands
        self.timetable_approvals = db.timetable_approvals
        self.audit_logs = db.audit_logs
        # Reference data
        self.reference_subjects = db.reference_subjects
        self.reference_teacher_ranks = db.reference_teacher_ranks
        self.admin_constraints = db.admin_constraints
        self.default_settings = db.default_settings
        
    # ============== PHASE 1: PRE-VALIDATION ==============
    
    async def validate_data_readiness(self, school_id: str) -> PreValidationResult:
        """
        المرحلة 1: التحقق من جاهزية البيانات الأساسية
        Phase 1: Validate basic data readiness
        """
        issues = []
        summary = {
            "school": None,
            "academic_year": None,
            "academic_term": None,
            "stages": 0,
            "grades": 0,
            "classes": 0,
            "subjects": 0,
            "grade_subjects": 0,
            "teachers": 0,
            "teachers_with_assignments": 0,
            "teacher_availability_records": 0,
            "working_days": 0,
            "periods_per_day": 0,
            "constraints": 0,
            "holidays": 0
        }
        
        # 1. Check school exists
        school = await self.schools.find_one({"id": school_id}, {"_id": 0})
        if not school:
            issues.append(ValidationIssue(
                category="school",
                severity="critical",
                message_ar="المدرسة غير موجودة",
                message_en="School not found",
                entity_id=school_id
            ))
            return PreValidationResult(is_valid=False, can_proceed=False, issues=issues, summary=summary)
        summary["school"] = school.get("name", school.get("name_ar", ""))
        
        # 2. Check academic year
        academic_year = await self.academic_years.find_one(
            {"school_id": school_id, "is_current": True}, {"_id": 0}
        )
        if not academic_year:
            # Try to find any academic year
            academic_year = await self.academic_years.find_one(
                {"school_id": school_id}, {"_id": 0}
            )
        if not academic_year:
            issues.append(ValidationIssue(
                category="academic_year",
                severity="critical",
                message_ar="لا يوجد عام دراسي محدد",
                message_en="No academic year defined"
            ))
        else:
            summary["academic_year"] = academic_year.get("name", academic_year.get("id"))
        
        # 3. Check academic term/semester
        if academic_year:
            academic_term = await self.academic_terms.find_one(
                {"school_id": school_id, "academic_year_id": academic_year.get("id"), "is_active": True},
                {"_id": 0}
            )
            if academic_term:
                summary["academic_term"] = academic_term.get("name")
        
        # 4. Check academic structure - Stages
        stages_count = await self.stages.count_documents({"school_id": school_id, "is_active": True})
        if stages_count == 0:
            # Check reference stages
            ref_stages_count = await self.stages.count_documents({"is_active": True})
            stages_count = ref_stages_count
        summary["stages"] = stages_count
        if stages_count == 0:
            issues.append(ValidationIssue(
                category="stages",
                severity="warning",
                message_ar="لا توجد مراحل دراسية محددة",
                message_en="No academic stages defined"
            ))
        
        # 5. Check Grades
        grades_count = await self.grades.count_documents({"school_id": school_id, "is_active": True})
        if grades_count == 0:
            # Check reference grades
            grades_count = await self.grades.count_documents({"is_active": True})
        summary["grades"] = grades_count
        if grades_count == 0:
            issues.append(ValidationIssue(
                category="grades",
                severity="critical",
                message_ar="لا توجد صفوف دراسية محددة",
                message_en="No grades defined"
            ))
        
        # 6. Check Classes
        classes_count = await self.classes.count_documents({"school_id": school_id, "is_active": {"$ne": False}})
        summary["classes"] = classes_count
        if classes_count == 0:
            issues.append(ValidationIssue(
                category="classes",
                severity="critical",
                message_ar="لا توجد فصول دراسية",
                message_en="No classes defined"
            ))
        
        # 7. Check Subjects
        subjects_count = await self.subjects.count_documents({"school_id": school_id, "is_active": {"$ne": False}})
        if subjects_count == 0:
            # Check reference subjects
            subjects_count = await self.reference_subjects.count_documents({"is_active": {"$ne": False}})
        summary["subjects"] = subjects_count
        if subjects_count == 0:
            issues.append(ValidationIssue(
                category="subjects",
                severity="critical",
                message_ar="لا توجد مواد دراسية",
                message_en="No subjects defined"
            ))
        
        # 8. Check Grade-Subject mappings
        grade_subjects_count = await self.grade_subjects.count_documents({"school_id": school_id, "is_active": True})
        summary["grade_subjects"] = grade_subjects_count
        if grade_subjects_count == 0:
            issues.append(ValidationIssue(
                category="grade_subjects",
                severity="warning",
                message_ar="لا توجد روابط بين الصفوف والمواد",
                message_en="No grade-subject mappings"
            ))
        
        # 9. Check Teachers
        teachers_count = await self.teachers.count_documents({"school_id": school_id, "is_active": {"$ne": False}})
        summary["teachers"] = teachers_count
        if teachers_count == 0:
            issues.append(ValidationIssue(
                category="teachers",
                severity="critical",
                message_ar="لا يوجد معلمون مسجلون",
                message_en="No teachers registered"
            ))
        
        # 10. Check Teacher Assignments (teacher_subjects or teacher_assignments)
        assignments_count = await self.teacher_assignments.count_documents({"school_id": school_id, "is_active": True})
        if assignments_count == 0:
            assignments_count = await self.teacher_subjects.count_documents({"school_id": school_id, "is_active": True})
        summary["teachers_with_assignments"] = assignments_count
        if assignments_count == 0:
            issues.append(ValidationIssue(
                category="teacher_assignments",
                severity="critical",
                message_ar="لا توجد إسنادات للمعلمين",
                message_en="No teacher assignments"
            ))
        
        # 11. Check Teacher Availability
        availability_count = await self.teacher_availability.count_documents({"school_id": school_id})
        summary["teacher_availability_records"] = availability_count
        
        # 12. Check School Settings
        settings = await self.school_settings.find_one({"school_id": school_id}, {"_id": 0})
        if settings:
            working_days = settings.get("working_days", [])
            # Handle dict format: {"sunday": True, "monday": True, ...}
            if isinstance(working_days, dict):
                working_days_list = [day for day, active in working_days.items() if active]
                summary["working_days"] = len(working_days_list)
            elif isinstance(working_days, list):
                summary["working_days"] = len(working_days)
            else:
                summary["working_days"] = 0
            
            summary["periods_per_day"] = settings.get("periods_per_day", 0)
            
            if summary["working_days"] == 0:
                issues.append(ValidationIssue(
                    category="settings",
                    severity="critical",
                    message_ar="لا توجد أيام عمل محددة",
                    message_en="No working days defined"
                ))
            if summary["periods_per_day"] == 0:
                issues.append(ValidationIssue(
                    category="settings",
                    severity="critical",
                    message_ar="عدد الحصص اليومية غير محدد",
                    message_en="Periods per day not defined"
                ))
        else:
            issues.append(ValidationIssue(
                category="settings",
                severity="critical",
                message_ar="لا توجد إعدادات للمدرسة",
                message_en="No school settings found"
            ))
        
        # 13. Check Constraints
        constraints_count = await self.school_constraints.count_documents({"school_id": school_id, "is_active": True})
        if constraints_count == 0:
            constraints_count = await self.admin_constraints.count_documents({"is_active": True})
        summary["constraints"] = constraints_count
        
        # 14. Check Holidays
        holidays_count = await self.holidays.count_documents({"school_id": school_id, "is_active": True})
        summary["holidays"] = holidays_count
        
        # Determine validity
        critical_issues = [i for i in issues if i.severity == "critical"]
        is_valid = len(critical_issues) == 0
        can_proceed = len(critical_issues) <= 2  # Allow proceeding with up to 2 critical issues
        
        return PreValidationResult(
            is_valid=is_valid,
            can_proceed=can_proceed,
            issues=issues,
            summary=summary
        )
    
    # ============== PHASE 2: LOAD SCHOOL SETTINGS ==============
    
    async def load_school_settings(self, school_id: str) -> Dict[str, Any]:
        """
        المرحلة 2: تحميل إعدادات المدرسة المعتمدة
        Phase 2: Load approved school settings
        """
        settings = await self.school_settings.find_one({"school_id": school_id}, {"_id": 0})
        
        if not settings:
            default = await self.default_settings.find_one({"id": "default-school-settings"}, {"_id": 0})
            if default:
                settings = default
            else:
                settings = {
                    "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"],
                    "periods_per_day": 7,
                    "period_duration_minutes": 45,
                    "break_duration_minutes": 20,
                    "prayer_duration_minutes": 20,
                    "school_day_start": "07:00",
                    "school_day_end": "13:15"
                }
        
        db_time_slots = []
        async for ts in self.db.time_slots.find({"school_id": school_id}, {"_id": 0}):
            db_time_slots.append(ts)
        db_time_slots.sort(key=lambda x: x.get("period_number") if x.get("period_number") is not None else (x.get("slot_number") if x.get("slot_number") is not None else 99))

        if db_time_slots:
            time_slots = []
            for ts in db_time_slots:
                is_break = ts.get("is_break", False)
                is_prayer = ts.get("is_prayer", False)
                if is_prayer:
                    slot_type = "prayer"
                elif is_break:
                    slot_type = "break"
                else:
                    slot_type = ts.get("type", "class")
                    if slot_type not in ("class", "period"):
                        slot_type = "class"

                time_slots.append({
                    "period": ts.get("period_number") or ts.get("slot_number"),
                    "start_time": ts.get("start_time", ""),
                    "end_time": ts.get("end_time", ""),
                    "type": slot_type,
                    "is_break": is_break,
                    "is_prayer": is_prayer,
                    "name_ar": ts.get("name_ar") or ts.get("label_ar") or ts.get("label") or (
                        "استراحة" if is_break else "صلاة" if is_prayer else f"الحصة {ts.get('period_number', '')}"
                    ),
                })

            teaching_slots = [s for s in time_slots if s["type"] in ("class", "period")]
            teaching_period_numbers = [s["period"] for s in teaching_slots if s.get("period") is not None]
            periods_per_day = len(teaching_slots) if teaching_slots else settings.get("periods_per_day", 7)
        else:
            time_slots = settings.get("time_slots", [])
            if not time_slots:
                time_slots = self._generate_default_time_slots(
                    settings.get("school_day_start", "07:00"),
                    settings.get("periods_per_day", 7),
                    settings.get("period_duration_minutes", 45),
                    settings.get("break_duration_minutes", 20),
                    settings.get("prayer_duration_minutes", 20)
                )
            teaching_slots = [s for s in time_slots if s.get("type") in ("class", "period")]
            teaching_period_numbers = [s["period"] for s in teaching_slots if s.get("period") is not None]
            periods_per_day = len(teaching_slots) if teaching_slots else settings.get("periods_per_day", 7)
        
        working_days_raw = settings.get("working_days", ["sunday", "monday", "tuesday", "wednesday", "thursday"])
        if isinstance(working_days_raw, dict):
            working_days = [day for day, active in working_days_raw.items() if active]
        elif isinstance(working_days_raw, list):
            working_days = working_days_raw
        else:
            working_days = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
        
        return {
            "working_days": working_days,
            "periods_per_day": periods_per_day,
            "teaching_period_numbers": sorted(teaching_period_numbers),
            "period_duration_minutes": settings.get("period_duration_minutes", 45),
            "break_duration_minutes": settings.get("break_duration_minutes", 20),
            "prayer_duration_minutes": settings.get("prayer_duration_minutes", 20),
            "school_day_start": settings.get("school_day_start", "07:00"),
            "school_day_end": settings.get("school_day_end", "13:15"),
            "time_slots": time_slots
        }
    
    def _generate_default_time_slots(
        self,
        start_time: str,
        periods: int,
        period_duration: int,
        break_duration: int,
        prayer_duration: int
    ) -> List[Dict[str, Any]]:
        """Generate default time slots"""
        slots = []
        hour, minute = map(int, start_time.split(":"))
        current_minutes = hour * 60 + minute
        
        for i in range(1, periods + 1):
            start = f"{current_minutes // 60:02d}:{current_minutes % 60:02d}"
            current_minutes += period_duration
            end = f"{current_minutes // 60:02d}:{current_minutes % 60:02d}"
            
            slots.append({
                "period": i,
                "start_time": start,
                "end_time": end,
                "type": "class",
                "name_ar": f"الحصة {i}",
                "name_en": f"Period {i}"
            })
            
            # Add break after 3rd period
            if i == 3:
                start = end
                current_minutes += break_duration
                end = f"{current_minutes // 60:02d}:{current_minutes % 60:02d}"
                slots.append({
                    "period": None,
                    "start_time": start,
                    "end_time": end,
                    "type": "break",
                    "name_ar": "الاستراحة",
                    "name_en": "Break"
                })
            
            # Add prayer after 6th period
            if i == 6:
                start = end
                current_minutes += prayer_duration
                end = f"{current_minutes // 60:02d}:{current_minutes % 60:02d}"
                slots.append({
                    "period": None,
                    "start_time": start,
                    "end_time": end,
                    "type": "prayer",
                    "name_ar": "صلاة الظهر",
                    "name_en": "Prayer"
                })
            
            current_minutes += 5  # 5 minutes between periods
        
        return slots
    
    # ============== PHASE 3: BUILD ACADEMIC DEMAND MATRIX ==============
    
    async def build_academic_demand(self, school_id: str) -> List[AcademicDemand]:
        """
        المرحلة 3: بناء مصفوفة الطلب الأكاديمي
        Phase 3: Build Academic Demand Matrix
        """
        demands = []
        
        # Get all classes
        classes = await self.classes.find(
            {"school_id": school_id, "is_active": {"$ne": False}},
            {"_id": 0}
        ).to_list(500)
        
        for cls in classes:
            class_id = cls.get("id") or cls.get("class_id")
            class_name = cls.get("name") or cls.get("name_ar", "")
            grade_id = cls.get("grade_id", "")
            
            # Get subjects for this grade
            grade_subjects = await self.grade_subjects.find(
                {"school_id": school_id, "grade_id": grade_id, "is_active": True},
                {"_id": 0}
            ).to_list(50)
            
            if not grade_subjects:
                assignments = await self.teacher_assignments.find(
                    {
                        "school_id": school_id,
                        "is_active": True,
                        "$or": [
                            {"class_id": class_id},
                            {"class_id": None},
                            {"class_id": {"$exists": False}}
                        ]
                    },
                    {"_id": 0}
                ).to_list(50)
                
                seen_subjects = set()
                for assignment in assignments:
                    sub_id = assignment.get("subject_id")
                    if sub_id and sub_id not in seen_subjects:
                        seen_subjects.add(sub_id)
                        grade_subjects.append({
                            "subject_id": sub_id,
                            "weekly_periods": assignment.get("weekly_periods") or assignment.get("weekly_sessions", 4),
                            "teacher_id": assignment.get("teacher_id")
                        })
            
            subjects_data = []
            total_periods = 0
            
            for gs in grade_subjects:
                subject_id = gs.get("subject_id")
                weekly_periods = gs.get("weekly_periods", 4)
                total_periods += weekly_periods
                
                # Find suitable teachers for this subject
                suitable_teachers = []
                
                # From teacher_assignments
                teacher_assigns = await self.teacher_assignments.find(
                    {
                        "school_id": school_id,
                        "subject_id": subject_id,
                        "is_active": True,
                        "$or": [
                            {"class_id": class_id},
                            {"class_id": None},
                            {"class_id": {"$exists": False}},
                            {"grade_id": grade_id},
                            {"section_ids": {"$in": [class_id]}}
                        ]
                    },
                    {"_id": 0, "teacher_id": 1}
                ).to_list(20)
                
                for ta in teacher_assigns:
                    if ta.get("teacher_id") not in suitable_teachers:
                        suitable_teachers.append(ta.get("teacher_id"))
                
                # If no specific assignment, find any teacher who can teach this subject
                if not suitable_teachers:
                    teachers_with_subject = await self.teachers.find(
                        {
                            "school_id": school_id,
                            "is_active": {"$ne": False},
                            "$or": [
                                {"primary_subject_id": subject_id},
                                {"subject_ids": subject_id},
                                {"specialization": subject_id}
                            ]
                        },
                        {"_id": 0, "id": 1, "teacher_id": 1}
                    ).to_list(20)
                    
                    for t in teachers_with_subject:
                        tid = t.get("id") or t.get("teacher_id")
                        if tid and tid not in suitable_teachers:
                            suitable_teachers.append(tid)
                
                subjects_data.append({
                    "subject_id": subject_id,
                    "weekly_periods": weekly_periods,
                    "suitable_teachers": suitable_teachers,
                    "priority": gs.get("priority", 1)
                })
            
            demands.append(AcademicDemand(
                class_id=class_id,
                class_name=class_name,
                grade_id=grade_id,
                subjects=subjects_data,
                total_periods_required=total_periods
            ))
        
        return demands
    
    # ============== PHASE 4: BUILD RESOURCE AVAILABILITY MATRIX ==============
    
    async def build_resource_availability(self, school_id: str, settings: Dict[str, Any]) -> List[ResourceAvailability]:
        """
        المرحلة 4: بناء مصفوفة الموارد المتاحة
        Phase 4: Build Resource Availability Matrix
        """
        resources = []
        
        # Get all teachers
        teachers = await self.teachers.find(
            {"school_id": school_id, "is_active": {"$ne": False}},
            {"_id": 0}
        ).to_list(500)
        
        working_days = settings.get("working_days", ["sunday", "monday", "tuesday", "wednesday", "thursday"])
        periods_per_day = settings.get("periods_per_day", 7)
        
        for teacher in teachers:
            teacher_id = teacher.get("id") or teacher.get("teacher_id")
            teacher_name = teacher.get("full_name") or teacher.get("full_name_ar", "")
            
            # Get teacher's weekly load (from rank)
            rank_id = teacher.get("rank_id") or teacher.get("rank")
            weekly_load = 24  # Default
            if rank_id:
                rank = await self.teacher_ranks.find_one({"id": rank_id}, {"_id": 0})
                if not rank:
                    rank = await self.reference_teacher_ranks.find_one({"id": rank_id}, {"_id": 0})
                if rank:
                    weekly_load = rank.get("max_weekly_load", 24)
            
            # Get subject IDs from teacher doc + teacher_assignments
            subject_ids = list(teacher.get("subject_ids", []) or [])
            if not subject_ids and teacher.get("primary_subject_id"):
                subject_ids = [teacher.get("primary_subject_id")]
            
            assignment_subjects = await self.teacher_assignments.find(
                {"school_id": school_id, "teacher_id": teacher_id, "is_active": True},
                {"_id": 0, "subject_id": 1}
            ).to_list(20)
            for asn in assignment_subjects:
                sid = asn.get("subject_id")
                if sid and sid not in subject_ids:
                    subject_ids.append(sid)
            
            availability = {}
            teaching_period_numbers = settings.get("teaching_period_numbers", list(range(1, periods_per_day + 1)))
            for day in working_days:
                availability[day] = list(teaching_period_numbers)
            
            # Apply teacher availability restrictions
            teacher_avail = await self.teacher_availability.find(
                {"school_id": school_id, "teacher_id": teacher_id},
                {"_id": 0}
            ).to_list(100)
            
            for avail in teacher_avail:
                day = avail.get("day_of_week", "").lower()
                period = avail.get("period_number")
                is_available = avail.get("is_available", True)
                
                if day in availability and period and not is_available:
                    if period in availability[day]:
                        availability[day].remove(period)
            
            resources.append(ResourceAvailability(
                teacher_id=teacher_id,
                teacher_name=teacher_name,
                subject_ids=subject_ids,
                weekly_load=weekly_load,
                current_load=0,
                availability=availability
            ))
        
        return resources
    
    # ============== PHASE 5: PRE-SCHEDULING CONSTRAINT CHECK ==============
    
    async def pre_scheduling_check(
        self,
        school_id: str,
        demands: List[AcademicDemand],
        resources: List[ResourceAvailability],
        settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        المرحلة 5: التحقق المسبق من التعارضات
        Phase 5: Pre-Scheduling Constraint Check
        """
        warnings = []
        errors = []
        
        working_days = settings.get("working_days", [])
        periods_per_day = settings.get("periods_per_day", 7)
        total_slots_per_week = len(working_days) * periods_per_day
        
        # Calculate total demand
        total_demand = sum(d.total_periods_required for d in demands)
        
        # Calculate total teacher capacity
        total_capacity = sum(r.weekly_load for r in resources)
        
        # Check capacity vs demand
        if total_demand > total_capacity:
            errors.append({
                "type": "capacity_shortage",
                "message_ar": f"الطاقة الاستيعابية للمعلمين ({total_capacity}) أقل من الطلب الأكاديمي ({total_demand})",
                "message_en": f"Teacher capacity ({total_capacity}) is less than academic demand ({total_demand})"
            })
        
        # Check for subjects without teachers
        subjects_without_teachers = []
        for demand in demands:
            for subject in demand.subjects:
                if not subject.get("suitable_teachers"):
                    subjects_without_teachers.append({
                        "class_id": demand.class_id,
                        "class_name": demand.class_name,
                        "subject_id": subject.get("subject_id")
                    })
        
        if subjects_without_teachers:
            errors.append({
                "type": "subjects_without_teachers",
                "message_ar": f"يوجد {len(subjects_without_teachers)} مادة بدون معلم مخصص",
                "message_en": f"{len(subjects_without_teachers)} subjects have no assigned teachers",
                "details": subjects_without_teachers
            })
        
        # Check classes without subjects
        classes_without_subjects = [d for d in demands if not d.subjects]
        if classes_without_subjects:
            warnings.append({
                "type": "classes_without_subjects",
                "message_ar": f"يوجد {len(classes_without_subjects)} فصل بدون مواد محددة",
                "message_en": f"{len(classes_without_subjects)} classes have no subjects defined"
            })
        
        # Calculate scheduling feasibility
        can_schedule = len(errors) == 0 or (len(errors) <= 1 and errors[0].get("type") == "capacity_shortage")
        
        return {
            "can_schedule": can_schedule,
            "warnings": warnings,
            "errors": errors,
            "statistics": {
                "total_demand_periods": total_demand,
                "total_teacher_capacity": total_capacity,
                "total_classes": len(demands),
                "total_teachers": len(resources),
                "total_slots_per_week": total_slots_per_week,
                "utilization_rate": (total_demand / total_capacity * 100) if total_capacity > 0 else 0
            }
        }
    
    # ============== PHASE 6: GENERATE DRAFT TIMETABLE ==============
    
    async def generate_draft_timetable(
        self,
        school_id: str,
        run_id: str,
        demands: List[AcademicDemand],
        resources: List[ResourceAvailability],
        settings: Dict[str, Any],
        constraints: List[Dict[str, Any]]
    ) -> Tuple[str, List[TimetableSession], List[TimetableConflict], List[UnscheduledDemand]]:
        """
        المرحلة 6: إنشاء مسودة الجدول
        Phase 6: Generate Draft Timetable
        """
        timetable_id = str(uuid.uuid4())
        sessions = []
        conflicts = []
        unscheduled = []
        
        working_days = settings.get("working_days", ["sunday", "monday", "tuesday", "wednesday", "thursday"])
        periods_per_day = settings.get("periods_per_day", 7)
        time_slots = settings.get("time_slots", [])
        teaching_period_numbers = settings.get("teaching_period_numbers", list(range(1, periods_per_day + 1)))
        
        slot_lookup = {}
        for slot in time_slots:
            period_num = slot.get("period") or slot.get("slot_number")
            if period_num:
                slot_lookup[period_num] = {
                    "start_time": slot.get("start_time", ""),
                    "end_time": slot.get("end_time", "")
                }
        
        grid = {day: {p: {} for p in teaching_period_numbers} for day in working_days}
        teacher_grid = {day: {p: set() for p in teaching_period_numbers} for day in working_days}
        
        # Track resource usage
        resource_usage = {r.teacher_id: 0 for r in resources}
        resource_lookup = {r.teacher_id: r for r in resources}
        
        # Sort demands by difficulty (fewer teacher options = harder)
        sorted_demands = []
        for demand in demands:
            for subject in demand.subjects:
                sorted_demands.append({
                    "class_id": demand.class_id,
                    "class_name": demand.class_name,
                    "grade_id": demand.grade_id,
                    "subject_id": subject.get("subject_id"),
                    "weekly_periods": subject.get("weekly_periods", 4),
                    "suitable_teachers": subject.get("suitable_teachers", []),
                    "priority": subject.get("priority", 1),
                    "difficulty": 1 / (len(subject.get("suitable_teachers", [])) + 0.1)
                })
        
        # Sort by difficulty (hardest first)
        sorted_demands.sort(key=lambda x: (-x["difficulty"], -x["priority"]))
        
        # Schedule each demand
        for demand in sorted_demands:
            class_id = demand["class_id"]
            subject_id = demand["subject_id"]
            weekly_periods = demand["weekly_periods"]
            suitable_teachers = demand["suitable_teachers"]
            
            scheduled_count = 0
            
            # Distribute periods across days
            periods_per_working_day = max(1, weekly_periods // len(working_days))
            remaining = weekly_periods
            
            for day in working_days:
                if remaining <= 0:
                    break
                
                periods_today = min(periods_per_working_day + (1 if remaining > periods_per_working_day * (len(working_days) - working_days.index(day)) else 0), remaining)
                
                for _ in range(periods_today):
                    if remaining <= 0:
                        break
                    
                    # Find best slot and teacher
                    best_candidate = None
                    best_score = -1
                    
                    for period in teaching_period_numbers:
                        # HARD CONSTRAINT: class_id + day + period must be unique
                        # A class cannot have two sessions in the same time slot
                        if class_id in grid[day][period]:
                            continue
                        
                        for teacher_id in suitable_teachers:
                            resource = resource_lookup.get(teacher_id)
                            if not resource:
                                continue
                            
                            # Check teacher availability
                            if period not in resource.availability.get(day, []):
                                continue
                            
                            # HARD CONSTRAINT: teacher_id + day + period must be unique
                            # Teacher cannot be in two places at the same time
                            if teacher_id in teacher_grid[day][period]:
                                continue
                            
                            # Check teacher load
                            if resource_usage.get(teacher_id, 0) >= resource.weekly_load:
                                continue
                            
                            score = 100

                            load_ratio = resource_usage.get(teacher_id, 0) / resource.weekly_load
                            score -= load_ratio * 30

                            filled_periods = sorted([
                                p for p in teaching_period_numbers
                                if class_id in grid[day].get(p, {})
                            ])
                            if filled_periods:
                                last_filled = filled_periods[-1]
                                if period == last_filled + 1:
                                    score += 8
                                elif period < last_filled:
                                    score += 3
                                elif period > last_filled + 2:
                                    score -= 5
                            else:
                                if period <= 2:
                                    score += 5

                            for constraint in constraints:
                                if constraint.get("is_active", True):
                                    rule_key = constraint.get("rule_key", "")
                                    if rule_key == "no_first_period" and period == 1:
                                        affected_subjects = constraint.get("affected_subjects", [])
                                        if subject_id in affected_subjects:
                                            score -= 50
                                    if rule_key == "no_last_period" and period == teaching_period_numbers[-1]:
                                        affected_subjects = constraint.get("affected_subjects", [])
                                        if subject_id in affected_subjects:
                                            score -= 50

                            score = self._apply_soft_constraint_scoring(
                                score, settings, grid, teacher_grid, resource_usage,
                                class_id, subject_id, teacher_id, day, period,
                                working_days, teaching_period_numbers
                            )
                            
                            if score > best_score:
                                best_score = score
                                best_candidate = {
                                    "teacher_id": teacher_id,
                                    "day": day,
                                    "period": period,
                                    "score": score
                                }
                    
                    if best_candidate:
                        # Create session
                        session_id = str(uuid.uuid4())
                        slot_times = slot_lookup.get(best_candidate["period"], {"start_time": "", "end_time": ""})
                        
                        session = TimetableSession(
                            id=session_id,
                            timetable_id=timetable_id,
                            school_id=school_id,
                            class_id=class_id,
                            grade_id=demand["grade_id"],
                            subject_id=subject_id,
                            teacher_id=best_candidate["teacher_id"],
                            day_of_week=best_candidate["day"],
                            period_number=best_candidate["period"],
                            start_time=slot_times["start_time"],
                            end_time=slot_times["end_time"],
                            session_type="class",
                            source_type="ai_generated",
                            status="scheduled"
                        )
                        sessions.append(session)
                        
                        # Update tracking
                        grid[best_candidate["day"]][best_candidate["period"]][class_id] = session
                        teacher_grid[best_candidate["day"]][best_candidate["period"]].add(best_candidate["teacher_id"])
                        resource_usage[best_candidate["teacher_id"]] = resource_usage.get(best_candidate["teacher_id"], 0) + 1
                        
                        scheduled_count += 1
                        remaining -= 1
            
            if scheduled_count < weekly_periods:
                unscheduled.append(UnscheduledDemand(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    school_id=school_id,
                    class_id=class_id,
                    grade_id=demand["grade_id"],
                    subject_id=subject_id,
                    required_periods=weekly_periods,
                    scheduled_periods=scheduled_count,
                    remaining_periods=weekly_periods - scheduled_count,
                    reason_ar="لم يتوفر وقت أو معلم مناسب",
                    reason_en="No suitable time or teacher available"
                ))
        
        all_classes = set()
        class_grade_map = {}
        for demand in sorted_demands:
            all_classes.add(demand["class_id"])
            class_grade_map[demand["class_id"]] = demand.get("grade_id", "")

        for class_id in all_classes:
            for day in working_days:
                for period in teaching_period_numbers:
                    # HARD CONSTRAINT: class_id + day + period must be unique
                    if class_id in grid[day][period]:
                        continue

                    best_candidate = None
                    best_score = -1

                    schedulable_demands = [
                        d for d in sorted_demands
                        if d["class_id"] == class_id and d["suitable_teachers"]
                    ]

                    class_day_subjects = set()
                    for p in teaching_period_numbers:
                        if class_id in grid[day][p]:
                            s = grid[day][p][class_id]
                            class_day_subjects.add(s.subject_id)

                    subject_session_counts = {}
                    for s in sessions:
                        if s.class_id == class_id:
                            sk = s.subject_id
                            subject_session_counts[sk] = subject_session_counts.get(sk, 0) + 1

                    for demand in schedulable_demands:
                        subject_id = demand["subject_id"]
                        weekly_needed = demand.get("weekly_periods", 4)
                        current_count = subject_session_counts.get(subject_id, 0)

                        for teacher_id in demand["suitable_teachers"]:
                            if teacher_id in teacher_grid[day][period]:
                                continue

                            resource = resource_lookup.get(teacher_id)
                            if not resource:
                                continue

                            if resource_usage.get(teacher_id, 0) >= resource.weekly_load:
                                continue

                            if period not in resource.availability.get(day, []):
                                continue

                            score = 50

                            if subject_id not in class_day_subjects:
                                score += 20

                            load_ratio = resource_usage.get(teacher_id, 0) / max(resource.weekly_load, 1)
                            score -= load_ratio * 15

                            if current_count < weekly_needed:
                                score += 25
                            else:
                                score -= 10

                            if score > best_score:
                                best_score = score
                                best_candidate = {
                                    "teacher_id": teacher_id,
                                    "day": day,
                                    "period": period,
                                    "subject_id": subject_id,
                                    "grade_id": class_grade_map.get(class_id, ""),
                                }

                    if best_candidate:
                        session_id = str(uuid.uuid4())
                        slot_times = slot_lookup.get(best_candidate["period"], {"start_time": "", "end_time": ""})

                        session = TimetableSession(
                            id=session_id,
                            timetable_id=timetable_id,
                            school_id=school_id,
                            class_id=class_id,
                            grade_id=best_candidate["grade_id"],
                            subject_id=best_candidate["subject_id"],
                            teacher_id=best_candidate["teacher_id"],
                            day_of_week=best_candidate["day"],
                            period_number=best_candidate["period"],
                            start_time=slot_times["start_time"],
                            end_time=slot_times["end_time"],
                            session_type="class",
                            source_type="ai_generated",
                            status="scheduled"
                        )
                        sessions.append(session)

                        grid[best_candidate["day"]][best_candidate["period"]][class_id] = session
                        teacher_grid[best_candidate["day"]][best_candidate["period"]].add(best_candidate["teacher_id"])
                        resource_usage[best_candidate["teacher_id"]] = resource_usage.get(best_candidate["teacher_id"], 0) + 1

        final_unscheduled = []
        for u in unscheduled:
            filled = sum(
                1 for s in sessions
                if s.class_id == u.class_id and s.subject_id == u.subject_id
            )
            if filled < u.required_periods:
                u.scheduled_periods = filled
                u.remaining_periods = u.required_periods - filled
                final_unscheduled.append(u)

        # HARD CONSTRAINT VALIDATION: class_id + day + period uniqueness
        # Final safety check to catch any class time conflicts before returning
        class_slot_check = {}
        for s in sessions:
            key = (s.class_id, s.day_of_week, s.period_number)
            if key in class_slot_check:
                dup = class_slot_check[key]
                conflicts.append(TimetableConflict(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    timetable_id=timetable_id,
                    conflict_type=ConflictType.CLASS_OVERLAP.value,
                    class_id=s.class_id,
                    day_of_week=s.day_of_week,
                    period_number=s.period_number,
                    severity=ConflictSeverity.CRITICAL.value,
                    message_ar=f"الفصل لديه حصتين في نفس الوقت ({s.day_of_week} - الحصة {s.period_number})",
                    message_en=f"Class has two sessions at same time ({s.day_of_week} period {s.period_number})"
                ))
            class_slot_check[key] = s

        # HARD CONSTRAINT VALIDATION: teacher_id + day + period uniqueness
        # Final safety check to catch any teacher time conflicts before returning
        teacher_slot_check = {}
        for s in sessions:
            key = (s.teacher_id, s.day_of_week, s.period_number)
            if key in teacher_slot_check:
                conflicts.append(TimetableConflict(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    timetable_id=timetable_id,
                    conflict_type=ConflictType.TEACHER_OVERLAP.value,
                    teacher_id=s.teacher_id,
                    day_of_week=s.day_of_week,
                    period_number=s.period_number,
                    severity=ConflictSeverity.CRITICAL.value,
                    message_ar=f"لا يمكن إسناد أكثر من حصة لنفس المعلم في نفس الوقت ({s.day_of_week} - الحصة {s.period_number})",
                    message_en=f"Teacher is double-booked at same time ({s.day_of_week} period {s.period_number})"
                ))
            teacher_slot_check[key] = s

        underutilized_teachers = self._detect_underutilized_teachers(
            sorted_demands, resources, resource_usage, sessions
        )

        return timetable_id, sessions, conflicts, final_unscheduled, underutilized_teachers
    
    def _detect_underutilized_teachers(
        self,
        sorted_demands: List[Dict[str, Any]],
        resources: List,
        resource_usage: Dict[str, int],
        sessions: List
    ) -> List[Dict[str, Any]]:
        teacher_demand_classes = {}
        teacher_subjects = {}
        for demand in sorted_demands:
            for tid in demand.get("suitable_teachers", []):
                if tid not in teacher_subjects:
                    teacher_subjects[tid] = set()
                    teacher_demand_classes[tid] = set()
                teacher_subjects[tid].add(demand.get("subject_id", ""))
                teacher_demand_classes[tid].add(demand.get("class_id", ""))

        underutilized = []
        for resource in resources:
            tid = resource.teacher_id
            actual_sessions = resource_usage.get(tid, 0)
            has_demand_match = tid in teacher_subjects
            has_subject_ids = bool(resource.subject_ids)
            has_availability = bool(resource.availability) and any(
                len(periods) > 0 for periods in resource.availability.values()
            )

            if actual_sessions == 0 and (has_demand_match or has_subject_ids):
                reasons_ar = []
                reasons_en = []
                if not has_subject_ids:
                    reasons_ar.append("لا توجد مواد مسندة للمعلم")
                    reasons_en.append("No subjects assigned to teacher")
                if not has_demand_match:
                    reasons_ar.append("المواد المسندة لا تتطابق مع أي فصل يحتاج هذه المواد")
                    reasons_en.append("Assigned subjects don't match any class demand")
                if not has_availability:
                    reasons_ar.append("لا يوجد توفر زمني صالح")
                    reasons_en.append("No valid time availability")
                if has_demand_match and has_availability and has_subject_ids:
                    reasons_ar.append("خطأ في منطق التوزيع - المعلم مؤهل لكن لم يتم اختياره")
                    reasons_en.append("Distribution logic error - teacher is eligible but was not selected")

                underutilized.append({
                    "teacher_id": tid,
                    "teacher_name": getattr(resource, 'teacher_name', '') or tid,
                    "weekly_load": resource.weekly_load,
                    "assigned_sessions": 0,
                    "subject_ids": list(teacher_subjects.get(tid, resource.subject_ids or [])),
                    "matched_classes": len(teacher_demand_classes.get(tid, [])),
                    "has_availability": has_availability,
                    "has_subject_assignments": has_subject_ids,
                    "has_demand_match": has_demand_match,
                    "severity": "critical",
                    "reasons_ar": reasons_ar,
                    "reasons_en": reasons_en,
                    "reason_ar": " | ".join(reasons_ar) if reasons_ar else "المعلم لديه مواد مسندة لكن لم يحصل على أي حصة",
                    "reason_en": " | ".join(reasons_en) if reasons_en else "Teacher has assignments but received zero sessions"
                })
            elif actual_sessions > 0 and actual_sessions < resource.weekly_load * 0.3 and has_demand_match:
                underutilized.append({
                    "teacher_id": tid,
                    "teacher_name": getattr(resource, 'teacher_name', '') or tid,
                    "weekly_load": resource.weekly_load,
                    "assigned_sessions": actual_sessions,
                    "subject_ids": list(teacher_subjects.get(tid, [])),
                    "matched_classes": len(teacher_demand_classes.get(tid, [])),
                    "has_availability": has_availability,
                    "has_subject_assignments": has_subject_ids,
                    "has_demand_match": has_demand_match,
                    "severity": "warning",
                    "reason_ar": f"المعلم لديه {actual_sessions} حصة فقط من أصل {resource.weekly_load} نصاب",
                    "reason_en": f"Teacher has only {actual_sessions} of {resource.weekly_load} capacity filled"
                })

        return underutilized

    # ============== PHASE 7: DETECT CONFLICTS ==============
    
    async def detect_conflicts(
        self,
        sessions: List[TimetableSession],
        resources: List[ResourceAvailability],
        constraints: List[Dict[str, Any]],
        run_id: str
    ) -> List[TimetableConflict]:
        """
        المرحلة 7: اكتشاف التعارضات
        Phase 7: Detect Conflicts
        """
        conflicts = []
        
        # Group sessions by day and period
        slot_sessions = {}
        for session in sessions:
            key = (session.day_of_week, session.period_number)
            if key not in slot_sessions:
                slot_sessions[key] = []
            slot_sessions[key].append(session)
        
        # Check for conflicts
        for key, slot_list in slot_sessions.items():
            day, period = key
            
            # Check teacher conflicts (same teacher in multiple places)
            teachers_in_slot = {}
            for session in slot_list:
                tid = session.teacher_id
                if tid in teachers_in_slot:
                    conflicts.append(TimetableConflict(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        timetable_id=session.timetable_id,
                        conflict_type=ConflictType.TEACHER_OVERLAP.value,
                        teacher_id=tid,
                        day_of_week=day,
                        period_number=period,
                        severity=ConflictSeverity.CRITICAL.value,
                        message_ar=f"المعلم مشغول في حصتين في نفس الوقت",
                        message_en="Teacher is double-booked"
                    ))
                teachers_in_slot[tid] = session
            
            # Check class conflicts (same class in multiple sessions)
            classes_in_slot = {}
            for session in slot_list:
                cid = session.class_id
                if cid in classes_in_slot:
                    conflicts.append(TimetableConflict(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        timetable_id=session.timetable_id,
                        conflict_type=ConflictType.CLASS_OVERLAP.value,
                        class_id=cid,
                        day_of_week=day,
                        period_number=period,
                        severity=ConflictSeverity.CRITICAL.value,
                        message_ar=f"الفصل لديه حصتين في نفس الوقت",
                        message_en="Class has two sessions at the same time"
                    ))
                classes_in_slot[cid] = session
        
        # Check teacher overload
        teacher_loads = {}
        for session in sessions:
            tid = session.teacher_id
            teacher_loads[tid] = teacher_loads.get(tid, 0) + 1
        
        resource_lookup = {r.teacher_id: r for r in resources}
        for tid, load in teacher_loads.items():
            resource = resource_lookup.get(tid)
            if resource and load > resource.weekly_load:
                conflicts.append(TimetableConflict(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    timetable_id=sessions[0].timetable_id if sessions else None,
                    conflict_type=ConflictType.TEACHER_OVERLOAD.value,
                    teacher_id=tid,
                    day_of_week="",
                    period_number=0,
                    severity=ConflictSeverity.HIGH.value,
                    message_ar=f"تجاوز نصاب المعلم ({load} حصة من {resource.weekly_load})",
                    message_en=f"Teacher overload ({load} of {resource.weekly_load} periods)"
                ))
        
        return conflicts
    
    # ============== PHASE 8: OPTIMIZATION ==============
    
    async def optimize_timetable(
        self,
        sessions: List[TimetableSession],
        conflicts: List[TimetableConflict],
        resources: List[ResourceAvailability],
        settings: Dict[str, Any]
    ) -> Tuple[List[TimetableSession], float]:
        """
        المرحلة 8: تحسين الجدول بخوارزمية Hill Climbing مع إعادة تشغيل عشوائية
        Phase 8: Optimize Timetable using Hill Climbing with random restarts
        """
        import copy as _copy
        import random as _random

        if not sessions:
            return sessions, 0.0

        initial_score = self._calculate_optimization_score(sessions, conflicts, resources)
        best_sessions = _copy.deepcopy(sessions)
        best_score = initial_score

        max_iterations = settings.get("max_iterations", 200)
        max_no_improve = settings.get("max_no_improve", 30)

        resource_map = {}
        for r in resources:
            resource_map[r.teacher_id] = r

        def _build_slot_map(sess_list):
            teacher_slots = {}
            section_slots = {}
            for s in sess_list:
                key = (s.day_of_week, s.period_number)
                teacher_slots.setdefault(s.teacher_id, set()).add(key)
                section_slots.setdefault(s.class_id, set()).add(key)
            return teacher_slots, section_slots

        def _count_conflicts(sess_list):
            teacher_slots = {}
            section_slots = {}
            conflict_count = 0
            for s in sess_list:
                key = (s.day_of_week, s.period_number)
                t_key = (s.teacher_id, key)
                s_key = (s.class_id, key)
                if t_key in teacher_slots:
                    conflict_count += 1
                teacher_slots[t_key] = True
                if s_key in section_slots:
                    conflict_count += 1
                section_slots[s_key] = True
            return conflict_count

        def _has_class_conflict(sess_list):
            """Hard constraint: class_id + day + period must be unique"""
            seen = set()
            for s in sess_list:
                key = (s.class_id, s.day_of_week, s.period_number)
                if key in seen:
                    return True
                seen.add(key)
            return False

        def _has_teacher_conflict(sess_list):
            """Hard constraint: teacher_id + day + period must be unique"""
            seen = set()
            for s in sess_list:
                key = (s.teacher_id, s.day_of_week, s.period_number)
                if key in seen:
                    return True
                seen.add(key)
            return False

        all_days = list(set(s.day_of_week for s in sessions))
        all_periods = list(set(s.period_number for s in sessions))

        current_sessions = _copy.deepcopy(sessions)
        current_score = initial_score
        no_improve_count = 0

        for iteration in range(max_iterations):
            if no_improve_count >= max_no_improve:
                break

            move_type = _random.choice(["swap", "move", "resolve_conflict"])
            candidate = _copy.deepcopy(current_sessions)

            if move_type == "swap" and len(candidate) >= 2:
                i, j = _random.sample(range(len(candidate)), 2)
                candidate[i].day_of_week, candidate[j].day_of_week = candidate[j].day_of_week, candidate[i].day_of_week
                candidate[i].period_number, candidate[j].period_number = candidate[j].period_number, candidate[i].period_number

            elif move_type == "move":
                idx = _random.randrange(len(candidate))
                candidate[idx].day_of_week = _random.choice(all_days)
                candidate[idx].period_number = _random.choice(all_periods)

            elif move_type == "resolve_conflict":
                teacher_slot_count = {}
                for si, s in enumerate(candidate):
                    key = (s.teacher_id, s.day_of_week, s.period_number)
                    teacher_slot_count.setdefault(key, []).append(si)

                conflict_groups = [indices for indices in teacher_slot_count.values() if len(indices) > 1]
                if conflict_groups:
                    group = _random.choice(conflict_groups)
                    move_idx = _random.choice(group[1:])
                    candidate[move_idx].day_of_week = _random.choice(all_days)
                    candidate[move_idx].period_number = _random.choice(all_periods)
                else:
                    section_slot_count = {}
                    for si, s in enumerate(candidate):
                        key = (s.class_id, s.day_of_week, s.period_number)
                        section_slot_count.setdefault(key, []).append(si)
                    sec_conflicts = [indices for indices in section_slot_count.values() if len(indices) > 1]
                    if sec_conflicts:
                        group = _random.choice(sec_conflicts)
                        move_idx = _random.choice(group[1:])
                        candidate[move_idx].day_of_week = _random.choice(all_days)
                        candidate[move_idx].period_number = _random.choice(all_periods)

            # HARD CONSTRAINT: reject any optimization that creates class OR teacher conflicts
            if _has_class_conflict(candidate) or _has_teacher_conflict(candidate):
                no_improve_count += 1
                continue

            availability_violated = False
            for s in candidate:
                r = resource_map.get(s.teacher_id)
                if r and hasattr(r, 'availability') and r.availability:
                    avail_periods = r.availability.get(s.day_of_week, [])
                    if avail_periods and s.period_number not in avail_periods:
                        availability_violated = True
                        break
            if availability_violated:
                no_improve_count += 1
                continue

            new_conflicts_count = _count_conflicts(candidate)
            old_conflicts_count = _count_conflicts(current_sessions)

            new_score = self._calculate_optimization_score(candidate, [], resources)
            new_score -= new_conflicts_count * 15

            if new_score > current_score or (new_conflicts_count < old_conflicts_count):
                current_sessions = candidate
                current_score = new_score
                no_improve_count = 0

                if current_score > best_score:
                    best_sessions = _copy.deepcopy(current_sessions)
                    best_score = current_score
            else:
                no_improve_count += 1

        final_score = self._calculate_optimization_score(best_sessions, conflicts, resources)
        return best_sessions, max(final_score, best_score)
    
    def _apply_soft_constraint_scoring(
        self, score, settings, grid, teacher_grid, resource_usage,
        class_id, subject_id, teacher_id, day, period,
        working_days, teaching_period_numbers
    ) -> float:
        soft_constraints = settings.get("soft_constraints", [])
        sc_map = {sc.get("scoring_key"): sc for sc in soft_constraints if sc.get("is_active", True)}

        sc = sc_map.get("no_consecutive_same_subject")
        if sc:
            w = sc.get("weight", 8) / 10.0
            prev_period = period - 1
            next_period = period + 1
            if prev_period in grid.get(day, {}):
                prev_session = grid[day].get(prev_period, {}).get(class_id)
                if prev_session and prev_session.subject_id == subject_id:
                    score -= 15 * w
            if next_period in grid.get(day, {}):
                next_session = grid[day].get(next_period, {}).get(class_id)
                if next_session and next_session.subject_id == subject_id:
                    score -= 15 * w

        sc = sc_map.get("minimize_teacher_gaps")
        if sc:
            w = sc.get("weight", 7) / 10.0
            teacher_periods_today = []
            for p in teaching_period_numbers:
                if teacher_id in teacher_grid.get(day, {}).get(p, set()):
                    teacher_periods_today.append(p)
            if teacher_periods_today:
                teacher_periods_today.append(period)
                teacher_periods_today.sort()
                gaps = 0
                for i in range(1, len(teacher_periods_today)):
                    gap = teacher_periods_today[i] - teacher_periods_today[i-1] - 1
                    if gap > 0:
                        gaps += gap
                score -= gaps * 5 * w

        sc = sc_map.get("hard_subjects_early")
        if sc:
            w = sc.get("weight", 5) / 10.0
            if period <= 3:
                score += 3 * w
            elif period == teaching_period_numbers[-1]:
                score -= 1 * w

        sc = sc_map.get("limit_consecutive_teacher")
        if sc:
            w = sc.get("weight", 7) / 10.0
            consecutive = 0
            for p in range(period - 1, 0, -1):
                if teacher_id in teacher_grid.get(day, {}).get(p, set()):
                    consecutive += 1
                else:
                    break
            if consecutive >= 3:
                score -= 12 * w

        sc = sc_map.get("balanced_daily_teacher_load")
        if sc:
            w = sc.get("weight", 8) / 10.0
            teacher_day_counts = {}
            for d in working_days:
                cnt = 0
                for p in teaching_period_numbers:
                    if teacher_id in teacher_grid.get(d, {}).get(p, set()):
                        cnt += 1
                teacher_day_counts[d] = cnt
            today_count = teacher_day_counts.get(day, 0) + 1
            if teacher_day_counts:
                avg = sum(teacher_day_counts.values()) / len(teacher_day_counts)
                if today_count > avg + 2:
                    score -= 8 * w

        sc = sc_map.get("balanced_weekly_distribution")
        if sc:
            w = sc.get("weight", 9) / 10.0
            subject_day_counts = {}
            for d in working_days:
                cnt = 0
                for p in teaching_period_numbers:
                    s = grid.get(d, {}).get(p, {}).get(class_id)
                    if s and s.subject_id == subject_id:
                        cnt += 1
                subject_day_counts[d] = cnt
            today_count = subject_day_counts.get(day, 0)
            if today_count >= 2:
                score -= 10 * w

        sc = sc_map.get("minimize_class_gaps")
        if sc:
            w = sc.get("weight", 6) / 10.0
            class_periods_today = []
            for p in teaching_period_numbers:
                if class_id in grid.get(day, {}).get(p, {}):
                    class_periods_today.append(p)
            if class_periods_today:
                class_periods_today.append(period)
                class_periods_today.sort()
                gaps = 0
                for i in range(1, len(class_periods_today)):
                    g = class_periods_today[i] - class_periods_today[i-1] - 1
                    if g > 0:
                        gaps += g
                score -= gaps * 4 * w

        sc = sc_map.get("fair_first_period")
        if sc and period == 1:
            w = sc.get("weight", 4) / 10.0
            first_period_count = 0
            for d in working_days:
                if teacher_id in teacher_grid.get(d, {}).get(1, set()):
                    first_period_count += 1
            if first_period_count >= 3:
                score -= 6 * w

        sc = sc_map.get("fair_last_period")
        if sc and period == teaching_period_numbers[-1]:
            w = sc.get("weight", 4) / 10.0
            last_period_count = 0
            lp = teaching_period_numbers[-1]
            for d in working_days:
                if teacher_id in teacher_grid.get(d, {}).get(lp, set()):
                    last_period_count += 1
            if last_period_count >= 3:
                score -= 6 * w

        sc = sc_map.get("diverse_after_break")
        if sc:
            w = sc.get("weight", 3) / 10.0
            prev_period = period - 1
            if prev_period > 0 and prev_period in grid.get(day, {}):
                if class_id not in grid[day].get(prev_period, {}):
                    pass
                else:
                    prev_session = grid[day][prev_period].get(class_id)
                    if prev_session and prev_session.subject_id != subject_id:
                        score += 2 * w

        sc = sc_map.get("pe_appropriate_times")
        if sc:
            w = sc.get("weight", 3) / 10.0
            if period >= len(teaching_period_numbers) - 2:
                score += 3 * w

        sc = sc_map.get("minimize_teacher_travel")
        if sc:
            w = sc.get("weight", 2) / 10.0
            pass

        return score

    def _calculate_optimization_score(
        self,
        sessions: List[TimetableSession],
        conflicts: List[TimetableConflict],
        resources: List[ResourceAvailability]
    ) -> float:
        """Calculate optimization score (0-100)"""
        if not sessions:
            return 0.0
        
        score = 100.0
        
        # Deduct for conflicts
        critical_conflicts = len([c for c in conflicts if c.severity == ConflictSeverity.CRITICAL.value])
        high_conflicts = len([c for c in conflicts if c.severity == ConflictSeverity.HIGH.value])
        medium_conflicts = len([c for c in conflicts if c.severity == ConflictSeverity.MEDIUM.value])
        
        score -= critical_conflicts * 20
        score -= high_conflicts * 10
        score -= medium_conflicts * 5
        
        # Check load balance
        teacher_loads = {}
        for session in sessions:
            tid = session.teacher_id
            teacher_loads[tid] = teacher_loads.get(tid, 0) + 1
        
        if teacher_loads:
            avg_load = sum(teacher_loads.values()) / len(teacher_loads)
            variance = sum((load - avg_load) ** 2 for load in teacher_loads.values()) / len(teacher_loads)
            # Deduct for high variance (unbalanced)
            score -= min(variance / 10, 20)
        
        return max(0, min(100, score))
    
    # ============== MAIN GENERATION METHOD ==============
    
    async def generate_timetable(
        self,
        school_id: str,
        academic_year_id: Optional[str] = None,
        term_id: Optional[str] = None,
        created_by: str = "system"
    ) -> GenerationResult:
        """
        التوليد الرئيسي للجدول
        Main Timetable Generation Method
        """
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Create run record
        run_doc = {
            "id": run_id,
            "school_id": school_id,
            "academic_year_id": academic_year_id,
            "term_id": term_id,
            "run_type": "full_generation",
            "status": TimetableRunStatus.PENDING.value,
            "started_at": now,
            "created_by": created_by,
            "completion_percentage": 0,
            "conflicts_count": 0,
            "unscheduled_count": 0,
            "notes": ""
        }
        await self.timetable_runs.insert_one(run_doc)
        
        try:
            # Phase 1: Validate
            await self._log_run(run_id, "info", "بدء التحقق من جاهزية البيانات", {"phase": 1})
            await self.timetable_runs.update_one(
                {"id": run_id},
                {"$set": {"status": TimetableRunStatus.VALIDATING.value, "completion_percentage": 5}}
            )
            
            validation = await self.validate_data_readiness(school_id)
            if not validation.can_proceed:
                await self._log_run(run_id, "error", "فشل التحقق - بيانات ناقصة", {"issues": len(validation.issues)})
                await self.timetable_runs.update_one(
                    {"id": run_id},
                    {"$set": {"status": TimetableRunStatus.FAILED.value, "finished_at": datetime.now(timezone.utc).isoformat()}}
                )
                return GenerationResult(
                    success=False,
                    run_id=run_id,
                    status=TimetableRunStatus.FAILED.value,
                    completion_percentage=5,
                    total_sessions=0,
                    scheduled_sessions=0,
                    conflicts_count=0,
                    unscheduled_count=0,
                    optimization_score=0,
                    message_ar="فشل التحقق من البيانات: " + (validation.issues[0].message_ar if validation.issues else "خطأ غير معروف"),
                    message_en="Data validation failed: " + (validation.issues[0].message_en if validation.issues else "Unknown error")
                )
            
            # Phase 2: Load settings
            await self._log_run(run_id, "info", "تحميل إعدادات المدرسة", {"phase": 2})
            await self.timetable_runs.update_one(
                {"id": run_id},
                {"$set": {"status": TimetableRunStatus.LOADING.value, "completion_percentage": 15}}
            )
            settings = await self.load_school_settings(school_id)
            
            # Phase 3: Build demand
            await self._log_run(run_id, "info", "بناء مصفوفة الطلب الأكاديمي", {"phase": 3})
            await self.timetable_runs.update_one({"id": run_id}, {"$set": {"completion_percentage": 25}})
            demands = await self.build_academic_demand(school_id)
            
            # Phase 4: Build resources
            await self._log_run(run_id, "info", "بناء مصفوفة الموارد المتاحة", {"phase": 4})
            await self.timetable_runs.update_one({"id": run_id}, {"$set": {"completion_percentage": 35}})
            resources = await self.build_resource_availability(school_id, settings)
            
            # Phase 5: Pre-check
            await self._log_run(run_id, "info", "التحقق المسبق من التعارضات", {"phase": 5})
            await self.timetable_runs.update_one({"id": run_id}, {"$set": {"completion_percentage": 45}})
            pre_check = await self.pre_scheduling_check(school_id, demands, resources, settings)
            
            if not pre_check["can_schedule"]:
                await self._log_run(run_id, "warning", "يوجد مشاكل قد تؤثر على الجدولة", {"errors": len(pre_check["errors"])})
            
            # Load hard constraints (system rules)
            hard_constraints = await self.hard_constraints.find(
                {"is_system": True, "is_active": True}, {"_id": 0}
            ).to_list(50)
            await self._log_run(run_id, "info", f"تم تحميل {len(hard_constraints)} قيد إلزامي من النظام", {"hard_constraints_count": len(hard_constraints)})

            soft_constraints_list = await self.soft_constraints.find(
                {"is_active": True}, {"_id": 0}
            ).to_list(50)
            await self._log_run(run_id, "info", f"تم تحميل {len(soft_constraints_list)} قيد تفضيلي", {"soft_constraints_count": len(soft_constraints_list)})
            settings["soft_constraints"] = soft_constraints_list

            constraints = await self.school_constraints.find(
                {"school_id": school_id, "is_active": True}, {"_id": 0}
            ).to_list(50)
            if not constraints:
                constraints = await self.constraints.find({"is_active": True}, {"_id": 0}).to_list(50)

            all_constraints = hard_constraints + constraints
            
            # Phase 6: Generate
            await self._log_run(run_id, "info", "بدء توليد الجدول", {"phase": 6})
            await self.timetable_runs.update_one(
                {"id": run_id},
                {"$set": {"status": TimetableRunStatus.GENERATING.value, "completion_percentage": 55}}
            )
            
            timetable_id, sessions, gen_conflicts, unscheduled, underutilized_teachers = await self.generate_draft_timetable(
                school_id, run_id, demands, resources, settings, all_constraints
            )
            
            # Phase 7: Detect conflicts
            await self._log_run(run_id, "info", "اكتشاف التعارضات", {"phase": 7})
            await self.timetable_runs.update_one({"id": run_id}, {"$set": {"completion_percentage": 70}})
            conflicts = await self.detect_conflicts(sessions, resources, all_constraints, run_id)
            
            # Phase 8: Optimize
            await self._log_run(run_id, "info", "تحسين الجدول", {"phase": 8})
            await self.timetable_runs.update_one(
                {"id": run_id},
                {"$set": {"status": TimetableRunStatus.OPTIMIZING.value, "completion_percentage": 85}}
            )
            optimized_sessions, optimization_score = await self.optimize_timetable(sessions, conflicts, resources, settings)
            
            # Save timetable
            total_demand = sum(d.total_periods_required for d in demands)
            
            timetable_doc = {
                "id": timetable_id,
                "school_id": school_id,
                "academic_year_id": academic_year_id,
                "term_id": term_id,
                "name": f"الجدول المدرسي - {datetime.now().strftime('%Y-%m-%d')}",
                "status": TimetableStatus.DRAFT.value,
                "version_number": 1,
                "is_published": False,
                "created_by": created_by,
                "created_at": now,
                "updated_at": now,
                "statistics": {
                    "total_sessions": len(optimized_sessions),
                    "total_demand": total_demand,
                    "completion_rate": (len(optimized_sessions) / total_demand * 100) if total_demand > 0 else 0,
                    "conflicts_count": len(conflicts),
                    "optimization_score": optimization_score
                }
            }
            await self.timetables.insert_one(timetable_doc)
            
            # Save sessions
            if optimized_sessions:
                session_docs = [s.model_dump() for s in optimized_sessions]
                await self.timetable_sessions.insert_many(session_docs)
            
            # Save conflicts
            if conflicts:
                conflict_docs = [c.model_dump() for c in conflicts]
                await self.timetable_conflicts.insert_many(conflict_docs)
            
            # Save unscheduled
            if unscheduled:
                unscheduled_docs = [u.model_dump() for u in unscheduled]
                await self.unscheduled_demands.insert_many(unscheduled_docs)

            if underutilized_teachers:
                await self._log_run(run_id, "warning", f"معلمون بحصص أقل من المتوقع: {len(underutilized_teachers)}", {
                    "underutilized_teachers": underutilized_teachers
                })
                await self.timetables.update_one(
                    {"id": timetable_id},
                    {"$set": {"underutilized_teachers": underutilized_teachers}}
                )
            
            # Update run
            status = TimetableRunStatus.COMPLETED.value if len(unscheduled) == 0 else TimetableRunStatus.PARTIAL.value
            await self.timetable_runs.update_one(
                {"id": run_id},
                {"$set": {
                    "status": status,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "completion_percentage": 100,
                    "conflicts_count": len(conflicts),
                    "unscheduled_count": len(unscheduled),
                    "timetable_id": timetable_id
                }}
            )
            
            await self._log_run(run_id, "info", "اكتمل توليد الجدول", {
                "sessions": len(optimized_sessions),
                "conflicts": len(conflicts),
                "unscheduled": len(unscheduled),
                "score": optimization_score
            })
            
            return GenerationResult(
                success=True,
                timetable_id=timetable_id,
                run_id=run_id,
                status=status,
                completion_percentage=100,
                total_sessions=total_demand,
                scheduled_sessions=len(optimized_sessions),
                conflicts_count=len(conflicts),
                unscheduled_count=len(unscheduled),
                optimization_score=optimization_score,
                message_ar=f"تم توليد الجدول بنجاح ({len(optimized_sessions)} حصة)",
                message_en=f"Timetable generated successfully ({len(optimized_sessions)} sessions)"
            )
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Timetable generation error: {e}\n{tb}")
            await self._log_run(run_id, "error", f"خطأ في التوليد: {str(e)}", {"exception": str(e), "traceback": tb})
            await self.timetable_runs.update_one(
                {"id": run_id},
                {"$set": {
                    "status": TimetableRunStatus.FAILED.value,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "notes": str(e)
                }}
            )
            return GenerationResult(
                success=False,
                run_id=run_id,
                status=TimetableRunStatus.FAILED.value,
                completion_percentage=0,
                total_sessions=0,
                scheduled_sessions=0,
                conflicts_count=0,
                unscheduled_count=0,
                optimization_score=0,
                message_ar=f"فشل توليد الجدول: {str(e)}",
                message_en=f"Timetable generation failed: {str(e)}"
            )
    
    async def _log_run(self, run_id: str, level: str, message: str, context: Dict[str, Any] = None):
        """Log run event"""
        log_doc = {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "log_level": level,
            "message": message,
            "context": context or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await self.timetable_run_logs.insert_one(log_doc)
    
    # ============== RETRIEVAL METHODS ==============
    
    async def get_timetable(self, timetable_id: str) -> Optional[Dict[str, Any]]:
        """Get timetable by ID"""
        return await self.timetables.find_one({"id": timetable_id}, {"_id": 0})
    
    async def get_timetable_sessions(
        self,
        timetable_id: str,
        class_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        day_of_week: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get sessions for a timetable"""
        query = {"timetable_id": timetable_id}
        if class_id:
            query["class_id"] = class_id
        if teacher_id:
            query["teacher_id"] = teacher_id
        if day_of_week:
            query["day_of_week"] = day_of_week
        
        return await self.timetable_sessions.find(query, {"_id": 0}).sort([("day_of_week", 1), ("period_number", 1)]).to_list(500)
    
    async def get_timetable_conflicts(self, timetable_id: str) -> List[Dict[str, Any]]:
        """Get conflicts for a timetable"""
        return await self.timetable_conflicts.find({"timetable_id": timetable_id}, {"_id": 0}).to_list(500)
    
    async def get_run_logs(self, run_id: str) -> List[Dict[str, Any]]:
        """Get logs for a run"""
        return await self.timetable_run_logs.find({"run_id": run_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    
    async def get_school_timetables(self, school_id: str) -> List[Dict[str, Any]]:
        """Get all timetables for a school"""
        return await self.timetables.find({"school_id": school_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    async def publish_timetable(self, timetable_id: str, published_by: str) -> bool:
        """Publish a timetable"""
        # Check for critical conflicts
        conflicts = await self.timetable_conflicts.count_documents({
            "timetable_id": timetable_id,
            "severity": ConflictSeverity.CRITICAL.value,
            "is_resolved": False
        })
        
        if conflicts > 0:
            return False
        
        now = datetime.now(timezone.utc).isoformat()
        result = await self.timetables.update_one(
            {"id": timetable_id},
            {"$set": {
                "status": TimetableStatus.PUBLISHED.value,
                "is_published": True,
                "published_at": now,
                "published_by": published_by,
                "updated_at": now
            }}
        )
        
        return result.modified_count > 0
    
    async def archive_timetable(self, timetable_id: str, archived_by: str) -> bool:
        """Archive a timetable"""
        result = await self.timetables.update_one(
            {"id": timetable_id},
            {"$set": {
                "status": TimetableStatus.ARCHIVED.value,
                "archived_at": datetime.now(timezone.utc).isoformat(),
                "archived_by": archived_by
            }}
        )
        return result.modified_count > 0


# Export
__all__ = [
    "SmartSchedulingEngine",
    "TimetableRunStatus",
    "TimetableStatus",
    "SessionSourceType",
    "SessionStatus",
    "ConflictType",
    "ConflictSeverity",
    "DayOfWeek",
    "PreValidationResult",
    "GenerationResult",
    "TimetableSession",
    "TimetableConflict",
    "UnscheduledDemand"
]
