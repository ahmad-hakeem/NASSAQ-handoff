"""
Student Management Engine - محرك إدارة الطلاب
Handles student creation, parent linking, and related operations
"""
import logging
from datetime import datetime, timezone

from typing import Optional, Dict, Any, List
import re
import secrets
import string
import qrcode
import io
import base64
import uuid
from pydantic import BaseModel, Field, EmailStr
from enum import Enum

from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError

from engines.sql_utils import (
    model_to_dict, models_to_dicts, dict_to_model, apply_updates,
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_count, gd_delete_one,
)

logger = logging.getLogger(__name__)


class Gender(str, Enum):
    male = "male"
    female = "female"


class BloodType(str, Enum):
    A_positive = "A+"
    A_negative = "A-"
    B_positive = "B+"
    B_negative = "B-"
    AB_positive = "AB+"
    AB_negative = "AB-"
    O_positive = "O+"
    O_negative = "O-"


class ParentRelation(str, Enum):
    father = "father"
    mother = "mother"
    guardian = "guardian"
    other = "other"


class StudentBasicInfo(BaseModel):
    full_name_ar: str = Field(..., min_length=3, max_length=100)
    full_name_en: Optional[str] = Field(None, max_length=100)
    national_id: str = Field(..., min_length=10, max_length=10, pattern=r'^\d{10}$')
    date_of_birth: str = Field(...)
    gender: Gender
    nationality: str = Field(default="SA")
    grade_id: str = Field(...)
    section_id: str = Field(...)


class ParentContactInfo(BaseModel):
    parent_name_ar: str = Field(..., min_length=3, max_length=100)
    parent_name_en: Optional[str] = Field(None, max_length=100)
    parent_national_id: Optional[str] = Field(None, min_length=10, max_length=10, pattern=r'^\d{10}$')
    parent_phone: str = Field(..., pattern=r'^[\d+\-\s]{9,15}$')
    parent_email: Optional[EmailStr] = None
    parent_relation: ParentRelation
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    address: Optional[str] = None


class StudentHealthInfo(BaseModel):
    blood_type: Optional[BloodType] = None
    has_chronic_conditions: bool = False
    chronic_conditions: Optional[str] = None
    has_allergies: bool = False
    allergies: Optional[str] = None
    has_disabilities: bool = False
    disabilities: Optional[str] = None
    current_medications: Optional[str] = None
    requires_special_care: bool = False
    special_care_notes: Optional[str] = None
    emergency_medical_notes: Optional[str] = None


class CreateStudentRequest(BaseModel):
    basic_info: StudentBasicInfo
    parent_info: ParentContactInfo
    health_info: Optional[StudentHealthInfo] = None
    save_as_draft: bool = False


class StudentDraft(BaseModel):
    basic_info: Optional[Dict[str, Any]] = None
    parent_info: Optional[Dict[str, Any]] = None
    health_info: Optional[Dict[str, Any]] = None
    current_step: int = 1


class StudentManagementEngine:
    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    async def _generate_student_id(self, tenant_id: str) -> str:
        from pg_models import School, Student
        try:
            stmt = select(School).where(School.id == tenant_id).limit(1)
            result = await self.session.execute(stmt)
            school = result.scalars().first()

            school_code = "SCH"
            city_code = "CTY"

            if school:
                sd = model_to_dict(school)
                school_name = sd.get("name_ar", sd.get("name", "SCH"))
                school_code = ''.join(c for c in school_name[:3] if c.isalnum()).upper() or "SCH"
                city = sd.get("city", "CTY")
                city_code = ''.join(c for c in city[:3] if c.isalnum()).upper() or "CTY"

            year = datetime.now().strftime("%y")
            prefix = f"NSS-{school_code}-{city_code}-{year}-"

            stmt = select(func.count(Student.id)).where(
                Student.student_number.ilike(f"{prefix}%")
            )
            result = await self.session.execute(stmt)
            count = result.scalar() or 0

            # FIX (B9): Two concurrent student creations can both read the same
            # `count` value and produce identical student_numbers, breaking the
            # unique constraint. Probe for a free slot up to 20 times, then fall
            # back to a timestamp+random suffix that cannot collide.
            for offset in range(1, 21):
                candidate = f"{prefix}{str(count + offset).zfill(4)}"
                exists_stmt = select(Student.id).where(Student.student_number == candidate).limit(1)
                exists_result = await self.session.execute(exists_stmt)
                if exists_result.scalar() is None:
                    return candidate

            timestamp = datetime.now().strftime("%y%m%d%H%M%S")
            random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
            return f"{prefix}{timestamp}{random_suffix}"
        except Exception as e:
            logger.error(f"Error generating student ID: {e}")
            timestamp = datetime.now().strftime("%y%m%d%H%M")
            random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
            return f"NSS-STD-{timestamp}-{random_suffix}"

    async def _generate_parent_id(self, tenant_id: str) -> str:
        from pg_models import School, Parent
        try:
            stmt = select(School).where(School.id == tenant_id).limit(1)
            result = await self.session.execute(stmt)
            school = result.scalars().first()

            school_code = "SCH"
            city_code = "CTY"

            if school:
                sd = model_to_dict(school)
                school_name = sd.get("name_ar", sd.get("name", "SCH"))
                school_code = ''.join(c for c in school_name[:3] if c.isalnum()).upper() or "SCH"
                city = sd.get("city", "CTY")
                city_code = ''.join(c for c in city[:3] if c.isalnum()).upper() or "CTY"

            year = datetime.now().strftime("%y")
            prefix = f"NSS-{school_code}-{city_code}-{year}-P"

            stmt = select(func.count(Parent.id)).where(Parent.school_id == tenant_id)
            result = await self.session.execute(stmt)
            count = result.scalar() or 0

            seq_num = str(count + 1).zfill(4)
            return f"{prefix}{seq_num}"
        except Exception as e:
            logger.error(f"Error generating parent ID: {e}")
            timestamp = datetime.now().strftime("%y%m%d%H%M")
            random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
            return f"NSS-PRT-{timestamp}-{random_suffix}"

    def _generate_qr_code(self, data: str) -> str:
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
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
        password = ''.join(secrets.choice(chars) for _ in range(length))
        return password

    async def validate_national_id(self, national_id: str, tenant_id: str) -> Dict[str, Any]:
        from pg_models import Student
        stmt = select(Student).where(
            Student.national_id == national_id,
            Student.school_id == tenant_id,
            Student.is_active == True
        ).limit(1)
        result = await self.session.execute(stmt)
        existing_student = result.scalars().first()

        if existing_student:
            return {
                "valid": False,
                "message": "رقم الهوية مسجل مسبقاً لطالب آخر",
                "message_en": "National ID already registered for another student",
                "existing_type": "student",
                "existing_id": str(existing_student.student_number or "")
            }

        return {"valid": True}

    async def validate_parent_phone(self, phone: str, tenant_id: str) -> Dict[str, Any]:
        from pg_models import Parent
        stmt = select(Parent).where(
            Parent.phone == phone,
            Parent.school_id == tenant_id,
            Parent.is_active == True
        ).limit(1)
        result = await self.session.execute(stmt)
        existing_parent = result.scalars().first()

        if existing_parent:
            pd = model_to_dict(existing_parent)
            return {
                "exists": True,
                "parent_id": pd.get("id"),
                "parent_name_ar": pd.get("full_name"),
                "parent_name_en": pd.get("full_name_en"),
                "can_link": True,
                "message": "تم العثور على ولي الأمر، يمكن ربط الطالب به",
                "message_en": "Parent found, student can be linked"
            }

        return {"exists": False}

    async def create_student(
        self,
        request: CreateStudentRequest,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        from pg_models import Student
        try:
            validation = await self.validate_national_id(request.basic_info.national_id, tenant_id)
            if not validation["valid"]:
                return {"success": False, "error": validation["message"], "error_en": validation["message_en"]}

            parent_result = await self._create_or_link_parent(
                request.parent_info,
                tenant_id,
                created_by
            )

            now = datetime.now(timezone.utc)
            extra_data = {
                "nationality": request.basic_info.nationality,
                "health_info": request.health_info.dict() if request.health_info else None,
                "status": "active",
                "enrollment_date": now.isoformat(),
                "created_by": created_by,
                "updated_by": created_by,
            }

            # FIX (B9): Even with a probe in `_generate_student_id`, two concurrent
            # creations can race between probe and INSERT. Wrap the INSERT in a
            # retry loop on IntegrityError using a SAVEPOINT so a duplicate
            # `student_number` collision causes a regenerate-and-retry rather
            # than aborting the whole request transaction.
            student_id_formatted = None
            qr_code = None
            last_error = None
            for attempt in range(5):
                student_id_formatted = await self._generate_student_id(tenant_id)
                qr_code = self._generate_qr_code(student_id_formatted)

                student_obj = Student(
                    id=str(uuid.uuid4()),
                    full_name=request.basic_info.full_name_ar,
                    full_name_en=request.basic_info.full_name_en,
                    student_number=student_id_formatted,
                    national_id=request.basic_info.national_id,
                    date_of_birth=request.basic_info.date_of_birth,
                    gender=request.basic_info.gender.value,
                    qr_code=qr_code,
                    grade=request.basic_info.grade_id,
                    class_id=request.basic_info.section_id,
                    parent_id=parent_result.get("parent_id"),
                    school_id=tenant_id,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                if hasattr(student_obj, "data"):
                    student_obj.data = extra_data

                try:
                    async with self.session.begin_nested():
                        self.session.add(student_obj)
                        await self.session.flush()
                    break
                except IntegrityError as ie:
                    last_error = ie
                    logger.warning(
                        f"Student INSERT collided on attempt {attempt + 1} "
                        f"(student_number={student_id_formatted}); retrying."
                    )
                    continue
            else:
                raise last_error or RuntimeError("Failed to generate unique student_number after 5 attempts")

            user_result = await self._create_student_user_account(
                {"student_id": student_id_formatted, "full_name_ar": request.basic_info.full_name_ar, "full_name_en": request.basic_info.full_name_en},
                tenant_id,
                created_by
            )

            return {
                "success": True,
                "student_id": student_id_formatted,
                "qr_code": qr_code,
                "parent_id": parent_result.get("parent_id"),
                "is_new_parent": parent_result.get("is_new"),
                "user_account": user_result,
                "message": "تم إضافة الطالب بنجاح",
                "message_en": "Student added successfully"
            }

        except Exception as e:
            logger.error(f"Error creating student: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "حدث خطأ أثناء إضافة الطالب",
                "message_en": "Error occurred while adding student"
            }

    async def _create_or_link_parent(
        self,
        parent_info: ParentContactInfo,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        from pg_models import Parent
        existing = await self.validate_parent_phone(parent_info.parent_phone, tenant_id)

        if existing.get("exists"):
            return {
                "parent_id": existing["parent_id"],
                "is_new": False
            }

        parent_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        parent_obj = Parent(
            id=parent_id,
            full_name=parent_info.parent_name_ar,
            full_name_en=parent_info.parent_name_en,
            national_id=parent_info.parent_national_id,
            phone=parent_info.parent_phone,
            email=parent_info.parent_email,
            school_id=tenant_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        extra_data = {
            "relation": parent_info.parent_relation.value,
            "emergency_contact": parent_info.emergency_contact,
            "emergency_phone": parent_info.emergency_phone,
            "address": parent_info.address,
            "children": [],
            "status": "active",
            "created_by": created_by,
            "formatted_parent_id": await self._generate_parent_id(tenant_id),
        }
        if hasattr(parent_obj, "data"):
            parent_obj.data = extra_data

        self.session.add(parent_obj)
        await self.session.flush()

        await self._create_parent_user_account(
            {"parent_id": parent_id, "name_ar": parent_info.parent_name_ar, "name_en": parent_info.parent_name_en, "phone": parent_info.parent_phone, "email": parent_info.parent_email},
            tenant_id,
            created_by
        )

        return {
            "parent_id": parent_id,
            "is_new": True
        }

    async def _create_student_user_account(
        self,
        student_doc: Dict,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        from pg_models import User
        try:
            temp_password = self._generate_temp_password()
            now = datetime.now(timezone.utc)

            username = student_doc["student_id"].lower().replace("-", "")

            stmt = select(User).where(User.email == f"{username}@nassaq.student.local").limit(1)
            result = await self.session.execute(stmt)
            existing = result.scalars().first()
            if existing:
                username = f"{username}_{secrets.token_hex(2)}"

            import bcrypt
            hashed_pw = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            user_obj = User(
                id=str(uuid.uuid4()),
                email=f"{username}@nassaq.student.local",
                password_hash=hashed_pw,
                role="student",
                tenant_id=tenant_id,
                full_name=student_doc["full_name_ar"],
                full_name_en=student_doc.get("full_name_en"),
                is_active=True,
                created_at=now,
                updated_at=now,
            )

            extra = {
                "username": username,
                "linked_entity_id": student_doc["student_id"],
                "must_change_password": True,
                "created_by": created_by,
            }
            if hasattr(user_obj, "data"):
                user_obj.data = extra

            self.session.add(user_obj)
            await self.session.flush()

            return {
                "username": username,
                "temp_password": temp_password,
                "created": True
            }
        except Exception as e:
            logger.error(f"Error creating student user account: {e}")
            return {"created": False, "error": str(e)}

    async def _create_parent_user_account(
        self,
        parent_doc: Dict,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        from pg_models import User
        try:
            temp_password = self._generate_temp_password()
            now = datetime.now(timezone.utc)

            username = parent_doc["parent_id"].lower().replace("-", "")

            stmt = select(User).where(User.email == f"{username}@nassaq.parent.local").limit(1)
            result = await self.session.execute(stmt)
            existing = result.scalars().first()
            if existing:
                username = f"{username}_{secrets.token_hex(2)}"

            email = parent_doc.get("email") or f"{username}@nassaq.parent.local"

            import bcrypt
            hashed_pw = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            user_obj = User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=hashed_pw,
                role="parent",
                tenant_id=tenant_id,
                full_name=parent_doc["name_ar"],
                full_name_en=parent_doc.get("name_en"),
                phone=parent_doc.get("phone"),
                is_active=True,
                created_at=now,
                updated_at=now,
            )

            extra = {
                "username": username,
                "linked_entity_id": parent_doc["parent_id"],
                "must_change_password": True,
                "created_by": created_by,
            }
            if hasattr(user_obj, "data"):
                user_obj.data = extra

            self.session.add(user_obj)
            await self.session.flush()

            return {
                "username": username,
                "temp_password": temp_password,
                "created": True
            }
        except Exception as e:
            logger.error(f"Error creating parent user account: {e}")
            return {"created": False, "error": str(e)}

    async def save_draft(
        self,
        draft: StudentDraft,
        tenant_id: str,
        created_by: str,
        draft_id: Optional[str] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)

        draft_doc = {
            "tenant_id": tenant_id,
            "basic_info": draft.basic_info,
            "parent_info": draft.parent_info,
            "health_info": draft.health_info,
            "current_step": draft.current_step,
            "updated_at": now.isoformat(),
            "updated_by": created_by,
        }

        if draft_id:
            await gd_update_one(self.session, "student_drafts", {"id": draft_id, "tenant_id": tenant_id}, draft_doc)
            return {"draft_id": draft_id, "updated": True}
        else:
            draft_doc["created_at"] = now.isoformat()
            draft_doc["created_by"] = created_by
            new_id = await gd_insert(self.session, "student_drafts", {"id": str(uuid.uuid4()), **draft_doc})
            return {"draft_id": new_id, "created": True}

    async def get_draft(self, draft_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        return await gd_find_one(self.session, "student_drafts", {"id": draft_id, "tenant_id": tenant_id})

    async def list_drafts(self, tenant_id: str, created_by: Optional[str] = None) -> List[Dict[str, Any]]:
        filters = {"tenant_id": tenant_id}
        if created_by:
            filters["created_by"] = created_by
        return await gd_find(self.session, "student_drafts", filters, order_by="updated_at", desc_order=True, limit=50)

    async def delete_draft(self, draft_id: str, tenant_id: str) -> bool:
        count = await gd_delete_one(self.session, "student_drafts", {"id": draft_id, "tenant_id": tenant_id})
        return count > 0

    async def get_student(self, student_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        from pg_models import Student
        stmt = select(Student).where(
            Student.student_number == student_id,
            Student.school_id == tenant_id,
            Student.is_active == True
        ).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            stmt2 = select(Student).where(
                Student.id == student_id,
                Student.school_id == tenant_id,
                Student.is_active == True
            ).limit(1)
            result2 = await self.session.execute(stmt2)
            obj = result2.scalars().first()
        if obj:
            d = model_to_dict(obj)
            d["student_id"] = d.get("student_number")
            d["tenant_id"] = d.get("school_id")
            return d
        return None

    async def list_students(
        self,
        tenant_id: str,
        grade_id: Optional[str] = None,
        section_id: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        from pg_models import Student
        conditions = [Student.school_id == tenant_id, Student.is_active == True]

        if grade_id:
            conditions.append(Student.grade == grade_id)
        if section_id:
            conditions.append(Student.class_id == section_id)

        if search:
            search_pattern = f"%{search}%"
            conditions.append(
                or_(
                    Student.full_name.ilike(search_pattern),
                    Student.full_name_en.ilike(search_pattern),
                    Student.student_number.ilike(search_pattern),
                    Student.national_id.ilike(search_pattern),
                )
            )

        count_stmt = select(func.count(Student.id)).where(*conditions)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = select(Student).where(*conditions).order_by(Student.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        students = result.scalars().all()

        student_dicts = []
        for s in students:
            d = model_to_dict(s)
            d["student_id"] = d.get("student_number")
            d["tenant_id"] = d.get("school_id")
            student_dicts.append(d)

        return {
            "students": student_dicts,
            "total": total,
            "skip": skip,
            "limit": limit
        }

    async def get_grades(self, tenant_id: str) -> List[Dict[str, Any]]:
        grades = await gd_find(self.session, "grades", {"tenant_id": tenant_id})
        inactive = [g for g in grades if g.get("is_active") is False]
        active = [g for g in grades if g.get("is_active") is not False]

        if not active:
            active = [
                {"id": "grade_1", "name_ar": "الصف الأول", "name_en": "Grade 1", "level": 1},
                {"id": "grade_2", "name_ar": "الصف الثاني", "name_en": "Grade 2", "level": 2},
                {"id": "grade_3", "name_ar": "الصف الثالث", "name_en": "Grade 3", "level": 3},
                {"id": "grade_4", "name_ar": "الصف الرابع", "name_en": "Grade 4", "level": 4},
                {"id": "grade_5", "name_ar": "الصف الخامس", "name_en": "Grade 5", "level": 5},
                {"id": "grade_6", "name_ar": "الصف السادس", "name_en": "Grade 6", "level": 6},
            ]

        return active

    async def get_sections(self, tenant_id: str, grade_id: Optional[str] = None) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {"tenant_id": tenant_id}
        if grade_id:
            filters["grade_id"] = grade_id

        sections = await gd_find(self.session, "sections", filters)
        active = [s for s in sections if s.get("is_active") is not False]

        if not active:
            active = [
                {"id": "section_a", "name_ar": "أ", "name_en": "A", "capacity": 30},
                {"id": "section_b", "name_ar": "ب", "name_en": "B", "capacity": 30},
                {"id": "section_c", "name_ar": "ج", "name_en": "C", "capacity": 30},
            ]

        return active

    async def get_nationalities(self) -> List[Dict[str, str]]:
        return [
            {"code": "SA", "name_ar": "سعودي", "name_en": "Saudi"},
            {"code": "AE", "name_ar": "إماراتي", "name_en": "Emirati"},
            {"code": "KW", "name_ar": "كويتي", "name_en": "Kuwaiti"},
            {"code": "BH", "name_ar": "بحريني", "name_en": "Bahraini"},
            {"code": "OM", "name_ar": "عماني", "name_en": "Omani"},
            {"code": "QA", "name_ar": "قطري", "name_en": "Qatari"},
            {"code": "EG", "name_ar": "مصري", "name_en": "Egyptian"},
            {"code": "JO", "name_ar": "أردني", "name_en": "Jordanian"},
            {"code": "SY", "name_ar": "سوري", "name_en": "Syrian"},
            {"code": "LB", "name_ar": "لبناني", "name_en": "Lebanese"},
            {"code": "PS", "name_ar": "فلسطيني", "name_en": "Palestinian"},
            {"code": "YE", "name_ar": "يمني", "name_en": "Yemeni"},
            {"code": "IQ", "name_ar": "عراقي", "name_en": "Iraqi"},
            {"code": "SD", "name_ar": "سوداني", "name_en": "Sudanese"},
            {"code": "PK", "name_ar": "باكستاني", "name_en": "Pakistani"},
            {"code": "IN", "name_ar": "هندي", "name_en": "Indian"},
            {"code": "BD", "name_ar": "بنغالي", "name_en": "Bangladeshi"},
            {"code": "PH", "name_ar": "فلبيني", "name_en": "Filipino"},
            {"code": "ID", "name_ar": "إندونيسي", "name_en": "Indonesian"},
            {"code": "OTHER", "name_ar": "أخرى", "name_en": "Other"},
        ]

    async def get_blood_types(self) -> List[Dict[str, str]]:
        return [
            {"code": "A+", "name_ar": "A موجب", "name_en": "A Positive"},
            {"code": "A-", "name_ar": "A سالب", "name_en": "A Negative"},
            {"code": "B+", "name_ar": "B موجب", "name_en": "B Positive"},
            {"code": "B-", "name_ar": "B سالب", "name_en": "B Negative"},
            {"code": "AB+", "name_ar": "AB موجب", "name_en": "AB Positive"},
            {"code": "AB-", "name_ar": "AB سالب", "name_en": "AB Negative"},
            {"code": "O+", "name_ar": "O موجب", "name_en": "O Positive"},
            {"code": "O-", "name_ar": "O سالب", "name_en": "O Negative"},
        ]

    async def get_parent_relations(self) -> List[Dict[str, str]]:
        return [
            {"code": "father", "name_ar": "الأب", "name_en": "Father"},
            {"code": "mother", "name_ar": "الأم", "name_en": "Mother"},
            {"code": "guardian", "name_ar": "ولي الأمر", "name_en": "Guardian"},
            {"code": "other", "name_ar": "أخرى", "name_en": "Other"},
        ]
