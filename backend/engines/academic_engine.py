"""
NASSAQ Academic Structure Engine
محرك الهيكل الأكاديمي لمنصة نَسَّق

Handles:
- Educational stages (رياض أطفال، ابتدائي، متوسط، ثانوي)
- Grades within stages
- Sections/Classes
- Physical classrooms
- Subject management
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid


class AcademicStructureEngine:
    """
    Core Academic Structure Engine for NASSAQ
    Manages educational hierarchy and classroom structure
    """
    
    def __init__(self, db):
        self.db = db
        self.stages_collection = db.educational_stages
        self.grades_collection = db.grades
        self.sections_collection = db.sections
        self.classrooms_collection = db.physical_classrooms
        self.subjects_collection = db.subjects
        self.audit_collection = db.audit_logs
    
    # ============== EDUCATIONAL STAGES ==============
    
    async def seed_default_stages(self):
        """Seed default educational stages for Saudi Arabia"""
        default_stages = [
            {
                "code": "KG",
                "name_ar": "رياض الأطفال",
                "name_en": "Kindergarten",
                "order": 1,
                "min_age": 3,
                "max_age": 6,
                "grades_count": 3,  # KG1, KG2, KG3
                "is_mandatory": False
            },
            {
                "code": "PRIMARY",
                "name_ar": "المرحلة الابتدائية",
                "name_en": "Primary",
                "order": 2,
                "min_age": 6,
                "max_age": 12,
                "grades_count": 6,
                "is_mandatory": True
            },
            {
                "code": "INTERMEDIATE",
                "name_ar": "المرحلة المتوسطة",
                "name_en": "Intermediate",
                "order": 3,
                "min_age": 12,
                "max_age": 15,
                "grades_count": 3,
                "is_mandatory": True
            },
            {
                "code": "SECONDARY",
                "name_ar": "المرحلة الثانوية",
                "name_en": "Secondary",
                "order": 4,
                "min_age": 15,
                "max_age": 18,
                "grades_count": 3,
                "is_mandatory": False
            }
        ]
        
        count = 0
        for stage in default_stages:
            existing = await self.stages_collection.find_one({
                "code": stage["code"],
                "is_global": True
            })
            
            if not existing:
                stage["id"] = str(uuid.uuid4())
                stage["tenant_id"] = None
                stage["is_global"] = True
                stage["is_active"] = True
                stage["created_at"] = datetime.now(timezone.utc).isoformat()
                stage["created_by"] = "system"
                await self.stages_collection.insert_one(stage)
                count += 1
        
        return count
    
    async def get_stages(
        self,
        tenant_id: Optional[str] = None,
        include_global: bool = True
    ) -> List[Dict[str, Any]]:
        """Get educational stages"""
        query = {"is_active": True}
        
        if tenant_id:
            if include_global:
                query["$or"] = [
                    {"tenant_id": tenant_id},
                    {"is_global": True}
                ]
            else:
                query["tenant_id"] = tenant_id
        else:
            query["is_global"] = True
        
        stages = await self.stages_collection.find(
            query,
            {"_id": 0}
        ).sort("order", 1).to_list(100)
        
        return stages
    
    async def create_tenant_stage(
        self,
        tenant_id: str,
        code: str,
        name_ar: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a custom stage for a tenant"""
        stage_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        stage_doc = {
            "id": stage_id,
            "tenant_id": tenant_id,
            "code": code,
            "name_ar": name_ar,
            "name_en": kwargs.get("name_en"),
            "order": kwargs.get("order", 99),
            "min_age": kwargs.get("min_age"),
            "max_age": kwargs.get("max_age"),
            "grades_count": kwargs.get("grades_count", 1),
            "is_mandatory": kwargs.get("is_mandatory", False),
            "is_global": False,
            "is_active": True,
            "created_at": now,
            "created_by": created_by,
        }
        
        await self.stages_collection.insert_one(stage_doc)
        return stage_doc
    
    # ============== GRADES ==============
    
    async def seed_default_grades(self, tenant_id: str):
        """Seed default grades for a tenant based on stages"""
        stages = await self.get_stages(include_global=True)
        
        grade_names_ar = {
            1: "الأول", 2: "الثاني", 3: "الثالث",
            4: "الرابع", 5: "الخامس", 6: "السادس"
        }
        
        grade_names_en = {
            1: "First", 2: "Second", 3: "Third",
            4: "Fourth", 5: "Fifth", 6: "Sixth"
        }
        
        count = 0
        for stage in stages:
            stage_code = stage.get("code")
            grades_count = stage.get("grades_count", 3)
            
            for i in range(1, grades_count + 1):
                # Check if grade exists
                existing = await self.grades_collection.find_one({
                    "tenant_id": tenant_id,
                    "stage_code": stage_code,
                    "grade_number": i
                })
                
                if not existing:
                    if stage_code == "KG":
                        name_ar = f"روضة {i}"
                        name_en = f"KG{i}"
                    else:
                        name_ar = f"الصف {grade_names_ar.get(i, str(i))}"
                        name_en = f"Grade {i}"
                    
                    grade_doc = {
                        "id": str(uuid.uuid4()),
                        "tenant_id": tenant_id,
                        "stage_id": stage.get("id"),
                        "stage_code": stage_code,
                        "stage_name_ar": stage.get("name_ar"),
                        "grade_number": i,
                        "name_ar": name_ar,
                        "name_en": name_en,
                        "full_name_ar": f"{name_ar} - {stage.get('name_ar')}",
                        "display_order": stage.get("order", 1) * 10 + i,
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "created_by": "system"
                    }
                    
                    await self.grades_collection.insert_one(grade_doc)
                    count += 1
        
        return count
    
    async def get_grades(
        self,
        tenant_id: str,
        stage_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get grades for a tenant"""
        query = {"tenant_id": tenant_id, "is_active": True}
        
        if stage_code:
            query["stage_code"] = stage_code
        
        grades = await self.grades_collection.find(
            query,
            {"_id": 0}
        ).sort("display_order", 1).to_list(100)
        
        return grades
    
    async def create_grade(
        self,
        tenant_id: str,
        stage_code: str,
        grade_number: int,
        name_ar: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new grade"""
        grade_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Get stage info
        stage = await self.stages_collection.find_one({
            "$or": [
                {"code": stage_code, "tenant_id": tenant_id},
                {"code": stage_code, "is_global": True}
            ]
        })
        
        if not stage:
            raise ValueError("المرحلة غير موجودة")
        
        grade_doc = {
            "id": grade_id,
            "tenant_id": tenant_id,
            "stage_id": stage.get("id"),
            "stage_code": stage_code,
            "stage_name_ar": stage.get("name_ar"),
            "grade_number": grade_number,
            "name_ar": name_ar,
            "name_en": kwargs.get("name_en"),
            "full_name_ar": f"{name_ar} - {stage.get('name_ar')}",
            "display_order": kwargs.get("display_order", stage.get("order", 1) * 10 + grade_number),
            "is_active": True,
            "created_at": now,
            "created_by": created_by,
        }
        
        await self.grades_collection.insert_one(grade_doc)
        return grade_doc
    
    # ============== SECTIONS ==============
    
    async def create_section(
        self,
        tenant_id: str,
        grade_id: str,
        name: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new section/class"""
        section_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Get grade info
        grade = await self.grades_collection.find_one(
            {"id": grade_id, "tenant_id": tenant_id},
            {"_id": 0}
        )
        
        if not grade:
            raise ValueError("الصف غير موجود")
        
        section_doc = {
            "id": section_id,
            "tenant_id": tenant_id,
            "grade_id": grade_id,
            "grade_name_ar": grade.get("name_ar"),
            "stage_code": grade.get("stage_code"),
            "name": name,  # أ، ب، ج
            "full_name_ar": f"{grade.get('full_name_ar')} ({name})",
            "capacity": kwargs.get("capacity", 30),
            "current_count": 0,
            "homeroom_teacher_id": kwargs.get("homeroom_teacher_id"),
            "classroom_id": kwargs.get("classroom_id"),
            "is_active": True,
            "academic_year": kwargs.get("academic_year", "1446-1447"),
            "created_at": now,
            "created_by": created_by,
        }
        
        await self.sections_collection.insert_one(section_doc)
        return section_doc
    
    async def get_sections(
        self,
        tenant_id: str,
        grade_id: Optional[str] = None,
        stage_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get sections for a tenant"""
        query = {"tenant_id": tenant_id, "is_active": True}
        
        if grade_id:
            query["grade_id"] = grade_id
        if stage_code:
            query["stage_code"] = stage_code
        
        sections = await self.sections_collection.find(
            query,
            {"_id": 0}
        ).sort("full_name_ar", 1).to_list(1000)
        
        return sections
    
    async def update_section(
        self,
        section_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update a section"""
        now = datetime.now(timezone.utc).isoformat()
        
        protected = ["id", "tenant_id", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)
        
        updates["updated_at"] = now
        updates["updated_by"] = updated_by
        
        await self.sections_collection.update_one(
            {"id": section_id},
            {"$set": updates}
        )
        
        return await self.sections_collection.find_one(
            {"id": section_id},
            {"_id": 0}
        )
    
    async def assign_homeroom_teacher(
        self,
        section_id: str,
        teacher_id: str,
        assigned_by: str
    ) -> Dict[str, Any]:
        """Assign homeroom teacher to section"""
        now = datetime.now(timezone.utc).isoformat()
        
        await self.sections_collection.update_one(
            {"id": section_id},
            {
                "$set": {
                    "homeroom_teacher_id": teacher_id,
                    "homeroom_assigned_at": now,
                    "homeroom_assigned_by": assigned_by
                }
            }
        )
        
        return await self.sections_collection.find_one(
            {"id": section_id},
            {"_id": 0}
        )
    
    # ============== PHYSICAL CLASSROOMS ==============
    
    async def create_classroom(
        self,
        tenant_id: str,
        name: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a physical classroom"""
        classroom_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        classroom_doc = {
            "id": classroom_id,
            "tenant_id": tenant_id,
            "name": name,
            "building": kwargs.get("building"),
            "floor": kwargs.get("floor"),
            "room_type": kwargs.get("room_type", "classroom"),
            "capacity": kwargs.get("capacity", 30),
            "has_projector": kwargs.get("has_projector", False),
            "has_smartboard": kwargs.get("has_smartboard", False),
            "has_ac": kwargs.get("has_ac", True),
            "is_available": True,
            "notes": kwargs.get("notes"),
            "created_at": now,
            "created_by": created_by,
        }
        
        await self.classrooms_collection.insert_one(classroom_doc)
        return classroom_doc
    
    async def get_classrooms(
        self,
        tenant_id: str,
        room_type: Optional[str] = None,
        available_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get physical classrooms"""
        query = {"tenant_id": tenant_id}
        
        if room_type:
            query["room_type"] = room_type
        if available_only:
            query["is_available"] = True
        
        classrooms = await self.classrooms_collection.find(
            query,
            {"_id": 0}
        ).sort("name", 1).to_list(1000)
        
        return classrooms
    
    async def update_classroom(
        self,
        classroom_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update a classroom"""
        now = datetime.now(timezone.utc).isoformat()
        
        protected = ["id", "tenant_id", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)
        
        updates["updated_at"] = now
        updates["updated_by"] = updated_by
        
        await self.classrooms_collection.update_one(
            {"id": classroom_id},
            {"$set": updates}
        )
        
        return await self.classrooms_collection.find_one(
            {"id": classroom_id},
            {"_id": 0}
        )
    
    # ============== SUBJECTS ==============
    
    async def seed_default_subjects(self):
        """Seed default subjects"""
        default_subjects = [
            # Core subjects
            {"name_ar": "اللغة العربية", "name_en": "Arabic Language", "code": "ARB", "category": "core", "default_periods": 6},
            {"name_ar": "الرياضيات", "name_en": "Mathematics", "code": "MTH", "category": "core", "default_periods": 5},
            {"name_ar": "العلوم", "name_en": "Science", "code": "SCI", "category": "core", "default_periods": 4},
            {"name_ar": "اللغة الإنجليزية", "name_en": "English Language", "code": "ENG", "category": "core", "default_periods": 4},
            {"name_ar": "الدراسات الإسلامية", "name_en": "Islamic Studies", "code": "ISL", "category": "core", "default_periods": 4},
            {"name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies", "code": "SOC", "category": "core", "default_periods": 3},
            
            # Elective subjects
            {"name_ar": "الحاسب الآلي", "name_en": "Computer Science", "code": "CMP", "category": "elective", "default_periods": 2},
            {"name_ar": "التربية الفنية", "name_en": "Art Education", "code": "ART", "category": "elective", "default_periods": 2},
            {"name_ar": "التربية البدنية", "name_en": "Physical Education", "code": "PHY", "category": "activity", "default_periods": 2},
            {"name_ar": "المهارات الحياتية", "name_en": "Life Skills", "code": "LFS", "category": "elective", "default_periods": 1},
            
            # Secondary specific
            {"name_ar": "الفيزياء", "name_en": "Physics", "code": "PHS", "category": "core", "default_periods": 4, "stages": ["SECONDARY"]},
            {"name_ar": "الكيمياء", "name_en": "Chemistry", "code": "CHM", "category": "core", "default_periods": 4, "stages": ["SECONDARY"]},
            {"name_ar": "الأحياء", "name_en": "Biology", "code": "BIO", "category": "core", "default_periods": 4, "stages": ["SECONDARY"]},
        ]
        
        count = 0
        for subject in default_subjects:
            existing = await self.subjects_collection.find_one({
                "code": subject["code"],
                "is_global": True
            })
            
            if not existing:
                subject["id"] = str(uuid.uuid4())
                subject["tenant_id"] = None
                subject["is_global"] = True
                subject["is_active"] = True
                subject["created_at"] = datetime.now(timezone.utc).isoformat()
                subject["created_by"] = "system"
                await self.subjects_collection.insert_one(subject)
                count += 1
        
        return count
    
    async def get_subjects(
        self,
        tenant_id: Optional[str] = None,
        category: Optional[str] = None,
        stage_code: Optional[str] = None,
        include_global: bool = True
    ) -> List[Dict[str, Any]]:
        """Get subjects"""
        query = {"is_active": True}
        
        if tenant_id:
            if include_global:
                query["$or"] = [
                    {"tenant_id": tenant_id},
                    {"is_global": True}
                ]
            else:
                query["tenant_id"] = tenant_id
        else:
            query["is_global"] = True
        
        if category:
            query["category"] = category
        
        subjects = await self.subjects_collection.find(
            query,
            {"_id": 0}
        ).sort("name_ar", 1).to_list(1000)
        
        # Filter by stage if specified
        if stage_code:
            subjects = [
                s for s in subjects
                if not s.get("stages") or stage_code in s.get("stages", [])
            ]
        
        return subjects
    
    async def create_subject(
        self,
        name_ar: str,
        code: str,
        created_by: str,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new subject"""
        subject_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        subject_doc = {
            "id": subject_id,
            "tenant_id": tenant_id,
            "name_ar": name_ar,
            "name_en": kwargs.get("name_en"),
            "code": code,
            "category": kwargs.get("category", "core"),
            "default_periods": kwargs.get("default_periods", 4),
            "stages": kwargs.get("stages", []),
            "is_global": tenant_id is None,
            "is_active": True,
            "created_at": now,
            "created_by": created_by,
        }
        
        await self.subjects_collection.insert_one(subject_doc)
        return subject_doc
    
    # ============== ACADEMIC STRUCTURE SUMMARY ==============
    
    async def get_tenant_academic_structure(self, tenant_id: str) -> Dict[str, Any]:
        """Get complete academic structure for a tenant"""
        stages = await self.get_stages(tenant_id, include_global=True)
        grades = await self.get_grades(tenant_id)
        sections = await self.get_sections(tenant_id)
        classrooms = await self.get_classrooms(tenant_id)
        subjects = await self.get_subjects(tenant_id, include_global=True)
        
        # Build hierarchy
        structure = {
            "tenant_id": tenant_id,
            "stages": [],
            "total_grades": len(grades),
            "total_sections": len(sections),
            "total_classrooms": len(classrooms),
            "total_subjects": len(subjects),
        }
        
        for stage in stages:
            stage_grades = [g for g in grades if g.get("stage_code") == stage.get("code")]
            stage_sections = [s for s in sections if s.get("stage_code") == stage.get("code")]
            
            stage_data = {
                "id": stage.get("id"),
                "code": stage.get("code"),
                "name_ar": stage.get("name_ar"),
                "grades_count": len(stage_grades),
                "sections_count": len(stage_sections),
                "grades": []
            }
            
            for grade in stage_grades:
                grade_sections = [s for s in stage_sections if s.get("grade_id") == grade.get("id")]
                grade_data = {
                    "id": grade.get("id"),
                    "name_ar": grade.get("name_ar"),
                    "grade_number": grade.get("grade_number"),
                    "sections": grade_sections
                }
                stage_data["grades"].append(grade_data)
            
            structure["stages"].append(stage_data)
        
        return structure


# Export
__all__ = ["AcademicStructureEngine"]
