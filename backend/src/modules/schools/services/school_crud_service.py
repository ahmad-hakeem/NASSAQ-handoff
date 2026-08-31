"""
School CRUD Service
Handles School creation (standard & draft), deletion of drafts, status management (activation & suspension),
principal credentials management, live entity counts matching, and school entity normalization.
"""
from fastapi import HTTPException
from typing import List, Optional, Dict, Tuple, Any
from datetime import datetime, timezone
import uuid
import logging
from sqlalchemy.exc import IntegrityError

from dependencies import (
    UserRole, SchoolStatus,
    hash_password, audit_engine, AuditAction,
)
from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_insert_many,
    gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many,
)
from src.modules.schools.dto.school_dto import (
    SchoolCreate, SchoolResponse, SchoolStatusChangeRequest, SchoolCredentialsRequest
)
from src.common.utils.avatar_image import normalize_image_field_or_400
from src.common.utils.avatar_serving import is_internal_image_url, signed_image_url
from src.common.utils.platform_admin_preview import assess_principal_preview_eligibility
from src.common.utils.school_code import (
    insert_school_with_unique_code,
    insert_school_with_custom_code,
    is_school_code_conflict,
)

logger = logging.getLogger("nassaq")


def normalize_school(
    s: dict,
    *,
    principal_counts: Optional[Dict[str, int]] = None,
    student_counts: Optional[Dict[str, int]] = None,
    teacher_counts: Optional[Dict[str, int]] = None,
) -> dict:
    """Normalize school document to match SchoolResponse fields with live counts."""
    school_id = s.get("id") or ""
    principal_count = None
    if principal_counts is not None:
        principal_count = principal_counts.get(school_id, 0)

    preview = assess_principal_preview_eligibility(
        s,
        active_principal_count=principal_count,
    )

    if student_counts is not None:
        current_students = student_counts.get(school_id, 0)
    else:
        current_students = s.get("current_students") or s.get("student_count") or 0
    if teacher_counts is not None:
        current_teachers = teacher_counts.get(school_id, 0)
    else:
        current_teachers = s.get("current_teachers") or s.get("teacher_count") or 0

    return {
        **s,
        "logo_url": signed_image_url("logo", school_id, s.get("logo_url")),
        "name": s.get("name") or s.get("name_ar") or s.get("name_en") or "",
        "code": s.get("code") or s.get("license_number") or s.get("id") or "",
        "email": s.get("email") or "",
        "phone": s.get("phone") or s.get("principal_phone") or s.get("principal_mobile") or "",
        "address": s.get("address") or "",
        "city": s.get("city") or "",
        "region": s.get("region") or "",
        "country": s.get("country") or "SA",
        "status": s.get("status") or "active",
        "student_capacity": s.get("student_capacity") or s.get("student_count") or 500,
        "current_students": current_students,
        "current_teachers": current_teachers,
        "created_at": s.get("created_at") or "",
        "school_type": s.get("school_type") or "public",
        "stage": s.get("stage") or "primary",
        "language": s.get("language") or "ar",
        "calendar_system": s.get("calendar_system") or "hijri_gregorian",
        "educational_pathway": s.get("educational_pathway"),
        "principal_name": s.get("principal_name"),
        "principal_email": s.get("principal_email"),
        "principal_phone": s.get("principal_phone") or s.get("phone"),
        "principal_mobile": s.get("principal_mobile") or s.get("phone") or s.get("principal_phone"),
        "entity_kind": preview["entity_kind"],
        "can_preview_as_principal": preview["can_preview_as_principal"],
        "preview_block_reason": preview["preview_block_reason"],
    }


async def active_principal_counts_by_tenant(session) -> Dict[str, int]:
    """Batch count active school principals per tenant for preview metadata."""
    from sqlalchemy import text as _sa_text

    result = await session.execute(
        _sa_text(
            """
            SELECT tenant_id, COUNT(*)::int AS cnt
            FROM users
            WHERE role = 'school_principal'
              AND is_active = TRUE
              AND tenant_id IS NOT NULL
            GROUP BY tenant_id
            """
        )
    )
    rows = result.mappings().all()
    return {row["tenant_id"]: row["cnt"] for row in rows if row.get("tenant_id")}


async def live_entity_counts_by_tenant(session) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Batch live student/teacher counts per tenant for platform lists."""
    from engines.entity_counts import live_counts_by_tenant
    return await live_counts_by_tenant(session)


class SchoolCrudService:
    """Service handling School CRUD operations, life cycle, and credentials."""

    @staticmethod
    async def create_school(session, school_data: SchoolCreate, current_user: dict) -> SchoolResponse:
        if school_data.principal_email:
            existing_email = await gd_find_one(session, "users", {"email": school_data.principal_email})
            if existing_email:
                raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")

        if school_data.principal_phone:
            existing_phone = await gd_find_one(session, "users", {"phone": school_data.principal_phone})
            if existing_phone:
                raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")

        school_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        school_phone = school_data.principal_mobile or school_data.phone or school_data.principal_phone
        logo_url = await normalize_image_field_or_400(school_data.logo_url) if school_data.logo_url else None

        def _build_school_doc(code: str) -> dict:
            return {
                "id": school_id,
                "name": school_data.name,
                "name_en": school_data.name_en,
                "code": code,
                "email": school_data.email or school_data.principal_email or f"school-{code.lower()}@nassaq.com",
                "phone": school_phone,
                "address": school_data.address,
                "city": school_data.city,
                "region": school_data.region,
                "country": school_data.country or "SA",
                "logo_url": logo_url,
                "status": SchoolStatus.ACTIVE.value,
                "student_capacity": school_data.student_capacity,
                "current_students": 0,
                "current_teachers": 0,
                "language": school_data.language or "ar",
                "calendar_system": school_data.calendar_system or "hijri_gregorian",
                "school_type": school_data.school_type or "public",
                "stage": school_data.stage or "primary",
                "principal_name": school_data.principal_name,
                "principal_email": school_data.principal_email,
                "principal_phone": school_data.principal_phone or getattr(school_data, 'principal_mobile', None),
                "principal_mobile": school_data.principal_mobile or school_phone,
                "educational_pathway": school_data.educational_pathway,
                "created_at": created_at,
                "updated_at": created_at,
                "created_by": current_user.get("user_id"),
            }

        if school_data.code:
            try:
                await insert_school_with_custom_code(session, _build_school_doc, school_data.code)
            except IntegrityError as ie:
                if is_school_code_conflict(ie):
                    raise HTTPException(status_code=400, detail="رمز المدرسة مستخدم مسبقاً — يُرجى اختيار رمز آخر")
                raise
            school_code = school_data.code
        else:
            school_code, _ = await insert_school_with_unique_code(
                session, _build_school_doc, country=school_data.country or "SA"
            )

        school_email = school_data.email or school_data.principal_email or f"school-{school_code.lower()}@nassaq.com"

        if school_data.principal_email and school_data.principal_name:
            import secrets, string
            chars = string.ascii_letters + string.digits + "@#$"
            temp_password = ''.join(secrets.choice(chars) for _ in range(12))
            hashed_password = hash_password(temp_password)

            principal_id = str(uuid.uuid4())
            principal_doc = {
                "id": principal_id,
                "email": school_data.principal_email,
                "password_hash": hashed_password,
                "full_name": school_data.principal_name,
                "full_name_en": None,
                "role": UserRole.SCHOOL_PRINCIPAL.value,
                "tenant_id": school_id,
                "phone": school_data.principal_phone,
                "avatar_url": None,
                "is_active": True,
                "must_change_password": True,
                "preferred_language": school_data.language or "ar",
                "preferred_theme": "light",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            await gd_insert(session, "users", principal_doc)

            await audit_engine.log_data_change(
                action=AuditAction.TENANT_CREATED.value,
                performed_by=current_user.get("id", current_user.get("user_id")),
                entity_type="tenant",
                entity_id=school_id,
                new_values={
                    "school_code": school_code,
                    "school_name": school_data.name,
                    "principal_email": school_data.principal_email,
                    "school_type": school_data.school_type,
                    "stage": school_data.stage
                }
            )

            await audit_engine.log_data_change(
                action=AuditAction.USER_CREATED.value,
                performed_by=current_user.get("id", current_user.get("user_id")),
                entity_type="user",
                entity_id=principal_id,
                tenant_id=school_id,
                new_values={
                    "role": "school_principal",
                    "email": school_data.principal_email,
                    "full_name": school_data.principal_name
                }
            )

        default_settings = await gd_find_one(session, "default_settings", {"id": "default-school-settings"})
        if default_settings:
            from src.modules.schools.services.school_settings_service import normalize_school_settings_doc
            school_settings = normalize_school_settings_doc({
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
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            await gd_insert(session, "school_settings", school_settings)

        from src.common.constants.default_subjects import build_default_subject_docs
        await gd_insert_many(
            session, "subjects", build_default_subject_docs(school_id, created_at)
        )

        return SchoolResponse(
            id=school_id,
            name=school_data.name,
            name_en=school_data.name_en,
            code=school_code,
            email=school_email,
            phone=school_phone,
            address=school_data.address,
            city=school_data.city,
            region=school_data.region,
            country=school_data.country or "SA",
            logo_url=None,
            status=SchoolStatus.ACTIVE,
            student_capacity=school_data.student_capacity,
            current_students=0,
            current_teachers=0,
            created_at=created_at
        )

    @staticmethod
    async def create_school_draft(session, school_data: SchoolCreate, current_user: dict) -> SchoolResponse:
        school_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        school_phone = school_data.principal_mobile or school_data.phone or school_data.principal_phone
        logo_url = await normalize_image_field_or_400(school_data.logo_url) if school_data.logo_url else None

        def _build_school_doc(code: str) -> dict:
            return {
                "id": school_id,
                "name": school_data.name or "مسودة مدرسة",
                "name_en": school_data.name_en,
                "code": code,
                "email": school_data.email or f"school-{code.lower()}@nassaq.com",
                "phone": school_phone,
                "address": school_data.address or "",
                "city": school_data.city or "",
                "region": school_data.region,
                "country": school_data.country or "SA",
                "logo_url": logo_url,
                "status": "setup",
                "student_capacity": school_data.student_capacity,
                "current_students": 0,
                "current_teachers": 0,
                "language": school_data.language or "ar",
                "calendar_system": school_data.calendar_system or "hijri_gregorian",
                "school_type": school_data.school_type or "public",
                "stage": school_data.stage or "primary",
                "principal_name": school_data.principal_name or "",
                "principal_email": school_data.principal_email or "",
                "principal_phone": school_data.principal_phone or getattr(school_data, 'principal_mobile', None) or "",
                "principal_mobile": school_data.principal_mobile or school_phone,
                "educational_pathway": school_data.educational_pathway or "",
                "created_at": created_at,
                "updated_at": created_at,
                "created_by": current_user.get("user_id"),
            }

        if school_data.code:
            try:
                await insert_school_with_custom_code(session, _build_school_doc, school_data.code)
            except IntegrityError as ie:
                if is_school_code_conflict(ie):
                    raise HTTPException(status_code=400, detail="رمز المدرسة مستخدم مسبقاً — يُرجى اختيار رمز آخر")
                raise
            school_code = school_data.code
        else:
            school_code, _ = await insert_school_with_unique_code(
                session, _build_school_doc, country=school_data.country or "SA"
            )

        school_email = school_data.email or f"school-{school_code.lower()}@nassaq.com"

        await audit_engine.log_data_change(
            action=AuditAction.TENANT_CREATED.value,
            performed_by=current_user.get("id", current_user.get("user_id")),
            entity_type="tenant",
            entity_id=school_id,
            new_values={
                "school_code": school_code,
                "school_name": school_data.name,
                "status": "setup",
                "is_draft": True
            }
        )

        default_settings = await gd_find_one(session, "default_settings", {"id": "default-school-settings"})
        if default_settings:
            from src.modules.schools.services.school_settings_service import normalize_school_settings_doc
            school_settings = normalize_school_settings_doc({
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
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            await gd_insert(session, "school_settings", school_settings)

        return SchoolResponse(
            id=school_id,
            name=school_data.name or "مسودة مدرسة",
            name_en=school_data.name_en,
            code=school_code,
            email=school_email,
            phone=school_phone,
            address=school_data.address or "",
            city=school_data.city or "",
            region=school_data.region,
            country=school_data.country or "SA",
            logo_url=None,
            status=SchoolStatus.SETUP,
            student_capacity=school_data.student_capacity,
            current_students=0,
            current_teachers=0,
            created_at=created_at
        )

    @staticmethod
    async def delete_school_draft(session, school_id: str, current_user: dict) -> dict:
        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

        if school.get("status") != "setup":
            raise HTTPException(status_code=400, detail="يمكن حذف المسودات فقط (الحالة: قيد الإعداد)")

        await gd_delete_one(session, "schools", {"id": school_id})
        await gd_delete_many(session, "users", {"tenant_id": school_id})
        await gd_delete_many(session, "school_settings", {"school_id": school_id})

        await audit_engine.log_data_change(
            action=AuditAction.TENANT_UPDATED.value,
            performed_by=current_user.get("id", current_user.get("user_id")),
            entity_type="tenant",
            entity_id=school_id,
            new_values={
                "action": "DRAFT_DELETED",
                "school_name": school.get("name", ""),
            }
        )
        return {"success": True, "message": "تم حذف المسودة بنجاح"}

    @staticmethod
    async def update_school_draft(session, school_id: str, school_data: SchoolCreate, current_user: dict) -> SchoolResponse:
        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
        if school.get("status") != "setup":
            raise HTTPException(status_code=400, detail="يمكن تعديل مسودة مدرسة قيد الإعداد فقط")

        now = datetime.now(timezone.utc).isoformat()
        school_phone = school_data.principal_mobile or school_data.phone or school_data.principal_phone or school.get("phone")

        update_fields = {
            "name": school_data.name or school.get("name"),
            "name_en": school_data.name_en,
            "email": school_data.email or school.get("email"),
            "phone": school_phone,
            "address": school_data.address or "",
            "city": school_data.city or "",
            "region": school_data.region or school.get("region"),
            "country": school_data.country or "SA",
            "language": school_data.language or "ar",
            "calendar_system": school_data.calendar_system or "hijri_gregorian",
            "school_type": school_data.school_type or "public",
            "stage": school_data.stage or "primary",
            "student_capacity": school_data.student_capacity or school.get("student_capacity", 500),
            "principal_name": school_data.principal_name or school.get("principal_name") or "",
            "principal_email": school_data.principal_email or school.get("principal_email") or "",
            "principal_phone": school_data.principal_phone or getattr(school_data, 'principal_mobile', None) or school.get("principal_phone") or "",
            "principal_mobile": school_data.principal_mobile or school_phone or "",
            "educational_pathway": school_data.educational_pathway or "",
            "updated_at": now,
        }
        if school_data.logo_url:
            update_fields["logo_url"] = await normalize_image_field_or_400(school_data.logo_url)
        await gd_update_one(session, "schools", {"id": school_id}, update_fields)

        await audit_engine.log_data_change(
            action=AuditAction.TENANT_UPDATED.value,
            performed_by=current_user.get("id", current_user.get("user_id")),
            entity_type="tenant",
            entity_id=school_id,
            new_values={
                "action": "DRAFT_UPDATED",
                "school_name": update_fields["name"],
            }
        )

        updated = await gd_find_one(session, "schools", {"id": school_id})
        return SchoolResponse(**normalize_school(updated))

    @staticmethod
    async def finalize_school_draft(session, school_id: str, school_data: SchoolCreate, current_user: dict) -> dict:
        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
        if school.get("status") != "setup":
            raise HTTPException(status_code=400, detail="المدرسة ليست مسودة قيد الإعداد")

        if school_data.principal_email:
            existing_email = await gd_find_one(session, "users", {"email": school_data.principal_email})
            if existing_email and existing_email.get("tenant_id") != school_id:
                raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")

        if school_data.principal_phone:
            existing_phone = await gd_find_one(session, "users", {"phone": school_data.principal_phone})
            if existing_phone and existing_phone.get("tenant_id") != school_id:
                raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")

        now = datetime.now(timezone.utc).isoformat()
        school_phone = school_data.principal_mobile or school_data.phone or school_data.principal_phone or school.get("phone")

        update_fields = {
            "name": school_data.name or school.get("name"),
            "name_en": school_data.name_en,
            "email": school_data.email or school_data.principal_email or school.get("email"),
            "phone": school_phone,
            "address": school_data.address or "",
            "city": school_data.city or "",
            "region": school_data.region or school.get("region"),
            "country": school_data.country or "SA",
            "status": SchoolStatus.ACTIVE.value,
            "language": school_data.language or "ar",
            "calendar_system": school_data.calendar_system or "hijri_gregorian",
            "school_type": school_data.school_type or "public",
            "stage": school_data.stage or "primary",
            "student_capacity": school_data.student_capacity or school.get("student_capacity", 500),
            "principal_name": school_data.principal_name or school.get("principal_name") or "",
            "principal_email": school_data.principal_email or school.get("principal_email") or "",
            "principal_phone": school_data.principal_phone or getattr(school_data, 'principal_mobile', None) or school.get("principal_phone") or "",
            "principal_mobile": school_data.principal_mobile or school_phone or "",
            "educational_pathway": school_data.educational_pathway or "",
            "updated_at": now,
        }
        if school_data.logo_url:
            update_fields["logo_url"] = await normalize_image_field_or_400(school_data.logo_url)
        await gd_update_one(session, "schools", {"id": school_id}, update_fields)

        import secrets, string
        chars = string.ascii_letters + string.digits + "@#$"
        temp_password = ''.join(secrets.choice(chars) for _ in range(12))
        hashed_password = hash_password(temp_password)

        if school_data.principal_email and school_data.principal_name:
            existing_principal = await gd_find_one(session, "users", {
                "tenant_id": school_id,
                "role": UserRole.SCHOOL_PRINCIPAL.value
            })
            if existing_principal:
                await gd_update_one(session, "users", {"id": existing_principal["id"]}, {
                    "email": school_data.principal_email,
                    "full_name": school_data.principal_name,
                    "phone": school_data.principal_phone or getattr(school_data, 'principal_mobile', None),
                    "password_hash": hashed_password,
                    "is_active": True,
                    "must_change_password": True,
                    "updated_at": now,
                })
            else:
                principal_id = str(uuid.uuid4())
                principal_doc = {
                    "id": principal_id,
                    "email": school_data.principal_email,
                    "password_hash": hashed_password,
                    "full_name": school_data.principal_name,
                    "full_name_en": None,
                    "role": UserRole.SCHOOL_PRINCIPAL.value,
                    "tenant_id": school_id,
                    "phone": school_data.principal_phone or getattr(school_data, 'principal_mobile', None),
                    "avatar_url": None,
                    "is_active": True,
                    "must_change_password": True,
                    "preferred_language": school_data.language or "ar",
                    "preferred_theme": "light",
                    "created_at": now,
                    "updated_at": now,
                }
                await gd_insert(session, "users", principal_doc)

        # Ensure default subjects if not already present
        existing_subjects = await gd_count(session, "subjects", {"school_id": school_id})
        if existing_subjects == 0:
            from src.common.constants.default_subjects import build_default_subject_docs
            await gd_insert_many(session, "subjects", build_default_subject_docs(school_id, now))

        await audit_engine.log_data_change(
            action=AuditAction.TENANT_UPDATED.value,
            performed_by=current_user.get("id", current_user.get("user_id")),
            entity_type="tenant",
            entity_id=school_id,
            new_values={
                "school_code": school.get("code"),
                "school_name": update_fields["name"],
                "status": SchoolStatus.ACTIVE.value,
                "action": "DRAFT_FINALIZED",
            }
        )

        updated = await gd_find_one(session, "schools", {"id": school_id})
        resp = normalize_school(updated)
        resp["temp_password"] = temp_password
        return resp

    @staticmethod
    async def get_schools_list(session, status: Optional[str] = None) -> List[SchoolResponse]:
        query = {}
        if status:
            query["status"] = status
        schools = await gd_find(session, "schools", query, limit=1000)
        principal_counts = await active_principal_counts_by_tenant(session)
        student_counts, teacher_counts = await live_entity_counts_by_tenant(session)
        return [
            SchoolResponse(**normalize_school(
                s,
                principal_counts=principal_counts,
                student_counts=student_counts,
                teacher_counts=teacher_counts,
            ))
            for s in schools
        ]

    @staticmethod
    async def get_school_by_id(session, school_id: str, current_user: dict) -> SchoolResponse:
        privileged_roles = {UserRole.PLATFORM_ADMIN.value, UserRole.MINISTRY_REP.value}
        user_role = current_user.get("role")
        user_tenant = current_user.get("tenant_id")
        if user_role not in privileged_roles and school_id != user_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى بيانات هذه المدرسة")

        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
        principal_counts = await active_principal_counts_by_tenant(session)
        student_counts, teacher_counts = await live_entity_counts_by_tenant(session)
        return SchoolResponse(**normalize_school(
            school,
            principal_counts=principal_counts,
            student_counts=student_counts,
            teacher_counts=teacher_counts,
        ))

    @staticmethod
    async def update_status(session, school_id: str, status: SchoolStatus) -> dict:
        result = await gd_update_one(session, "schools", {"id": school_id}, {
            "status": status.value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        if result == 0:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
        return {"message": "تم تحديث حالة المدرسة"}

    @staticmethod
    async def suspend_school(session, school_id: str, body: SchoolStatusChangeRequest, current_user: dict) -> dict:
        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

        previous_status = school.get("status", "active")
        if previous_status == "suspended":
            return {
                "message": "المدرسة معلقة بالفعل",
                "school_id": school_id,
                "previous_status": previous_status,
                "new_status": "suspended",
                "reason": body.reason or "إيقاف إداري مؤقت",
            }

        now = datetime.now(timezone.utc).isoformat()
        reason_text = (body.reason if body and body.reason else "").strip() or "إيقاف إداري مؤقت"
        await gd_update_one(session, "schools", {"id": school_id}, {
            "status": "suspended",
            "suspended_at": now,
            "suspended_by": current_user.get("id", current_user.get("user_id")),
            "suspension_reason": reason_text,
            "updated_at": now,
        })
        await gd_update_many(session, "users", {"tenant_id": school_id, "is_active": True}, {
            "is_active": False,
            "suspended_at": now,
            "suspended_by_school": True
        })

        performer_id = current_user.get("id", current_user.get("user_id"))
        await audit_engine.log_data_change(
            action=AuditAction.TENANT_SUSPENDED.value,
            performed_by=performer_id,
            entity_type="school",
            entity_id=school_id,
            tenant_id=school_id,
            previous_values={"status": previous_status},
            new_values={
                "status": "suspended",
                "reason": reason_text,
                "performed_by_email": current_user.get("email", ""),
                "school_name": school.get("name", ""),
            },
            actor_role=current_user.get("role"),
            actor_email=current_user.get("email"),
            actor_name=current_user.get("full_name"),
        )

        return {
            "message": "تم تعليق المدرسة بنجاح",
            "school_id": school_id,
            "previous_status": previous_status,
            "new_status": "suspended",
            "reason": reason_text,
            "timestamp": now,
        }

    @staticmethod
    async def activate_school(session, school_id: str, body: SchoolStatusChangeRequest, current_user: dict) -> dict:
        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

        previous_status = school.get("status", "suspended")
        now = datetime.now(timezone.utc).isoformat()
        reason_text = (body.reason if body and body.reason else "").strip() or "إعادة تفعيل المدرسة"

        await gd_update_one(session, "schools", {"id": school_id}, {
            "status": "active",
            "activated_at": now,
            "activated_by": current_user.get("id", current_user.get("user_id")),
            "activation_reason": reason_text,
            "updated_at": now,
        })

        await gd_update_many(
            session, "users",
            {"tenant_id": school_id, "is_active": False, "suspended_by_school": True},
            {"is_active": True, "activated_at": now, "suspended_by_school": False,
             "last_password_change": now},
        )

        performer_id = current_user.get("id", current_user.get("user_id"))
        await audit_engine.log_data_change(
            action=AuditAction.TENANT_ACTIVATED.value,
            performed_by=performer_id,
            entity_type="school",
            entity_id=school_id,
            tenant_id=school_id,
            previous_values={"status": previous_status},
            new_values={
                "status": "active",
                "reason": body.reason,
                "performed_by_email": current_user.get("email", ""),
                "school_name": school.get("name", ""),
            },
            actor_role=current_user.get("role"),
            actor_email=current_user.get("email"),
            actor_name=current_user.get("full_name"),
        )

        return {
            "message": "تم تفعيل المدرسة بنجاح",
            "school_id": school_id,
            "previous_status": previous_status,
            "new_status": "active",
            "reason": body.reason,
            "timestamp": now,
        }

    @staticmethod
    async def get_school_detail(session, school_id: str, current_user: dict) -> dict:
        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

        users = await gd_find(session, "users", {"tenant_id": school_id}, limit=1000)
        students = await gd_find(session, "students", {"school_id": school_id}, limit=500)
        teachers = await gd_find(session, "teachers", {"school_id": school_id}, limit=500)
        classes = await gd_find(session, "classes", {"school_id": school_id, "is_active": {"$ne": False}}, limit=200)

        principal_account = await gd_find_one(session, "users", {"tenant_id": school_id, "role": UserRole.SCHOOL_PRINCIPAL.value})
        has_credentials = principal_account is not None

        audit_logs = await gd_find(session, "audit_logs", {"$or": [{"tenant_id": school_id}, {"entity_id": school_id}]}, limit=100)
        audit_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        audit_logs = audit_logs[:50]

        performer_id = current_user.get("id", current_user.get("user_id"))
        await audit_engine.log_data_change(
            action=AuditAction.TENANT_UPDATED.value,
            performed_by=performer_id,
            entity_type="school",
            entity_id=school_id,
            tenant_id=school_id,
            new_values={"action": "VIEW_SCHOOL", "school_name": school.get("name", "")}
        )

        principal_counts = await active_principal_counts_by_tenant(session)
        student_counts, teacher_counts = await live_entity_counts_by_tenant(session)
        school_payload = normalize_school(
            school,
            principal_counts=principal_counts,
            student_counts=student_counts,
            teacher_counts=teacher_counts,
        )

        return {
            "school": school_payload,
            "stats": {
                "total_users": len(users),
                "total_students": len(students),
                "total_teachers": len(teachers),
                "total_classes": len(classes),
            },
            "principal_account": principal_account,
            "has_credentials": has_credentials,
            "users": users[:100],
            "students": students[:100],
            "teachers": teachers[:100],
            "classes": classes[:50],
            "audit_logs": audit_logs,
        }

    @staticmethod
    async def manage_school_credentials(session, school_id: str, body: SchoolCredentialsRequest, current_user: dict) -> dict:
        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

        import secrets, string as _string
        now = datetime.now(timezone.utc).isoformat()
        principal_name = body.name or school.get("principal_name") or "مدير المدرسة"

        existing_principal = await gd_find_one(session, "users", {
            "tenant_id": school_id,
            "role": UserRole.SCHOOL_PRINCIPAL.value
        })

        raw_password = None
        generated = False
        if body.password:
            raw_password = body.password
        elif not existing_principal:
            chars = _string.ascii_letters + _string.digits + "!@#$%"
            raw_password = ''.join(secrets.choice(chars) for _ in range(14))
            generated = True

        is_new = False
        if existing_principal:
            update_fields = {
                "email": body.email,
                "full_name": principal_name,
                "must_change_password": True if raw_password else existing_principal.get("must_change_password", False),
                "updated_at": now,
            }
            if raw_password:
                update_fields["password_hash"] = hash_password(raw_password)
                update_fields["last_password_change"] = now
            await gd_update_one(session, "users", {"id": existing_principal["id"]}, update_fields)
            principal_id = existing_principal["id"]
        else:
            hashed = hash_password(raw_password)
            principal_id = str(uuid.uuid4())
            await gd_insert(session, "users", {
                "id": principal_id,
                "email": body.email,
                "password_hash": hashed,
                "full_name": principal_name,
                "role": UserRole.SCHOOL_PRINCIPAL.value,
                "tenant_id": school_id,
                "is_active": True,
                "must_change_password": True,
                "preferred_language": "ar",
                "preferred_theme": "light",
                "created_at": now,
                "updated_at": now,
            })
            is_new = True

        await gd_update_one(session, "schools", {"id": school_id}, {
            "principal_email": body.email,
            "principal_name": principal_name,
            "updated_at": now,
        })

        performer_id = current_user.get("id", current_user.get("user_id"))
        await audit_engine.log_data_change(
            action=AuditAction.USER_CREATED.value if is_new else AuditAction.USER_UPDATED.value,
            performed_by=performer_id,
            entity_type="user",
            entity_id=principal_id,
            tenant_id=school_id,
            new_values={
                "action": "SET_SCHOOL_CREDENTIALS",
                "email": body.email,
                "school_name": school.get("name", ""),
                "is_new_account": is_new,
            }
        )

        return {
            "success": True,
            "is_new": is_new,
            "email": body.email,
            "name": principal_name,
            "temp_password": raw_password,
            "password_was_generated": generated,
            "password_was_changed": raw_password is not None,
            "message": "تم إنشاء حساب المدير بنجاح" if is_new else "تم تحديث بيانات الدخول بنجاح",
        }

    @staticmethod
    async def patch_school(session, school_id: str, data: dict, current_user: dict) -> dict:
        privileged_roles = {UserRole.PLATFORM_ADMIN.value}
        if current_user.get("role") not in privileged_roles and school_id != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح بتعديل بيانات هذه المدرسة")

        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

        patchable = ["name", "name_en", "email", "phone", "address", "city", "region",
                     "logo_url", "website", "principal_name", "status", "ai_enabled",
                     "student_capacity", "school_type", "stage"]
        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        for field in patchable:
            if field in data:
                update_data[field] = data[field]

        if "logo_url" in update_data and is_internal_image_url(update_data["logo_url"]):
            update_data.pop("logo_url")
        if "logo_url" in update_data:
            update_data["logo_url"] = await normalize_image_field_or_400(update_data["logo_url"])

        await gd_update_one(session, "schools", {"id": school_id}, update_data)
        updated = await gd_find_one(session, "schools", {"id": school_id})
        updated["logo_url"] = signed_image_url("logo", school_id, updated.get("logo_url"))
        return updated

    @staticmethod
    async def update_school(session, school_id: str, data: dict, current_user: dict) -> dict:
        privileged_roles = {UserRole.PLATFORM_ADMIN.value}
        if current_user.get("role") not in privileged_roles and school_id != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح بتعديل بيانات هذه المدرسة")

        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        allowed_fields = ["name", "name_en", "email", "phone", "address", "city", "region", "logo_url", "website", "principal_name"]
        for field in allowed_fields:
            if field in data and data[field] is not None:
                update_data[field] = data[field]

        if "logo_url" in update_data and is_internal_image_url(update_data["logo_url"]):
            update_data.pop("logo_url")
        if "logo_url" in update_data:
            update_data["logo_url"] = await normalize_image_field_or_400(update_data["logo_url"])

        await gd_update_one(session, "schools", {"id": school_id}, update_data)
        updated_school = await gd_find_one(session, "schools", {"id": school_id})
        updated_school["logo_url"] = signed_image_url("logo", school_id, updated_school.get("logo_url"))
        return updated_school
