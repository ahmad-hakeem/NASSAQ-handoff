"""
Class Management Engine - محرك إدارة الفصول
Handles class/section creation and management
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import secrets
from pydantic import BaseModel, Field
from enum import Enum

from sqlalchemy import select, and_, or_, func, desc as sa_desc

from pg_models import Class, Student, Teacher, GradeLevel
from engines.sql_utils import model_to_dict, models_to_dicts, dict_to_model, apply_updates

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

    @property
    def session(self):
        return self.db.session

    async def _generate_class_id(self, tenant_id: str, grade_id: str) -> str:
        """Generate unique class ID"""
        year = datetime.now().strftime("%y")
        prefix = f"CLS-{grade_id[:3].upper()}-{year}-"
        stmt = select(func.count(Class.id)).where(
            and_(Class.school_id == tenant_id, Class.id.like(f"{prefix}%"))
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
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

            obj = Class(
                id=class_id,
                name=request.name_ar,
                name_en=request.name_en,
                school_id=tenant_id,
                grade_id=request.grade_id,
                capacity=request.capacity,
                current_students=len(request.student_ids or []),
                homeroom_teacher_id=request.homeroom_teacher_id,
                classroom_id=request.room_number,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            self.session.add(obj)
            await self.session.flush()

            if request.student_ids:
                stmt = select(Student).where(
                    and_(Student.id.in_(request.student_ids), Student.school_id == tenant_id)
                )
                result = await self.session.execute(stmt)
                for s in result.scalars().all():
                    s.class_id = class_id
                    s.updated_at = now
                await self.session.flush()

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
        stmt = select(Class).where(
            and_(Class.id == class_id, Class.school_id == tenant_id, Class.is_active == True)
        ).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if not row:
            return None
        d = model_to_dict(row)
        d.pop("_id", None)
        d["class_id"] = d["id"]
        d["tenant_id"] = d.get("school_id", "")
        d["name_ar"] = d.get("name", "")
        # Include live student count so the detail view stays consistent with
        # the cards in the list.
        count_stmt = select(func.count(Student.id)).where(
            and_(
                Student.school_id == tenant_id,
                Student.is_active == True,
                Student.class_id == class_id,
            )
        )
        d["student_count"] = int((await self.session.execute(count_stmt)).scalar() or 0)
        return d

    async def list_classes(
        self,
        tenant_id: str,
        grade_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        allowed_class_ids: Optional[set] = None,
    ) -> Dict[str, Any]:
        """List classes with filters.

        ``allowed_class_ids`` narrows the result to a caller-authorized set
        (Task #1089): regular school teachers may only see their OWN
        assigned classes, so callers pass the canonical
        ``get_teacher_allowed_class_ids`` set. ``None`` = no narrowing
        (default, tenant-scoped only). An EMPTY set means the caller owns
        no classes and MUST get an empty page — never the whole tenant.
        """
        conditions = [Class.school_id == tenant_id, Class.is_active == True]

        if allowed_class_ids is not None:
            conditions.append(Class.id.in_(list(allowed_class_ids)))

        if grade_id:
            conditions.append(Class.grade_id == grade_id)
        if status == "inactive":
            conditions[-1] = Class.is_active == False
        if search:
            conditions.append(
                or_(
                    Class.name.ilike(f"%{search}%"),
                    Class.name_en.ilike(f"%{search}%"),
                    Class.id.ilike(f"%{search}%"),
                )
            )

        count_stmt = select(func.count(Class.id)).where(and_(*conditions))
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Class)
            .where(and_(*conditions))
            .order_by(sa_desc(Class.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        # Aggregate live student counts per class for the current page so the
        # UI cards display "{student_count} / {capacity} طلاب" and the fill
        # progress instead of always rendering 0. Counts only active students
        # actually assigned to a class within this tenant.
        class_ids = [r.id for r in rows]
        counts_map: Dict[str, int] = {}
        if class_ids:
            count_stmt = (
                select(Student.class_id, func.count(Student.id))
                .where(
                    and_(
                        Student.school_id == tenant_id,
                        Student.is_active == True,
                        Student.class_id.in_(class_ids),
                    )
                )
                .group_by(Student.class_id)
            )
            count_rows = await self.session.execute(count_stmt)
            counts_map = {cid: int(c or 0) for cid, c in count_rows.all() if cid}

        classes = []
        for row in rows:
            d = model_to_dict(row)
            d.pop("_id", None)
            d["class_id"] = d["id"]
            d["tenant_id"] = d.get("school_id", "")
            d["name_ar"] = d.get("name", "")
            d["student_count"] = counts_map.get(row.id, 0)
            classes.append(d)

        return {"classes": classes, "total": total}

    async def get_grades(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available grades"""
        stmt = select(GradeLevel).where(
            and_(
                or_(GradeLevel.school_id == tenant_id, GradeLevel.school_id.is_(None)),
                GradeLevel.is_active == True,
            )
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        if rows:
            grades = []
            for g in rows:
                grades.append({
                    "id": g.id,
                    "grade_level": g.code or g.id,
                    "name_ar": g.name_ar or "",
                    "name_en": g.name_en or "",
                })
            return grades

        stmt2 = select(Student.grade).where(
            and_(Student.school_id == tenant_id, Student.is_active == True, Student.grade.isnot(None))
        ).distinct()
        result2 = await self.session.execute(stmt2)
        grade_levels = sorted(
            [row[0] for row in result2.all() if row[0]],
            key=lambda x: int(x) if x.isdigit() else 999
        )
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
        stmt = select(Teacher).where(
            and_(Teacher.school_id == tenant_id, Teacher.is_active == True)
        ).limit(200)
        result = await self.session.execute(stmt)
        teachers = []
        for t in result.scalars().all():
            teachers.append({
                "teacher_id": t.id,
                "full_name_ar": t.full_name or "",
                "full_name_en": t.full_name_en or "",
            })
        return teachers

    async def get_students(self, tenant_id: str, grade_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available students for class assignment"""
        conditions = [Student.school_id == tenant_id, Student.is_active == True]
        if grade_id:
            grade_level = grade_id.replace("grade_", "") if grade_id.startswith("grade_") else grade_id
            conditions.append(Student.grade == grade_level)

        stmt = select(Student).where(and_(*conditions)).limit(500)
        result = await self.session.execute(stmt)
        students = []
        for s in result.scalars().all():
            students.append({
                "student_id": s.id,
                "full_name_ar": s.full_name or "",
                "full_name_en": s.full_name_en or "",
                "grade_id": f"grade_{s.grade}" if s.grade else "",
            })
        return students

    async def get_class_types(self) -> List[Dict[str, str]]:
        """Get class types"""
        return [
            {"code": "regular", "name_ar": "عادي", "name_en": "Regular"},
            {"code": "advanced", "name_ar": "متقدم", "name_en": "Advanced"},
            {"code": "special_needs", "name_ar": "احتياجات خاصة", "name_en": "Special Needs"},
        ]
