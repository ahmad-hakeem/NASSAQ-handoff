"""
Teacher Management Engine - محرك إدارة المعلمين
Handles teacher creation and management for school principals
"""
import logging
from datetime import datetime, timezone

from typing import Optional, Dict, Any, List
import secrets
import string
import qrcode
import io
import base64
from pydantic import BaseModel, Field, EmailStr, model_validator
from enum import Enum

from sqlalchemy import select, func, or_

from pg_models import Teacher, User, School, Subject, LookupOption
from engines.sql_utils import (
    model_to_dict, models_to_dicts, dict_to_model, apply_updates,
    gd_find, gd_find_one, gd_insert, gd_count,
)
from src.common.utils.date_only import resolve_optional_birth_dates

logger = logging.getLogger(__name__)

# ==================== Enums ====================

class Gender(str, Enum):
    male = "male"
    female = "female"

class TeacherRank(str, Enum):
    teacher = "teacher"
    senior_teacher = "senior_teacher"
    expert = "expert"
    department_head = "department_head"
    assistant = "assistant"
    advanced = "advanced"
    practitioner = "practitioner"

class ContractType(str, Enum):
    permanent = "permanent"
    contract = "contract"
    part_time = "part_time"

# ==================== Pydantic Models ====================

class TeacherBasicInfo(BaseModel):
    full_name_ar: str = Field(..., min_length=3, max_length=100)
    full_name_en: Optional[str] = Field(None, max_length=100)
    national_id: str = Field(..., min_length=10, max_length=10)
    date_of_birth: Optional[str] = None
    birth_date_hijri: Optional[str] = None
    gender: Gender
    nationality: str = Field(default="SA")
    phone: str = Field(...)
    email: EmailStr

    @model_validator(mode="after")
    def validate_birth_dates(self):
        self.date_of_birth, self.birth_date_hijri = resolve_optional_birth_dates(
            self.date_of_birth, self.birth_date_hijri
        )
        return self

class TeacherQualifications(BaseModel):
    academic_degree: str
    specialization: Optional[str] = None
    university: Optional[str] = None
    graduation_year: Optional[int] = None
    years_of_experience: int = Field(ge=0)
    teacher_rank: TeacherRank
    certifications: Optional[List[str]] = None

class TeacherSubjectsAssignment(BaseModel):
    subject_ids: List[str]
    grade_ids: List[str]
    primary_subject_id: str
    max_periods_per_week: int = Field(default=24, ge=1, le=30)

class TeacherSchedulePreferences(BaseModel):
    contract_type: ContractType
    available_days: List[str] = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    preferred_periods: Optional[List[int]] = None
    notes: Optional[str] = None

class CreateTeacherRequest(BaseModel):
    basic_info: TeacherBasicInfo
    qualifications: TeacherQualifications
    subjects: TeacherSubjectsAssignment
    schedule: Optional[TeacherSchedulePreferences] = None

# ==================== Engine Class ====================

class TeacherManagementEngine:

    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    # ==================== ID Generation ====================

    async def _generate_teacher_id(self, tenant_id: str) -> str:
        try:
            stmt = select(School).where(School.id == tenant_id).limit(1)
            result = await self.session.execute(stmt)
            school = result.scalars().first()

            school_code = "SCH"
            if school:
                school_name = school.name or "SCH"
                school_code = ''.join(c for c in school_name[:3] if c.isalnum()).upper() or "SCH"

            year = datetime.now().strftime("%y")
            prefix = f"TCH-{school_code}-{year}-"

            stmt = select(func.count(Teacher.id)).where(Teacher.school_id == tenant_id)
            result = await self.session.execute(stmt)
            count = result.scalar() or 0

            seq_num = str(count + 1).zfill(4)
            return f"{prefix}{seq_num}"
        except Exception as e:
            logger.error(f"Error generating teacher ID: {e}")
            timestamp = datetime.now().strftime("%y%m%d%H%M")
            return f"TCH-{timestamp}-{secrets.token_hex(2).upper()}"

    def _generate_qr_code(self, data: str) -> str:
        try:
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            return ""

    def _generate_temp_password(self, length: int = 12) -> str:
        chars = string.ascii_letters + string.digits + "!@#$%"
        return ''.join(secrets.choice(chars) for _ in range(length))

    # ==================== Validation ====================

    async def validate_national_id(self, national_id: str, tenant_id: str) -> Dict[str, Any]:
        stmt = select(Teacher).where(
            Teacher.national_id == national_id,
            Teacher.school_id == tenant_id,
            Teacher.is_active == True
        ).limit(1)
        result = await self.session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            return {
                "valid": False,
                "message": "رقم الهوية مسجل مسبقاً لمعلم آخر",
                "message_en": "National ID already registered for another teacher",
                "existing_id": existing.id
            }
        return {"valid": True}

    async def validate_email(self, email: str, tenant_id: str) -> Dict[str, Any]:
        stmt = select(User).where(User.email == email, User.is_active == True).limit(1)
        result = await self.session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            return {
                "valid": False,
                "message": "البريد الإلكتروني مسجل مسبقاً",
                "message_en": "Email already registered"
            }
        return {"valid": True}

    # ==================== CRUD Operations ====================

    async def create_teacher(
        self,
        request: CreateTeacherRequest,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        try:
            validation = await self.validate_national_id(request.basic_info.national_id, tenant_id)
            if not validation["valid"]:
                return {"success": False, "error": validation["message"], "error_en": validation["message_en"]}

            email_validation = await self.validate_email(request.basic_info.email, tenant_id)
            if not email_validation["valid"]:
                return {"success": False, "error": email_validation["message"], "error_en": email_validation["message_en"]}

            teacher_id = await self._generate_teacher_id(tenant_id)
            qr_code = self._generate_qr_code(teacher_id)

            now = datetime.now(timezone.utc)

            obj = Teacher(
                id=str(teacher_id),
                full_name=request.basic_info.full_name_ar,
                full_name_en=request.basic_info.full_name_en,
                email=request.basic_info.email,
                phone=request.basic_info.phone,
                school_id=tenant_id,
                specialization=request.qualifications.specialization,
                rank=request.qualifications.teacher_rank.value,
                qualification=request.qualifications.academic_degree,
                years_of_experience=request.qualifications.years_of_experience,
                gender=request.basic_info.gender.value,
                national_id=request.basic_info.national_id,
                date_of_birth=request.basic_info.date_of_birth,
                weekly_periods=request.subjects.max_periods_per_week,
                is_active=True,
            )
            self.session.add(obj)
            await self.session.flush()

            teacher_doc = {
                "teacher_id": teacher_id,
                "tenant_id": tenant_id,
                "qr_code": qr_code,
                "full_name_ar": request.basic_info.full_name_ar,
                "full_name_en": request.basic_info.full_name_en,
                "national_id": request.basic_info.national_id,
                "date_of_birth": request.basic_info.date_of_birth,
                "gender": request.basic_info.gender.value,
                "nationality": request.basic_info.nationality,
                "phone": request.basic_info.phone,
                "email": request.basic_info.email,
                "academic_degree": request.qualifications.academic_degree,
                "specialization": request.qualifications.specialization,
                "university": request.qualifications.university,
                "graduation_year": request.qualifications.graduation_year,
                "years_of_experience": request.qualifications.years_of_experience,
                "teacher_rank": request.qualifications.teacher_rank.value,
                "certifications": request.qualifications.certifications or [],
                "subject_ids": request.subjects.subject_ids,
                "grade_ids": request.subjects.grade_ids,
                "primary_subject_id": request.subjects.primary_subject_id,
                "max_periods_per_week": request.subjects.max_periods_per_week,
                "contract_type": request.schedule.contract_type.value if request.schedule else "permanent",
                "available_days": request.schedule.available_days if request.schedule else ["sunday", "monday", "tuesday", "wednesday", "thursday"],
                "preferred_periods": request.schedule.preferred_periods if request.schedule else None,
                "schedule_notes": request.schedule.notes if request.schedule else None,
                "status": "active",
                "is_deleted": False,
                "hire_date": now.isoformat(),
                "created_at": now.isoformat(),
                "created_by": created_by,
                "updated_at": now.isoformat(),
            }

            user_result = await self._create_teacher_user_account(teacher_doc, tenant_id, created_by)

            return {
                "success": True,
                "teacher_id": teacher_id,
                "date_of_birth": request.basic_info.date_of_birth,
                "birth_date_hijri": request.basic_info.birth_date_hijri,
                "qr_code": qr_code,
                "user_account": user_result,
                "message": "تم إضافة المعلم بنجاح",
                "message_en": "Teacher added successfully"
            }

        except Exception as e:
            logger.error(f"Error creating teacher: {e}", exc_info=True)
            return {
                "success": False,
                "error": "حدث خطأ أثناء إضافة المعلم",
                "message": "حدث خطأ أثناء إضافة المعلم",
                "message_en": "Error occurred while adding teacher"
            }

    async def _create_teacher_user_account(
        self,
        teacher_doc: Dict,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        try:
            temp_password = self._generate_temp_password()
            now = datetime.now(timezone.utc)

            username = teacher_doc["email"].split("@")[0]

            stmt = select(User).where(User.email == f"{username}@nassaq.teacher.local").limit(1)
            result = await self.session.execute(stmt)
            if result.scalars().first():
                username = f"{username}_{secrets.token_hex(2)}"

            import bcrypt
            password_hash = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            obj = User(
                id=str(secrets.token_hex(16)),
                email=teacher_doc["email"],
                password_hash=password_hash,
                full_name=teacher_doc["full_name_ar"],
                full_name_en=teacher_doc.get("full_name_en"),
                role="teacher",
                tenant_id=tenant_id,
                phone=teacher_doc["phone"],
                must_change_password=True,
                is_active=True,
            )
            self.session.add(obj)
            await self.session.flush()

            return {
                "username": username,
                "email": teacher_doc["email"],
                "temp_password": temp_password,
                "created": True
            }
        except Exception as e:
            logger.error(f"Error creating teacher user account: {e}")
            return {"created": False, "error": str(e)}

    # ==================== Query Operations ====================

    async def get_teacher(self, teacher_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        stmt = select(Teacher).where(
            Teacher.id == teacher_id,
            Teacher.school_id == tenant_id,
            Teacher.is_active == True
        ).limit(1)
        result = await self.session.execute(stmt)
        teacher = result.scalars().first()
        if not teacher:
            return None
        d = model_to_dict(teacher)
        d["teacher_id"] = d.get("id")
        d["tenant_id"] = d.get("school_id")
        return d

    async def list_teachers(
        self,
        tenant_id: str,
        subject_id: Optional[str] = None,
        grade_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        stmt = select(Teacher).where(
            Teacher.school_id == tenant_id,
            Teacher.is_active == True
        )

        if search:
            stmt = stmt.where(or_(
                Teacher.full_name.ilike(f"%{search}%"),
                Teacher.full_name_en.ilike(f"%{search}%"),
                Teacher.email.ilike(f"%{search}%"),
            ))

        count_stmt = select(func.count(Teacher.id)).where(
            Teacher.school_id == tenant_id,
            Teacher.is_active == True
        )
        if search:
            count_stmt = count_stmt.where(or_(
                Teacher.full_name.ilike(f"%{search}%"),
                Teacher.full_name_en.ilike(f"%{search}%"),
                Teacher.email.ilike(f"%{search}%"),
            ))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = stmt.order_by(Teacher.created_at.desc())
        if skip:
            stmt = stmt.offset(skip)
        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        teachers = []
        for t in result.scalars().all():
            d = model_to_dict(t)
            d["teacher_id"] = d.get("id")
            d["tenant_id"] = d.get("school_id")
            teachers.append(d)

        return {
            "teachers": teachers,
            "total": total,
            "skip": skip,
            "limit": limit
        }

    # ==================== Options/Lookups ====================

    async def get_subjects(self, tenant_id: str) -> List[Dict[str, Any]]:
        stmt = select(Subject).where(
            or_(Subject.school_id == tenant_id, Subject.is_global == True),
            Subject.is_active == True
        ).limit(100)
        result = await self.session.execute(stmt)
        subjects = models_to_dicts(result.scalars().all())
        # No fake-id fallback: real schools are seeded with the canonical
        # standard subject catalog at creation (and via the Alembic
        # backfill migration), so an empty result means the school
        # genuinely has no active subjects. The add-teacher wizard renders
        # its own "no subjects configured" empty state in that case, and
        # the Subjects tab under Timetable Settings lets admins add them.
        return subjects

    async def get_grades(self, tenant_id: str) -> List[Dict[str, Any]]:
        grades = await gd_find(self.session, "grades", {
            "tenant_id": tenant_id, "is_active": True
        }, limit=100)

        if not grades:
            grades = [
                {"id": "grade_1", "name_ar": "الصف الأول", "name_en": "Grade 1"},
                {"id": "grade_2", "name_ar": "الصف الثاني", "name_en": "Grade 2"},
                {"id": "grade_3", "name_ar": "الصف الثالث", "name_en": "Grade 3"},
                {"id": "grade_4", "name_ar": "الصف الرابع", "name_en": "Grade 4"},
                {"id": "grade_5", "name_ar": "الصف الخامس", "name_en": "Grade 5"},
                {"id": "grade_6", "name_ar": "الصف السادس", "name_en": "Grade 6"},
            ]
        return grades

    async def _lookup_options(self, category: str, limit: int = 20) -> List[Dict[str, Any]]:
        stmt = select(LookupOption).where(
            LookupOption.category == category,
            LookupOption.is_active == True
        ).limit(limit)
        result = await self.session.execute(stmt)
        return [
            {"code": r.key, "name_ar": r.value_ar, "name_en": r.value_en}
            for r in result.scalars().all()
        ]

    async def get_academic_degrees(self) -> List[Dict[str, str]]:
        rows = await self._lookup_options("academic_degree")
        if rows:
            return rows
        return [
            {"code": "diploma", "name_ar": "دبلوم", "name_en": "Diploma"},
            {"code": "bachelor", "name_ar": "بكالوريوس", "name_en": "Bachelor's"},
            {"code": "master", "name_ar": "ماجستير", "name_en": "Master's"},
            {"code": "doctorate", "name_ar": "دكتوراه", "name_en": "Doctorate"},
        ]

    async def get_teacher_ranks(self) -> List[Dict[str, str]]:
        rows = await self._lookup_options("teacher_rank")
        if rows:
            return rows
        return [
            {"code": "teacher", "name_ar": "معلم", "name_en": "Teacher"},
            {"code": "senior_teacher", "name_ar": "معلم أول", "name_en": "Senior Teacher"},
            {"code": "expert", "name_ar": "معلم خبير", "name_en": "Expert Teacher"},
            {"code": "department_head", "name_ar": "رئيس قسم", "name_en": "Department Head"},
        ]

    async def get_contract_types(self) -> List[Dict[str, str]]:
        rows = await self._lookup_options("contract_type")
        if rows:
            return rows
        return [
            {"code": "permanent", "name_ar": "دائم", "name_en": "Permanent"},
            {"code": "contract", "name_ar": "متعاقد", "name_en": "Contract"},
            {"code": "part_time", "name_ar": "دوام جزئي", "name_en": "Part-time"},
        ]

    async def get_nationalities(self) -> List[Dict[str, str]]:
        rows = await self._lookup_options("nationality", limit=100)
        if rows:
            return rows
        return [
            {"code": "SA", "name_ar": "سعودي", "name_en": "Saudi"},
            {"code": "EG", "name_ar": "مصري", "name_en": "Egyptian"},
            {"code": "JO", "name_ar": "أردني", "name_en": "Jordanian"},
            {"code": "SY", "name_ar": "سوري", "name_en": "Syrian"},
            {"code": "PS", "name_ar": "فلسطيني", "name_en": "Palestinian"},
            {"code": "SD", "name_ar": "سوداني", "name_en": "Sudanese"},
            {"code": "YE", "name_ar": "يمني", "name_en": "Yemeni"},
            {"code": "TN", "name_ar": "تونسي", "name_en": "Tunisian"},
            {"code": "MA", "name_ar": "مغربي", "name_en": "Moroccan"},
            {"code": "PK", "name_ar": "باكستاني", "name_en": "Pakistani"},
            {"code": "IN", "name_ar": "هندي", "name_en": "Indian"},
            {"code": "OTHER", "name_ar": "أخرى", "name_en": "Other"},
        ]
