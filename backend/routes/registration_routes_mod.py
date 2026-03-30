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
    """
    Unified rejection endpoint — works for any request type.
    """
    if not data.reason or len(data.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="يرجى إدخال سبب الرفض")

    from engines.approval_engine import approval_engine
    result = await approval_engine.reject(request_id, data.reason.strip(), current_user)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("detail", "خطأ غير متوقع"))
    return result


@router.post("/registration-requests/{request_id}/request-info")
async def request_more_info_unified(
    request_id: str,
    data: RequestMoreInfoData,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Unified info-request endpoint — works for any request type.
    """
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
    Submit additional information (called by teacher):
    1. Update request with new info
    2. Change status to pending_review
    """
    request = await db.registration_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="طلب التسجيل غير موجود")
    
    if request.get("status") not in ("more_info_requested", "info_required"):
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
