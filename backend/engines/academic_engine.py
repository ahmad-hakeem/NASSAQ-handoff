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

from sqlalchemy import select, or_, func

from pg_models import EducationalStage, PhysicalClassroom, Subject
from engines.sql_utils import (
    model_to_dict, models_to_dicts, dict_to_model, apply_updates,
    gd_find, gd_find_one, gd_insert, gd_update_one,
)


class AcademicStructureEngine:
    """
    Core Academic Structure Engine for NASSAQ
    Manages educational hierarchy and classroom structure
    """

    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    # ============== EDUCATIONAL STAGES ==============

    async def seed_default_stages(self):
        default_stages = [
            {
                "code": "KG",
                "name_ar": "رياض الأطفال",
                "name_en": "Kindergarten",
                "order": 1,
                "min_age": 3,
                "max_age": 6,
                "grades_count": 3,
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
            stmt = select(EducationalStage).where(
                EducationalStage.code == stage["code"]
            ).limit(1)
            result = await self.session.execute(stmt)
            existing = result.scalars().first()

            if not existing:
                obj = EducationalStage(
                    id=str(uuid.uuid4()),
                    code=stage["code"],
                    name_ar=stage["name_ar"],
                    name_en=stage["name_en"],
                    order=stage["order"],
                    is_active=True,
                )
                self.session.add(obj)
                await self.session.flush()
                count += 1

        return count

    async def get_stages(
        self,
        tenant_id: Optional[str] = None,
        include_global: bool = True
    ) -> List[Dict[str, Any]]:
        stmt = select(EducationalStage).where(
            EducationalStage.is_active == True
        ).order_by(EducationalStage.order.asc())
        result = await self.session.execute(stmt)
        return models_to_dicts(result.scalars().all())

    async def create_tenant_stage(
        self,
        tenant_id: str,
        code: str,
        name_ar: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        stage_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        obj = EducationalStage(
            id=stage_id,
            code=code,
            name_ar=name_ar,
            name_en=kwargs.get("name_en"),
            order=kwargs.get("order", 99),
            is_active=True,
        )
        self.session.add(obj)
        await self.session.flush()

        result = model_to_dict(obj)
        result["tenant_id"] = tenant_id
        result["min_age"] = kwargs.get("min_age")
        result["max_age"] = kwargs.get("max_age")
        result["grades_count"] = kwargs.get("grades_count", 1)
        result["is_mandatory"] = kwargs.get("is_mandatory", False)
        result["is_global"] = False
        result["created_at"] = now
        result["created_by"] = created_by
        return result

    # ============== GRADES ==============

    async def seed_default_grades(self, tenant_id: str):
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
                existing = await gd_find_one(self.session, "grades", {
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

                    await gd_insert(self.session, "grades", grade_doc)
                    count += 1

        return count

    async def get_grades(
        self,
        tenant_id: str,
        stage_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        filters = {"tenant_id": tenant_id, "is_active": True}
        if stage_code:
            filters["stage_code"] = stage_code
        return await gd_find(
            self.session, "grades", filters,
            order_by="display_order", desc_order=False, limit=100
        )

    async def create_grade(
        self,
        tenant_id: str,
        stage_code: str,
        grade_number: int,
        name_ar: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        grade_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        stmt = select(EducationalStage).where(
            EducationalStage.code == stage_code
        ).limit(1)
        result = await self.session.execute(stmt)
        stage = result.scalars().first()

        if not stage:
            raise ValueError("المرحلة غير موجودة")

        stage_dict = model_to_dict(stage)

        grade_doc = {
            "id": grade_id,
            "tenant_id": tenant_id,
            "stage_id": stage_dict.get("id"),
            "stage_code": stage_code,
            "stage_name_ar": stage_dict.get("name_ar"),
            "grade_number": grade_number,
            "name_ar": name_ar,
            "name_en": kwargs.get("name_en"),
            "full_name_ar": f"{name_ar} - {stage_dict.get('name_ar')}",
            "display_order": kwargs.get("display_order", stage_dict.get("order", 1) * 10 + grade_number),
            "is_active": True,
            "created_at": now,
            "created_by": created_by,
        }

        await gd_insert(self.session, "grades", grade_doc)
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
        section_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        grade = await gd_find_one(self.session, "grades", {
            "id": grade_id, "tenant_id": tenant_id
        })
        if not grade:
            raise ValueError("الصف غير موجود")

        section_doc = {
            "id": section_id,
            "tenant_id": tenant_id,
            "grade_id": grade_id,
            "grade_name_ar": grade.get("name_ar"),
            "stage_code": grade.get("stage_code"),
            "name": name,
            "full_name_ar": f"{grade.get('full_name_ar')} ({name})",
            # Legacy section metadata only; section rosters are open-ended.
            "capacity": kwargs.get("capacity"),
            "current_students": 0,
            "homeroom_teacher_id": kwargs.get("homeroom_teacher_id"),
            "classroom_id": kwargs.get("classroom_id"),
            "is_active": True,
            "academic_year": kwargs.get("academic_year", "1446-1447"),
            "created_at": now,
            "created_by": created_by,
        }

        await gd_insert(self.session, "sections", section_doc)
        return section_doc

    async def get_sections(
        self,
        tenant_id: str,
        grade_id: Optional[str] = None,
        stage_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        filters = {"tenant_id": tenant_id, "is_active": True}
        if grade_id:
            filters["grade_id"] = grade_id
        if stage_code:
            filters["stage_code"] = stage_code
        return await gd_find(
            self.session, "sections", filters,
            order_by="full_name_ar", desc_order=False, limit=1000
        )

    async def update_section(
        self,
        section_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()

        protected = ["id", "tenant_id", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)

        updates["updated_at"] = now
        updates["updated_by"] = updated_by

        await gd_update_one(self.session, "sections", {"id": section_id}, updates)
        return await gd_find_one(self.session, "sections", {"id": section_id})

    async def assign_homeroom_teacher(
        self,
        section_id: str,
        teacher_id: str,
        assigned_by: str
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        await gd_update_one(self.session, "sections", {"id": section_id}, {
            "homeroom_teacher_id": teacher_id,
            "homeroom_assigned_at": now,
            "homeroom_assigned_by": assigned_by
        })
        return await gd_find_one(self.session, "sections", {"id": section_id})

    # ============== PHYSICAL CLASSROOMS ==============

    async def create_classroom(
        self,
        tenant_id: str,
        name: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        classroom_id = str(uuid.uuid4())

        obj = PhysicalClassroom(
            id=classroom_id,
            tenant_id=tenant_id,
            name=name,
            building=kwargs.get("building"),
            floor=kwargs.get("floor"),
            room_type=kwargs.get("room_type", "classroom"),
            capacity=kwargs.get("capacity", 30),
            has_projector=kwargs.get("has_projector", False),
            has_smartboard=kwargs.get("has_smartboard", False),
            has_ac=kwargs.get("has_ac", True),
            is_available=True,
            notes=kwargs.get("notes"),
        )
        self.session.add(obj)
        await self.session.flush()

        result = model_to_dict(obj)
        result["created_by"] = created_by
        return result

    async def get_classrooms(
        self,
        tenant_id: str,
        room_type: Optional[str] = None,
        available_only: bool = False
    ) -> List[Dict[str, Any]]:
        stmt = select(PhysicalClassroom).where(
            PhysicalClassroom.tenant_id == tenant_id
        )
        if room_type:
            stmt = stmt.where(PhysicalClassroom.room_type == room_type)
        if available_only:
            stmt = stmt.where(PhysicalClassroom.is_available == True)
        stmt = stmt.order_by(PhysicalClassroom.name.asc())
        result = await self.session.execute(stmt)
        return models_to_dicts(result.scalars().all())

    async def update_classroom(
        self,
        classroom_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        protected = ["id", "tenant_id", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)

        stmt = select(PhysicalClassroom).where(
            PhysicalClassroom.id == classroom_id
        ).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            return None

        apply_updates(obj, updates)
        await self.session.flush()
        return model_to_dict(obj)

    # ============== SUBJECTS ==============

    async def seed_default_subjects(self):
        default_subjects = [
            {"name_ar": "اللغة العربية", "name_en": "Arabic Language", "code": "ARB", "category": "core", "default_periods": 6},
            {"name_ar": "الرياضيات", "name_en": "Mathematics", "code": "MTH", "category": "core", "default_periods": 5},
            {"name_ar": "العلوم", "name_en": "Science", "code": "SCI", "category": "core", "default_periods": 4},
            {"name_ar": "اللغة الإنجليزية", "name_en": "English Language", "code": "ENG", "category": "core", "default_periods": 4},
            {"name_ar": "الدراسات الإسلامية", "name_en": "Islamic Studies", "code": "ISL", "category": "core", "default_periods": 4},
            {"name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies", "code": "SOC", "category": "core", "default_periods": 3},
            {"name_ar": "الحاسب الآلي", "name_en": "Computer Science", "code": "CMP", "category": "elective", "default_periods": 2},
            {"name_ar": "التربية الفنية", "name_en": "Art Education", "code": "ART", "category": "elective", "default_periods": 2},
            {"name_ar": "التربية البدنية", "name_en": "Physical Education", "code": "PHY", "category": "activity", "default_periods": 2},
            {"name_ar": "المهارات الحياتية", "name_en": "Life Skills", "code": "LFS", "category": "elective", "default_periods": 1},
            {"name_ar": "الفيزياء", "name_en": "Physics", "code": "PHS", "category": "core", "default_periods": 4, "stages": ["SECONDARY"]},
            {"name_ar": "الكيمياء", "name_en": "Chemistry", "code": "CHM", "category": "core", "default_periods": 4, "stages": ["SECONDARY"]},
            {"name_ar": "الأحياء", "name_en": "Biology", "code": "BIO", "category": "core", "default_periods": 4, "stages": ["SECONDARY"]},
        ]

        count = 0
        for subj in default_subjects:
            stmt = select(Subject).where(
                Subject.code == subj["code"],
                Subject.is_global == True
            ).limit(1)
            result = await self.session.execute(stmt)
            if not result.scalars().first():
                obj = Subject(
                    id=str(uuid.uuid4()),
                    name=subj["name_ar"],
                    name_ar=subj["name_ar"],
                    name_en=subj["name_en"],
                    code=subj["code"],
                    school_id=None,
                    category=subj.get("category", "core"),
                    default_periods_per_week=subj.get("default_periods", 4),
                    applicable_stages=subj.get("stages", []),
                    is_global=True,
                    is_active=True,
                )
                self.session.add(obj)
                await self.session.flush()
                count += 1

        return count

    async def get_subjects(
        self,
        tenant_id: Optional[str] = None,
        category: Optional[str] = None,
        stage_code: Optional[str] = None,
        include_global: bool = True
    ) -> List[Dict[str, Any]]:
        stmt = select(Subject).where(Subject.is_active == True)

        if tenant_id:
            if include_global:
                stmt = stmt.where(or_(
                    Subject.school_id == tenant_id,
                    Subject.is_global == True
                ))
            else:
                stmt = stmt.where(Subject.school_id == tenant_id)
        else:
            stmt = stmt.where(Subject.is_global == True)

        if category:
            stmt = stmt.where(Subject.category == category)

        stmt = stmt.order_by(Subject.name_ar.asc())
        result = await self.session.execute(stmt)
        subjects = models_to_dicts(result.scalars().all())

        if stage_code:
            subjects = [
                s for s in subjects
                if not s.get("applicable_stages") or stage_code in s.get("applicable_stages", [])
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
        subject_id = str(uuid.uuid4())

        obj = Subject(
            id=subject_id,
            name=name_ar,
            name_ar=name_ar,
            name_en=kwargs.get("name_en"),
            code=code,
            school_id=tenant_id,
            category=kwargs.get("category", "core"),
            default_periods_per_week=kwargs.get("default_periods", 4),
            applicable_stages=kwargs.get("stages", []),
            is_global=tenant_id is None,
            is_active=True,
        )
        self.session.add(obj)
        await self.session.flush()

        result = model_to_dict(obj)
        result["created_by"] = created_by
        return result

    # ============== ACADEMIC STRUCTURE SUMMARY ==============

    async def get_tenant_academic_structure(self, tenant_id: str) -> Dict[str, Any]:
        stages = await self.get_stages(tenant_id, include_global=True)
        grades = await self.get_grades(tenant_id)
        sections = await self.get_sections(tenant_id)
        classrooms = await self.get_classrooms(tenant_id)
        subjects = await self.get_subjects(tenant_id, include_global=True)

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


__all__ = ["AcademicStructureEngine"]
