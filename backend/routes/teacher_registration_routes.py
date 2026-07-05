"""
NASSAQ Teacher Registration Routes
مسارات API لتسجيل المعلمين المستقلين

Endpoints:
- Create registration request
- Track request status
- Admin review operations
- Teacher invite system
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
import logging
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

logger = logging.getLogger("nassaq.teacher_registration_routes")


# ============== MODELS ==============

class TeacherRegistrationCreate(BaseModel):
    """نموذج طلب تسجيل معلم"""
    # Step 1: Basic Info
    full_name: str
    national_id: str
    phone: str
    email: EmailStr
    
    # Step 2: Professional Info
    subject: str
    education_level: str
    years_of_experience: int
    academic_degree: str
    
    # Step 3: Teacher Rank
    teacher_rank: str
    
    # Step 4: School Data
    school_name: str
    school_country: str
    school_city: str
    school_type: str
    
    # Optional
    referred_by: Optional[str] = None


class TeacherDirectRegistration(BaseModel):
    """نموذج تسجيل معلم مباشر — بدون مراجعة"""
    full_name: str
    national_id: str
    phone: str
    email: EmailStr
    password: str

    subject: str
    education_level: str
    years_of_experience: int
    academic_degree: str

    teacher_rank: str

    school_name: str
    school_country: str = "SA"
    school_city: str
    school_type: str

    referred_by: Optional[str] = None


class MoreInfoRequest(BaseModel):
    """طلب معلومات إضافية"""
    questions: List[str]


class RejectRequest(BaseModel):
    """رفض الطلب"""
    reason: str


class TeacherInviteCreate(BaseModel):
    """دعوة معلم"""
    invitee_name: str
    invitee_email: EmailStr
    invitee_phone: Optional[str] = None


def create_teacher_registration_router(db, get_current_user, require_roles, UserRole):
    """Factory function to create teacher registration router"""
    
    router = APIRouter(prefix="/teacher-registration", tags=["Teacher Registration"])
    
    # Initialize engine
    from engines.teacher_registration_engine import TeacherRegistrationEngine
    engine = TeacherRegistrationEngine(db)
    
    # ============== PUBLIC ENDPOINTS ==============
    
    @router.post("/request")
    async def create_registration_request(
        data: TeacherRegistrationCreate,
        request: Request
    ):
        """إنشاء طلب تسجيل معلم جديد (Public - No Auth Required)"""
        try:
            # Get IP and User Agent for tracking
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

            # Normalize email to lowercase so the pending request — and the
            # user account minted from it on approval — carry the same
            # canonical form used by login and password-reset.
            email_norm = (str(data.email) or "").strip().lower()

            result = await engine.create_registration_request(
                full_name=data.full_name,
                national_id=data.national_id,
                phone=data.phone,
                email=email_norm,
                subject=data.subject,
                education_level=data.education_level,
                years_of_experience=data.years_of_experience,
                academic_degree=data.academic_degree,
                teacher_rank=data.teacher_rank,
                school_name=data.school_name,
                school_country=data.school_country,
                school_city=data.school_city,
                school_type=data.school_type,
                ip_address=ip_address,
                user_agent=user_agent,
                referred_by=data.referred_by
            )
            
            return result
            
        except ValueError as e:
            raise HTTPException(status_code=400, detail="خطأ في البيانات المرسلة")
    
    @router.post("/direct")
    async def direct_teacher_registration(
        data: TeacherDirectRegistration,
        request: Request,
    ):
        """تسجيل معلم مستقل مباشر بدون مراجعة — Direct Independent-Teacher registration without approval.

        The public "Teacher Experience" (معلم نسق) landing CTA lands here. It mints a
        pre-bootstrap **Independent Teacher** (role=independent_teacher, tenant_id=NULL,
        auto-approved) by delegating to the single canonical IT instant-signup helper
        `_create_independent_teacher_instant`, so there is exactly one IT account-creation
        code path. The frontend then orchestrates MFA enrolment → onboarding wizard →
        POST /independent-teacher/bootstrap (which materialises the IT workspace and stamps
        tenant_type/school_type="independent_teacher"). No stray school-teacher `teachers`
        row or school-teacher permission set is created here.
        """
        import re as _re

        from pg_models import User
        from dependencies import hash_password  # noqa: F401 (kept for parity/imports)
        from shared_models import validate_password_complexity, RegistrationRequest as RegistrationRequestModel
        from sqlalchemy import or_, select as sa_select, func as sa_func
        from routes.registration_routes_mod import _create_independent_teacher_instant

        try:
            validate_password_complexity(data.password)
        except ValueError:
            raise HTTPException(status_code=400, detail="كلمة المرور لا تستوفي متطلبات التعقيد")

        session = db.session

        # Normalize email to lowercase so create, uniqueness, login and reset
        # all agree on the same canonical form (mirrors /auth/register). The
        # uniqueness check matches case-insensitively so legacy uppercase rows
        # still block a differently-cased duplicate.
        email_norm = (str(data.email) or "").strip().lower()

        stmt = sa_select(User).where(
            or_(
                sa_func.lower(User.email) == email_norm,
                User.phone == data.phone,
                User.national_id == data.national_id,
            )
        ).limit(1)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            if (existing.email or "").lower() == email_norm:
                raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
            if existing.phone == data.phone:
                raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً")
            if existing.national_id == data.national_id:
                raise HTTPException(status_code=400, detail="رقم الهوية مسجل مسبقاً")

        # Build the canonical registration payload and delegate to the single
        # IT instant-signup helper. The professional/profile fields the teacher
        # supplied are preserved on the auto-approved registration_requests doc.
        raw_phone = data.phone or ""
        phone_clean = _re.sub(r"[\s\-]", "", raw_phone)

        reg_request = RegistrationRequestModel(
            full_name=data.full_name,
            phone=data.phone,
            account_type="independent_teacher",
            email=email_norm,
            national_id=data.national_id,
            password=data.password,
            subject=data.subject,
            specialization=data.subject,
            educational_level=data.education_level,
            school_name=data.school_name,
            school_city=data.school_city,
            country=data.school_country,
            years_of_experience=(str(data.years_of_experience) if data.years_of_experience is not None else None),
        )

        result = await _create_independent_teacher_instant(
            reg_request, data.full_name, phone_clean, raw_phone,
        )

        logger.info(f"Direct independent-teacher registration: {email_norm}")
        return result

    @router.get("/status/{tracking_code}")
    async def get_request_status(
        tracking_code: str,
        request: Request
    ):
        """تتبع حالة الطلب بكود التتبع (Public)"""
        result = await engine.get_request_status(tracking_code=tracking_code)
        
        if not result:
            raise HTTPException(status_code=404, detail="الطلب غير موجود")
        
        return result
    
    @router.get("/status-by-device")
    async def get_request_status_by_device(
        request: Request
    ):
        """تتبع حالة الطلب بالجهاز (Public)"""
        import hashlib
        
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        data = f"{ip_address or ''}-{user_agent or ''}"
        device_fingerprint = hashlib.sha256(data.encode()).hexdigest()[:32]
        
        result = await engine.get_request_status(device_fingerprint=device_fingerprint)
        
        if not result:
            return {"found": False, "message": "لا يوجد طلب مرتبط بهذا الجهاز"}
        
        return {"found": True, **result}
    
    @router.get("/invite/{invite_code}")
    async def get_invite_info(invite_code: str):
        """الحصول على معلومات الدعوة (Public)"""
        invite = await engine.get_invite_by_code(invite_code)
        
        if not invite:
            raise HTTPException(status_code=404, detail="الدعوة غير موجودة أو منتهية")
        
        # Check expiry
        expires_at = datetime.fromisoformat(invite["expires_at"].replace('Z', '+00:00'))
        if datetime.now() > expires_at.replace(tzinfo=None):
            raise HTTPException(status_code=400, detail="انتهت صلاحية الدعوة")
        
        return {
            "inviter_name": invite.get("inviter_name"),
            "invitee_name": invite["invitee_name"],
            "invitee_email": invite["invitee_email"],
            "valid": True
        }
    
    # ============== ADMIN ENDPOINTS ==============
    
    @router.get("/requests")
    async def get_pending_requests(
        status: Optional[str] = None,
        limit: int = Query(default=100, le=500),
        skip: int = 0,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب طلبات التسجيل المعلقة (Admin Only)"""
        requests = await engine.get_pending_requests(
            status=status,
            limit=limit,
            skip=skip
        )
        
        return {
            "requests": requests,
            "total": len(requests)
        }
    
    @router.get("/requests/{request_id}")
    async def get_request_details(
        request_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب تفاصيل طلب معين (Admin Only)"""
        result = await engine.get_request_status(request_id=request_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="الطلب غير موجود")
        
        # Get full details for admin
        from engines.teacher_registration_engine import TeacherRegistrationEngine
        full_request = await gd_find_one(db.session, "teacher_registration_requests", {"id": request_id})
        
        return full_request
    
    @router.post("/requests/{request_id}/approve")
    async def approve_request(
        request_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """قبول طلب التسجيل (Admin Only)"""
        try:
            result = await engine.approve_request(
                request_id=request_id,
                approved_by=current_user["id"]
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail="خطأ في البيانات المرسلة")
    
    @router.post("/requests/{request_id}/reject")
    async def reject_request(
        request_id: str,
        data: RejectRequest,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """رفض طلب التسجيل (Admin Only)"""
        try:
            result = await engine.reject_request(
                request_id=request_id,
                rejected_by=current_user["id"],
                reason=data.reason
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail="خطأ في البيانات المرسلة")
    
    @router.post("/requests/{request_id}/more-info")
    async def request_more_info(
        request_id: str,
        data: MoreInfoRequest,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """طلب معلومات إضافية (Admin Only)"""
        try:
            result = await engine.request_more_info(
                request_id=request_id,
                requested_by=current_user["id"],
                questions=data.questions
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail="خطأ في البيانات المرسلة")
    
    # ============== TEACHER INVITE ENDPOINTS ==============
    
    @router.post("/invites")
    async def create_invite(
        data: TeacherInviteCreate,
        current_user: dict = Depends(get_current_user)
    ):
        """إنشاء دعوة معلم جديدة"""
        try:
            result = await engine.create_invite(
                inviter_id=current_user["id"],
                invitee_name=data.invitee_name,
                invitee_email=data.invitee_email,
                invitee_phone=data.invitee_phone
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail="خطأ في البيانات المرسلة")
    
    @router.get("/invites/my")
    async def get_my_invites(
        current_user: dict = Depends(get_current_user)
    ):
        """جلب الدعوات التي أرسلتها"""
        invites = await engine.get_user_invites(current_user["id"])
        stats = await engine.get_invite_stats(current_user["id"])
        
        return {
            "invites": invites,
            "stats": stats
        }
    
    # ============== PENDING SCHOOLS ==============
    
    @router.get("/pending-schools")
    async def get_pending_schools(
        limit: int = 100,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب المدارس المعلقة للتواصل (Admin Only)"""
        schools = await engine.get_pending_schools(limit=limit)
        
        return {
            "schools": schools,
            "total": len(schools)
        }
    
    # ============== DROPDOWN DATA ==============
    
    @router.get("/options/subjects")
    async def get_subjects():
        """قائمة المواد الدراسية"""
        return {
            "subjects": [
                {"value": "arabic", "label_ar": "اللغة العربية", "label_en": "Arabic"},
                {"value": "english", "label_ar": "اللغة الإنجليزية", "label_en": "English"},
                {"value": "math", "label_ar": "الرياضيات", "label_en": "Mathematics"},
                {"value": "science", "label_ar": "العلوم", "label_en": "Science"},
                {"value": "physics", "label_ar": "الفيزياء", "label_en": "Physics"},
                {"value": "chemistry", "label_ar": "الكيمياء", "label_en": "Chemistry"},
                {"value": "biology", "label_ar": "الأحياء", "label_en": "Biology"},
                {"value": "islamic", "label_ar": "التربية الإسلامية", "label_en": "Islamic Studies"},
                {"value": "social", "label_ar": "الاجتماعيات", "label_en": "Social Studies"},
                {"value": "computer", "label_ar": "الحاسب الآلي", "label_en": "Computer Science"},
                {"value": "art", "label_ar": "التربية الفنية", "label_en": "Art"},
                {"value": "pe", "label_ar": "التربية البدنية", "label_en": "Physical Education"},
                {"value": "other", "label_ar": "أخرى", "label_en": "Other"},
            ]
        }
    
    @router.get("/options/education-levels")
    async def get_education_levels():
        """قائمة المراحل التعليمية"""
        return {
            "levels": [
                {"value": "kindergarten", "label_ar": "رياض الأطفال", "label_en": "Kindergarten"},
                {"value": "primary", "label_ar": "المرحلة الابتدائية", "label_en": "Primary"},
                {"value": "intermediate", "label_ar": "المرحلة المتوسطة", "label_en": "Intermediate"},
                {"value": "secondary", "label_ar": "المرحلة الثانوية", "label_en": "Secondary"},
                {"value": "all", "label_ar": "جميع المراحل", "label_en": "All Levels"},
            ]
        }
    
    @router.get("/options/teacher-ranks")
    async def get_teacher_ranks():
        """قائمة رتب المعلمين"""
        return {
            "ranks": [
                {"value": "expert", "label_ar": "معلم خبير", "label_en": "Expert Teacher"},
                {"value": "advanced", "label_ar": "معلم متقدم", "label_en": "Advanced Teacher"},
                {"value": "practitioner", "label_ar": "معلم ممارس", "label_en": "Practitioner Teacher"},
                {"value": "assistant", "label_ar": "معلم مساعد", "label_en": "Assistant Teacher"},
            ]
        }
    
    @router.get("/options/academic-degrees")
    async def get_academic_degrees():
        """قائمة المؤهلات العلمية"""
        return {
            "degrees": [
                {"value": "high_school", "label_ar": "ثانوية عامة", "label_en": "High School"},
                {"value": "diploma", "label_ar": "دبلوم", "label_en": "Diploma"},
                {"value": "bachelor", "label_ar": "بكالوريوس", "label_en": "Bachelor's"},
                {"value": "master", "label_ar": "ماجستير", "label_en": "Master's"},
                {"value": "phd", "label_ar": "دكتوراه", "label_en": "PhD"},
            ]
        }
    
    @router.get("/options/school-types")
    async def get_school_types():
        """قائمة أنواع المدارس"""
        return {
            "types": [
                {"value": "public", "label_ar": "حكومية", "label_en": "Public"},
                {"value": "private", "label_ar": "خاصة", "label_en": "Private"},
                {"value": "international", "label_ar": "عالمية", "label_en": "International"},
            ]
        }
    
    return router


# Export
__all__ = ["create_teacher_registration_router"]
