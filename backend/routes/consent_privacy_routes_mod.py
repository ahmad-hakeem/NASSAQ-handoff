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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


router = APIRouter()


_ADMIN_ROLES = frozenset({
    UserRole.PLATFORM_ADMIN.value,
    UserRole.SCHOOL_PRINCIPAL.value,
    UserRole.SCHOOL_ADMIN.value,
    UserRole.SCHOOL_SUB_ADMIN.value,
})


def _is_consent_admin(current_user: dict) -> bool:
    return current_user.get("role", "") in _ADMIN_ROLES


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
    """Record a user's consent decision.

    SECURITY: A caller may record consent only for themselves or, if they
    are a parent/guardian, for a student linked to their account.  Admin
    roles (principal, school_admin, sub_admin, platform_admin) may record
    on behalf of any user in their tenant.
    """
    from engines.sql_utils import gd_find_one as _gd1
    school_id = current_user.get("tenant_id")
    caller_id = current_user["id"]
    role = current_user.get("role", "")

    target_user_id = data.user_id
    target_student_id = data.student_id

    if not _is_consent_admin(current_user):
        if target_user_id and target_user_id != caller_id:
            raise HTTPException(status_code=403, detail="لا يمكنك تسجيل موافقة لمستخدم آخر")
        if target_student_id:
            if role == "parent":
                parent = await _gd1(db.session, "parents", {"user_id": caller_id})
                linked = parent and target_student_id in (parent.get("student_ids") or [])
                if not linked:
                    link = await _gd1(db.session, "guardian_links", {"parent_user_id": caller_id, "student_id": target_student_id})
                    linked = bool(link)
                if not linked:
                    raise HTTPException(status_code=403, detail="لا يمكنك تسجيل موافقة لطالب غير مرتبط بحسابك")
            else:
                raise HTTPException(status_code=403, detail="غير مصرح")

    target_user = target_user_id or target_student_id or caller_id

    consent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    consent_doc = {
        "id": consent_id,
        "tenant_id": school_id,
        "consent_type": data.consent_type.value,
        "user_id": data.user_id,
        "student_id": data.student_id,
        "target_user": target_user,
        "status": data.status.value,
        "granted_by": caller_id,
        "granted_by_name": current_user.get("full_name"),
        "version": data.version,
        "notes": data.notes,
        "expires_at": data.expires_at,
        "ip_address": None,
        "created_at": now,
        "updated_at": now
    }

    await gd_insert(db.session, "consent_records", consent_doc)
    consent_doc.pop("_id", None)
    return consent_doc


@router.get("/consent/user/{user_id}")
async def get_user_consents(
    user_id: str,
    consent_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all consent records for a user.

    SECURITY: Callers may only view their own consent records.  Admin
    roles may view any user's records within their tenant.
    """
    if not _is_consent_admin(current_user) and current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="لا يمكنك عرض سجلات موافقة مستخدم آخر")

    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id, "target_user": user_id}
    if consent_type:
        query["consent_type"] = consent_type

    records = await gd_find(db.session, "consent_records", query, order_by="created_at", desc_order=True, limit=100)

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
    """Get all consent records for a student (given by parent/guardian).

    SECURITY: Only the student's guardians or admin roles may view a
    student's consent records.  Any other caller receives 403.
    """
    if not _is_consent_admin(current_user):
        from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
        allowed = await can_view_student(db.session, current_user, student_id)
        require_can_view_student_sync_check(allowed)

    school_id = current_user.get("tenant_id")
    records = await gd_find(db.session, "consent_records", {"tenant_id": school_id, "student_id": student_id}, order_by="created_at", desc_order=True, limit=100)

    return {"records": records, "total": len(records)}


@router.post("/consent/withdraw")
async def withdraw_consent(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Withdraw a previously granted consent.

    SECURITY: A caller may only withdraw consent records that belong to
    them (target_user == caller) or, if they are a guardian, to a
    student linked to their account.  Admin roles may withdraw any record
    in their tenant.
    """
    school_id = current_user.get("tenant_id")
    consent_id = data.get("consent_id")
    reason = data.get("reason", "")

    consent = await gd_find_one(db.session, "consent_records", {"id": consent_id, "tenant_id": school_id})
    if not consent:
        raise HTTPException(status_code=404, detail="سجل الموافقة غير موجود")

    if not _is_consent_admin(current_user):
        caller_id = current_user["id"]
        record_target = consent.get("target_user")
        record_student = consent.get("student_id")
        if record_target and record_target == caller_id:
            pass
        elif record_student:
            role = current_user.get("role", "")
            if role == "parent":
                parent = await gd_find_one(db.session, "parents", {"user_id": caller_id})
                linked = parent and record_student in (parent.get("student_ids") or [])
                if not linked:
                    link = await gd_find_one(db.session, "guardian_links", {"parent_user_id": caller_id, "student_id": record_student})
                    linked = bool(link)
                if not linked:
                    raise HTTPException(status_code=403, detail="لا يمكنك سحب موافقة لطالب غير مرتبط بحسابك")
            else:
                raise HTTPException(status_code=403, detail="غير مصرح")
        else:
            raise HTTPException(status_code=403, detail="غير مصرح")

    now = datetime.now(timezone.utc).isoformat()

    await gd_update_one(db.session, "consent_records", {"id": consent_id}, {"status": "withdrawn", "updated_at": now})

    await gd_insert(db.session, "consent_records", {
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
    """Check if a specific consent is active for a user.

    SECURITY: Callers may only check their own consent status.  Admin
    roles may check any user's status within their tenant.
    """
    if not _is_consent_admin(current_user) and current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="لا يمكنك الاستعلام عن حالة موافقة مستخدم آخر")

    school_id = current_user.get("tenant_id")

    latest = await gd_find_one(db.session, "consent_records", {"tenant_id": school_id, "target_user": user_id, "consent_type": consent_type},
        sort=[("created_at", -1)])

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
    """Get consents that are pending for the current user.

    SECURITY: Always scoped to the caller's own records.
    """
    school_id = current_user.get("tenant_id")

    all_types = [e.value for e in ConsentTypeEnum]
    required_types = ["terms_of_service", "privacy_policy", "data_collection"]

    user_consents = await gd_find(db.session, "consent_records", {"tenant_id": school_id, "target_user": current_user["id"], "status": "granted"}, limit=100)

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

    await gd_insert(db.session, "data_deletion_requests", deletion_request)
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

    requests = await gd_find(db.session, "data_deletion_requests", query, order_by="requested_at", desc_order=True, limit=100)
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

    req = await gd_find_one(db.session, "data_deletion_requests", {"id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    new_status = "approved" if action == "approve" else "rejected"

    await gd_update_one(db.session, "data_deletion_requests", {"id": request_id}, {
            "status": new_status,
            "reviewed_by": current_user["id"],
            "reviewed_at": now,
            "review_notes": notes
        })

    if action == "approve":
        entity_type = req.get("entity_type")
        entity_id = req.get("entity_id")
        tenant = req.get("tenant_id")

        if entity_type == "student":
            await gd_update_one(db.session, "students", {"id": entity_id, "tenant_id": tenant}, {
                    "full_name": "محذوف",
                    "email": None,
                    "phone": None,
                    "national_id": None,
                    "date_of_birth": None,
                    "address": None,
                    "is_anonymized": True,
                    "anonymized_at": now
                })

        await gd_update_one(db.session, "data_deletion_requests", {"id": request_id}, {"completed_at": now, "status": "completed"})

    return {"message": f"تم {action} طلب الحذف", "status": new_status}


@router.get("/privacy/data-export/{user_id}")
async def export_user_data(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Export all data for a user (data portability).

    SECURITY: Only the user themselves or platform/school admins may export
    another user's data.
    """
    school_id = current_user.get("tenant_id")

    if current_user["id"] != user_id and current_user.get("role") not in ("platform_admin", "school_principal"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    user_data = await gd_find_one(db.session, "users", {"id": user_id})
    consents = await gd_find(db.session, "consent_records", {"target_user": user_id, "tenant_id": school_id}, limit=100)
    notifications = await gd_find(db.session, "notifications", {"recipient_id": user_id}, limit=500)
    audit_logs = await gd_find(db.session, "audit_logs", {"actor_id": user_id, "tenant_id": school_id}, limit=500)

    student_data = None
    student = await gd_find_one(db.session, "students", {"id": user_id, "tenant_id": school_id})
    if student:
        student_data = {
            "profile": student,
            "attendance": await gd_find(db.session, "attendance", {"student_id": user_id, "tenant_id": school_id}, limit=1000),
            "grades": await gd_find(db.session, "grades", {"student_id": user_id}, limit=500),
            "behaviour": await gd_find(db.session, "behaviour_records", {"student_id": user_id, "tenant_id": school_id}, limit=500),
            "participation": await gd_find(db.session, "participation_records", {"student_id": user_id, "tenant_id": school_id}, limit=500)
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

    total_users = await gd_count(db.session, "users", {"tenant_id": school_id})

    consent_stats = {}
    for ct in ConsentTypeEnum:
        granted = await gd_count(db.session, "consent_records", {"tenant_id": school_id, "consent_type": ct.value, "status": "granted"})
        denied = await gd_count(db.session, "consent_records", {"tenant_id": school_id, "consent_type": ct.value, "status": "denied"})
        withdrawn = await gd_count(db.session, "consent_records", {"tenant_id": school_id, "consent_type": ct.value, "status": "withdrawn"})
        consent_stats[ct.value] = {
            "granted": granted,
            "denied": denied,
            "withdrawn": withdrawn,
            "compliance_rate": round(granted / max(1, total_users) * 100, 1)
        }

    pending_deletions = await gd_count(db.session, "data_deletion_requests", {"tenant_id": school_id, "status": "pending"})

    return {
        "total_users": total_users,
        "consent_stats": consent_stats,
        "pending_deletion_requests": pending_deletions,
        "report_date": datetime.now(timezone.utc).isoformat()
    }
