"""
Schedule Management Engine - محرك إدارة الجداول
Handles weekly schedule creation and management
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum

from sqlalchemy import select, and_, func, desc as sa_desc

from pg_models import Teacher, Subject, Class
from engines.sql_utils import (
    model_to_dict, gd_find, gd_find_one, gd_insert, gd_count,
)

logger = logging.getLogger(__name__)

class DayOfWeek(str, Enum):
    sunday = "sunday"
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"

class PeriodSlot(BaseModel):
    """Single period in the schedule"""
    period_number: int = Field(ge=1, le=10)
    subject_id: str
    teacher_id: str
    class_id: str
    start_time: str
    end_time: str

class DaySchedule(BaseModel):
    """Schedule for a single day"""
    day: DayOfWeek
    periods: List[PeriodSlot]

class CreateScheduleRequest(BaseModel):
    """Request to create a weekly schedule"""
    name_ar: str = Field(..., min_length=1)
    name_en: Optional[str] = None
    grade_id: str
    class_id: str
    academic_year: str
    semester: int = Field(ge=1, le=2)
    days: List[DaySchedule]
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None

class ScheduleManagementEngine:
    """Engine for managing class schedules"""

    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    async def _generate_schedule_id(self, tenant_id: str) -> str:
        """Generate unique schedule ID"""
        year = datetime.now().strftime("%y")
        count = await gd_count(self.session, "schedules", {"tenant_id": tenant_id})
        return f"SCH-{year}-{str(count + 1).zfill(4)}"

    async def create_schedule(
        self,
        request: CreateScheduleRequest,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        """Create a new weekly schedule"""
        try:
            schedule_id = await self._generate_schedule_id(tenant_id)
            now = datetime.now(timezone.utc)

            days_data = []
            for day_schedule in request.days:
                periods_data = []
                for period in day_schedule.periods:
                    periods_data.append({
                        "period_number": period.period_number,
                        "subject_id": period.subject_id,
                        "teacher_id": period.teacher_id,
                        "class_id": period.class_id,
                        "start_time": period.start_time,
                        "end_time": period.end_time,
                    })
                days_data.append({
                    "day": day_schedule.day.value,
                    "periods": periods_data,
                })

            schedule_doc = {
                "id": schedule_id,
                "schedule_id": schedule_id,
                "tenant_id": tenant_id,
                "name_ar": request.name_ar,
                "name_en": request.name_en,
                "grade_id": request.grade_id,
                "class_id": request.class_id,
                "academic_year": request.academic_year,
                "semester": request.semester,
                "days": days_data,
                "effective_from": request.effective_from,
                "effective_to": request.effective_to,
                "status": "active",
                "is_deleted": False,
                "created_at": now.isoformat(),
                "created_by": created_by,
                "updated_at": now.isoformat(),
            }

            await gd_insert(self.session, "schedules", schedule_doc)

            return {
                "success": True,
                "schedule_id": schedule_id,
                "message": "تم إنشاء الجدول بنجاح",
                "message_en": "Schedule created successfully"
            }
        except Exception as e:
            logger.error(f"Error creating schedule: {e}")
            return {"success": False, "error": str(e)}

    async def get_schedule(self, schedule_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get schedule by ID"""
        results = await gd_find(self.session, "schedules", {
            "schedule_id": schedule_id,
            "tenant_id": tenant_id,
        })
        for r in results:
            if not r.get("is_deleted"):
                r.pop("_id", None)
                return r
        return None

    async def list_schedules(
        self,
        tenant_id: str,
        class_id: Optional[str] = None,
        grade_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List schedules"""
        filters = {"tenant_id": tenant_id}
        if class_id:
            filters["class_id"] = class_id
        if grade_id:
            filters["grade_id"] = grade_id

        all_results = await gd_find(
            self.session, "schedules", filters,
            order_by="created_at", desc_order=True,
        )
        active = [r for r in all_results if not r.get("is_deleted")]
        total = len(active)
        page = active[skip:skip + limit]
        for r in page:
            r.pop("_id", None)

        return {"schedules": page, "total": total}

    async def get_class_schedule(self, class_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get active schedule for a class"""
        results = await gd_find(self.session, "schedules", {
            "class_id": class_id,
            "tenant_id": tenant_id,
            "status": "active",
        })
        for r in results:
            if not r.get("is_deleted"):
                r.pop("_id", None)
                return r
        return None

    async def _lookup_teacher(self, teacher_id: str) -> Optional[dict]:
        stmt = select(Teacher).where(Teacher.id == teacher_id).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if row:
            return {"full_name_ar": row.full_name or "", "full_name_en": row.full_name_en or ""}
        return None

    async def _lookup_subject(self, subject_id: str) -> Optional[dict]:
        stmt = select(Subject).where(Subject.id == subject_id).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if row:
            return {"name_ar": row.name_ar or row.name or "", "name_en": row.name_en or ""}
        return None

    async def _lookup_class(self, class_id: str) -> Optional[dict]:
        stmt = select(Class).where(Class.id == class_id).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if row:
            return {"name_ar": row.name or "", "name_en": row.name_en or "", "grade_id": row.grade_id or ""}
        return None

    async def get_current_sessions(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all currently running sessions"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.strftime("%A").lower()

        day_map = {
            "sunday": "sunday", "monday": "monday", "tuesday": "tuesday",
            "wednesday": "wednesday", "thursday": "thursday",
            "friday": "friday", "saturday": "saturday",
        }
        today = day_map.get(current_day, "sunday")

        schedules = await gd_find(self.session, "schedules", {
            "tenant_id": tenant_id,
            "status": "active",
        })

        current_sessions = []

        for schedule in schedules:
            if schedule.get("is_deleted"):
                continue
            for day_data in (schedule.get("days") or []):
                if day_data.get("day") == today:
                    for period in day_data.get("periods", []):
                        start = period.get("start_time", "00:00")
                        end = period.get("end_time", "23:59")

                        if start <= current_time <= end:
                            teacher = await self._lookup_teacher(period.get("teacher_id", ""))
                            subject = await self._lookup_subject(period.get("subject_id", ""))
                            class_info = await self._lookup_class(period.get("class_id", ""))

                            current_sessions.append({
                                "schedule_id": schedule.get("schedule_id"),
                                "class_id": period.get("class_id"),
                                "class_name": class_info.get("name_ar") if class_info else "",
                                "grade_id": class_info.get("grade_id") if class_info else "",
                                "subject_id": period.get("subject_id"),
                                "subject_name": subject.get("name_ar") if subject else "",
                                "teacher_id": period.get("teacher_id"),
                                "teacher_name": teacher.get("full_name_ar") if teacher else "",
                                "period_number": period.get("period_number"),
                                "start_time": start,
                                "end_time": end,
                                "status": "active",
                            })

        return current_sessions

    async def get_today_schedule(self, tenant_id: str, class_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get today's schedule for all or specific class"""
        now = datetime.now()
        current_day = now.strftime("%A").lower()

        day_map = {
            "sunday": "sunday", "monday": "monday", "tuesday": "tuesday",
            "wednesday": "wednesday", "thursday": "thursday",
            "friday": "friday", "saturday": "saturday",
        }
        today = day_map.get(current_day, "sunday")

        filters = {"tenant_id": tenant_id, "status": "active"}
        if class_id:
            filters["class_id"] = class_id

        schedules = await gd_find(self.session, "schedules", filters)

        today_sessions = []
        for schedule in schedules:
            if schedule.get("is_deleted"):
                continue
            for day_data in (schedule.get("days") or []):
                if day_data.get("day") == today:
                    for period in day_data.get("periods", []):
                        teacher = await self._lookup_teacher(period.get("teacher_id", ""))
                        subject = await self._lookup_subject(period.get("subject_id", ""))
                        class_info = await self._lookup_class(period.get("class_id", ""))

                        today_sessions.append({
                            "class_id": period.get("class_id"),
                            "class_name": class_info.get("name_ar") if class_info else "",
                            "subject_name": subject.get("name_ar") if subject else "",
                            "teacher_name": teacher.get("full_name_ar") if teacher else "",
                            "period_number": period.get("period_number"),
                            "start_time": period.get("start_time"),
                            "end_time": period.get("end_time"),
                        })

        today_sessions.sort(key=lambda x: x.get("period_number", 0))
        return today_sessions

    async def get_default_periods(self) -> List[Dict[str, Any]]:
        """Get default period times"""
        return [
            {"number": 1, "start": "07:30", "end": "08:15", "name_ar": "الحصة الأولى"},
            {"number": 2, "start": "08:20", "end": "09:05", "name_ar": "الحصة الثانية"},
            {"number": 3, "start": "09:10", "end": "09:55", "name_ar": "الحصة الثالثة"},
            {"number": 4, "start": "10:15", "end": "11:00", "name_ar": "الحصة الرابعة"},
            {"number": 5, "start": "11:05", "end": "11:50", "name_ar": "الحصة الخامسة"},
            {"number": 6, "start": "11:55", "end": "12:40", "name_ar": "الحصة السادسة"},
            {"number": 7, "start": "12:45", "end": "13:30", "name_ar": "الحصة السابعة"},
        ]

    async def get_days(self) -> List[Dict[str, str]]:
        """Get weekdays"""
        return [
            {"code": "sunday", "name_ar": "الأحد", "name_en": "Sunday"},
            {"code": "monday", "name_ar": "الإثنين", "name_en": "Monday"},
            {"code": "tuesday", "name_ar": "الثلاثاء", "name_en": "Tuesday"},
            {"code": "wednesday", "name_ar": "الأربعاء", "name_en": "Wednesday"},
            {"code": "thursday", "name_ar": "الخميس", "name_en": "Thursday"},
        ]

    async def get_teachers(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available teachers"""
        stmt = select(Teacher).where(
            and_(Teacher.school_id == tenant_id, Teacher.is_active == True)
        ).limit(200)
        result = await self.session.execute(stmt)
        teachers = []
        for t in result.scalars().all():
            d = model_to_dict(t)
            teachers.append({
                "teacher_id": d.get("id"),
                "full_name_ar": d.get("full_name") or "",
                "subject_ids": d.get("subject_ids") or [],
            })
        return teachers

    async def get_subjects(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available subjects"""
        stmt = select(Subject).where(
            and_(Subject.school_id == tenant_id, Subject.is_active == True)
        ).limit(100)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        if rows:
            subjects = []
            for s in rows:
                subjects.append({
                    "id": s.id,
                    "name_ar": s.name_ar or s.name or "",
                    "name_en": s.name_en or "",
                })
            return subjects

        return [
            {"id": "math", "name_ar": "الرياضيات", "name_en": "Mathematics"},
            {"id": "arabic", "name_ar": "اللغة العربية", "name_en": "Arabic"},
            {"id": "english", "name_ar": "اللغة الإنجليزية", "name_en": "English"},
            {"id": "science", "name_ar": "العلوم", "name_en": "Science"},
            {"id": "social", "name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies"},
            {"id": "islamic", "name_ar": "التربية الإسلامية", "name_en": "Islamic Studies"},
            {"id": "pe", "name_ar": "التربية البدنية", "name_en": "PE"},
            {"id": "art", "name_ar": "التربية الفنية", "name_en": "Art"},
        ]

    async def get_classes(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available classes"""
        stmt = select(Class).where(
            and_(Class.school_id == tenant_id, Class.is_active == True)
        ).limit(200)
        result = await self.session.execute(stmt)
        classes = []
        for c in result.scalars().all():
            classes.append({
                "class_id": c.id,
                "name_ar": c.name or "",
                "grade_id": c.grade_id or "",
            })
        return classes
