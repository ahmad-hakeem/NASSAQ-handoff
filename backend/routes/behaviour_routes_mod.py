"""
NASSAQ Route Module: Behaviour engine endpoints
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
from enum import Enum

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

router = APIRouter()



# ============== BEHAVIOUR ENGINE ROUTES ==============
# Import behaviour engine models
class BehaviourCategoryEnum(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

class BehaviourSeverityEnum(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"

class BehaviourStatusEnum(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    ARCHIVED = "archived"

class BehaviourTypeCreate(BaseModel):
    name_ar: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    category: BehaviourCategoryEnum
    default_severity: BehaviourSeverityEnum
    default_points: int = 0
    auto_escalate: bool = False
    escalation_threshold: Optional[int] = None

class BehaviourRecordCreate(BaseModel):
    student_id: str
    behaviour_type_id: str
    title: str
    incident_date: str
    description: Optional[str] = None
    class_id: Optional[str] = None
    category: Optional[BehaviourCategoryEnum] = None
    severity: Optional[BehaviourSeverityEnum] = None
    points: Optional[int] = None
    incident_location: Optional[str] = None
    witnesses: List[str] = []
    requires_follow_up: bool = False
    follow_up_date: Optional[str] = None
    is_confidential: bool = False
    visible_to_parent: bool = True

class DisciplinaryActionCreate(BaseModel):
    behaviour_record_id: str
    student_id: str
    action_type: str
    description: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post("/behaviour-types")
async def create_behaviour_type(
    data: BehaviourTypeCreate,
    school_id: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a new behaviour type"""
    type_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    type_doc = {
        "id": type_id,
        "tenant_id": school_id,
        "name_ar": data.name_ar,
        "name_en": data.name_en,
        "description": data.description,
        "category": data.category.value,
        "default_severity": data.default_severity.value,
        "default_points": data.default_points,
        "auto_escalate": data.auto_escalate,
        "escalation_threshold": data.escalation_threshold,
        "is_active": True,
        "is_global": school_id is None,
        "created_at": now,
        "created_by": current_user["id"],
    }
    
    await db.behaviour_types.insert_one(type_doc)
    type_doc.pop("_id", None)
    return type_doc


@router.get("/behaviour-types")
async def get_behaviour_types(
    school_id: Optional[str] = None,
    category: Optional[str] = None,
    include_global: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """Get behaviour types"""
    query = {"is_active": True}
    
    if school_id:
        if include_global:
            query["$or"] = [
                {"tenant_id": school_id},
                {"is_global": True}
            ]
        else:
            query["tenant_id"] = school_id
    else:
        query["is_global"] = True
    
    if category:
        query["category"] = category
    
    types = await db.behaviour_types.find(query, {"_id": 0}).to_list(1000)
    return {"behaviour_types": types, "total": len(types)}


@router.post("/behaviour-types/seed-defaults")
async def seed_default_behaviour_types(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Seed default behaviour types"""
    default_types = [
        {"name_ar": "تميز أكاديمي", "name_en": "Academic Excellence", "category": "positive", "default_severity": "minor", "default_points": 10},
        {"name_ar": "مساعدة الزملاء", "name_en": "Helping Peers", "category": "positive", "default_severity": "minor", "default_points": 5},
        {"name_ar": "مشاركة فعالة", "name_en": "Active Participation", "category": "positive", "default_severity": "minor", "default_points": 3},
        {"name_ar": "سلوك قيادي", "name_en": "Leadership Behaviour", "category": "positive", "default_severity": "moderate", "default_points": 15},
        {"name_ar": "تأخر عن الحصة", "name_en": "Late to Class", "category": "negative", "default_severity": "minor", "default_points": -2},
        {"name_ar": "عدم إحضار الواجب", "name_en": "Missing Homework", "category": "negative", "default_severity": "minor", "default_points": -3},
        {"name_ar": "تشويش في الفصل", "name_en": "Classroom Disruption", "category": "negative", "default_severity": "moderate", "default_points": -5, "auto_escalate": True, "escalation_threshold": 3},
        {"name_ar": "استخدام الهاتف", "name_en": "Phone Usage", "category": "negative", "default_severity": "moderate", "default_points": -5},
        {"name_ar": "تنمر", "name_en": "Bullying", "category": "negative", "default_severity": "major", "default_points": -20, "auto_escalate": True, "escalation_threshold": 1},
        {"name_ar": "شجار", "name_en": "Fighting", "category": "negative", "default_severity": "severe", "default_points": -30, "auto_escalate": True, "escalation_threshold": 1},
        {"name_ar": "غش في الاختبار", "name_en": "Cheating", "category": "negative", "default_severity": "major", "default_points": -25, "auto_escalate": True, "escalation_threshold": 1},
    ]
    
    count = 0
    for bt in default_types:
        existing = await db.behaviour_types.find_one({"name_ar": bt["name_ar"], "is_global": True})
        if not existing:
            bt["id"] = str(uuid.uuid4())
            bt["tenant_id"] = None
            bt["is_global"] = True
            bt["is_active"] = True
            bt["created_at"] = datetime.now(timezone.utc).isoformat()
            bt["created_by"] = current_user["id"]
            await db.behaviour_types.insert_one(bt)
            count += 1
    
    return {"message": f"تم إضافة {count} نوع سلوك افتراضي", "added": count}


@router.post("/behaviour-records")
async def create_behaviour_record(
    data: BehaviourRecordCreate,
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.TEACHER, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Record a new behaviour incident"""
    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Get behaviour type
    behaviour_type = await db.behaviour_types.find_one({"id": data.behaviour_type_id}, {"_id": 0})
    if not behaviour_type:
        raise HTTPException(status_code=404, detail="نوع السلوك غير موجود")
    
    # Get student
    student = await db.students.find_one({"id": data.student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    # Edit window (48 hours)
    from datetime import timedelta
    edit_until = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    
    record_doc = {
        "id": record_id,
        "tenant_id": school_id,
        "student_id": data.student_id,
        "student_name": student.get("full_name"),
        "class_id": data.class_id or student.get("class_id"),
        "behaviour_type_id": data.behaviour_type_id,
        "behaviour_type_name": behaviour_type.get("name_ar"),
        "category": (data.category.value if data.category else behaviour_type.get("category")),
        "severity": (data.severity.value if data.severity else behaviour_type.get("default_severity")),
        "title": data.title,
        "description": data.description,
        "points": data.points if data.points is not None else behaviour_type.get("default_points", 0),
        "incident_date": data.incident_date,
        "incident_location": data.incident_location,
        "witnesses": data.witnesses,
        "status": "pending",
        "requires_follow_up": data.requires_follow_up,
        "follow_up_date": data.follow_up_date,
        "parent_notified": False,
        "principal_reviewed": False,
        "is_confidential": data.is_confidential,
        "visible_to_parent": data.visible_to_parent,
        "recorded_by": current_user["id"],
        "recorded_by_name": current_user.get("full_name"),
        "recorded_at": now,
        "editable_until": edit_until,
    }
    
    await db.behaviour_records.insert_one(record_doc)
    
    # Auto-escalation check
    if behaviour_type.get("auto_escalate"):
        from datetime import timedelta
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        count = await db.behaviour_records.count_documents({
            "tenant_id": school_id,
            "student_id": data.student_id,
            "behaviour_type_id": data.behaviour_type_id,
            "incident_date": {"$gte": thirty_days_ago}
        })
        threshold = behaviour_type.get("escalation_threshold", 3)
        if count >= threshold:
            await db.behaviour_records.update_one(
                {"id": record_id},
                {"$set": {"status": "escalated", "requires_follow_up": True}}
            )
            record_doc["status"] = "escalated"
            record_doc["requires_follow_up"] = True
    
    # Audit log
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "behaviour_recorded",
        "action_category": "behaviour",
        "actor_id": current_user["id"],
        "actor_name": current_user.get("full_name", ""),
        "target_type": "student",
        "target_id": data.student_id,
        "target_name": student.get("full_name"),
        "tenant_id": school_id,
        "details": {"behaviour_type": behaviour_type.get("name_ar"), "category": record_doc["category"]},
        "timestamp": now
    })
    
    record_doc.pop("_id", None)
    return record_doc


@router.get("/behaviour-records/student/{student_id}")
async def get_student_behaviour_history(
    student_id: str,
    school_id: str,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get behaviour history for a student"""
    query = {"tenant_id": school_id, "student_id": student_id}
    
    if category:
        query["category"] = category
    
    if start_date or end_date:
        query["incident_date"] = {}
        if start_date:
            query["incident_date"]["$gte"] = start_date
        if end_date:
            query["incident_date"]["$lte"] = end_date
    
    total = await db.behaviour_records.count_documents(query)
    records = await db.behaviour_records.find(query, {"_id": 0}).sort("incident_date", -1).skip(skip).limit(limit).to_list(limit)
    
    # Summary
    all_records = await db.behaviour_records.find(
        {"tenant_id": school_id, "student_id": student_id},
        {"category": 1, "points": 1, "severity": 1, "_id": 0}
    ).to_list(10000)
    
    summary = {
        "total_records": len(all_records),
        "positive_count": sum(1 for r in all_records if r.get("category") == "positive"),
        "negative_count": sum(1 for r in all_records if r.get("category") == "negative"),
        "total_points": sum(r.get("points", 0) for r in all_records),
    }
    
    return {"records": records, "total": total, "summary": summary, "skip": skip, "limit": limit}


@router.get("/behaviour-records/class/{class_id}")
async def get_class_behaviour_summary(
    class_id: str,
    school_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get behaviour summary for a class"""
    query = {"tenant_id": school_id, "class_id": class_id}
    
    if start_date or end_date:
        query["incident_date"] = {}
        if start_date:
            query["incident_date"]["$gte"] = start_date
        if end_date:
            query["incident_date"]["$lte"] = end_date
    
    records = await db.behaviour_records.find(query, {"_id": 0}).to_list(10000)
    
    # Group by student
    student_stats = {}
    for record in records:
        sid = record.get("student_id")
        if sid not in student_stats:
            student_stats[sid] = {
                "student_id": sid,
                "student_name": record.get("student_name"),
                "positive_count": 0,
                "negative_count": 0,
                "total_points": 0
            }
        
        if record.get("category") == "positive":
            student_stats[sid]["positive_count"] += 1
        else:
            student_stats[sid]["negative_count"] += 1
        
        student_stats[sid]["total_points"] += record.get("points", 0)
    
    sorted_students = sorted(student_stats.values(), key=lambda x: x["total_points"], reverse=True)
    
    return {
        "class_id": class_id,
        "total_records": len(records),
        "positive_total": sum(1 for r in records if r.get("category") == "positive"),
        "negative_total": sum(1 for r in records if r.get("category") == "negative"),
        "student_rankings": sorted_students
    }


@router.get("/behaviour-records/follow-ups")
async def get_pending_follow_ups(
    school_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get behaviour records that require follow-up"""
    tenant = current_user.get("tenant_id") or school_id
    if not tenant:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    query = {
        "tenant_id": tenant,
        "requires_follow_up": True,
        "status": {"$nin": ["resolved", "archived"]}
    }

    records = await db.behaviour_records.find(query, {"_id": 0}).sort("follow_up_date", 1).to_list(100)

    overdue = []
    upcoming = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for r in records:
        fdate = r.get("follow_up_date", "")
        if fdate and fdate <= today:
            overdue.append(r)
        else:
            upcoming.append(r)

    return {
        "total": len(records),
        "overdue": overdue,
        "overdue_count": len(overdue),
        "upcoming": upcoming,
        "upcoming_count": len(upcoming)
    }


@router.get("/behaviour-records/{record_id}")
async def get_behaviour_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single behaviour record"""
    record = await db.behaviour_records.find_one({"id": record_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="سجل السلوك غير موجود")
    return record


@router.put("/behaviour-records/{record_id}")
async def update_behaviour_record(
    record_id: str,
    updates: dict,
    force: bool = False,
    current_user: dict = Depends(require_roles([UserRole.TEACHER, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a behaviour record"""
    now = datetime.now(timezone.utc).isoformat()
    
    record = await db.behaviour_records.find_one({"id": record_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="سجل السلوك غير موجود")
    
    # Check edit window
    if not force and record.get("editable_until"):
        if now > record["editable_until"]:
            raise HTTPException(status_code=400, detail="انتهت فترة التعديل المسموحة")
    
    # Protected fields
    protected = ["id", "tenant_id", "student_id", "recorded_by", "recorded_at"]
    for field in protected:
        updates.pop(field, None)
    
    updates["updated_at"] = now
    updates["updated_by"] = current_user["id"]
    
    await db.behaviour_records.update_one({"id": record_id}, {"$set": updates})
    
    return await db.behaviour_records.find_one({"id": record_id}, {"_id": 0})


@router.delete("/behaviour-records/{record_id}")
async def delete_behaviour_record(
    record_id: str,
    current_user: dict = Depends(require_roles([UserRole.TEACHER, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    tenant_id = current_user.get("tenant_id")
    record = await db.behaviour_records.find_one({"id": record_id, "tenant_id": tenant_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="سجل السلوك غير موجود")
    await db.behaviour_records.delete_one({"id": record_id, "tenant_id": tenant_id})
    return {"detail": "تم حذف السجل بنجاح", "id": record_id}


@router.post("/behaviour-records/{record_id}/principal-review")
async def principal_review_behaviour(
    record_id: str,
    notes: Optional[str] = None,
    new_status: str = "reviewed",
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL]))
):
    """Principal reviews a behaviour record"""
    now = datetime.now(timezone.utc).isoformat()
    
    record = await db.behaviour_records.find_one({"id": record_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="سجل السلوك غير موجود")
    
    await db.behaviour_records.update_one(
        {"id": record_id},
        {
            "$set": {
                "principal_reviewed": True,
                "principal_reviewed_by": current_user["id"],
                "principal_reviewed_at": now,
                "principal_notes": notes,
                "status": new_status,
                "updated_at": now
            }
        }
    )
    
    # Audit log
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "behaviour_reviewed",
        "action_category": "behaviour",
        "actor_id": current_user["id"],
        "actor_name": current_user.get("full_name", ""),
        "target_type": "behaviour_record",
        "target_id": record_id,
        "target_name": record.get("student_name"),
        "tenant_id": record.get("tenant_id"),
        "details": {"new_status": new_status},
        "timestamp": now
    })
    
    return await db.behaviour_records.find_one({"id": record_id}, {"_id": 0})


@router.post("/behaviour-records/{record_id}/notify-parent")
async def notify_parent_about_behaviour(
    record_id: str,
    current_user: dict = Depends(require_roles([UserRole.TEACHER, UserRole.SCHOOL_PRINCIPAL]))
):
    """Mark parent as notified about behaviour"""
    now = datetime.now(timezone.utc).isoformat()
    
    await db.behaviour_records.update_one(
        {"id": record_id},
        {
            "$set": {
                "parent_notified": True,
                "parent_notified_at": now,
                "parent_notified_by": current_user["id"]
            }
        }
    )
    
    return {"message": "تم تسجيل إشعار ولي الأمر"}


@router.post("/disciplinary-actions")
async def create_disciplinary_action(
    data: DisciplinaryActionCreate,
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL]))
):
    """Create a disciplinary action"""
    action_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    action_doc = {
        "id": action_id,
        "tenant_id": school_id,
        "behaviour_record_id": data.behaviour_record_id,
        "student_id": data.student_id,
        "action_type": data.action_type,
        "description": data.description,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "is_active": True,
        "is_completed": False,
        "approved_by": current_user["id"],
        "approved_at": now,
        "created_by": current_user["id"],
        "created_at": now,
    }
    
    await db.disciplinary_actions.insert_one(action_doc)
    
    # Update behaviour record
    await db.behaviour_records.update_one(
        {"id": data.behaviour_record_id},
        {
            "$set": {
                "disciplinary_action": data.action_type,
                "disciplinary_action_date": now,
                "status": "resolved"
            }
        }
    )
    
    # Get student for audit
    student = await db.students.find_one({"id": data.student_id}, {"full_name": 1, "_id": 0})
    
    # Audit log
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "disciplinary_action",
        "action_category": "behaviour",
        "actor_id": current_user["id"],
        "actor_name": current_user.get("full_name", ""),
        "target_type": "student",
        "target_id": data.student_id,
        "target_name": student.get("full_name") if student else None,
        "tenant_id": school_id,
        "details": {"action_type": data.action_type},
        "is_sensitive": True,
        "timestamp": now
    })
    
    action_doc.pop("_id", None)
    return action_doc


@router.get("/disciplinary-actions/student/{student_id}")
async def get_student_disciplinary_actions(
    student_id: str,
    school_id: str,
    active_only: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get disciplinary actions for a student"""
    query = {"tenant_id": school_id, "student_id": student_id}
    
    if active_only:
        query["is_active"] = True
        query["is_completed"] = False
    
    actions = await db.disciplinary_actions.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"actions": actions, "total": len(actions)}


@router.get("/behaviour-profile/student/{student_id}")
async def get_student_behaviour_profile(
    student_id: str,
    school_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive behaviour profile for a student"""
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    # Get all records
    records = await db.behaviour_records.find(
        {"tenant_id": school_id, "student_id": student_id},
        {"_id": 0}
    ).to_list(10000)
    
    # Calculate metrics
    total_points = sum(r.get("points", 0) for r in records)
    positive_count = sum(1 for r in records if r.get("category") == "positive")
    negative_count = sum(1 for r in records if r.get("category") == "negative")
    
    # Active disciplinary actions
    active_actions = await db.disciplinary_actions.count_documents({
        "tenant_id": school_id,
        "student_id": student_id,
        "is_active": True,
        "is_completed": False
    })
    
    # Behaviour score (0-100)
    if len(records) > 0:
        behaviour_score = min(100, max(0, 100 + total_points))
    else:
        behaviour_score = 100
    
    # Behaviour level
    if behaviour_score >= 90:
        behaviour_level = "ممتاز"
    elif behaviour_score >= 75:
        behaviour_level = "جيد جداً"
    elif behaviour_score >= 60:
        behaviour_level = "جيد"
    elif behaviour_score >= 50:
        behaviour_level = "مقبول"
    else:
        behaviour_level = "يحتاج متابعة"
    
    return {
        "student_id": student_id,
        "student_name": student.get("full_name"),
        "total_records": len(records),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "total_points": total_points,
        "behaviour_score": behaviour_score,
        "behaviour_level": behaviour_level,
        "active_disciplinary_actions": active_actions,
        "last_incident": records[0]["incident_date"] if records else None,
        "needs_attention": behaviour_score < 60 or active_actions > 0
    }


@router.get("/behaviour-statistics")
async def get_behaviour_statistics(
    school_id: Optional[str] = None,
    period: str = "month",
    class_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive behaviour statistics for the school"""
    tenant = current_user.get("tenant_id") or school_id
    if not tenant:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    now = datetime.now(timezone.utc)
    if period == "week":
        start = (now - timedelta(days=7)).isoformat()
    elif period == "month":
        start = (now - timedelta(days=30)).isoformat()
    elif period == "semester":
        start = (now - timedelta(days=120)).isoformat()
    else:
        start = (now - timedelta(days=365)).isoformat()

    query = {"tenant_id": tenant, "recorded_at": {"$gte": start}}
    if class_id:
        query["class_id"] = class_id

    records = await db.behaviour_records.find(query, {"_id": 0}).to_list(10000)

    total = len(records)
    positive = sum(1 for r in records if r.get("category") == "positive")
    negative = sum(1 for r in records if r.get("category") == "negative")
    neutral = sum(1 for r in records if r.get("category") == "neutral")
    escalated = sum(1 for r in records if r.get("status") == "escalated")
    pending_review = sum(1 for r in records if r.get("status") == "pending")
    total_points = sum(r.get("points", 0) for r in records)

    by_severity = {}
    for r in records:
        sev = r.get("severity", "minor")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    by_type = {}
    for r in records:
        btype = r.get("behaviour_type_name", "غير محدد")
        by_type[btype] = by_type.get(btype, 0) + 1

    top_students_neg = {}
    for r in records:
        if r.get("category") == "negative":
            sid = r.get("student_id")
            if sid not in top_students_neg:
                top_students_neg[sid] = {"student_id": sid, "student_name": r.get("student_name"), "count": 0, "points": 0}
            top_students_neg[sid]["count"] += 1
            top_students_neg[sid]["points"] += r.get("points", 0)

    top_negative = sorted(top_students_neg.values(), key=lambda x: x["count"], reverse=True)[:10]

    top_students_pos = {}
    for r in records:
        if r.get("category") == "positive":
            sid = r.get("student_id")
            if sid not in top_students_pos:
                top_students_pos[sid] = {"student_id": sid, "student_name": r.get("student_name"), "count": 0, "points": 0}
            top_students_pos[sid]["count"] += 1
            top_students_pos[sid]["points"] += r.get("points", 0)

    top_positive = sorted(top_students_pos.values(), key=lambda x: x["points"], reverse=True)[:10]

    daily = {}
    for r in records:
        d = r.get("incident_date", "")[:10]
        if d:
            if d not in daily:
                daily[d] = {"positive": 0, "negative": 0, "neutral": 0}
            cat = r.get("category", "neutral")
            daily[d][cat] = daily[d].get(cat, 0) + 1

    return {
        "period": period,
        "total_records": total,
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "escalated_count": escalated,
        "pending_review": pending_review,
        "total_points": total_points,
        "positive_ratio": round(positive / max(1, total) * 100, 1),
        "by_severity": by_severity,
        "by_type": dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)),
        "top_negative_students": top_negative,
        "top_positive_students": top_positive,
        "daily_trend": dict(sorted(daily.items())),
        "needs_attention_count": len([s for s in top_negative if s["count"] >= 3])
    }


@router.get("/behaviour-records/class/{class_id}/detailed-summary")
async def get_class_behaviour_detailed_summary(
    class_id: str,
    school_id: Optional[str] = None,
    period: str = "month",
    current_user: dict = Depends(get_current_user)
):
    """Get detailed behaviour summary with rankings for a class"""
    tenant = current_user.get("tenant_id") or school_id
    if not tenant:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    now = datetime.now(timezone.utc)
    if period == "week":
        start = (now - timedelta(days=7)).isoformat()
    elif period == "month":
        start = (now - timedelta(days=30)).isoformat()
    else:
        start = (now - timedelta(days=120)).isoformat()

    records = await db.behaviour_records.find(
        {"tenant_id": tenant, "class_id": class_id, "recorded_at": {"$gte": start}},
        {"_id": 0}
    ).to_list(10000)

    students = await db.students.find(
        {"tenant_id": school_id, "class_id": class_id},
        {"_id": 0, "id": 1, "full_name": 1}
    ).to_list(100)

    student_data = {}
    for s in students:
        student_data[s["id"]] = {
            "student_id": s["id"],
            "student_name": s.get("full_name"),
            "positive": 0, "negative": 0, "points": 0,
            "behaviour_score": 100
        }

    for r in records:
        sid = r.get("student_id")
        if sid in student_data:
            if r.get("category") == "positive":
                student_data[sid]["positive"] += 1
            elif r.get("category") == "negative":
                student_data[sid]["negative"] += 1
            student_data[sid]["points"] += r.get("points", 0)

    for sid, d in student_data.items():
        d["behaviour_score"] = min(100, max(0, 100 + d["points"]))

    ranked = sorted(student_data.values(), key=lambda x: x["behaviour_score"], reverse=True)
    for i, s in enumerate(ranked):
        s["rank"] = i + 1

    class_avg = round(sum(s["behaviour_score"] for s in ranked) / max(1, len(ranked)), 1)

    return {
        "class_id": class_id,
        "period": period,
        "total_records": len(records),
        "class_average_score": class_avg,
        "student_count": len(ranked),
        "students": ranked,
        "needs_attention": [s for s in ranked if s["behaviour_score"] < 60]
    }


