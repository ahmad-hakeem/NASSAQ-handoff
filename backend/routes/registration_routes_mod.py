"""
NASSAQ Route Module: Registration requests
Unified Approval Engine API endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from middleware.rate_limiter import rate_store
from utils.trusted_proxy import extract_client_ip
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token, create_refresh_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)

from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate, dict_to_model
from shared_models import (
    RegistrationRequest, RegistrationRequestResponse, ApproveRequestData, RejectRequestData, RequestMoreInfoData,
    UserResponse,
)
from pg_models import School, User as UserModel, SchoolSettings
from utils.school_code import generate_school_code, insert_school_with_unique_code

router = APIRouter()



def _normalize_arabic(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r'[أإآ]', 'ا', text)
    text = text.replace('ة', 'ه').replace('ى', 'ي')
    text = re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower()

def _fuzzy_similarity(a: str, b: str) -> float:
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
async def check_school_name(request: Request, name: str = Query(..., min_length=2)):
    client_ip = extract_client_ip(request)
    rate_key = f"school_name_check:{client_ip}"
    limited, _, retry_after = await rate_store.is_rate_limited(rate_key, 20, 60)
    if limited:
        raise HTTPException(
            status_code=429,
            detail="طلبات كثيرة، يرجى المحاولة لاحقاً.",
            headers={"Retry-After": str(retry_after)},
        )

    normalized = _normalize_arabic(name)
    if len(normalized) < 2:
        return {"is_duplicate": False}

    # Only check registered schools (never pending requests — those are internal
    # pipeline data and must not be exposed to unauthenticated callers).
    # Use normalised exact-match only: fuzzy matching would allow prefix-scanning
    # enumeration of the tenant list.  An exact match only confirms a conflict
    # the caller already knows the full name for, so it reveals nothing new.
    existing_schools = await gd_find(db.session, "schools", {}, limit=500)
    for s in existing_schools:
        if _normalize_arabic(s.get("name", "")) == normalized:
            return {"is_duplicate": True}

    return {"is_duplicate": False}


async def _generate_school_code_instant() -> str:
    """Generate the next sequential school code for public SA signups.

    Thin wrapper over the shared, hardened generator so the public instant
    signup and the platform-admin create-school path mint codes from a single
    consolidated implementation. The collision-safe INSERT (with regeneration)
    lives in ``insert_school_with_unique_code`` — this only produces a first
    candidate.
    """
    return await generate_school_code(db.session, country="SA")


async def _create_school_instant(
    request_data: RegistrationRequest,
    full_name: str,
    phone_clean: str,
    raw_phone: str,
):
    """
    Direct sign-up flow for new schools: creates the School + active Principal user
    and returns an auth token so the user is immediately logged in.
    """
    from sqlalchemy import select

    session = db.session
    now_iso = datetime.now(timezone.utc).isoformat()

    school_email = (request_data.school_email or "").strip().lower()
    school_phone = (request_data.school_phone or "").strip() or (phone_clean or raw_phone)
    school_name = (request_data.school_name or "").strip()
    school_city = (request_data.school_city or "").strip()
    user_password = (request_data.password or "")

    if not school_name:
        raise HTTPException(status_code=400, detail="يرجى إدخال اسم المدرسة")
    if not school_email:
        raise HTTPException(status_code=400, detail="يرجى إدخال البريد الإلكتروني للمدرسة")
    if not school_city:
        raise HTTPException(status_code=400, detail="يرجى إدخال مدينة المدرسة")
    if not user_password or len(user_password) < 8:
        raise HTTPException(status_code=400, detail="يجب أن تتكون كلمة المرور من 8 أحرف على الأقل")

    from sqlalchemy import func as _sa_func
    stmt = select(UserModel).where(_sa_func.lower(UserModel.email) == school_email).limit(1)
    result = await session.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="يوجد حساب مسجل مسبقًا بنفس البريد الإلكتروني")

    capacity_raw = request_data.student_capacity or "500"
    try:
        student_capacity = int(capacity_raw)
    except (ValueError, TypeError):
        student_capacity = 500

    school_id = str(uuid.uuid4())
    principal_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    password_hash_value = hash_password(user_password)

    def _build_school_doc(code: str) -> dict:
        return {
            "id": school_id,
            "name": school_name,
            "name_ar": school_name,
            "name_en": "",
            "code": code,
            "email": school_email,
            "phone": school_phone,
            "address": (request_data.school_address or "").strip(),
            "city": school_city,
            "region": "",
            "country": "SA",
            "status": "active",
            "student_capacity": student_capacity,
            "current_students": 0,
            "current_teachers": 0,
            "school_type": "public",
            "principal_name": full_name,
            "principal_email": school_email,
            "principal_phone": school_phone,
            "created_at": now_iso,
            "updated_at": now_iso,
            "created_by": None,
        }

    # Insert the school with a bounded, savepoint-based retry that silently
    # regenerates the auto-generated code on a schools_code_key collision
    # (double-submit, concurrent signup, or cross-path collision with the
    # admin create-school flow). Only genuine non-code errors propagate.
    school_code, school_obj = await insert_school_with_unique_code(
        session, _build_school_doc, country="SA"
    )

    principal_obj = dict_to_model(UserModel, {
        "id": principal_id,
        "email": school_email,
        "password_hash": password_hash_value,
        "full_name": full_name,
        "role": "school_principal",
        "school_id": school_id,
        "tenant_id": school_id,
        "phone": school_phone,
        "is_active": True,
        "must_change_password": False,
        "preferred_language": "ar",
        "preferred_theme": "light",
        "permissions": ["manage_school", "manage_teachers", "manage_students", "view_reports", "manage_settings"],
        "created_at": now_iso,
        "updated_at": now_iso,
        "created_by": None,
    })
    session.add(principal_obj)
    await session.flush()

    try:
        default_settings = await gd_find_one(session, "default_settings", {"id": "default-school-settings"})
        if default_settings:
            from routes.school_settings_mod import normalize_school_settings_doc
            settings_obj = dict_to_model(SchoolSettings, normalize_school_settings_doc({
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
                "created_at": now_iso,
                "updated_at": now_iso,
            }))
            session.add(settings_obj)
            await session.flush()
    except Exception as e:
        logger.warning(f"[InstantSignup] Skipped default school settings seed for {school_id}: {e}")

    submission_data = request_data.model_dump()
    submission_data.pop("password", None)
    submission_data["account_type"] = "school"
    submission_data["full_name"] = full_name

    extra_fields = {k: v for k, v in submission_data.items() if k not in ("id", "type", "name", "email", "phone", "school_name", "status", "source", "password")}
    extra_fields["account_type"] = "school"
    extra_fields["full_name"] = full_name
    extra_fields["auto_approved"] = True

    request_doc = {
        "id": request_id,
        "type": "school",
        "name": full_name,
        "email": school_email,
        "phone": phone_clean or raw_phone,
        "school_name": school_name,
        "status": "approved",
        "source": "public_signup_instant",
        "data": extra_fields,
        "payload_snapshot": submission_data,
        "linked_entity_type": "school",
        "linked_entity_id": school_id,
        "review_notes": "Auto-approved (instant sign-up)",
        "reviewed_at": now_iso,
        "reviewed_by": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await gd_insert(session, "registration_requests", request_doc)

    try:
        audit_entry = {
            "id": str(uuid.uuid4()),
            "action": "account_auto_approved",
            "event_type": "School Account Auto-Approved",
            "entity_type": "school",
            "entity_id": school_id,
            "actor_name": full_name,
            "actor_id": principal_id,
            "details": {
                "account_type": "school",
                "source": "public_signup_instant",
                "school_code": school_code,
                "request_id": request_id,
            },
            "timestamp": now_iso,
            "created_at": now_iso,
        }
        await gd_insert(session, "audit_logs", audit_entry)
    except Exception as e:
        logger.error(f"[InstantSignup] Failed to write audit log: {e}")

    token_payload = {
        "sub": principal_id,
        "role": "school_principal",
        "tenant_id": school_id,
        "school_id": school_id,
    }
    access_token = create_access_token(token_payload)
    try:
        import jwt as _jwt
        access_jti = _jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM]).get("jti")
    except Exception:
        access_jti = None
    refresh = create_refresh_token(token_payload, remember_me=False, linked_access_jti=access_jti)

    user_response = UserResponse(
        id=principal_id,
        email=school_email,
        full_name=full_name,
        full_name_en=None,
        role=UserRole("school_principal"),
        tenant_id=school_id,
        phone=school_phone,
        avatar_url=None,
        is_active=True,
        must_change_password=False,
        preferred_language="ar",
        preferred_theme="light",
        created_at=now_iso,
        updated_at=now_iso,
    )

    logger.info(f"[InstantSignup] School created and auto-logged-in: {school_name} (code={school_code}, principal={principal_id[:8]}…)")

    return {
        "id": request_id,
        "status": "approved",
        "account_type": "school",
        "school_id": school_id,
        "school_code": school_code,
        "school_name": school_name,
        "full_name": full_name,
        "email": school_email,
        "phone": phone_clean or raw_phone,
        "created_at": now_iso,
        "access_token": access_token,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": user_response.model_dump(),
    }


async def _create_independent_teacher_instant(
    request_data: RegistrationRequest,
    full_name: str,
    phone_clean: str,
    raw_phone: str,
):
    """
    Direct sign-up flow for Independent Teachers (IT). Per spec the IT
    account is created **pre-bootstrap**: an active `users` row with
    role=independent_teacher and tenant_id=NULL is inserted, and an auth
    token is returned. The frontend then orchestrates MFA enrolment →
    onboarding wizard → POST /independent-teacher/bootstrap (which
    materialises the synthetic itw_{user_id} workspace).
    """
    from sqlalchemy import select

    session = db.session
    now_iso = datetime.now(timezone.utc).isoformat()

    teacher_email = (request_data.email or "").strip().lower()
    user_password = (request_data.password or "")

    if not teacher_email:
        raise HTTPException(status_code=400, detail="يرجى إدخال البريد الإلكتروني")
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", teacher_email):
        raise HTTPException(status_code=400, detail="صيغة البريد الإلكتروني غير صحيحة")
    if not user_password or len(user_password) < 8:
        raise HTTPException(status_code=400, detail="يجب أن تتكون كلمة المرور من 8 أحرف على الأقل")

    from sqlalchemy import func as _sa_func
    stmt = select(UserModel).where(_sa_func.lower(UserModel.email) == teacher_email).limit(1)
    result = await session.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="يوجد حساب مسجل مسبقًا بنفس البريد الإلكتروني")

    user_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    password_hash_value = hash_password(user_password)

    user_obj = dict_to_model(UserModel, {
        "id": user_id,
        "email": teacher_email,
        "password_hash": password_hash_value,
        "full_name": full_name,
        "role": "independent_teacher",
        "school_id": None,
        "tenant_id": None,
        "phone": phone_clean or raw_phone,
        "is_active": True,
        "must_change_password": False,
        "preferred_language": "ar",
        "preferred_theme": "light",
        "permissions": [],
        "created_at": now_iso,
        "updated_at": now_iso,
        "created_by": None,
    })
    session.add(user_obj)
    await session.flush()

    submission_data = request_data.model_dump()
    submission_data.pop("password", None)
    submission_data["account_type"] = "independent_teacher"
    submission_data["full_name"] = full_name

    extra_fields = {k: v for k, v in submission_data.items() if k not in ("id", "type", "name", "email", "phone", "school_name", "status", "source", "password")}
    extra_fields["account_type"] = "independent_teacher"
    extra_fields["full_name"] = full_name
    extra_fields["auto_approved"] = True

    request_doc = {
        "id": request_id,
        "type": "independent_teacher",
        "name": full_name,
        "email": teacher_email,
        "phone": phone_clean or raw_phone,
        "school_name": None,
        "status": "approved",
        "source": "public_signup_instant",
        "data": extra_fields,
        "payload_snapshot": submission_data,
        "linked_entity_type": "user",
        "linked_entity_id": user_id,
        "review_notes": "Auto-approved (instant IT sign-up)",
        "reviewed_at": now_iso,
        "reviewed_by": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await gd_insert(session, "registration_requests", request_doc)

    try:
        audit_entry = {
            "id": str(uuid.uuid4()),
            "action": "account_auto_approved",
            "event_type": "Independent Teacher Account Auto-Approved",
            "entity_type": "user",
            "entity_id": user_id,
            "actor_name": full_name,
            "actor_id": user_id,
            "details": {
                "account_type": "independent_teacher",
                "source": "public_signup_instant",
                "request_id": request_id,
            },
            "timestamp": now_iso,
            "created_at": now_iso,
        }
        await gd_insert(session, "audit_logs", audit_entry)
    except Exception as e:
        logger.error(f"[InstantSignup] Failed to write IT audit log: {e}")

    # Pre-bootstrap: tenant_id is NULL by design — frontend will route
    # the user through /auth/mfa/enroll → /teacher/onboarding before any
    # workspace-scoped API call succeeds.
    token_payload = {
        "sub": user_id,
        "role": "independent_teacher",
        "tenant_id": None,
        "school_id": None,
    }
    access_token = create_access_token(token_payload)
    try:
        import jwt as _jwt
        access_jti = _jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM]).get("jti")
    except Exception:
        access_jti = None
    refresh = create_refresh_token(token_payload, remember_me=False, linked_access_jti=access_jti)

    user_response = UserResponse(
        id=user_id,
        email=teacher_email,
        full_name=full_name,
        full_name_en=None,
        role=UserRole("independent_teacher"),
        tenant_id=None,
        phone=phone_clean or raw_phone,
        avatar_url=None,
        is_active=True,
        must_change_password=False,
        preferred_language="ar",
        preferred_theme="light",
        created_at=now_iso,
        updated_at=now_iso,
    )

    logger.info(f"[InstantSignup] Independent teacher created and auto-logged-in: user={user_id[:8]}… email={teacher_email}")

    return {
        "id": request_id,
        "status": "approved",
        "account_type": "independent_teacher",
        "user_id": user_id,
        "full_name": full_name,
        "email": teacher_email,
        "phone": phone_clean or raw_phone,
        "created_at": now_iso,
        "access_token": access_token,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": user_response.model_dump(),
    }


@router.post("/registration-requests", response_model=None)
async def create_registration_request(request_data: RegistrationRequest):
    """
    Create a new registration request.

    For account_type == "school" this is an INSTANT sign-up: the school + an
    active principal user are created immediately and an auth token is returned
    so the front end can log the user in directly.

    For other account types the legacy "pending admin review" flow still applies.
    """

    VALID_ACCOUNT_TYPES = {"school", "teacher", "independent_teacher", "parent", "student"}
    account_type = (request_data.account_type or "").strip().lower()
    if not account_type or account_type not in VALID_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="يرجى اختيار نوع الحساب"
        )

    full_name = (request_data.full_name or "").strip()
    if not full_name or len(full_name) < 2:
        raise HTTPException(
            status_code=400,
            detail="يرجى إدخال الاسم الكامل"
        )

    raw_phone = request_data.phone or ''
    phone_clean = re.sub(r'[\s\-]', '', raw_phone)
    if phone_clean:
        phone_digits = re.sub(r'^(\+?966|0)', '', phone_clean)
        if len(phone_digits) >= 7:
            spaced_regex = ''.join(f'[\\s\\-]*{re.escape(c)}' for c in phone_digits)
            phone_regex = f"(\\+?966|0)?{spaced_regex}$"
            existing_user_phone = await gd_find_one(db.session, "users", {
                "phone": {"$regex": phone_regex},
                "is_active": True
            })
            if existing_user_phone:
                raise HTTPException(
                    status_code=400,
                    detail="يوجد حساب نشط مسجل بنفس رقم الهاتف"
                )
            existing_pending_phone = await gd_find_one(db.session, "registration_requests", {
                "phone": {"$regex": phone_regex},
                "status": {"$in": ["pending", "pending_review"]}
            })
            if existing_pending_phone:
                raise HTTPException(
                    status_code=400,
                    detail="يوجد طلب تسجيل معلق بنفس رقم الهاتف"
                )

    if account_type == "school":
        return await _create_school_instant(request_data, full_name, phone_clean, raw_phone)

    if account_type == "independent_teacher":
        return await _create_independent_teacher_instant(request_data, full_name, phone_clean, raw_phone)

    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    submission_data = request_data.model_dump()
    submission_data.pop("password", None)
    submission_data["account_type"] = account_type
    submission_data["full_name"] = full_name

    extra_fields = {k: v for k, v in submission_data.items() if k not in ("id", "type", "name", "email", "phone", "school_name", "status", "source", "password")}
    extra_fields["account_type"] = account_type
    extra_fields["full_name"] = full_name

    request_doc = {
        "id": request_id,
        "type": account_type,
        "name": full_name,
        "email": (request_data.email or "").strip().lower() or None,
        "phone": phone_clean or raw_phone,
        "school_name": (request_data.school_name or "").strip() or None,
        "status": "pending_review",
        "source": "public_signup",
        "data": extra_fields,
        "payload_snapshot": submission_data,
        "linked_entity_type": None,
        "linked_entity_id": None,
        "review_notes": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "created_at": now,
        "updated_at": now
    }
    
    await gd_insert(db.session, "registration_requests", request_doc)
    logger.info(f"[ApprovalQueue] Created registration request id={request_id[:8]}… type={account_type} status=pending_review source=public_signup")

    try:
        from engines.approval_engine import _emit_event, _get_db
        await _emit_event(_get_db(), "approval_request_created", request_id, account_type,
                          status_after="pending_review",
                          details={"source": "public_signup"})
    except Exception as e:
        logger.error(f"Failed to emit request_created event: {e}")

    try:
        audit_entry = {
            "id": str(uuid.uuid4()),
            "action": "account_request_created",
            "event_type": "Account Request Created",
            "entity_type": "registration_request",
            "entity_id": request_id,
            "actor_name": full_name,
            "actor_id": None,
            "details": {
                "account_type": account_type,
                "source": "public_signup",
            },
            "timestamp": now,
            "created_at": now
        }
        await gd_insert(db.session, "audit_logs", audit_entry)
    except Exception as e:
        logger.error(f"Failed to create audit log for registration request: {e}")

    try:
        admin_users = await gd_find(db.session, "users", {"role": {"$in": ["platform_admin", "platform_operations_manager"]}, "is_active": True}, limit=50)

        account_type_labels_ar = {
            "student": "طالب",
            "parent": "ولي أمر",
            "teacher": "معلم",
            "school": "مدرسة",
            "principal": "مدير مدرسة",
            "supervisor": "مشرف",
            "staff": "موظف",
        }
        account_type_label_ar = account_type_labels_ar.get(account_type, account_type)
        title_ar = f"طلب تسجيل جديد — {account_type_label_ar}"
        message_ar = f"تقدّم {full_name} بطلب تسجيل جديد بصفة {account_type_label_ar}"

        notif_docs = []
        for admin in admin_users:
            notif_docs.append({
                "id": str(uuid.uuid4()),
                "user_id": admin["id"],
                "type": "registration_request",
                "title": title_ar,
                "message": message_ar,
                "is_read": False,
                "action_url": "/admin/users?tab=requests",
                "metadata": {"request_id": request_id, "account_type": account_type, "account_type_label_ar": account_type_label_ar},
                "created_at": now
            })
        if notif_docs:
            await gd_insert_many(db.session, "notifications", notif_docs)
    except Exception as e:
        logger.error(f"Failed to send admin notifications for registration request: {e}")
    
    return RegistrationRequestResponse(
        id=request_id,
        full_name=full_name,
        phone=request_data.phone,
        email=request_data.email,
        national_id=request_data.national_id,
        account_type=account_type,
        status="pending_review",
        school_name=request_data.school_name,
        school_email=request_data.school_email,
        school_phone=request_data.school_phone,
        school_city=request_data.school_city,
        school_address=request_data.school_address,
        student_capacity=request_data.student_capacity,
        school_code=request_data.school_code,
        specialization=request_data.specialization,
        subject=request_data.subject,
        educational_level=request_data.educational_level,
        school_mentioned=request_data.school_mentioned,
        country=request_data.country,
        years_of_experience=request_data.years_of_experience,
        created_at=request_doc["created_at"]
    )

@router.get("/registration-requests")
async def get_registration_requests(
    status: Optional[str] = None,
    account_type: Optional[str] = None,
    source: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_SUB_ADMIN]))
):
    """Get all registration requests (admin only) with optional filters"""
    query = {}
    if status:
        query["status"] = status
    if account_type:
        query["account_type"] = account_type
    if source:
        query["source"] = source
    
    requests = await gd_find(db.session, "registration_requests", query, order_by="created_at", desc_order=True, limit=1000)
    logger.info(f"[ApprovalQueue] GET /registration-requests query={query} → {len(requests)} result(s)")
    return {"requests": requests, "total": len(requests)}

@router.get("/registration-requests/{request_id}")
async def get_registration_request(
    request_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get a single registration request with full details, review history, and lifecycle events"""
    from engines.approval_engine import approval_engine
    details = await approval_engine.get_request_details(request_id)
    if not details:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")
    return details


@router.get("/approval-types")
async def get_approval_types(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get all registered approval request types and their display metadata"""
    from engines.approval_engine import approval_engine
    return {"types": approval_engine.get_registered_types()}


@router.post("/registration-requests/{request_id}/approve")
async def approve_request_unified(
    request_id: str,
    data: ApproveRequestData = ApproveRequestData(),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Unified approval endpoint — dispatches to the correct handler
    based on the request's account_type field.
    """
    from engines.approval_engine import approval_engine
    notes = data.admin_note or ''
    # `school_id` is the reviewer's choice of which school an approved School
    # Teacher joins — the signup form's school field is optional free text.
    context = {"school_id": data.school_id}
    result = await approval_engine.approve(request_id, current_user, notes=notes, context=context)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    response = {
        "success": True,
        "message": result.message,
        "request_type": result.request_type,
        **result.created_entities,
    }
    if result.credentials:
        response["credentials"] = result.credentials
        response["temporary_password"] = result.credentials.get("temporary_password")
        response["email"] = result.credentials.get("email")
    if result.message_template:
        response["message_template"] = result.message_template
    return response


@router.post("/registration-requests/{request_id}/approve-school")
async def approve_school_request_compat(
    request_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Backward-compatible alias — routes to unified approve"""
    from engines.approval_engine import approval_engine
    result = await approval_engine.approve(request_id, current_user)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    response = {
        "success": True,
        "message": result.message,
        "request_type": result.request_type,
        **result.created_entities,
    }
    if result.credentials:
        response["credentials"] = result.credentials
        response["temporary_password"] = result.credentials.get("temporary_password")
        response["email"] = result.credentials.get("email")
    if result.message_template:
        response["message_template"] = result.message_template
    return response


@router.post("/registration-requests/{request_id}/reject")
async def reject_request_unified(
    request_id: str,
    data: RejectRequestData,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Unified rejection endpoint — works for any request type."""
    if not data.reason or len(data.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="يرجى إدخال سبب الرفض")

    from engines.approval_engine import approval_engine
    result = await approval_engine.reject(request_id, data.reason.strip(), current_user)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("detail", "خطأ غير متوقع"))
    return result


@router.post("/registration-requests/{request_id}/under-review")
async def mark_under_review_unified(
    request_id: str,
    data: dict = Body(default={}),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Mark a request as under review"""
    notes = (data.get("notes") or "").strip()

    from engines.approval_engine import approval_engine
    result = await approval_engine.mark_under_review(request_id, notes, current_user)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("detail", "خطأ غير متوقع"))
    return result


@router.post("/registration-requests/{request_id}/archive")
async def archive_request_unified(
    request_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Archive a completed (approved/rejected) request"""
    from engines.approval_engine import approval_engine
    result = await approval_engine.archive(request_id, current_user)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("detail", "خطأ غير متوقع"))
    return result


@router.post("/registration-requests/{request_id}/cancel")
async def cancel_request_unified(
    request_id: str,
    data: dict = Body(default={}),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Cancel a pending request"""
    reason = (data.get("reason") or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="يرجى إدخال سبب الإلغاء")

    from engines.approval_engine import approval_engine
    result = await approval_engine.cancel(request_id, reason, current_user)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("detail", "خطأ غير متوقع"))
    return result


@router.post("/registration-requests/{request_id}/request-info")
async def request_more_info_unified(
    request_id: str,
    data: RequestMoreInfoData,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Unified info-request endpoint — works for any request type."""
    if not data.message or len(data.message.strip()) < 10:
        raise HTTPException(status_code=400, detail="يرجى إدخال المعلومات المطلوبة بشكل واضح")

    from engines.approval_engine import approval_engine
    result = await approval_engine.request_info(request_id, data.message.strip(), current_user)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("detail", "خطأ غير متوقع"))
    return result


@router.post("/registration-requests/{request_id}/submit-info")
async def submit_additional_info(
    request_id: str,
    info: dict
):
    """
    Submit additional information (called by applicant):
    Transition from info_required → pending_review
    """
    from engines.approval_engine import validate_transition

    request = await gd_find_one(db.session, "registration_requests", {"id": request_id})
    if not request:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")
    
    current_status = request.get("status", "")
    valid, err_msg = validate_transition(current_status, "pending_review")
    if not valid:
        raise HTTPException(status_code=400, detail="لا يوجد طلب معلومات معلق")
    
    now = datetime.now(timezone.utc).isoformat()
    
    ALLOWED_INFO_FIELDS = {"national_id", "email", "phone", "specialization", "subject"}
    update_data = {
        "status": "pending_review",
        "additional_info_response": str(info.get("response", ""))[:2000],
        "additional_info_submitted_at": now,
        "updated_at": now
    }
    
    for key in ALLOWED_INFO_FIELDS:
        if info.get(key):
            update_data[key] = str(info[key])[:200]
    
    update_result = await gd_update_one(db.session, "registration_requests", {"id": request_id, "status": current_status}, update_data)
    if update_result == 0:
        raise HTTPException(status_code=409, detail="الطلب تغيّرت حالته — يرجى المحاولة مرة أخرى")

    try:
        from engines.approval_engine import _emit_event, _get_db
        await _emit_event(_get_db(), "approval_request_info_submitted", request_id,
                          request.get("account_type", "unknown"),
                          status_before=current_status, status_after="pending_review")
    except Exception as e:
        logger.warning(f"Failed to emit approval event for request {request_id}: {e}")
    
    return {
        "success": True,
        "message": "تم إرسال المعلومات الإضافية بنجاح وسيتم مراجعة طلبك قريباً"
    }


@router.get("/approval-queue")
async def get_approval_queue(
    status: Optional[str] = None,
    request_type: Optional[str] = None,
    source: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Consolidated approval queue endpoint"""
    from engines.approval_engine import approval_engine
    filters = {}
    if status:
        filters["status"] = status
    if request_type:
        filters["request_type"] = request_type
    if source:
        filters["source"] = source
    result = await approval_engine.get_queue(filters)
    return result


@router.get("/approval-events/{request_id}")
async def get_approval_events(
    request_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get lifecycle events for a specific approval request"""
    events = await gd_find(db.session, "approval_events", {"request_id": request_id}, order_by="timestamp", desc_order=True, limit=100)
    return {"events": events, "total": len(events)}


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
        "source": "parent_portal",
        "submitted_by": current_user["id"],
        "submitted_at": now,
        "updated_at": now
    }

    await gd_insert(db.session, "registration_requests", enrollment_doc)
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

    requests = await gd_find(db.session, "registration_requests", query, order_by="submitted_at", desc_order=True, limit=100)
    return {"requests": requests, "total": len(requests)}


@router.post("/student-enrollment/{request_id}/approve")
async def approve_student_enrollment(
    request_id: str,
    data: dict = {},
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Approve a student enrollment"""
    req = await gd_find_one(db.session, "registration_requests", {"id": request_id, "type": "student_enrollment"})
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
    if student_doc.get("class_id"):
        _enr_class = await gd_find_one(
            db.session, "classes",
            {"id": student_doc["class_id"], "school_id": school_id},
        )
        if _enr_class:
            # Capacity gate — net +1 for the approved enrolment.
            from engines.entity_counts import enforce_class_capacity
            await enforce_class_capacity(db.session, _enr_class, school_id)
    await gd_insert(db.session, "students", student_doc)

    # Recompute the school's stored counts from live rows (Task #826) so the
    # denormalized columns stay accurate instead of drifting.
    from engines.entity_counts import reconcile_school_counts, reconcile_class_counts
    await reconcile_school_counts(db.session, school_id)
    # Recompute the class counter too (Task #829) so classes.current_students
    # never drifts via the enrollment-approval path.
    if student_doc.get("class_id"):
        await reconcile_class_counts(db.session, student_doc["class_id"], school_id)

    await gd_update_one(db.session, "registration_requests", {"id": request_id}, {
            "status": "approved",
            "approved_by": current_user["id"],
            "approved_at": now,
            "student_id": student_id,
            "updated_at": now
        })

    return {"message": "تم قبول طلب التسجيل وإنشاء حساب الطالب", "student_id": student_id}


@router.post("/student-enrollment/{request_id}/reject")
async def reject_student_enrollment(
    request_id: str,
    data: dict = {},
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Reject a student enrollment"""
    req = await gd_find_one(db.session, "registration_requests", {"id": request_id, "type": "student_enrollment"})
    if not req:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "registration_requests", {"id": request_id}, {
            "status": "rejected",
            "rejected_by": current_user["id"],
            "rejected_at": now,
            "rejection_reason": data.get("reason", ""),
            "updated_at": now
        })

    return {"message": "تم رفض طلب التسجيل"}
