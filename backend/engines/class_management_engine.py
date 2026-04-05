"""
Class Management Engine - محرك إدارة الفصول
Handles class/section creation and management
"""
import logging
from datetime import datetime, timezone
from bson_compat import ObjectId
from typing import Optional, Dict, Any, List
import secrets
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)

class ClassType(str, Enum):
    regular = "regular"
    advanced = "advanced"
    special_needs = "special_needs"

class CreateClassRequest(BaseModel):
    name_ar: str = Field(..., min_length=1)
    name_en: Optional[str] = None
    grade_id: str
    class_type: ClassType = ClassType.regular
    capacity: int = Field(default=30, ge=1, le=50)
    homeroom_teacher_id: Optional[str] = None
    room_number: Optional[str] = None
    floor: Optional[int] = None
    building: Optional[str] = None
    student_ids: Optional[List[str]] = None
    notes: Optional[str] = None

class ClassManagementEngine:
    """Engine for managing class/section operations"""
    
    def __init__(self, db):
        self.db = db
        self.classes_collection = db.classes
        self.sections_collection = db.sections
        self.grades_collection = db.grades
        self.teachers_collection = db.teachers
        self.students_collection = db.students
    
    async def _generate_class_id(self, tenant_id: str, grade_id: str) -> str:
        """Generate unique class ID"""
        year = datetime.now().strftime("%y")
        prefix = f"CLS-{grade_id[:3].upper()}-{year}-"
        count = await self.classes_collection.count_documents({
            "class_id": {"$regex": f"^{prefix}"},
            "tenant_id": tenant_id
        })
        return f"{prefix}{str(count + 1).zfill(3)}"
    
    async def create_class(
        self,
        request: CreateClassRequest,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        """Create a new class/section"""
        try:
            class_id = await self._generate_class_id(tenant_id, request.grade_id)
            now = datetime.now(timezone.utc)
            
            class_doc = {
                "class_id": class_id,
                "tenant_id": tenant_id,
                "name_ar": request.name_ar,
                "name_en": request.name_en,
                "grade_id": request.grade_id,
                "class_type": request.class_type.value,
                "capacity": request.capacity,
                "current_students": len(request.student_ids or []),
                "homeroom_teacher_id": request.homeroom_teacher_id,
                "room_number": request.room_number,
                "floor": request.floor,
                "building": request.building,
                "student_ids": request.student_ids or [],
                "notes": request.notes,
                "status": "active",
                "is_deleted": False,
                "created_at": now.isoformat(),
                "created_by": created_by,
                "updated_at": now.isoformat(),
            }
            
            await self.classes_collection.insert_one(class_doc)
            
            # Update students with class assignment
            if request.student_ids:
                await self.students_collection.update_many(
                    {"student_id": {"$in": request.student_ids}},
                    {"$set": {"class_id": class_id, "updated_at": now.isoformat()}}
                )
            
            return {
                "success": True,
                "class_id": class_id,
                "message": "تم إنشاء الفصل بنجاح",
                "message_en": "Class created successfully"
            }
        except Exception as e:
            logger.error(f"Error creating class: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "حدث خطأ أثناء إنشاء الفصل",
                "message_en": "Error creating class"
            }
    
    async def get_class(self, class_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get class by ID"""
        cls = await self.classes_collection.find_one({
            "class_id": class_id,
            "tenant_id": tenant_id,
            "is_deleted": {"$ne": True}
        }, {"_id": 0})
        return cls
    
    async def list_classes(
        self,
        tenant_id: str,
        grade_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List classes with filters"""
        query = {"tenant_id": tenant_id, "is_deleted": {"$ne": True}}
        
        if grade_id:
            query["grade_id"] = grade_id
        if status:
            query["status"] = status
        if search:
            query["$or"] = [
                {"name_ar": {"$regex": search, "$options": "i"}},
                {"name_en": {"$regex": search, "$options": "i"}},
                {"class_id": {"$regex": search, "$options": "i"}},
            ]
        
        total = await self.classes_collection.count_documents(query)
        classes = await self.classes_collection.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return {"classes": classes, "total": total}
    
    async def get_grades(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available grades"""
        grades = await self.grades_collection.find(
            {"$or": [{"tenant_id": tenant_id}, {"school_id": tenant_id}], "is_active": {"$ne": False}},
            {"_id": 0}
        ).to_list(100)
        
        if not grades:
            grade_levels = await self.students_collection.distinct("grade_level", {"school_id": tenant_id, "is_active": {"$ne": False}})
            grade_levels = sorted([g for g in grade_levels if g], key=lambda x: int(x) if x.isdigit() else 999)
            grade_names = {
                "1": ("الصف الأول", "Grade 1"), "2": ("الصف الثاني", "Grade 2"),
                "3": ("الصف الثالث", "Grade 3"), "4": ("الصف الرابع", "Grade 4"),
                "5": ("الصف الخامس", "Grade 5"), "6": ("الصف السادس", "Grade 6"),
                "7": ("الصف السابع", "Grade 7"), "8": ("الصف الثامن", "Grade 8"),
                "9": ("الصف التاسع", "Grade 9"), "10": ("الصف العاشر", "Grade 10"),
                "11": ("الصف الحادي عشر", "Grade 11"), "12": ("الصف الثاني عشر", "Grade 12"),
            }
            grades = []
            for gl in grade_levels:
                names = grade_names.get(gl, (f"الصف {gl}", f"Grade {gl}"))
                grades.append({"id": f"grade_{gl}", "grade_level": gl, "name_ar": names[0], "name_en": names[1]})
        return grades
    
    async def get_teachers(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available teachers for homeroom assignment"""
        teachers_raw = await self.teachers_collection.find(
            {"$or": [{"tenant_id": tenant_id}, {"school_id": tenant_id}], "is_active": {"$ne": False}},
            {"_id": 0, "id": 1, "teacher_id": 1, "full_name": 1, "full_name_ar": 1, "full_name_en": 1, "name": 1, "name_ar": 1}
        ).to_list(200)
        teachers = []
        for t in teachers_raw:
            teachers.append({
                "teacher_id": t.get("teacher_id") or t.get("id", ""),
                "full_name_ar": t.get("full_name_ar") or t.get("name_ar") or t.get("full_name") or t.get("name", ""),
                "full_name_en": t.get("full_name_en") or "",
            })
        return teachers
    
    async def get_students(self, tenant_id: str, grade_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available students for class assignment"""
        query = {"$or": [{"tenant_id": tenant_id}, {"school_id": tenant_id}], "is_active": {"$ne": False}}
        if grade_id:
            grade_level = grade_id.replace("grade_", "") if grade_id.startswith("grade_") else grade_id
            query["grade_level"] = grade_level
        
        students_raw = await self.students_collection.find(
            query,
            {"_id": 0, "id": 1, "student_id": 1, "full_name": 1, "full_name_ar": 1, "full_name_en": 1, "grade_level": 1}
        ).to_list(500)
        students = []
        for s in students_raw:
            students.append({
                "student_id": s.get("student_id") or s.get("id", ""),
                "full_name_ar": s.get("full_name_ar") or s.get("full_name", ""),
                "full_name_en": s.get("full_name_en") or "",
                "grade_id": f"grade_{s.get('grade_level', '')}" if s.get("grade_level") else "",
            })
        return students
    
    async def get_class_types(self) -> List[Dict[str, str]]:
        """Get class types"""
        return [
            {"code": "regular", "name_ar": "عادي", "name_en": "Regular"},
            {"code": "advanced", "name_ar": "متقدم", "name_en": "Advanced"},
            {"code": "special_needs", "name_ar": "احتياجات خاصة", "name_en": "Special Needs"},
        ]
