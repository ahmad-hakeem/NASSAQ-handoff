"""
NASSAQ Route Module: Registration requests
Unified Approval Engine API endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from bson_compat import ObjectId
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
async def check_school_name(name: str = Query(..., min_length=2)):
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
    submission_data = request_data.model_dump()

    request_doc = {
        "id": request_id,
        **submission_data,
        "status": "pending_review",
        "source": "public_signup",
        "payload_snapshot": submission_data,
        "linked_entity_type": None,
        "linked_entity_id": None,
        "linked_user_id": None,
        "linked_school_id": None,
        "review_notes": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "priority": "normal",
        "created_at": now,
        "updated_at": now
    }
    
    await db.registration_requests.insert_one(request_doc)
    logger.info(f"[ApprovalQueue] Created registration request id={request_id[:8]}… type={request_data.account_type} status=pending_review source=public_signup")

    try:
        from engines.approval_engine import _emit_event, _get_db
        await _emit_event(_get_db(), "approval_request_created", request_id, request_data.account_type,
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
            "actor_name": request_data.full_name,
            "actor_id": None,
            "details": {
                "account_type": request_data.account_type,
                "source": "public_signup",
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
    source: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get all registration requests (admin only) with optional filters"""
    query = {}
    if status:
        query["status"] = status
    if account_type:
        query["account_type"] = account_type
    if source:
        query["source"] = source
    
    requests = await db.registration_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
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
    result = await approval_engine.approve(request_id, current_user, notes=notes)
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

    request = await db.registration_requests.find_one({"id": request_id}, {"_id": 0})
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
    
    update_result = await db.registration_requests.update_one(
        {"id": request_id, "status": current_status},
        {"$set": update_data}
    )
    if update_result.modified_count == 0:
        raise HTTPException(status_code=409, detail="الطلب تغيّرت حالته — يرجى المحاولة مرة أخرى")

    try:
        from engines.approval_engine import _emit_event, _get_db
        await _emit_event(_get_db(), "approval_request_info_submitted", request_id,
                          request.get("account_type", "unknown"),
                          status_before=current_status, status_after="pending_review")
    except Exception:
        pass
    
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
    events = await db.approval_events.find(
        {"request_id": request_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(100)
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
