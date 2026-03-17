"""
Schedule Management Engine - محرك إدارة الجداول
Handles weekly schedule creation and management
"""
import logging
from datetime import datetime, timezone, time
from bson import ObjectId
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum

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
    start_time: str  # HH:MM format
    end_time: str    # HH:MM format

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
    academic_year: str  # e.g., "2025-2026"
    semester: int = Field(ge=1, le=2)
    days: List[DaySchedule]
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None

class ScheduleManagementEngine:
    """Engine for managing class schedules"""
    
    def __init__(self, db):
        self.db = db
        self.schedules_collection = db.schedules
        self.sessions_collection = db.sessions
        self.teachers_collection = db.teachers
        self.subjects_collection = db.subjects
        self.classes_collection = db.classes
    
    async def _generate_schedule_id(self, tenant_id: str) -> str:
        """Generate unique schedule ID"""
        year = datetime.now().strftime("%y")
        count = await self.schedules_collection.count_documents({"tenant_id": tenant_id})
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
            
            # Convert days to dict format
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
            
            await self.schedules_collection.insert_one(schedule_doc)
            
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
        return await self.schedules_collection.find_one({
            "schedule_id": schedule_id,
            "tenant_id": tenant_id,
            "is_deleted": {"$ne": True}
        }, {"_id": 0})
    
    async def list_schedules(
        self,
        tenant_id: str,
        class_id: Optional[str] = None,
        grade_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List schedules"""
        query = {"tenant_id": tenant_id, "is_deleted": {"$ne": True}}
        if class_id:
            query["class_id"] = class_id
        if grade_id:
            query["grade_id"] = grade_id
        
        total = await self.schedules_collection.count_documents(query)
        schedules = await self.schedules_collection.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return {"schedules": schedules, "total": total}
    
    async def get_class_schedule(self, class_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get active schedule for a class"""
        return await self.schedules_collection.find_one({
            "class_id": class_id,
            "tenant_id": tenant_id,
            "status": "active",
            "is_deleted": {"$ne": True}
        }, {"_id": 0})
    
    # ==================== Live Sessions ====================
    
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
        
        schedules = await self.schedules_collection.find({
            "tenant_id": tenant_id,
            "status": "active",
            "is_deleted": {"$ne": True}
        }).to_list(200)
        
        current_sessions = []
        
        for schedule in schedules:
            for day_data in schedule.get("days", []):
                if day_data.get("day") == today:
                    for period in day_data.get("periods", []):
                        start = period.get("start_time", "00:00")
                        end = period.get("end_time", "23:59")
                        
                        if start <= current_time <= end:
                            teacher = await self.teachers_collection.find_one(
                                {"teacher_id": period.get("teacher_id")},
                                {"full_name_ar": 1, "full_name_en": 1}
                            )
                            subject = await self.subjects_collection.find_one(
                                {"id": period.get("subject_id")},
                                {"name_ar": 1, "name_en": 1}
                            )
                            class_info = await self.classes_collection.find_one(
                                {"class_id": period.get("class_id")},
                                {"name_ar": 1, "name_en": 1, "grade_id": 1}
                            )
                            
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
        
        query = {"tenant_id": tenant_id, "status": "active", "is_deleted": {"$ne": True}}
        if class_id:
            query["class_id"] = class_id
        
        schedules = await self.schedules_collection.find(query).to_list(200)
        
        today_sessions = []
        for schedule in schedules:
            for day_data in schedule.get("days", []):
                if day_data.get("day") == today:
                    for period in day_data.get("periods", []):
                        teacher = await self.teachers_collection.find_one(
                            {"teacher_id": period.get("teacher_id")}, {"full_name_ar": 1}
                        )
                        subject = await self.subjects_collection.find_one(
                            {"id": period.get("subject_id")}, {"name_ar": 1}
                        )
                        class_info = await self.classes_collection.find_one(
                            {"class_id": period.get("class_id")}, {"name_ar": 1}
                        )
                        
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
    
    # ==================== Options ====================
    
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
        teachers = await self.teachers_collection.find(
            {"tenant_id": tenant_id, "is_deleted": {"$ne": True}},
            {"_id": 0, "teacher_id": 1, "full_name_ar": 1, "subject_ids": 1}
        ).to_list(200)
        return teachers
    
    async def get_subjects(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available subjects"""
        subjects = await self.subjects_collection.find(
            {"tenant_id": tenant_id, "is_active": {"$ne": False}},
            {"_id": 0}
        ).to_list(100)
        if not subjects:
            subjects = [
                {"id": "math", "name_ar": "الرياضيات", "name_en": "Mathematics"},
                {"id": "arabic", "name_ar": "اللغة العربية", "name_en": "Arabic"},
                {"id": "english", "name_ar": "اللغة الإنجليزية", "name_en": "English"},
                {"id": "science", "name_ar": "العلوم", "name_en": "Science"},
                {"id": "social", "name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies"},
                {"id": "islamic", "name_ar": "التربية الإسلامية", "name_en": "Islamic Studies"},
                {"id": "pe", "name_ar": "التربية البدنية", "name_en": "PE"},
                {"id": "art", "name_ar": "التربية الفنية", "name_en": "Art"},
            ]
        return subjects
    
    async def get_classes(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available classes"""
        classes = await self.classes_collection.find(
            {"tenant_id": tenant_id, "is_deleted": {"$ne": True}},
            {"_id": 0, "class_id": 1, "name_ar": 1, "grade_id": 1}
        ).to_list(200)
        return classes
