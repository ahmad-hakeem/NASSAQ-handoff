"""
NASSAQ Route Module: Registration requests
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import uuid, os, logging, json, random, re, io, base64

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)

from shared_models import (
    RegistrationRequest, RegistrationRequestResponse, ApproveRequestData, RejectRequestData, RequestMoreInfoData
)

router = APIRouter()



# ============== HELPER: FUZZY SCHOOL NAME MATCHING ==============
def _normalize_arabic(text: str) -> str:
    """Normalize Arabic text for fuzzy comparison"""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r'[أإآ]', 'ا', text)
    text = text.replace('ة', 'ه').replace('ى', 'ي')
    text = re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower()

def _fuzzy_similarity(a: str, b: str) -> float:
    """Simple fuzzy similarity ratio between two strings (0-1)"""
    a, b = _normalize_arabic(a), _normalize_arabic(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    longer = max(len(a), len(b))
    common = 0
    for i, c in enumerate(a):
        if i < len(b) and c == b[i]:
            common += 1
    if a in b or b in a:
        return max(0.7, common / longer)
    return common / longer

@router.get("/registration-requests/check-school-name")
async def check_school_name(name: str = Query(..., min_length=2)):
    """Check if a similar school name already exists (fuzzy match)"""
    normalized = _normalize_arabic(name)
    if len(normalized) < 2:
        return {"similar_schools": [], "is_duplicate": False}

    existing_schools = await db.schools.find(
        {}, {"_id": 0, "id": 1, "name": 1, "city": 1, "status": 1}
    ).to_list(500)

    pending_requests = await db.registration_requests.find(
        {"account_type": "school", "status": {"$in": ["pending", "pending_review"]}},
        {"_id": 0, "school_name": 1, "school_city": 1}
    ).to_list(200)

    similar = []
    for s in existing_schools:
        score = _fuzzy_similarity(name, s.get("name", ""))
        if score >= 0.6:
            similar.append({
                "name": s.get("name"),
                "city": s.get("city"),
                "source": "registered",
                "similarity": round(score, 2)
            })

    for r in pending_requests:
        score = _fuzzy_similarity(name, r.get("school_name", ""))
        if score >= 0.6:
            similar.append({
                "name": r.get("school_name"),
                "city": r.get("school_city"),
                "source": "pending_request",
                "similarity": round(score, 2)
            })

    similar.sort(key=lambda x: x["similarity"], reverse=True)
    return {
        "similar_schools": similar[:5],
        "is_duplicate": any(s["similarity"] >= 0.85 for s in similar)
    }


# ============== REGISTRATION REQUESTS ROUTES ==============
@router.post("/registration-requests", response_model=RegistrationRequestResponse)
async def create_registration_request(request_data: RegistrationRequest):
    """Create a new registration request for admin review"""

    raw_phone = request_data.phone or ''
    phone_clean = re.sub(r'[\s\-]', '', raw_phone)
    if phone_clean:
        phone_digits = re.sub(r'^(\+?966|0)', '', phone_clean)
        if len(phone_digits) >= 7:
            spaced_regex = ''.join(f'[\\s\\-]*{re.escape(c)}' for c in phone_digits)
            phone_regex = f"(\\+?966|0)?{spaced_regex}$"
            existing_user_phone = await db.users.find_one({
                "phone": {"$regex": phone_regex},
                "is_active": True
            })
            if existing_user_phone:
                raise HTTPException(
                    status_code=400,
                    detail="يوجد حساب نشط مسجل بنفس رقم الهاتف"
                )
            existing_pending_phone = await db.registration_requests.find_one({
                "phone": {"$regex": phone_regex},
                "status": {"$in": ["pending", "pending_review"]}
            })
            if existing_pending_phone:
                raise HTTPException(
                    status_code=400,
                    detail="يوجد طلب تسجيل معلق بنفس رقم الهاتف"
                )

    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    request_doc = {
        "id": request_id,
        **request_data.model_dump(),
        "status": "pending_review",
        "created_at": now,
        "updated_at": now
    }
    
    await db.registration_requests.insert_one(request_doc)

    try:
        audit_entry = {
            "id": str(uuid.uuid4()),
            "action": "account_request_created",
            "event_type": "Account Request Created",
            "entity_type": "registration_request",
            "entity_id": request_id,
            "actor_name": request_data.full_name,
            "actor_id": None,
            "details": {
                "account_type": request_data.account_type,
                "phone": request_data.phone,
                "email": request_data.email,
                "school_name": request_data.school_name
            },
            "timestamp": now,
            "created_at": now
        }
        await db.audit_logs.insert_one(audit_entry)
    except Exception as e:
        logger.error(f"Failed to create audit log for registration request: {e}")

    try:
        admin_users = await db.users.find(
            {"role": {"$in": ["platform_admin", "platform_operations_manager"]}, "is_active": True},
            {"_id": 0, "id": 1}
        ).to_list(50)

        notif_docs = []
        for admin in admin_users:
            notif_docs.append({
                "id": str(uuid.uuid4()),
                "recipient_id": admin["id"],
                "notification_type": "registration_request",
                "title": "طلب تسجيل جديد",
                "message": f"طلب تسجيل جديد من {request_data.full_name} ({request_data.account_type})",
                "read_status": False,
                "action_url": "/admin/users?tab=requests",
                "metadata": {"request_id": request_id, "account_type": request_data.account_type},
                "created_at": now
            })
        if notif_docs:
            await db.notifications.insert_many(notif_docs)
    except Exception as e:
        logger.error(f"Failed to send admin notifications for registration request: {e}")
    
    return RegistrationRequestResponse(
        id=request_id,
        full_name=request_data.full_name,
        phone=request_data.phone,
        email=request_data.email,
        national_id=request_data.national_id,
        account_type=request_data.account_type,
        status="pending_review",
        subject=request_data.subject,
        educational_level=request_data.educational_level,
        school_mentioned=request_data.school_mentioned,
        country=request_data.country,
        created_at=request_doc["created_at"]
    )

@router.get("/registration-requests")
async def get_registration_requests(
    status: Optional[str] = None,
    account_type: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get all registration requests (admin only)"""
    query = {}
    if status:
        query["status"] = status
    if account_type:
        query["account_type"] = account_type
    
    requests = await db.registration_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"requests": requests, "total": len(requests)}

@router.get("/registration-requests/{request_id}")
async def get_registration_request(
    request_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get a single registration request by ID"""
    request = await db.registration_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")
    return request

@router.put("/registration-requests/{request_id}/status")
async def update_registration_request_status(
    request_id: str,
    status: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update registration request status (admin only) - Simple status update"""
    result = await db.registration_requests.update_one(
        {"id": request_id},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")
    return {"message": "تم تحديث حالة الطلب"}


def generate_teacher_id():
    """Generate unique Teacher ID like TCH-948271"""
    import random
    return f"TCH-{random.randint(100000, 999999)}"

def generate_qr_code_data(teacher_id: str, user_id: str):
    """Generate QR code data for teacher"""
    import base64
    import json
    qr_data = {
        "type": "teacher",
        "teacher_id": teacher_id,
        "user_id": user_id,
        "platform": "NASSAQ"
    }
    # Encode as base64 JSON
    return base64.b64encode(json.dumps(qr_data).encode()).decode()

def generate_secure_password(length=10):
    """Generate a secure random password"""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


@router.post("/registration-requests/{request_id}/approve")
async def approve_teacher_request(
    request_id: str,
    data: ApproveRequestData,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Approve a teacher registration request:
    1. Validate the request exists and is pending
    2. Check for duplicate email/phone/national_id
    3. Create user account
    4. Generate Teacher ID
    5. Generate QR Code
    6. Create login credentials
    7. Update request status
    8. Return credentials to admin
    """
    # Step 1: Get the request
    request = await db.registration_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")
    
    if request.get("status") not in ["pending", "pending_review"]:
        raise HTTPException(status_code=400, detail="هذا الطلب تم معالجته مسبقاً")
    
    # Step 2: Validate - Check for duplicates
    email = request.get("email")
    phone = request.get("phone")
    national_id = request.get("national_id")
    
    if email:
        existing_email = await db.users.find_one({"email": email})
        if existing_email:
            raise HTTPException(status_code=400, detail="يوجد حساب مسجل مسبقًا بنفس البريد الإلكتروني")
    
    if phone:
        existing_phone = await db.users.find_one({"phone": phone})
        if existing_phone:
            raise HTTPException(status_code=400, detail="يوجد حساب مسجل مسبقًا بنفس رقم الهاتف")
    
    if national_id:
        existing_id = await db.users.find_one({"national_id": national_id})
        if existing_id:
            raise HTTPException(status_code=400, detail="يوجد حساب مسجل مسبقًا بنفس رقم الهوية")
    
    # Step 3: Create user account
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    temp_password = generate_secure_password()
    
    new_user = {
        "id": user_id,
        "email": email,
        "password_hash": hash_password(temp_password),
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
        "created_by": current_user["id"],
        "account_type": "independent_teacher"
    }
    
    await db.users.insert_one(new_user)
    
    # Step 4: Generate Teacher ID
    teacher_id = generate_teacher_id()
    
    # Step 5: Generate QR Code
    qr_code = generate_qr_code_data(teacher_id, user_id)
    
    # Save teacher record
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
        "school_id": None,  # Independent teacher
        "qr_code": qr_code,
        "is_active": True,
        "created_at": now,
        "created_by": current_user["id"]
    }
    await db.teachers.insert_one(teacher_record)
    
    # Save QR code record
    qr_record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "teacher_id": teacher_id,
        "qr_data": qr_code,
        "created_at": now
    }
    await db.teacher_qr_codes.insert_one(qr_record)
    
    # Step 7: Update request status
    await db.registration_requests.update_one(
        {"id": request_id},
        {
            "$set": {
                "status": "approved",
                "approved_by": current_user["id"],
                "approved_by_name": current_user.get("full_name"),
                "approved_at": now,
                "updated_at": now
            }
        }
    )
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "teacher_request_approved",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "registration_request",
        "target_id": request_id,
        "target_name": request.get("full_name"),
        "details": {
            "user_id": user_id,
            "teacher_id": teacher_id,
            "email": email
        },
        "timestamp": now
    }
    await db.audit_logs.insert_one(audit_log)
    
    # Step 8: Generate message template
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
    
    return {
        "success": True,
        "message": "تم إنشاء حساب المعلم بنجاح",
        "user_id": user_id,
        "teacher_id": teacher_id,
        "email": email,
        "temporary_password": temp_password,
        "qr_code": qr_code,
        "message_template": message_template
    }


@router.post("/registration-requests/{request_id}/approve-school")
async def approve_school_request(
    request_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    request = await db.registration_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")

    if request.get("account_type") != "school":
        raise HTTPException(status_code=400, detail="هذا الطلب ليس طلب تسجيل مدرسة")

    if request.get("status") not in ["pending", "pending_review"]:
        raise HTTPException(status_code=400, detail="هذا الطلب تم معالجته مسبقاً")

    school_email = request.get("school_email") or request.get("email")
    school_phone = request.get("school_phone") or request.get("phone")
    school_name = request.get("school_name", "")
    principal_name = request.get("full_name", "")

    if school_email:
        existing_email = await db.users.find_one({"email": school_email})
        if existing_email:
            raise HTTPException(status_code=400, detail="يوجد حساب مسجل مسبقًا بنفس البريد الإلكتروني")

    now = datetime.now(timezone.utc).isoformat()
    year_suffix = datetime.now().strftime("%y")
    country_code = "SA"
    last_school = await db.schools.find_one(
        {"code": {"$regex": f"^NSS-{country_code}-{year_suffix}-"}},
        sort=[("code", -1)]
    )
    if last_school and last_school.get("code"):
        try:
            last_num = int(last_school["code"].split("-")[-1])
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    school_code = f"NSS-{country_code}-{year_suffix}-{str(next_num).zfill(4)}"

    existing_code = await db.schools.find_one({"code": school_code})
    if existing_code:
        school_code = f"NSS-{country_code}-{year_suffix}-{str(next_num + 1).zfill(4)}"

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
        "created_by": current_user.get("id", current_user.get("user_id"))
    }
    await db.schools.insert_one(school_doc)

    temp_password = generate_secure_password(12)
    principal_id = str(uuid.uuid4())
    principal_doc = {
        "id": principal_id,
        "email": school_email,
        "password_hash": hash_password(temp_password),
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
        "created_by": current_user.get("id", current_user.get("user_id"))
    }
    await db.users.insert_one(principal_doc)

    default_settings = await db.default_settings.find_one({"id": "default-school-settings"}, {"_id": 0})
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
            "updated_at": now
        }
        await db.school_settings.insert_one(school_settings)

    await db.registration_requests.update_one(
        {"id": request_id},
        {
            "$set": {
                "status": "approved",
                "approved_by": current_user["id"],
                "approved_by_name": current_user.get("full_name"),
                "approved_at": now,
                "updated_at": now,
                "school_id": school_id,
                "principal_user_id": principal_id,
                "school_code": school_code
            }
        }
    )

    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "school_request_approved",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "registration_request",
        "target_id": request_id,
        "target_name": school_name,
        "details": {
            "school_id": school_id,
            "school_code": school_code,
            "principal_id": principal_id,
            "principal_email": school_email
        },
        "timestamp": now
    }
    await db.audit_logs.insert_one(audit_log)

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

    logger.info(f"School registration approved: {school_name} (code: {school_code}, principal: {school_email})")

    return {
        "success": True,
        "message": "تم إنشاء المدرسة وحساب المدير بنجاح",
        "school_id": school_id,
        "school_code": school_code,
        "principal_id": principal_id,
        "email": school_email,
        "temporary_password": temp_password,
        "message_template": message_template
    }


@router.post("/registration-requests/{request_id}/reject")
async def reject_teacher_request(
    request_id: str,
    data: RejectRequestData,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Reject a teacher registration request:
    1. Update request status to rejected
    2. Save rejection reason
    3. Log the action
    """
    if not data.reason or len(data.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="يرجى إدخال سبب الرفض")
    
    request = await db.registration_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")
    
    if request.get("status") == "approved":
        raise HTTPException(status_code=400, detail="لا يمكن رفض طلب تم قبوله مسبقاً")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.registration_requests.update_one(
        {"id": request_id},
        {
            "$set": {
                "status": "rejected",
                "rejection_reason": data.reason,
                "rejected_by": current_user["id"],
                "rejected_by_name": current_user.get("full_name"),
                "rejected_at": now,
                "updated_at": now
            }
        }
    )
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "teacher_request_rejected",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "registration_request",
        "target_id": request_id,
        "target_name": request.get("full_name"),
        "details": {
            "reason": data.reason
        },
        "timestamp": now
    }
    await db.audit_logs.insert_one(audit_log)
    
    return {
        "success": True,
        "message": "تم رفض الطلب بنجاح",
        "rejection_reason": data.reason
    }


@router.post("/registration-requests/{request_id}/request-info")
async def request_more_info(
    request_id: str,
    data: RequestMoreInfoData,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Request additional information from the teacher:
    1. Update request status to more_info_requested
    2. Save the message
    3. Log the action
    """
    if not data.message or len(data.message.strip()) < 10:
        raise HTTPException(status_code=400, detail="يرجى إدخال المعلومات المطلوبة بشكل واضح")
    
    request = await db.registration_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")
    
    if request.get("status") in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="لا يمكن طلب معلومات لطلب تم معالجته")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.registration_requests.update_one(
        {"id": request_id},
        {
            "$set": {
                "status": "more_info_requested",
                "additional_info_request": data.message,
                "info_requested_by": current_user["id"],
                "info_requested_by_name": current_user.get("full_name"),
                "info_requested_at": now,
                "updated_at": now
            }
        }
    )
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "teacher_request_info_requested",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "registration_request",
        "target_id": request_id,
        "target_name": request.get("full_name"),
        "details": {
            "message": data.message
        },
        "timestamp": now
    }
    await db.audit_logs.insert_one(audit_log)
    
    return {
        "success": True,
        "message": "تم إرسال طلب المعلومات الإضافية",
        "info_requested": data.message
    }


@router.post("/registration-requests/{request_id}/submit-info")
async def submit_additional_info(
    request_id: str,
    info: dict
):
    """
    Submit additional information (called by teacher):
    1. Update request with new info
    2. Change status to pending_review
    """
    request = await db.registration_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")
    
    if request.get("status") != "more_info_requested":
        raise HTTPException(status_code=400, detail="لا يوجد طلب معلومات معلق")
    
    now = datetime.now(timezone.utc).isoformat()
    
    update_data = {
        "status": "pending_review",
        "additional_info_response": info.get("response", ""),
        "additional_info_submitted_at": now,
        "updated_at": now
    }
    
    # Update any provided fields
    for key in ["national_id", "email", "phone", "specialization", "subject"]:
        if info.get(key):
            update_data[key] = info[key]
    
    await db.registration_requests.update_one(
        {"id": request_id},
        {"$set": update_data}
    )
    
    return {
        "success": True,
        "message": "تم إرسال المعلومات الإضافية بنجاح وسيتم مراجعة طلبك قريباً"
    }


@router.post("/student-enrollment")
async def create_student_enrollment(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Student enrollment request (by parent or admin)"""
    school_id = current_user.get("tenant_id")
    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    enrollment_doc = {
        "id": request_id,
        "tenant_id": school_id,
        "type": "student_enrollment",
        "student_name": data.get("student_name"),
        "student_national_id": data.get("national_id"),
        "date_of_birth": data.get("date_of_birth"),
        "gender": data.get("gender"),
        "grade_level": data.get("grade_level"),
        "parent_name": data.get("parent_name") or current_user.get("full_name"),
        "parent_phone": data.get("parent_phone") or current_user.get("phone"),
        "parent_email": data.get("parent_email") or current_user.get("email"),
        "parent_user_id": current_user["id"],
        "previous_school": data.get("previous_school"),
        "health_notes": data.get("health_notes"),
        "status": "pending",
        "submitted_by": current_user["id"],
        "submitted_at": now,
        "updated_at": now
    }

    await db.registration_requests.insert_one(enrollment_doc)
    enrollment_doc.pop("_id", None)
    return enrollment_doc


@router.get("/student-enrollment")
async def get_student_enrollments(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get student enrollment requests"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id, "type": "student_enrollment"}
    if status:
        query["status"] = status

    if current_user.get("role") == "parent":
        query["parent_user_id"] = current_user["id"]

    requests = await db.registration_requests.find(query, {"_id": 0}).sort("submitted_at", -1).to_list(100)
    return {"requests": requests, "total": len(requests)}


@router.post("/student-enrollment/{request_id}/approve")
async def approve_student_enrollment(
    request_id: str,
    data: dict = {},
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Approve a student enrollment"""
    req = await db.registration_requests.find_one({"id": request_id, "type": "student_enrollment"})
    if not req:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")

    school_id = req.get("tenant_id") or current_user.get("tenant_id")
    now = datetime.now(timezone.utc).isoformat()
    student_id = str(uuid.uuid4())

    student_doc = {
        "id": student_id,
        "tenant_id": school_id,
        "full_name": req.get("student_name"),
        "national_id": req.get("student_national_id"),
        "date_of_birth": req.get("date_of_birth"),
        "gender": req.get("gender"),
        "grade_level": data.get("grade_level") or req.get("grade_level"),
        "class_id": data.get("class_id"),
        "class_name": data.get("class_name"),
        "parent_phone": req.get("parent_phone"),
        "parent_id": req.get("parent_user_id"),
        "parent_user_id": req.get("parent_user_id"),
        "enrollment_status": "enrolled",
        "is_active": True,
        "created_at": now,
        "updated_at": now
    }
    await db.students.insert_one(student_doc)

    await db.registration_requests.update_one(
        {"id": request_id},
        {"$set": {
            "status": "approved",
            "approved_by": current_user["id"],
            "approved_at": now,
            "student_id": student_id,
            "updated_at": now
        }}
    )

    return {"message": "تم قبول طلب التسجيل وإنشاء حساب الطالب", "student_id": student_id}


@router.post("/student-enrollment/{request_id}/reject")
async def reject_student_enrollment(
    request_id: str,
    data: dict = {},
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Reject a student enrollment"""
    req = await db.registration_requests.find_one({"id": request_id, "type": "student_enrollment"})
    if not req:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    await db.registration_requests.update_one(
        {"id": request_id},
        {"$set": {
            "status": "rejected",
            "rejected_by": current_user["id"],
            "rejected_at": now,
            "rejection_reason": data.get("reason", ""),
            "updated_at": now
        }}
    )

    return {"message": "تم رفض طلب التسجيل"}
