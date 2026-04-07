"""
NASSAQ Approval Handlers
معالجات الموافقة لمنصة نَسَّق

Type-specific approval handlers for the unified approval engine.
Each handler converts a pending registration request into active entities.

To add a new request type:
1. Create a class extending ApprovalHandler
2. Implement create_entities()
3. Optionally implement verify_after_approve()
4. Register in server.py via approval_engine.register()
"""

import os
from datetime import datetime, timezone
from typing import Optional
import uuid
import secrets
import string
import random
import base64
import json
import logging

from sqlalchemy import select, and_, desc as sa_desc

from pg_models import User, Teacher, School, SchoolSettings
from engines.sql_utils import model_to_dict, dict_to_model, gd_insert, gd_find_one
from engines.approval_engine import ApprovalHandler, ApprovalResult


def _get_db():
    from dependencies import db
    return db


def _hash_password(password: str) -> str:
    from dependencies import hash_password
    return hash_password(password)

logger = logging.getLogger("nassaq.approval_handlers")


def _generate_secure_password(length=10):
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _generate_teacher_id():
    return f"TCH-{random.randint(100000, 999999)}"


def _generate_qr_code_data(teacher_id: str, user_id: str):
    qr_data = {
        "type": "teacher",
        "teacher_id": teacher_id,
        "user_id": user_id,
        "platform": "NASSAQ"
    }
    return base64.b64encode(json.dumps(qr_data).encode()).decode()


class TeacherApprovalHandler(ApprovalHandler):
    request_type = "teacher"
    display_name = "Independent Teacher"
    display_name_ar = "معلم مستقل"

    def get_display_fields(self) -> list:
        """Return human-readable display fields for a teacher/school approval."""
        return [
            {"key": "full_name", "label": "الاسم", "label_en": "Name"},
            {"key": "email", "label": "البريد", "label_en": "Email"},
            {"key": "phone", "label": "الهاتف", "label_en": "Phone"},
            {"key": "specialization", "label": "التخصص", "label_en": "Specialization"},
            {"key": "subject", "label": "المادة", "label_en": "Subject"},
            {"key": "educational_level", "label": "المرحلة", "label_en": "Level"},
            {"key": "years_of_experience", "label": "سنوات الخبرة", "label_en": "Experience"},
            {"key": "created_at", "label": "تاريخ الطلب", "label_en": "Date"},
        ]

    async def validate_before_approve(self, request: dict) -> Optional[str]:
        """Validate business rules before approving teacher/school registration."""
        database = _get_db()
        session = database.session
        email = request.get("email")
        phone = request.get("phone")
        national_id = request.get("national_id")

        if email:
            stmt = select(User).where(User.email == email).limit(1)
            result = await session.execute(stmt)
            if result.scalars().first():
                return "يوجد حساب مسجل مسبقًا بنفس البريد الإلكتروني"

        if phone:
            stmt = select(User).where(User.phone == phone).limit(1)
            result = await session.execute(stmt)
            if result.scalars().first():
                return "يوجد حساب مسجل مسبقًا بنفس رقم الهاتف"

        if national_id:
            stmt = select(User).where(User.national_id == national_id).limit(1)
            result = await session.execute(stmt)
            if result.scalars().first():
                return "يوجد حساب مسجل مسبقًا بنفس رقم الهوية"

        return None

    async def create_entities(self, request: dict, approved_by: dict) -> ApprovalResult:
        """Create the teacher or school entities upon approval."""
        database = _get_db()
        session = database.session
        now = datetime.now(timezone.utc).isoformat()
        email = request.get("email")
        phone = request.get("phone")
        national_id = request.get("national_id")
        approver_id = approved_by.get("id", approved_by.get("user_id"))

        user_id = str(uuid.uuid4())
        temp_password = _generate_secure_password()
        teacher_id = _generate_teacher_id()
        qr_code = _generate_qr_code_data(teacher_id, user_id)

        new_user = dict_to_model(User, {
            "id": user_id,
            "email": email,
            "password_hash": _hash_password(temp_password),
            "full_name": request.get("full_name"),
            "role": "teacher",
            "phone": phone,
            "national_id": national_id,
            "is_active": True,
            "must_change_password": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": now,
            "updated_at": now,
            "created_by": approver_id,
            "account_type": "independent_teacher",
            "permissions": ["view_own_profile", "manage_own_classes", "view_own_students", "take_attendance"],
        })
        session.add(new_user)
        await session.flush()

        teacher_record = dict_to_model(Teacher, {
            "id": str(uuid.uuid4()),
            "full_name": request.get("full_name"),
            "email": email,
            "phone": phone,
            "specialization": request.get("subject") or request.get("specialization"),
            "years_of_experience": int(request.get("years_of_experience") or 0),
            "school_id": None,
            "is_active": True,
            "created_at": now,
            "user_id": user_id,
            "teacher_id": teacher_id,
            "qr_code": qr_code,
            "created_by": approver_id,
        })
        session.add(teacher_record)
        await session.flush()

        await gd_insert(session, "teacher_qr_codes", {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "teacher_id": teacher_id,
            "qr_data": qr_code,
            "created_at": now,
        })

        login_url = f"{os.environ.get('FRONTEND_URL', 'https://nassaq.com')}/login"
        message_template = f"""مرحبًا،

تم قبول طلب إنشاء حسابك على منصة نَسَّق | NASSAQ.

بيانات الدخول الخاصة بك:

البريد الإلكتروني:
{email}

كلمة المرور المؤقتة:
{temp_password}

معرف المعلم الخاص بك:
{teacher_id}

يرجى تسجيل الدخول وتغيير كلمة المرور عند أول دخول.

رابط الدخول:
{login_url}

مع تحيات فريق نَسَّق | NASSAQ"""

        return ApprovalResult(
            success=True,
            message="تم إنشاء حساب المعلم بنجاح",
            request_type="teacher",
            created_entities={
                "user_id": user_id,
                "teacher_id": teacher_id,
                "email": email,
            },
            credentials={
                "email": email,
                "temporary_password": temp_password,
                "teacher_id": teacher_id,
                "qr_code": qr_code,
            },
            message_template=message_template,
        )

    async def verify_after_approve(self, request: dict, result: ApprovalResult) -> Optional[str]:
        """Verify that entities were created successfully after approval."""
        database = _get_db()
        session = database.session
        user_id = result.created_entities.get("user_id")
        teacher_id = result.created_entities.get("teacher_id")

        stmt = select(User).where(User.id == user_id).limit(1)
        res = await session.execute(stmt)
        user = res.scalars().first()
        if not user:
            return f"Post-approval verification failed: user {user_id} not found in users collection"
        if not user.is_active:
            return f"Post-approval verification failed: user {user_id} is not active"

        stmt2 = select(Teacher).where(Teacher.id == teacher_id).limit(1)
        res2 = await session.execute(stmt2)
        teacher = res2.scalars().first()
        if not teacher:
            return f"Post-approval verification failed: teacher record {teacher_id} not found"

        logger.info(f"Teacher verification passed: user_id={user_id}, teacher_id={teacher_id}")
        return None


class SchoolApprovalHandler(ApprovalHandler):
    request_type = "school"
    display_name = "School"
    display_name_ar = "مدرسة"

    def get_display_fields(self) -> list:
        """Return human-readable display fields for a teacher/school approval."""
        return [
            {"key": "school_name", "label": "اسم المدرسة", "label_en": "School Name"},
            {"key": "full_name", "label": "اسم المدير", "label_en": "Principal"},
            {"key": "school_email", "label": "البريد", "label_en": "Email"},
            {"key": "school_phone", "label": "الهاتف", "label_en": "Phone"},
            {"key": "school_city", "label": "المدينة", "label_en": "City"},
            {"key": "school_address", "label": "العنوان", "label_en": "Address"},
            {"key": "student_capacity", "label": "السعة", "label_en": "Capacity"},
            {"key": "created_at", "label": "تاريخ الطلب", "label_en": "Date"},
        ]

    async def validate_before_approve(self, request: dict) -> Optional[str]:
        """Validate business rules before approving teacher/school registration."""
        database = _get_db()
        session = database.session
        school_email = request.get("school_email") or request.get("email")
        if school_email:
            stmt = select(User).where(User.email == school_email).limit(1)
            result = await session.execute(stmt)
            if result.scalars().first():
                return "يوجد حساب مسجل مسبقًا بنفس البريد الإلكتروني"
        return None

    async def _generate_school_code(self) -> str:
        database = _get_db()
        session = database.session
        year_suffix = datetime.now().strftime("%y")
        country_code = "SA"
        prefix = f"NSS-{country_code}-{year_suffix}-"

        stmt = (
            select(School)
            .where(School.code.like(f"{prefix}%"))
            .order_by(sa_desc(School.code))
            .limit(1)
        )
        result = await session.execute(stmt)
        last_school = result.scalars().first()

        next_num = 1
        if last_school and last_school.code:
            try:
                last_num = int(last_school.code.split("-")[-1])
                next_num = last_num + 1
            except (ValueError, IndexError) as e:
                logging.getLogger("nassaq.approval").debug("School code parse fallback: %s", e)

        school_code = f"{prefix}{str(next_num).zfill(4)}"

        stmt2 = select(School).where(School.code == school_code).limit(1)
        result2 = await session.execute(stmt2)
        if result2.scalars().first():
            school_code = f"{prefix}{str(next_num + 1).zfill(4)}"

        return school_code

    async def create_entities(self, request: dict, approved_by: dict) -> ApprovalResult:
        """Create the teacher or school entities upon approval."""
        database = _get_db()
        session = database.session
        now = datetime.now(timezone.utc).isoformat()
        approver_id = approved_by.get("id", approved_by.get("user_id"))

        school_email = request.get("school_email") or request.get("email")
        school_phone = request.get("school_phone") or request.get("phone")
        school_name = request.get("school_name", "")
        principal_name = request.get("full_name", "")

        school_code = await self._generate_school_code()
        school_id = str(uuid.uuid4())

        capacity_raw = request.get("student_capacity", "500")
        try:
            student_capacity = int(capacity_raw)
        except (ValueError, TypeError):
            student_capacity = 500

        school_obj = dict_to_model(School, {
            "id": school_id,
            "name": school_name,
            "name_ar": school_name,
            "name_en": "",
            "code": school_code,
            "email": school_email or f"school-{school_code.lower()}@nassaq.com",
            "phone": school_phone,
            "address": request.get("school_address", ""),
            "city": request.get("school_city", ""),
            "region": "",
            "country": "SA",
            "status": "active",
            "student_capacity": student_capacity,
            "current_students": 0,
            "current_teachers": 0,
            "school_type": request.get("school_type", "public"),
            "principal_name": principal_name,
            "principal_email": school_email,
            "principal_phone": school_phone,
            "created_at": now,
            "updated_at": now,
            "created_by": approver_id,
        })
        session.add(school_obj)
        await session.flush()

        temp_password = _generate_secure_password(12)
        principal_id = str(uuid.uuid4())
        principal_obj = dict_to_model(User, {
            "id": principal_id,
            "email": school_email,
            "password_hash": _hash_password(temp_password),
            "full_name": principal_name,
            "role": "school_principal",
            "school_id": school_id,
            "phone": school_phone,
            "is_active": True,
            "must_change_password": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "permissions": ["manage_school", "manage_teachers", "manage_students", "view_reports", "manage_settings"],
            "created_at": now,
            "updated_at": now,
            "created_by": approver_id,
        })
        session.add(principal_obj)
        await session.flush()

        default_settings = await gd_find_one(session, "default_settings", {"id": "default-school-settings"})
        if default_settings:
            settings_obj = dict_to_model(SchoolSettings, {
                "id": f"settings-{school_id}",
                "school_id": school_id,
                "working_days": default_settings.get("working_days"),
                "working_days_ar": default_settings.get("working_days_ar"),
                "working_days_en": default_settings.get("working_days_en"),
                "weekend_days_ar": default_settings.get("weekend_days_ar"),
                "weekend_days_en": default_settings.get("weekend_days_en"),
                "periods_per_day": default_settings.get("periods_per_day"),
                "period_duration_minutes": default_settings.get("period_duration_minutes"),
                "break_duration_minutes": default_settings.get("break_duration_minutes"),
                "prayer_duration_minutes": default_settings.get("prayer_duration_minutes"),
                "school_day_start": default_settings.get("school_day_start"),
                "school_day_end": default_settings.get("school_day_end"),
                "time_slots": default_settings.get("time_slots"),
                "education_track": "track-general",
                "created_at": now,
                "updated_at": now,
            })
            session.add(settings_obj)
            await session.flush()

        login_url = f"{os.environ.get('FRONTEND_URL', 'https://nassaq.com')}/login"
        message_template = f"""مرحبًا {principal_name}،

تم قبول طلب تسجيل مدرستكم "{school_name}" على منصة نَسَّق | NASSAQ.

بيانات الدخول الخاصة بك:

البريد الإلكتروني:
{school_email}

كلمة المرور المؤقتة:
{temp_password}

رمز المدرسة:
{school_code}

يرجى تسجيل الدخول وتغيير كلمة المرور عند أول دخول.

رابط الدخول:
{login_url}

مع تحيات فريق نَسَّق | NASSAQ"""

        logger.info(f"School created: {school_name} (code: {school_code})")

        return ApprovalResult(
            success=True,
            message="تم إنشاء المدرسة وحساب المدير بنجاح",
            request_type="school",
            created_entities={
                "school_id": school_id,
                "school_code": school_code,
                "principal_id": principal_id,
                "email": school_email,
            },
            credentials={
                "email": school_email,
                "temporary_password": temp_password,
                "school_code": school_code,
            },
            message_template=message_template,
        )

    async def verify_after_approve(self, request: dict, result: ApprovalResult) -> Optional[str]:
        """Verify that entities were created successfully after approval."""
        database = _get_db()
        session = database.session
        school_id = result.created_entities.get("school_id")
        principal_id = result.created_entities.get("principal_id")

        stmt = select(School).where(School.id == school_id).limit(1)
        res = await session.execute(stmt)
        school = res.scalars().first()
        if not school:
            return f"Post-approval verification failed: school {school_id} not found"
        if school.status != "active":
            return f"Post-approval verification failed: school {school_id} is not active"

        stmt2 = select(User).where(User.id == principal_id).limit(1)
        res2 = await session.execute(stmt2)
        principal = res2.scalars().first()
        if not principal:
            return f"Post-approval verification failed: principal user {principal_id} not found"
        if principal.school_id != school_id:
            return f"Post-approval verification failed: principal not linked to school"
        if not principal.is_active:
            return f"Post-approval verification failed: principal user is not active"

        logger.info(f"School verification passed: school_id={school_id}, principal_id={principal_id}")
        return None
