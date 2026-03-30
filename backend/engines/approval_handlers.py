"""
NASSAQ Approval Handlers
معالجات الموافقة لمنصة نَسَّق

Type-specific approval handlers for the unified approval engine.
Each handler converts a pending registration request into active entities.

To add a new request type:
1. Create a class extending ApprovalHandler
2. Implement create_entities()
3. Register in server.py via approval_engine.register()
"""

from datetime import datetime, timezone
from typing import Optional
import uuid
import secrets
import string
import random
import base64
import json
import logging

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

    def get_display_fields(self):
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
        database = _get_db()
        email = request.get("email")
        phone = request.get("phone")
        national_id = request.get("national_id")

        if email:
            existing = await database.users.find_one({"email": email})
            if existing:
                return "يوجد حساب مسجل مسبقًا بنفس البريد الإلكتروني"

        if phone:
            existing = await database.users.find_one({"phone": phone})
            if existing:
                return "يوجد حساب مسجل مسبقًا بنفس رقم الهاتف"

        if national_id:
            existing = await database.users.find_one({"national_id": national_id})
            if existing:
                return "يوجد حساب مسجل مسبقًا بنفس رقم الهوية"

        return None

    async def create_entities(self, request: dict, approved_by: dict) -> ApprovalResult:
        database = _get_db()
        now = datetime.now(timezone.utc).isoformat()
        email = request.get("email")
        phone = request.get("phone")
        national_id = request.get("national_id")
        approver_id = approved_by.get("id", approved_by.get("user_id"))

        user_id = str(uuid.uuid4())
        temp_password = _generate_secure_password()
        teacher_id = _generate_teacher_id()
        qr_code = _generate_qr_code_data(teacher_id, user_id)

        new_user = {
            "id": user_id,
            "email": email,
            "password_hash": _hash_password(temp_password),
            "full_name": request.get("full_name"),
            "role": "teacher",
            "phone": phone,
            "national_id": national_id,
            "region": None,
            "city": None,
            "educational_department": None,
            "school_name_ar": request.get("school_mentioned"),
            "permissions": ["view_own_profile", "manage_own_classes", "view_own_students", "take_attendance"],
            "is_active": True,
            "must_change_password": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": now,
            "updated_at": now,
            "created_by": approver_id,
            "account_type": "independent_teacher"
        }
        await database.users.insert_one(new_user)

        teacher_record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "teacher_id": teacher_id,
            "full_name": request.get("full_name"),
            "email": email,
            "phone": phone,
            "specialization": request.get("subject") or request.get("specialization"),
            "educational_level": request.get("educational_level"),
            "years_of_experience": int(request.get("years_of_experience") or 0),
            "school_id": None,
            "qr_code": qr_code,
            "is_active": True,
            "created_at": now,
            "created_by": approver_id
        }
        await database.teachers.insert_one(teacher_record)

        qr_record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "teacher_id": teacher_id,
            "qr_data": qr_code,
            "created_at": now
        }
        await database.teacher_qr_codes.insert_one(qr_record)

        login_url = "https://nassaqapp.com/login"
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


class SchoolApprovalHandler(ApprovalHandler):
    request_type = "school"
    display_name = "School"
    display_name_ar = "مدرسة"

    def get_display_fields(self):
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
        database = _get_db()
        school_email = request.get("school_email") or request.get("email")
        if school_email:
            existing = await database.users.find_one({"email": school_email})
            if existing:
                return "يوجد حساب مسجل مسبقًا بنفس البريد الإلكتروني"
        return None

    async def _generate_school_code(self) -> str:
        database = _get_db()
        year_suffix = datetime.now().strftime("%y")
        country_code = "SA"
        prefix = f"NSS-{country_code}-{year_suffix}-"

        last_school = await database.schools.find_one(
            {"code": {"$regex": f"^{prefix}"}},
            sort=[("code", -1)]
        )
        next_num = 1
        if last_school and last_school.get("code"):
            try:
                last_num = int(last_school["code"].split("-")[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                pass

        school_code = f"{prefix}{str(next_num).zfill(4)}"
        existing = await database.schools.find_one({"code": school_code})
        if existing:
            school_code = f"{prefix}{str(next_num + 1).zfill(4)}"

        return school_code

    async def create_entities(self, request: dict, approved_by: dict) -> ApprovalResult:
        database = _get_db()
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

        school_doc = {
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
            "logo_url": None,
            "status": "active",
            "student_capacity": student_capacity,
            "current_students": 0,
            "current_teachers": 0,
            "language": "ar",
            "calendar_system": "hijri_gregorian",
            "school_type": request.get("school_type", "public"),
            "stage": "primary",
            "principal_name": principal_name,
            "principal_email": school_email,
            "principal_phone": school_phone,
            "created_at": now,
            "updated_at": now,
            "created_by": approver_id,
        }
        await database.schools.insert_one(school_doc)

        temp_password = _generate_secure_password(12)
        principal_id = str(uuid.uuid4())
        principal_doc = {
            "id": principal_id,
            "email": school_email,
            "password_hash": _hash_password(temp_password),
            "full_name": principal_name,
            "full_name_en": None,
            "role": "school_principal",
            "tenant_id": school_id,
            "phone": school_phone,
            "avatar_url": None,
            "is_active": True,
            "must_change_password": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "permissions": ["manage_school", "manage_teachers", "manage_students", "view_reports", "manage_settings"],
            "created_at": now,
            "updated_at": now,
            "created_by": approver_id,
        }
        await database.users.insert_one(principal_doc)

        default_settings = await database.default_settings.find_one({"id": "default-school-settings"}, {"_id": 0})
        if default_settings:
            school_settings = {
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
            }
            await database.school_settings.insert_one(school_settings)

        login_url = "https://nassaqapp.com/login"
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
