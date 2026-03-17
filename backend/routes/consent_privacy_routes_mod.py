"""
NASSAQ Route Module: Consent & Privacy Engine
User consent management, data privacy, right to deletion, and consent tracking.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone
from enum import Enum
import uuid

from dependencies import (
    db, get_current_user, require_roles, UserRole, logger
)

router = APIRouter()


class ConsentTypeEnum(str, Enum):
    TERMS_OF_SERVICE = "terms_of_service"
    PRIVACY_POLICY = "privacy_policy"
    DATA_COLLECTION = "data_collection"
    PHOTO_CONSENT = "photo_consent"
    FIELD_TRIP = "field_trip"
    MEDICAL_TREATMENT = "medical_treatment"
    COMMUNICATION = "communication"
    MARKETING = "marketing"
    DATA_SHARING = "data_sharing"
    CUSTOM = "custom"


class ConsentStatus(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    PENDING = "pending"


class ConsentRecordCreate(BaseModel):
    consent_type: ConsentTypeEnum
    user_id: Optional[str] = None
    student_id: Optional[str] = None
    granted_by: Optional[str] = None
    status: ConsentStatus = ConsentStatus.GRANTED
    version: Optional[str] = None
    notes: Optional[str] = None
    expires_at: Optional[str] = None


class DataDeletionRequest(BaseModel):
    entity_type: str
    entity_id: str
    reason: str
    confirmation: bool = False


@router.post("/consent/record")
async def record_consent(
    data: ConsentRecordCreate,
    current_user: dict = Depends(get_current_user)
):
    """Record a user's consent decision"""
    school_id = current_user.get("tenant_id")
    consent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    target_user = data.user_id or data.student_id or current_user["id"]

    consent_doc = {
        "id": consent_id,
        "tenant_id": school_id,
        "consent_type": data.consent_type.value,
        "user_id": data.user_id,
        "student_id": data.student_id,
        "target_user": target_user,
        "status": data.status.value,
        "granted_by": data.granted_by or current_user["id"],
        "granted_by_name": current_user.get("full_name"),
        "version": data.version,
        "notes": data.notes,
        "expires_at": data.expires_at,
        "ip_address": None,
        "created_at": now,
        "updated_at": now
    }

    await db.consent_records.insert_one(consent_doc)
    consent_doc.pop("_id", None)
    return consent_doc


@router.get("/consent/user/{user_id}")
async def get_user_consents(
    user_id: str,
    consent_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all consent records for a user"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id, "target_user": user_id}
    if consent_type:
        query["consent_type"] = consent_type

    records = await db.consent_records.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)

    active_consents = {}
    for r in records:
        ct = r.get("consent_type")
        if ct not in active_consents:
            active_consents[ct] = r

    return {"records": records, "active_consents": active_consents, "total": len(records)}


@router.get("/consent/student/{student_id}")
async def get_student_consents(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all consent records for a student (given by parent/guardian)"""
    school_id = current_user.get("tenant_id")
    records = await db.consent_records.find(
        {"tenant_id": school_id, "student_id": student_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    return {"records": records, "total": len(records)}


@router.post("/consent/withdraw")
async def withdraw_consent(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Withdraw a previously granted consent"""
    school_id = current_user.get("tenant_id")
    consent_id = data.get("consent_id")
    reason = data.get("reason", "")

    consent = await db.consent_records.find_one(
        {"id": consent_id, "tenant_id": school_id}
    )
    if not consent:
        raise HTTPException(status_code=404, detail="سجل الموافقة غير موجود")

    now = datetime.now(timezone.utc).isoformat()

    await db.consent_records.update_one(
        {"id": consent_id},
        {"$set": {"status": "withdrawn", "updated_at": now}}
    )

    await db.consent_records.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "consent_type": consent["consent_type"],
        "user_id": consent.get("user_id"),
        "student_id": consent.get("student_id"),
        "target_user": consent.get("target_user"),
        "status": "withdrawn",
        "granted_by": current_user["id"],
        "granted_by_name": current_user.get("full_name"),
        "version": consent.get("version"),
        "notes": f"سحب الموافقة: {reason}",
        "created_at": now,
        "updated_at": now
    })

    return {"message": "تم سحب الموافقة بنجاح", "consent_id": consent_id}


@router.get("/consent/check")
async def check_consent(
    user_id: str,
    consent_type: str,
    current_user: dict = Depends(get_current_user)
):
    """Check if a specific consent is active for a user"""
    school_id = current_user.get("tenant_id")

    latest = await db.consent_records.find_one(
        {"tenant_id": school_id, "target_user": user_id, "consent_type": consent_type},
        {"_id": 0},
        sort=[("created_at", -1)]
    )

    if not latest:
        return {"has_consent": False, "status": "not_found", "consent_type": consent_type}

    is_active = latest.get("status") == "granted"
    if is_active and latest.get("expires_at"):
        if latest["expires_at"] < datetime.now(timezone.utc).isoformat():
            is_active = False

    return {
        "has_consent": is_active,
        "status": latest.get("status"),
        "consent_type": consent_type,
        "granted_at": latest.get("created_at"),
        "expires_at": latest.get("expires_at")
    }


@router.get("/consent/pending")
async def get_pending_consents(
    current_user: dict = Depends(get_current_user)
):
    """Get consents that are pending for the current user"""
    school_id = current_user.get("tenant_id")

    all_types = [e.value for e in ConsentTypeEnum]
    required_types = ["terms_of_service", "privacy_policy", "data_collection"]

    user_consents = await db.consent_records.find(
        {"tenant_id": school_id, "target_user": current_user["id"], "status": "granted"},
        {"_id": 0, "consent_type": 1}
    ).to_list(100)

    granted_types = {c["consent_type"] for c in user_consents}
    pending = [t for t in required_types if t not in granted_types]

    return {
        "pending_consents": pending,
        "has_pending": len(pending) > 0,
        "all_types": all_types,
        "granted_types": list(granted_types)
    }


@router.post("/privacy/data-deletion-request")
async def request_data_deletion(
    data: DataDeletionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Request data deletion (right to be forgotten)"""
    school_id = current_user.get("tenant_id")

    if not data.confirmation:
        raise HTTPException(status_code=400, detail="يجب تأكيد طلب الحذف")

    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    deletion_request = {
        "id": request_id,
        "tenant_id": school_id,
        "entity_type": data.entity_type,
        "entity_id": data.entity_id,
        "reason": data.reason,
        "status": "pending",
        "requested_by": current_user["id"],
        "requested_by_name": current_user.get("full_name"),
        "requested_at": now,
        "reviewed_at": None,
        "reviewed_by": None,
        "completed_at": None
    }

    await db.data_deletion_requests.insert_one(deletion_request)
    deletion_request.pop("_id", None)
    return {"message": "تم تقديم طلب الحذف بنجاح وسيتم مراجعته", "request_id": request_id}


@router.get("/privacy/data-deletion-requests")
async def get_data_deletion_requests(
    status: Optional[str] = None,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ]))
):
    """Get data deletion requests (admin only)"""
    school_id = current_user.get("tenant_id")
    query = {}
    if school_id:
        query["tenant_id"] = school_id
    if status:
        query["status"] = status

    requests = await db.data_deletion_requests.find(query, {"_id": 0}).sort("requested_at", -1).to_list(100)
    return {"requests": requests, "total": len(requests)}


@router.put("/privacy/data-deletion-requests/{request_id}/review")
async def review_deletion_request(
    request_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ]))
):
    """Approve or reject a data deletion request"""
    school_id = current_user.get("tenant_id")
    action = data.get("action")
    notes = data.get("notes", "")

    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="الإجراء يجب أن يكون approve أو reject")

    req = await db.data_deletion_requests.find_one({"id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    new_status = "approved" if action == "approve" else "rejected"

    await db.data_deletion_requests.update_one(
        {"id": request_id},
        {"$set": {
            "status": new_status,
            "reviewed_by": current_user["id"],
            "reviewed_at": now,
            "review_notes": notes
        }}
    )

    if action == "approve":
        entity_type = req.get("entity_type")
        entity_id = req.get("entity_id")
        tenant = req.get("tenant_id")

        if entity_type == "student":
            await db.students.update_one(
                {"id": entity_id, "tenant_id": tenant},
                {"$set": {
                    "full_name": "محذوف",
                    "email": None,
                    "phone": None,
                    "national_id": None,
                    "date_of_birth": None,
                    "address": None,
                    "is_anonymized": True,
                    "anonymized_at": now
                }}
            )

        await db.data_deletion_requests.update_one(
            {"id": request_id},
            {"$set": {"completed_at": now, "status": "completed"}}
        )

    return {"message": f"تم {action} طلب الحذف", "status": new_status}


@router.get("/privacy/data-export/{user_id}")
async def export_user_data(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Export all data for a user (data portability)"""
    school_id = current_user.get("tenant_id")

    if current_user["id"] != user_id and current_user["role"] not in ["platform_admin", "school_principal"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    user_data = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    consents = await db.consent_records.find({"target_user": user_id, "tenant_id": school_id}, {"_id": 0}).to_list(100)
    notifications = await db.notifications.find({"recipient_id": user_id}, {"_id": 0}).to_list(500)
    audit_logs = await db.audit_logs.find({"actor_id": user_id, "tenant_id": school_id}, {"_id": 0}).to_list(500)

    student_data = None
    student = await db.students.find_one({"id": user_id, "tenant_id": school_id}, {"_id": 0})
    if student:
        student_data = {
            "profile": student,
            "attendance": await db.attendance.find({"student_id": user_id, "tenant_id": school_id}, {"_id": 0}).to_list(1000),
            "grades": await db.grades.find({"student_id": user_id}, {"_id": 0}).to_list(500),
            "behaviour": await db.behaviour_records.find({"student_id": user_id, "tenant_id": school_id}, {"_id": 0}).to_list(500),
            "participation": await db.participation_records.find({"student_id": user_id, "tenant_id": school_id}, {"_id": 0}).to_list(500)
        }

    return {
        "export_id": str(uuid.uuid4()),
        "user": user_data,
        "student_data": student_data,
        "consents": consents,
        "notifications_count": len(notifications),
        "audit_logs_count": len(audit_logs),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "format": "json"
    }


@router.get("/privacy/consent-report")
async def get_consent_report(
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ]))
):
    """Get consent compliance report"""
    school_id = current_user.get("tenant_id")

    total_users = await db.users.count_documents({"tenant_id": school_id})

    consent_stats = {}
    for ct in ConsentTypeEnum:
        granted = await db.consent_records.count_documents(
            {"tenant_id": school_id, "consent_type": ct.value, "status": "granted"}
        )
        denied = await db.consent_records.count_documents(
            {"tenant_id": school_id, "consent_type": ct.value, "status": "denied"}
        )
        withdrawn = await db.consent_records.count_documents(
            {"tenant_id": school_id, "consent_type": ct.value, "status": "withdrawn"}
        )
        consent_stats[ct.value] = {
            "granted": granted,
            "denied": denied,
            "withdrawn": withdrawn,
            "compliance_rate": round(granted / max(1, total_users) * 100, 1)
        }

    pending_deletions = await db.data_deletion_requests.count_documents(
        {"tenant_id": school_id, "status": "pending"}
    )

    return {
        "total_users": total_users,
        "consent_stats": consent_stats,
        "pending_deletion_requests": pending_deletions,
        "report_date": datetime.now(timezone.utc).isoformat()
    }
