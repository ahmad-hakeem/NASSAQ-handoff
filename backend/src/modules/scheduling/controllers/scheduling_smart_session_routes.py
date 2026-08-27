"""
NASSAQ Scheduling Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta, date as _date
import uuid, os, logging, json, random, re, io, base64

logger = logging.getLogger("nassaq.scheduling")

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct
from src.common.utils.session_settings import (
    sanitize_homework_view_mode as ss_sanitize_homework_view_mode,
    sanitize_recitation_attempts as ss_sanitize_recitation_attempts,
    load_tenant_participation_max as ss_load_tenant_participation_max,
    sanitize_participation_scores as ss_sanitize_participation_scores,
    sanitize_custom_element_fields as ss_sanitize_custom_element_fields,
    custom_fields_from_record as ss_custom_fields_from_record,
)


from shared_models import (
    StatusCheck, StatusCheckCreate, TeacherRankEnum, SessionStatusEnum, ScheduleStatusEnum, TimeSlotCreate, TimeSlotResponse, TeacherAssignmentCreate, TeacherAssignmentResponse, SchoolScheduleCreate, SchoolScheduleResponse, ScheduleSessionCreate, ScheduleSessionResponse
)

router = APIRouter()

# Class-scoped teaching endpoints (curriculum lessons + grade columns).
# These live on a SEPARATE router so they can be mounted WITHOUT the
# full-school-tenant capability gate that the smart-scheduling router
# carries (Task #773). They rely on `_verify_class_access` for per-class
# authorization, which already enforces IT workspace ownership, the
# §6.7 co-teaching collaborator path, and the §8 inv. 3 cross-workspace
# 404 invariant. Independent-Teacher callers manage their own classes'
# curriculum/grades here; genuinely school-wide smart-scheduling
# endpoints stay on `router` and remain denied for IT.
class_teaching_router = APIRouter()

# ============== SMART TIMETABLE SESSION MANAGEMENT APIs ==============

async def _assert_entities_in_school(
    school_id: str,
    *,
    teacher_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    class_id: Optional[str] = None,
) -> None:
    """
    Tenant-isolation guard for entity references attached to a session.

    The session-mutator routes (add / update / force) accept teacher,
    subject and class IDs from the client. Without this check a school
    admin with API access could bind an entity that belongs to a
    different tenant — leaking the foreign ID into their timetable and
    silently violating multi-tenancy. This helper resolves each
    supplied ID and rejects the request with a safe Arabic message
    (no raw exception strings) if any entity is missing or scoped to
    a different school.

    Parallel to ``_assert_session_mutable`` so all mutation paths share
    the same guarantees and can't drift apart over time.

    Fails closed: if the session/timetable lacks a school_id at all, or
    if the referenced entity has neither ``school_id`` nor ``tenant_id``,
    the request is rejected as an integrity error rather than silently
    accepted. Tenant identity on records may live under either field
    in this codebase (see ``_verify_teacher_access`` for prior art), so
    both are honored when comparing.
    """
    if not school_id:
        # The session/timetable itself is missing tenant scope — refuse
        # to mutate rather than allow an unscoped write.
        raise HTTPException(status_code=409, detail="الجدول لا يحتوي على معرف المدرسة")

    def _tenant_of(doc: dict) -> Optional[str]:
        return doc.get("school_id") or doc.get("tenant_id")

    checks = [
        ("teachers", teacher_id, "المعلم غير موجود", "المعلم لا ينتمي لهذه المدرسة"),
        ("subjects", subject_id, "المادة غير موجودة", "المادة لا تنتمي لهذه المدرسة"),
        ("classes",  class_id,   "الفصل غير موجود",   "الفصل لا ينتمي لهذه المدرسة"),
    ]
    for collection, ent_id, missing_msg, mismatch_msg in checks:
        if not ent_id:
            continue
        doc = await gd_find_one(db.session, collection, {"id": ent_id})
        if not doc:
            raise HTTPException(status_code=404, detail=missing_msg)
        owner = _tenant_of(doc)
        if not owner or owner != school_id:
            raise HTTPException(status_code=403, detail=mismatch_msg)


async def _assert_session_mutable(session: dict, current_user: dict) -> dict:
    """
    Shared guard for session mutations (edit / force / move / delete).

    Enforces two invariants required by the new master-grid manual-edit
    flow and demanded by replit.md:
      • Tenant isolation — non-platform admins may only mutate sessions
        in their own tenant.
      • Published timetables are immutable — the principal must edit on
        the draft and publish explicitly.

    Returns the parent timetable doc for callers that need it. Raises
    HTTPException with a safe Arabic message on violation (no raw
    exception strings leaked).
    """
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    user_role = current_user.get("role", "")
    is_platform_admin = user_role == UserRole.PLATFORM_ADMIN.value

    # Resolve the parent timetable up-front so we can derive tenant scope
    # from it when the session row itself is missing tenant fields. This
    # closes the fail-open edge for delete on unscoped sessions.
    tt_id = session.get("timetable_id")
    tt = await gd_find_one(db.session, "timetables", {"id": tt_id}) if tt_id else None

    school_id = (
        session.get("school_id")
        or session.get("tenant_id")
        or (tt.get("school_id") if tt else None)
        or (tt.get("tenant_id") if tt else None)
    )

    # Fail closed: a non-platform-admin can only mutate when we have a
    # concrete tenant scope and it matches their own.
    if not is_platform_admin:
        if not user_tenant or not school_id:
            raise HTTPException(status_code=409, detail="تعذر التحقق من نطاق المدرسة")
        if school_id != user_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح بالتعديل على هذه المدرسة")

    if tt and tt.get("status") == "published":
        raise HTTPException(status_code=400, detail="لا يمكن تعديل جدول منشور")
    return tt or {}


class UpdateSmartSessionRequest(BaseModel):
    """طلب تعديل حصة في الجدول الذكي"""
    teacher_id: Optional[str] = None
    subject_id: Optional[str] = None
    class_id: Optional[str] = None
    day_of_week: Optional[str] = None
    period_number: Optional[int] = None


class SwapSessionsRequest(BaseModel):
    """طلب تبديل حصتين"""
    session_id_1: str
    session_id_2: str


@router.put("/smart-scheduling/session/{session_id}")
async def update_smart_session(
    session_id: str,
    request: UpdateSmartSessionRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    تعديل حصة في الجدول الذكي
    Update a session in the smart timetable
    """
    # Get current session
    session = await gd_find_one(db.session, "timetable_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")

    # Tenant + published-state guard (shared with force / delete).
    await _assert_session_mutable(session, current_user)

    timetable_id = session.get("timetable_id")
    school_id = session.get("school_id")

    # Cross-tenant binding guard: any teacher/subject/class the client supplies
    # must belong to the same school as the session being edited. Honor
    # tenant_id as a fallback so behavior matches _assert_session_mutable.
    await _assert_entities_in_school(
        school_id or session.get("tenant_id"),
        teacher_id=request.teacher_id,
        subject_id=request.subject_id,
        class_id=request.class_id,
    )

    # Build update
    update_data = {"source_type": "hybrid_adjusted", "updated_at": datetime.now(timezone.utc).isoformat()}
    conflicts = []
    
    new_day = request.day_of_week or session.get("day_of_week")
    new_period = request.period_number or session.get("period_number")
    new_teacher = request.teacher_id or session.get("teacher_id")
    new_class = request.class_id or session.get("class_id")
    
    # Check for conflicts if moving to new slot or changing class/teacher
    if request.day_of_week or request.period_number:
        # Check teacher conflict
        teacher_conflict = await gd_find_one(db.session, "timetable_sessions", {
            "timetable_id": timetable_id,
            "teacher_id": new_teacher,
            "day_of_week": new_day,
            "period_number": new_period,
            "id": {"$ne": session_id}
        })
        
        if teacher_conflict:
            conflicts.append({
                "type": "teacher_overlap",
                "message_ar": "المعلم لديه حصة أخرى في هذا الوقت",
                "message_en": "Teacher has another session at this time"
            })
        
        # Check class conflict
        class_conflict = await gd_find_one(db.session, "timetable_sessions", {
            "timetable_id": timetable_id,
            "class_id": new_class,
            "day_of_week": new_day,
            "period_number": new_period,
            "id": {"$ne": session_id}
        })
        
        if class_conflict:
            conflicts.append({
                "type": "class_overlap",
                "message_ar": "الفصل لديه حصة أخرى في هذا الوقت",
                "message_en": "Class has another session at this time"
            })
        
        update_data["day_of_week"] = new_day
        update_data["period_number"] = new_period
    
    if request.teacher_id:
        update_data["teacher_id"] = request.teacher_id
        
        # Check teacher conflict with new teacher
        if not request.day_of_week and not request.period_number:
            teacher_conflict = await gd_find_one(db.session, "timetable_sessions", {
                "timetable_id": timetable_id,
                "teacher_id": request.teacher_id,
                "day_of_week": session.get("day_of_week"),
                "period_number": session.get("period_number"),
                "id": {"$ne": session_id}
            })
            
            if teacher_conflict:
                conflicts.append({
                    "type": "teacher_overlap",
                    "message_ar": "المعلم الجديد لديه حصة أخرى في هذا الوقت",
                    "message_en": "New teacher has another session at this time"
                })

    if request.class_id:
        update_data["class_id"] = request.class_id

        # Check class conflict with new class
        if not request.day_of_week and not request.period_number:
            class_conflict = await gd_find_one(db.session, "timetable_sessions", {
                "timetable_id": timetable_id,
                "class_id": request.class_id,
                "day_of_week": session.get("day_of_week"),
                "period_number": session.get("period_number"),
                "id": {"$ne": session_id}
            })

            if class_conflict:
                conflicts.append({
                    "type": "class_overlap",
                    "message_ar": "الفصل الجديد لديه حصة أخرى في هذا الوقت",
                    "message_en": "New class has another session at this time"
                })
    
    if request.subject_id:
        update_data["subject_id"] = request.subject_id
    
    # If there are critical conflicts, return warning but allow override
    if conflicts:
        return {
            "success": False,
            "session_id": session_id,
            "conflicts": conflicts,
            "message_ar": "يوجد تعارضات - يمكنك تأكيد التعديل أو إلغاؤه",
            "message_en": "Conflicts detected - you can confirm or cancel"
        }
    
    # Apply update
    await gd_update_one(db.session, "timetable_sessions", {"id": session_id}, update_data)
    
    return {
        "success": True,
        "session_id": session_id,
        "conflicts": [],
        "message_ar": "تم تعديل الحصة بنجاح",
        "message_en": "Session updated successfully"
    }


@router.put("/smart-scheduling/session/{session_id}/force")
async def force_update_smart_session(
    session_id: str,
    request: UpdateSmartSessionRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    تعديل حصة بالقوة (تجاهل التعارضات)
    Force update a session (ignore conflicts)
    """
    session = await gd_find_one(db.session, "timetable_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")

    # Tenant + published-state guard (force-update is still scoped to draft).
    await _assert_session_mutable(session, current_user)

    # Cross-tenant binding guard mirrors the standard update path.
    await _assert_entities_in_school(
        session.get("school_id") or session.get("tenant_id"),
        teacher_id=request.teacher_id,
        subject_id=request.subject_id,
        class_id=request.class_id,
    )

    update_data = {"source_type": "hybrid_adjusted", "updated_at": datetime.now(timezone.utc).isoformat()}
    
    if request.day_of_week:
        update_data["day_of_week"] = request.day_of_week
    if request.period_number:
        update_data["period_number"] = request.period_number
    if request.teacher_id:
        update_data["teacher_id"] = request.teacher_id
    if request.subject_id:
        update_data["subject_id"] = request.subject_id
    if request.class_id:
        update_data["class_id"] = request.class_id
    
    await gd_update_one(db.session, "timetable_sessions", {"id": session_id}, update_data)
    
    return {
        "success": True,
        "session_id": session_id,
        "message_ar": "تم تعديل الحصة بالقوة",
        "message_en": "Session force updated"
    }


@router.post("/smart-scheduling/sessions/swap")
async def swap_smart_sessions(
    request: SwapSessionsRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    تبديل حصتين
    Swap two sessions
    """
    session1 = await gd_find_one(db.session, "timetable_sessions", {"id": request.session_id_1})
    session2 = await gd_find_one(db.session, "timetable_sessions", {"id": request.session_id_2})
    
    if not session1 or not session2:
        raise HTTPException(status_code=404, detail="إحدى الحصتين غير موجودة")

    tt_id = session1.get("timetable_id")
    if tt_id != session2.get("timetable_id"):
        raise HTTPException(status_code=400, detail="لا يمكن تبديل حصص من جداول مختلفة")

    school_id = session1.get("school_id")
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    user_role = current_user.get("role", "")
    if user_tenant and school_id != user_tenant and user_role != UserRole.PLATFORM_ADMIN.value:
        raise HTTPException(status_code=403, detail="غير مصرح بالتعديل على هذه المدرسة")

    tt = await gd_find_one(db.session, "timetables", {"id": tt_id})
    if tt and tt.get("status") == "published":
        raise HTTPException(status_code=400, detail="لا يمكن تعديل جدول منشور")

    s1_day = session1.get("day_of_week") or session1.get("day")
    s1_period = session1.get("period_number")
    s1_slot = session1.get("time_slot_id")
    s1_start = session1.get("start_time")
    s1_end = session1.get("end_time")

    s2_day = session2.get("day_of_week") or session2.get("day")
    s2_period = session2.get("period_number")
    s2_slot = session2.get("time_slot_id")
    s2_start = session2.get("start_time")
    s2_end = session2.get("end_time")

    exclude_ids = [request.session_id_1, request.session_id_2]

    t1_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "teacher_id": session1.get("teacher_id"),
        "day_of_week": s2_day, "period_number": s2_period,
        "id": {"$nin": exclude_ids}
    })
    if t1_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: المعلم {session1.get('teacher_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    c1_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "class_id": session1.get("class_id"),
        "day_of_week": s2_day, "period_number": s2_period,
        "id": {"$nin": exclude_ids}
    })
    if c1_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: الفصل {session1.get('class_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    t2_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "teacher_id": session2.get("teacher_id"),
        "day_of_week": s1_day, "period_number": s1_period,
        "id": {"$nin": exclude_ids}
    })
    if t2_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: المعلم {session2.get('teacher_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    c2_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "class_id": session2.get("class_id"),
        "day_of_week": s1_day, "period_number": s1_period,
        "id": {"$nin": exclude_ids}
    })
    if c2_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: الفصل {session2.get('class_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    now = datetime.now(timezone.utc).isoformat()
    
    await gd_update_one(db.session, "timetable_sessions", {"id": request.session_id_1}, {
            "day_of_week": s2_day, "day": s2_day,
            "period_number": s2_period,
            "time_slot_id": s2_slot,
            "start_time": s2_start, "end_time": s2_end,
            "source_type": "hybrid_adjusted",
            "updated_at": now
        })
    
    await gd_update_one(db.session, "timetable_sessions", {"id": request.session_id_2}, {
            "day_of_week": s1_day, "day": s1_day,
            "period_number": s1_period,
            "time_slot_id": s1_slot,
            "start_time": s1_start, "end_time": s1_end,
            "source_type": "hybrid_adjusted",
            "updated_at": now
        })
    
    return {
        "success": True,
        "message_ar": "تم تبديل الحصتين بنجاح",
        "message_en": "Sessions swapped successfully"
    }


class SmartMoveRequest(BaseModel):
    session_id: str
    new_day: str
    new_period: int

@router.post("/smart-scheduling/sessions/move")
async def move_smart_session(
    request: SmartMoveRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    session = await gd_find_one(db.session, "timetable_sessions", {"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")

    tt_id = session.get("timetable_id")
    school_id = session.get("school_id")

    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    user_role = current_user.get("role", "")
    if user_tenant and school_id != user_tenant and user_role != UserRole.PLATFORM_ADMIN.value:
        raise HTTPException(status_code=403, detail="غير مصرح بالتعديل على هذه المدرسة")

    tt = await gd_find_one(db.session, "timetables", {"id": tt_id})
    if tt and tt.get("status") == "published":
        raise HTTPException(status_code=400, detail="لا يمكن تعديل جدول منشور")

    teacher_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "teacher_id": session.get("teacher_id"),
        "day_of_week": request.new_day,
        "period_number": request.new_period,
        "id": {"$ne": request.session_id}
    })
    if teacher_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: المعلم {session.get('teacher_name', '')} لديه حصة في نفس الوقت")

    class_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "class_id": session.get("class_id"),
        "day_of_week": request.new_day,
        "period_number": request.new_period,
        "id": {"$ne": request.session_id}
    })
    if class_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: الفصل {session.get('class_name', '')} لديه حصة في نفس الوقت")

    slot = await gd_find_one(db.session, "time_slots", {
        "school_id": school_id,
        "period_number": request.new_period,
        "is_break": {"$ne": True},
        "is_prayer": {"$ne": True}
    })
    if not slot:
        slot = await gd_find_one(db.session, "time_slots", {
            "school_id": school_id,
            "slot_number": request.new_period,
            "is_break": {"$ne": True},
            "is_prayer": {"$ne": True}
        })

    now = datetime.now(timezone.utc).isoformat()
    update_fields = {
        "day_of_week": request.new_day,
        "day": request.new_day,
        "period_number": request.new_period,
        "source_type": "hybrid_adjusted",
        "updated_at": now
    }
    if slot:
        update_fields["time_slot_id"] = slot.get("id")
        update_fields["start_time"] = slot.get("start_time")
        update_fields["end_time"] = slot.get("end_time")

    await gd_update_one(db.session, "timetable_sessions", {"id": request.session_id}, update_fields)

    return {
        "success": True,
        "message_ar": "تم نقل الحصة بنجاح",
        "message_en": "Session moved successfully"
    }


@router.delete("/smart-scheduling/session/{session_id}")
async def delete_smart_session(
    session_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    حذف حصة من الجدول
    Delete a session from the timetable
    """
    session = await gd_find_one(db.session, "timetable_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")

    # Tenant + published-state guard (mirrors edit / force).
    await _assert_session_mutable(session, current_user)

    await gd_delete_one(db.session, "timetable_sessions", {"id": session_id})
    
    return {
        "success": True,
        "message_ar": "تم حذف الحصة بنجاح",
        "message_en": "Session deleted successfully"
    }


class AddSmartSessionRequest(BaseModel):
    """طلب إضافة حصة يدوية للجدول"""
    timetable_id: str
    class_id: str
    subject_id: str
    teacher_id: str
    day_of_week: str
    period_number: int
    force: bool = False


@router.post("/smart-scheduling/session/add")
async def add_smart_session(
    request: Optional[AddSmartSessionRequest] = None,
    timetable_id: Optional[str] = None,
    class_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    day_of_week: Optional[str] = None,
    period_number: Optional[int] = None,
    force: bool = False,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    إضافة حصة يدوية للجدول
    Add a manual session to the timetable.

    Accepts either a JSON body (preferred — used by the new master-grid
    manual-edit drawer) or legacy query-string params for backwards
    compatibility with any older caller.
    """
    import uuid

    # Resolve inputs from either the JSON body or query params.
    if request is not None:
        timetable_id = request.timetable_id
        class_id = request.class_id
        subject_id = request.subject_id
        teacher_id = request.teacher_id
        day_of_week = request.day_of_week
        period_number = request.period_number
        force = request.force

    missing = [k for k, v in {
        "timetable_id": timetable_id, "class_id": class_id, "subject_id": subject_id,
        "teacher_id": teacher_id, "day_of_week": day_of_week, "period_number": period_number,
    }.items() if v in (None, "")]
    if missing:
        raise HTTPException(status_code=422, detail=f"حقول مفقودة: {', '.join(missing)}")

    # Get timetable
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")

    school_id = timetable.get("school_id") or timetable.get("tenant_id")

    # Tenant scope: a school admin can only mutate their own school's
    # timetable. Platform admin bypasses this gate (e.g. for support).
    # Fail closed for non-platform users when scope is missing — mirrors
    # _assert_session_mutable so add/update/force/delete behave identically.
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    user_role = current_user.get("role", "")
    is_platform_admin = user_role == UserRole.PLATFORM_ADMIN.value
    if not is_platform_admin:
        if not user_tenant or not school_id:
            raise HTTPException(status_code=409, detail="تعذر التحقق من نطاق المدرسة")
        if school_id != user_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح بالتعديل على هذه المدرسة")

    # Block edits on a published timetable (mirrors swap/move semantics).
    if timetable.get("status") == "published":
        raise HTTPException(status_code=400, detail="لا يمكن تعديل جدول منشور")

    # Cross-tenant binding guard: every entity referenced by the new
    # session must belong to the same school as the target timetable.
    # tenant_id is honored as a fallback for parity with the other guards.
    await _assert_entities_in_school(
        school_id or timetable.get("tenant_id"),
        teacher_id=teacher_id,
        subject_id=subject_id,
        class_id=class_id,
    )

    # Get class info (already validated above; safe to re-resolve for grade).
    cls = await gd_find_one(db.session, "classes", {"id": class_id})
    grade_id = cls.get("grade_id", "") if cls else ""
    
    # Check for conflicts
    conflicts = []
    
    # Teacher conflict
    teacher_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": timetable_id,
        "teacher_id": teacher_id,
        "day_of_week": day_of_week,
        "period_number": period_number
    })
    
    if teacher_conflict:
        conflicts.append({
            "type": "teacher_overlap",
            "message_ar": "المعلم لديه حصة أخرى في هذا الوقت"
        })
    
    # Class conflict
    class_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": timetable_id,
        "class_id": class_id,
        "day_of_week": day_of_week,
        "period_number": period_number
    })
    
    if class_conflict:
        conflicts.append({
            "type": "class_overlap",
            "message_ar": "الفصل لديه حصة أخرى في هذا الوقت"
        })
    
    if conflicts and not force:
        return {
            "success": False,
            "conflicts": conflicts,
            "message_ar": "يوجد تعارضات - لا يمكن إضافة الحصة"
        }
    
    # Create session
    session_id = str(uuid.uuid4())
    session_doc = {
        "id": session_id,
        "timetable_id": timetable_id,
        "school_id": school_id,
        "class_id": class_id,
        "grade_id": grade_id,
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "day_of_week": day_of_week,
        "period_number": period_number,
        "start_time": "",
        "end_time": "",
        "session_type": "class",
        "source_type": "manual",
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "timetable_sessions", session_doc)
    
    return {
        "success": True,
        "session_id": session_id,
        "message_ar": "تم إضافة الحصة بنجاح",
        "message_en": "Session added successfully"
    }





# ============== SESSION SETTINGS (per-subject evaluation pattern) ==============

class SessionSettingsRequest(BaseModel):
    subject_id: str
    participation_enabled: bool = True
    homework_enabled: bool = False
    homework_mode: Optional[str] = "didnt_submit"
    recitation_enabled: bool = False
    recitation_attempts: int = 1
    skills_enabled: bool = False
    custom_skills: List = []
    # Group A custom element fields — same contract as /class/{id}/session-settings
    custom_positive_behaviours: Optional[List] = None
    custom_negative_behaviours: Optional[List] = None
    custom_evaluation_items: Optional[List] = None
    behaviour_score_overrides: Optional[dict] = None

class SessionSettingsResponse(BaseModel):
    id: str
    teacher_id: str
    subject_id: str
    participation_enabled: bool
    homework_enabled: bool
    homework_mode: Optional[str]
    recitation_enabled: bool
    recitation_attempts: int
    skills_enabled: bool
    custom_skills: List[str]


async def _verify_teacher_access(teacher_id: str, current_user: dict):
    uid = current_user.get("id", "")
    tid = current_user.get("teacher_id", "")
    role = current_user.get("role", "")
    if uid == teacher_id or tid == teacher_id:
        return
    if role == UserRole.PLATFORM_ADMIN.value:
        return
    if role in ("school_admin", "school_sub_admin"):
        user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
        if user_tenant:
            teacher_doc = await gd_find_one(db.session, "teachers", {"id": teacher_id})
            if not teacher_doc:
                teacher_doc = await gd_find_one(db.session, "users", {"id": teacher_id})
            teacher_school = (teacher_doc or {}).get("school_id") or (teacher_doc or {}).get("tenant_id")
            if teacher_school == user_tenant:
                return
    raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى إعدادات معلم آخر")


@router.get("/teacher/{teacher_id}/session-settings")
async def get_session_settings(
    teacher_id: str,
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    await _verify_teacher_access(teacher_id, current_user)
    query = {"teacher_id": teacher_id}
    if subject_id:
        query["subject_id"] = subject_id
    settings = await gd_find(db.session, "session_settings", query, limit=100)
    if subject_id and settings:
        # Include Group A custom element fields so the فصولي modal shows
        # the same data as the class-specific lesson settings dialog.
        return {**settings[0], **ss_custom_fields_from_record(settings[0])}
    return settings


@router.put("/teacher/{teacher_id}/session-settings")
async def save_session_settings(
    teacher_id: str,
    request: SessionSettingsRequest,
    current_user: dict = Depends(get_current_user),
):
    await _verify_teacher_access(teacher_id, current_user)
    if request.homework_mode and request.homework_mode not in ("didnt_submit", "submitted"):
        raise HTTPException(status_code=422, detail="homework_mode must be 'didnt_submit' or 'submitted'")
    if request.recitation_attempts not in (1, 2, 3):
        raise HTTPException(status_code=422, detail="recitation_attempts must be 1, 2, or 3")
    existing = await gd_find_one(db.session, "session_settings", {
        "teacher_id": teacher_id,
        "subject_id": request.subject_id,
    })
    data = {
        "teacher_id": teacher_id,
        "subject_id": request.subject_id,
        "participation_enabled": request.participation_enabled,
        "homework_enabled": request.homework_enabled,
        "homework_mode": request.homework_mode,
        "recitation_enabled": request.recitation_enabled,
        "recitation_attempts": request.recitation_attempts,
        "skills_enabled": request.skills_enabled,
        "custom_skills": request.custom_skills,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Persist Group A custom element fields using the shared sanitizer so
    # the فصولي modal and the class-specific dialog use the same contract.
    # Absent-key = don't-touch (mirrors the class route's streak_bonus contract).
    req_dict = request.dict()
    data.update(ss_sanitize_custom_element_fields(req_dict))
    if existing:
        await gd_update_one(db.session, "session_settings", {"id": existing["id"]}, data)
        return {**data, **ss_custom_fields_from_record(data), "id": existing["id"]}
    else:
        doc_id = str(uuid.uuid4())
        data["id"] = doc_id
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        await gd_insert(db.session, "session_settings", data)
        return {**data, **ss_custom_fields_from_record(data)}


# ============== CURRICULUM PLAN ==============

ALLOWED_COLUMN_TYPES = {"coursework", "exams"}
# Input mode of a follow-up column: numeric grade (درجة), binary check
# (تحقق) or free text (نص). Stored on the column so the sheet renders the
# matching control; non-"grade" columns are excluded from numeric totals and
# from the student-record grade sync.
ALLOWED_INPUT_TYPES = {"grade", "check", "text"}

class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    week: int = Field(default=1, ge=1, le=52)
    order: int = Field(default=1, ge=1, le=100)
    notes: Optional[str] = Field(default=None, max_length=500)
    start_date: Optional[_date] = Field(default=None)
    end_date: Optional[_date] = Field(default=None)
    override_curriculum: bool = False
    override_reason: Optional[str] = Field(default=None, max_length=1000)

class LessonUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    week: Optional[int] = Field(default=None, ge=1, le=52)
    order: Optional[int] = Field(default=None, ge=1, le=100)
    is_completed: Optional[bool] = None
    is_skipped: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    start_date: Optional[_date] = Field(default=None)
    end_date: Optional[_date] = Field(default=None)
    override_curriculum: bool = False
    override_reason: Optional[str] = Field(default=None, max_length=1000)


async def _verify_class_access(class_id: str, current_user: dict, *, write: bool = False):
    role = current_user.get("role", "")
    if role == UserRole.PLATFORM_ADMIN.value:
        return
    cls = await gd_find_one(db.session, "classes", {"id": class_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    class_school = cls.get("school_id") or cls.get("tenant_id")
    # IT §6.7 (Task #210) — cross-workspace co-teaching widening for the
    # named class only. The single-tenant invariant is intentionally
    # relaxed here, but only for the exact class the row points at, and
    # write surfaces additionally require scope.mode == 'write'.
    if role == UserRole.INDEPENDENT_TEACHER.value:
        from src.core.guards.tenant_guard import independent_workspace_id
        from src.common.utils.collab_access import caller_collab_mode_for_class
        # Ownership check: if the class belongs to the caller's own workspace,
        # grant access immediately (both read and write).
        wsid = independent_workspace_id(current_user)
        # Harden: if wsid could not be reconstructed from the user record
        # (e.g. the `id` field is absent or aliased differently), fall back
        # to the tenant_id stored on the user — for IT teachers this is
        # explicitly set to itw_{user_id} during bootstrap and token refresh.
        if not wsid:
            _t = current_user.get("tenant_id") or current_user.get("school_id")
            if _t and isinstance(_t, str) and _t.startswith("itw_"):
                wsid = _t
        if wsid and str(class_school) == str(wsid):
            return
        logger.debug(
            "scheduling._verify_class_access: IT ownership check failed",
            extra={
                "class_id": class_id,
                "class_school": class_school,
                "wsid": wsid,
                "user_id": current_user.get("id"),
                "user_tenant_id": current_user.get("tenant_id"),
            },
        )
        # Cross-workspace: only collaborators may proceed.
        mode = await caller_collab_mode_for_class(db.session, current_user, class_id)
        if mode is not None:
            if write and mode != "write":
                raise HTTPException(status_code=403, detail="هذا التعاون مخصّص للقراءة فقط")
            return
        # Per §8 inv. 3: cross-workspace IDs must 404, never 403/200.
        raise HTTPException(status_code=404, detail="Class not found")
    if role in ("teacher",):
        tid = current_user.get("teacher_id") or current_user.get("id")
        if cls.get("homeroom_teacher_id") and tid and cls.get("homeroom_teacher_id") == tid:
            return
        # Canonical "teacher has access to class" check: any linkage row in
        # one of the sanctioned assignment tables grants access. Extend this
        # list when new flows persist teacher↔class linkage elsewhere.
        linkage_tables = (
            "class_subjects",
            "schedule_entries",
            "teacher_assignments",
            "class_sessions",
            "teacher_class_assignments",
        )
        for table in linkage_tables:
            rows = await gd_find(
                db.session, table,
                {"class_id": class_id, "teacher_id": tid},
                limit=1,
            )
            if rows:
                return
        logger.debug(
            "scheduling._verify_class_access denied teacher",
            extra={
                "class_id": class_id,
                "teacher_id": tid,
                "tenant_id": class_school,
                "homeroom_teacher_id": cls.get("homeroom_teacher_id"),
                "tables_checked": ("homeroom_teacher_id", *linkage_tables),
                "write": write,
            },
        )
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى هذا الفصل")
    if role in ("school_admin", "school_sub_admin", "school_principal"):
        user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
        if user_tenant and class_school == user_tenant:
            return
    raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى هذا الفصل")


async def _get_curriculum_date_range(class_doc: dict) -> dict:
    """Resolve the curriculum date range from the active term for a class's tenant.

    Returns a dict with keys: curriculum_start_date, curriculum_end_date
    (both may be None when no active academic year/term is found).
    """
    school_id = class_doc.get("school_id") or class_doc.get("tenant_id")
    if not school_id:
        return {"curriculum_start_date": None, "curriculum_end_date": None}

    # Try current academic year first
    year = await gd_find_one(db.session, "academic_years", {"school_id": school_id, "is_current": True})
    if not year:
        # Fallback: most recent academic year by start_date
        years = await gd_find(db.session, "academic_years", {"school_id": school_id}, order_by="start_date", desc_order=True, limit=1)
        year = years[0] if years else None

    if not year:
        return {"curriculum_start_date": None, "curriculum_end_date": None}

    # Try current term
    term = await gd_find_one(db.session, "terms", {"school_id": school_id, "is_current": True})
    if not term:
        term = await gd_find_one(db.session, "terms", {"academic_year_id": year.get("id"), "is_current": True})
    if not term:
        # Fallback: most recent term for the year
        terms = await gd_find(db.session, "terms", {"academic_year_id": year.get("id")}, order_by="start_date", limit=1)
        term = terms[0] if terms else None

    if term:
        return {
            "curriculum_start_date": str(term.get("start_date", ""))[:10] or None,
            "curriculum_end_date": str(term.get("end_date", ""))[:10] or None,
        }

    # Use academic year dates as fallback
    return {
        "curriculum_start_date": str(year.get("start_date", ""))[:10] or None,
        "curriculum_end_date": str(year.get("end_date", ""))[:10] or None,
    }


def _date_in_range(d: "_date | str", range_start: str, range_end: str) -> bool:
    """Return True if d falls within [range_start, range_end] (inclusive).

    Fails closed: any unparseable input returns False (treated as out-of-range).
    Accepts either a Python date object or an ISO-format string.
    """
    try:
        if isinstance(d, _date):
            parsed = d
        else:
            parsed = _date.fromisoformat(str(d)[:10])
        s = _date.fromisoformat(range_start[:10])
        e = _date.fromisoformat(range_end[:10])
        return s <= parsed <= e
    except (ValueError, TypeError, AttributeError):
        return False  # fail-closed on any unparseable value


@class_teaching_router.get("/class/{class_id}/curriculum-plan/lesson/new-metadata")
async def get_lesson_new_metadata(
    class_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return curriculum date range and sensible defaults for the Add Lesson dialog."""
    await _verify_class_access(class_id, current_user)
    cls = await gd_find_one(db.session, "classes", {"id": class_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    date_range = await _get_curriculum_date_range(cls)
    curriculum_start = date_range["curriculum_start_date"]
    curriculum_end = date_range["curriculum_end_date"]

    # Default start = max(today, curriculum_start); default end = curriculum_end
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    default_start = today_str
    if curriculum_start:
        try:
            cs = _date.fromisoformat(curriculum_start)
            td = _date.fromisoformat(today_str)
            default_start = max(cs, td).isoformat()
        except ValueError:
            pass
    default_end = curriculum_end or today_str

    return {
        "curriculum_start_date": curriculum_start,
        "curriculum_end_date": curriculum_end,
        "default_start_date": default_start,
        "default_end_date": default_end,
        "allow_override": True,
    }


def _curriculum_teacher_id(current_user: dict) -> Optional[str]:
    """The teacher identity that owns a curriculum plan for the caller.

    Mirrors the teacher resolution in ``_verify_class_access`` so the
    ``teacher_id`` stored on create and the teacher filter applied on read
    always agree.
    """
    return current_user.get("teacher_id") or current_user.get("id")


def _is_curriculum_teacher_scope(role: str) -> bool:
    """True for callers whose curriculum plan is private to themselves —
    classroom teachers and independent teachers. School-leadership and
    platform roles instead view across all teachers of a class.
    """
    return role in ("teacher", UserRole.INDEPENDENT_TEACHER.value)


def _verify_curriculum_lesson_owner(existing: dict, current_user: dict) -> None:
    """Fail closed when a teacher/IT caller targets a lesson that is not part
    of their own plan. Plans are private per (class, subject, teacher), so a
    teacher must never be able to edit or delete a colleague's lesson — even by
    id. We 404 (not 403) so the API does not confirm the foreign lesson exists.
    Leadership/platform callers are unaffected (they manage across teachers).
    """
    if not _is_curriculum_teacher_scope(current_user.get("role", "")):
        return
    if (existing.get("teacher_id") or "") != (_curriculum_teacher_id(current_user) or ""):
        raise HTTPException(status_code=404, detail="Lesson not found")


async def _resolve_curriculum_subjects(
    class_id: str, current_user: dict, cls: Optional[dict]
) -> List[Dict[str, str]]:
    """Subjects the caller may pick a curriculum plan for, in this class.

    Curriculum plans are private per (class, subject, teacher). A teacher/IT
    caller may only choose among the subjects THEY teach in the class;
    leadership/platform callers see every subject taught in the class.
    Resolution order: ``teacher_assignments`` → ``schedule_sessions`` →
    the class's own ``subject_id`` (IT single-subject classes).
    """
    role = current_user.get("role", "")
    teacher_scoped = _is_curriculum_teacher_scope(role)
    tid = _curriculum_teacher_id(current_user)

    pairs: Dict[str, str] = {}

    ta_filter: Dict[str, Any] = {"class_id": class_id}
    if teacher_scoped and tid:
        ta_filter["teacher_id"] = tid
    for ta in await gd_find(db.session, "teacher_assignments", ta_filter, limit=500):
        sid = ta.get("subject_id")
        if sid:
            pairs.setdefault(sid, ta.get("subject_name") or "")

    if not pairs:
        ss_filter: Dict[str, Any] = {"class_id": class_id}
        if teacher_scoped and tid:
            ss_filter["teacher_id"] = tid
        for ss in await gd_find(db.session, "schedule_sessions", ss_filter, limit=1000):
            sid = ss.get("subject_id")
            if sid:
                pairs.setdefault(sid, ss.get("subject_name") or "")

    if not pairs and cls:
        sid = cls.get("subject_id")
        if sid:
            pairs.setdefault(sid, cls.get("subject_name") or "")

    out: List[Dict[str, str]] = []
    for sid, name in pairs.items():
        if not name:
            subj = await gd_find_one(db.session, "subjects", {"id": sid})
            name = (subj or {}).get("name") or (subj or {}).get("name_ar") or ""
        out.append({"id": sid, "name": name})
    out.sort(key=lambda x: (x.get("name") or ""))
    return out


async def _sync_curriculum_portfolio(
    current_user: dict,
    class_id: str,
    subject_id: Optional[str],
    cls: Optional[dict] = None,
) -> None:
    """Mirror a teacher's curriculum plan into their portfolio's Planning
    Evidence as a live "خطة توزيع المنهج" card (one per class + subject).

    Fire-and-forget: a portfolio failure must never break the curriculum write.
    Runs only for teacher/IT callers — their plan is private and maps to their
    own portfolio; leadership/platform curriculum edits are class-wide and have
    no per-teacher portfolio card. Awaited inline (not a background task) so the
    upsert shares the request's DB session and commits with it.
    """
    if not _is_curriculum_teacher_scope(current_user.get("role", "")):
        return
    try:
        plan_teacher_id = _curriculum_teacher_id(current_user)
        portfolio_teacher_id = current_user.get("id")
        if not plan_teacher_id or not portfolio_teacher_id:
            return

        if cls is None:
            cls = await gd_find_one(db.session, "classes", {"id": class_id})
        school_id = (
            (cls or {}).get("school_id")
            or (cls or {}).get("tenant_id")
            or current_user.get("tenant_id")
            or ""
        )
        class_name = (cls or {}).get("name") or (cls or {}).get("class_name") or ""

        subject_name = ""
        if subject_id:
            subj = await gd_find_one(db.session, "subjects", {"id": subject_id})
            subject_name = (subj or {}).get("name") or (subj or {}).get("name_ar") or ""

        from engines.portfolio_evidence_engine import PortfolioEvidenceEngine
        await PortfolioEvidenceEngine(db).sync_curriculum_plan_evidence(
            portfolio_teacher_id=portfolio_teacher_id,
            plan_teacher_id=plan_teacher_id,
            school_id=school_id,
            class_id=class_id,
            subject_id=subject_id or "",
            class_name=class_name,
            subject_name=subject_name,
        )
    except Exception as _sync_err:
        logger.debug("curriculum portfolio sync failed: %s", _sync_err)


@class_teaching_router.get("/class/{class_id}/curriculum-plan")
async def get_curriculum_plan(
    class_id: str,
    subject_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    await _verify_class_access(class_id, current_user)
    role = current_user.get("role", "")

    # Curriculum plans are private per (class, subject, teacher). A teacher/IT
    # caller may only ever read their OWN plan: the teacher filter is forced
    # server-side and any client-supplied ``teacher_id`` is ignored, so one
    # teacher can never see another teacher's plan for the same class.
    # Leadership/platform callers may optionally narrow to one teacher.
    if _is_curriculum_teacher_scope(role):
        eff_teacher_id = _curriculum_teacher_id(current_user)
    else:
        eff_teacher_id = teacher_id or None

    query: Dict[str, Any] = {"class_id": class_id}
    if subject_id:
        query["subject_id"] = subject_id
    if eff_teacher_id:
        query["teacher_id"] = eff_teacher_id

    lessons = await gd_find(db.session, "curriculum_lessons", query, order_by="week", limit=500)
    total = len(lessons)
    completed = len([l for l in lessons if l.get("is_completed")])
    class_doc = await gd_find_one(db.session, "classes", {"id": class_id})
    date_range = await _get_curriculum_date_range(class_doc or {})
    subjects = await _resolve_curriculum_subjects(class_id, current_user, class_doc)

    # Smart Lesson Plan Assistant bridge: plans generated in the assistant and
    # "saved to class" live in the `lesson_plans` collection (NOT
    # `curriculum_lessons`), so they were invisible here. Merge them at read
    # time — single source of truth, so later edits in the assistant stay live.
    # Scope: the CALLER'S OWN saved plans only (created_by == users.id, the
    # ownership key the assistant routes pin on) inside the caller's workspace/
    # school tenant. Leadership gets [] — assistant plans are creator-private
    # (the assistant list route itself filters by created_by); widening them to
    # leadership is a separate product decision. Deliberately NOT filtered by
    # subject_id: assistant plans carry a free-text subject, and hiding them
    # behind a non-matching filter would re-create the invisibility bug.
    assistant_plans: List[Dict[str, Any]] = []
    if _is_curriculum_teacher_scope(role):
        from src.core.guards.tenant_guard import independent_workspace_id, require_request_school_id
        from src.modules.independent_teacher.controllers.independent_teacher_lesson_plans_routes import (
            _serialize as _serialize_assistant_plan,
        )
        try:
            caller_workspace = (
                independent_workspace_id(current_user)
                or require_request_school_id(current_user)
            )
        except HTTPException:
            caller_workspace = None
        if caller_workspace:
            plan_rows = await gd_find(
                db.session,
                "lesson_plans",
                {
                    "class_id": class_id,
                    "is_saved": True,
                    "created_by": current_user["id"],
                    "workspace_school_id": caller_workspace,
                },
                order_by="created_at",
                desc_order=True,
                limit=200,
            )
            assistant_plans = [_serialize_assistant_plan(r) for r in (plan_rows or [])]

    return {
        "lessons": lessons,
        "total": total,
        "completed": completed,
        "progress": round((completed / total * 100) if total > 0 else 0),
        "curriculum_start_date": date_range.get("curriculum_start_date"),
        "curriculum_end_date": date_range.get("curriculum_end_date"),
        "subjects": subjects,
        "selected_subject_id": subject_id or None,
        "assistant_plans": assistant_plans,
    }


@class_teaching_router.post("/class/{class_id}/curriculum-plan/lesson")
async def add_lesson(
    class_id: str,
    lesson: LessonCreate,
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    await _verify_class_access(class_id, current_user, write=True)

    cls = await gd_find_one(db.session, "classes", {"id": class_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    role = current_user.get("role", "")
    # Only a teacher/IT caller owns a private plan, so only they stamp their
    # teacher_id onto the lesson. Leadership/platform creators stay class-wide
    # (no owner) — exactly as before this change — instead of mis-filing the
    # lesson under the admin's own user id, which would hide it from teachers.
    eff_teacher_id = _curriculum_teacher_id(current_user) if _is_curriculum_teacher_scope(role) else None

    # Curriculum plans are private per (class, subject, teacher). For a
    # teacher/IT caller, validate that the chosen subject is one they actually
    # teach in this class so a lesson can't be filed under a colleague's
    # subject. Resolution is best-effort: when the caller's subjects can't be
    # determined we still allow the write (the stored teacher_id keeps the plan
    # isolated), but we never accept a known-foreign subject.
    if _is_curriculum_teacher_scope(role) and subject_id:
        allowed = await _resolve_curriculum_subjects(class_id, current_user, cls)
        allowed_ids = {s["id"] for s in allowed}
        if allowed_ids and subject_id not in allowed_ids:
            raise HTTPException(
                status_code=403,
                detail="غير مصرّح بإضافة درس لهذه المادة في هذا الفصل",
            )

    now_ts = datetime.now(timezone.utc).isoformat()
    doc_id = str(uuid.uuid4())

    # Date-range validation (only when dates are supplied)
    date_range = await _get_curriculum_date_range(cls)
    curriculum_start = date_range["curriculum_start_date"]
    curriculum_end = date_range["curriculum_end_date"]

    out_of_range = False
    if lesson.start_date or lesson.end_date:
        if curriculum_start and curriculum_end:
            start_ok = _date_in_range(lesson.start_date, curriculum_start, curriculum_end) if lesson.start_date else True
            end_ok = _date_in_range(lesson.end_date, curriculum_start, curriculum_end) if lesson.end_date else True
            out_of_range = not (start_ok and end_ok)

    if out_of_range:
        if not lesson.override_curriculum:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "curriculum_date_conflict",
                    "message": "الدرس خارج نطاق المنهج",
                    "details": {
                        # str() everything: date objects are not JSON
                        # serializable and would turn this 409 into a 500
                        # inside the HTTPException JSON handler.
                        "curriculum_start": str(curriculum_start) if curriculum_start else None,
                        "curriculum_end": str(curriculum_end) if curriculum_end else None,
                        "provided_start": str(lesson.start_date) if lesson.start_date else None,
                        "provided_end": str(lesson.end_date) if lesson.end_date else None,
                    },
                },
            )
        if not (lesson.override_reason or "").strip():
            raise HTTPException(status_code=422, detail="يجب كتابة مبرر للتجاوز")

    doc = {
        "id": doc_id,
        "class_id": class_id,
        "subject_id": subject_id or "",
        "teacher_id": eff_teacher_id or "",
        "title": lesson.title,
        "week": lesson.week,
        "order": lesson.order,
        "notes": lesson.notes,
        "is_completed": False,
        "is_skipped": False,
        "created_at": now_ts,
    }

    start_iso = lesson.start_date.isoformat() if lesson.start_date else None
    end_iso = lesson.end_date.isoformat() if lesson.end_date else None

    if start_iso:
        doc["start_date"] = start_iso
    if end_iso:
        doc["end_date"] = end_iso

    if out_of_range and lesson.override_curriculum:
        doc["override_curriculum"] = True
        doc["override_reason"] = lesson.override_reason.strip()
        doc["override_by_user_id"] = current_user.get("id")
        doc["override_time"] = now_ts

        # Audit record
        tenant_id = cls.get("school_id") or cls.get("tenant_id") or ""
        audit_doc = {
            "id": str(uuid.uuid4()),
            "lesson_id": doc_id,
            "class_id": class_id,
            "tenant_id": tenant_id,
            "user_id": current_user.get("id"),
            "override_reason": lesson.override_reason.strip(),
            "provided_start": start_iso,
            "provided_end": end_iso,
            "curriculum_start": curriculum_start,
            "curriculum_end": curriculum_end,
            "created_at": now_ts,
        }
        await gd_insert(db.session, "curriculum_lesson_audit", audit_doc)
        logger.info(
            "curriculum_lesson_override",
            extra={
                "lesson_id": doc_id,
                "class_id": class_id,
                "tenant_id": tenant_id,
                "user_id": current_user.get("id"),
                "override_reason": lesson.override_reason.strip(),
                "provided_start": start_iso,
                "provided_end": end_iso,
                "curriculum_start": curriculum_start,
                "curriculum_end": curriculum_end,
            },
        )

    await gd_insert(db.session, "curriculum_lessons", doc)
    await _sync_curriculum_portfolio(current_user, class_id, subject_id, cls)
    return doc


@class_teaching_router.put("/curriculum-lesson/{lesson_id}")
async def update_lesson(
    lesson_id: str,
    update: LessonUpdate,
    current_user: dict = Depends(get_current_user),
):
    existing = await gd_find_one(db.session, "curriculum_lessons", {"id": lesson_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Lesson not found")
    await _verify_class_access(existing["class_id"], current_user)
    _verify_curriculum_lesson_owner(existing, current_user)

    cls = await gd_find_one(db.session, "classes", {"id": existing["class_id"]})
    now_ts = datetime.now(timezone.utc).isoformat()

    # Date-range validation + override flow — mirrors the create path, and
    # only runs when the caller actually supplies a date.
    out_of_range = False
    curriculum_start = curriculum_end = None
    if update.start_date or update.end_date:
        date_range = await _get_curriculum_date_range(cls or {})
        curriculum_start = date_range["curriculum_start_date"]
        curriculum_end = date_range["curriculum_end_date"]
        if curriculum_start and curriculum_end:
            start_ok = _date_in_range(update.start_date, curriculum_start, curriculum_end) if update.start_date else True
            end_ok = _date_in_range(update.end_date, curriculum_start, curriculum_end) if update.end_date else True
            out_of_range = not (start_ok and end_ok)

    if out_of_range:
        if not update.override_curriculum:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "curriculum_date_conflict",
                    "message": "الدرس خارج نطاق المنهج",
                    "details": {
                        "curriculum_start": curriculum_start,
                        "curriculum_end": curriculum_end,
                        "provided_start": update.start_date,
                        "provided_end": update.end_date,
                    },
                },
            )
        if not (update.override_reason or "").strip():
            raise HTTPException(status_code=422, detail="يجب كتابة مبرر للتجاوز")

    # Build a partial update: only persist fields the caller actually provided,
    # preserving the existing optimistic/partial-update behavior.
    data: dict = {}
    if update.title is not None:
        data["title"] = update.title
    if update.order is not None:
        data["order"] = update.order
    if update.is_completed is not None:
        data["is_completed"] = update.is_completed
    if update.is_skipped is not None:
        data["is_skipped"] = update.is_skipped
    if update.notes is not None:
        data["notes"] = update.notes
    if update.start_date is not None:
        data["start_date"] = update.start_date.isoformat()
    if update.end_date is not None:
        data["end_date"] = update.end_date.isoformat()

    # When the week changes, keep `order` consistent within the target week so
    # sequencing / progress calculations don't break. If the caller didn't pass
    # an explicit order, append the lesson to the end of its new week.
    if update.week is not None:
        data["week"] = update.week
        if update.week != existing.get("week") and update.order is None:
            # Keep ordering within the same private plan bucket (class, subject,
            # teacher) so one teacher's lessons don't shift another's sequence.
            wk_filter: Dict[str, Any] = {"class_id": existing["class_id"], "week": update.week}
            if existing.get("teacher_id"):
                wk_filter["teacher_id"] = existing["teacher_id"]
            if existing.get("subject_id"):
                wk_filter["subject_id"] = existing["subject_id"]
            week_lessons = await gd_find(
                db.session,
                "curriculum_lessons",
                wk_filter,
                limit=500,
            )
            count = len([l for l in week_lessons if l.get("id") != lesson_id])
            data["order"] = count + 1

    # Override metadata + audit record (only on a genuine out-of-range override).
    if out_of_range and update.override_curriculum:
        start_iso = update.start_date.isoformat() if update.start_date else None
        end_iso = update.end_date.isoformat() if update.end_date else None
        data["override_curriculum"] = True
        data["override_reason"] = update.override_reason.strip()
        data["override_by_user_id"] = current_user.get("id")
        data["override_time"] = now_ts

        tenant_id = (cls or {}).get("school_id") or (cls or {}).get("tenant_id") or ""
        audit_doc = {
            "id": str(uuid.uuid4()),
            "lesson_id": lesson_id,
            "class_id": existing["class_id"],
            "tenant_id": tenant_id,
            "user_id": current_user.get("id"),
            "override_reason": update.override_reason.strip(),
            "provided_start": start_iso,
            "provided_end": end_iso,
            "curriculum_start": curriculum_start,
            "curriculum_end": curriculum_end,
            "created_at": now_ts,
        }
        await gd_insert(db.session, "curriculum_lesson_audit", audit_doc)
        logger.info(
            "curriculum_lesson_override",
            extra={
                "lesson_id": lesson_id,
                "class_id": existing["class_id"],
                "tenant_id": tenant_id,
                "user_id": current_user.get("id"),
                "override_reason": update.override_reason.strip(),
                "provided_start": start_iso,
                "provided_end": end_iso,
                "curriculum_start": curriculum_start,
                "curriculum_end": curriculum_end,
            },
        )

    data["updated_at"] = now_ts
    await gd_update_one(db.session, "curriculum_lessons", {"id": lesson_id}, data)
    await _sync_curriculum_portfolio(
        current_user, existing["class_id"], existing.get("subject_id") or "", cls
    )
    return {**existing, **data}


@class_teaching_router.delete("/curriculum-lesson/{lesson_id}")
async def delete_lesson(
    lesson_id: str,
    current_user: dict = Depends(get_current_user),
):
    existing = await gd_find_one(db.session, "curriculum_lessons", {"id": lesson_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Lesson not found")
    await _verify_class_access(existing["class_id"], current_user)
    _verify_curriculum_lesson_owner(existing, current_user)
    await gd_delete_one(db.session, "curriculum_lessons", {"id": lesson_id})
    await _sync_curriculum_portfolio(
        current_user, existing["class_id"], existing.get("subject_id") or ""
    )
    return {"success": True}


# ============== GRADE COLUMNS CONFIG ==============

class GradeColumnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    column_type: str = Field(default="coursework")
    input_type: str = Field(default="grade")
    max_grade: float = Field(default=10, ge=1, le=100)
    order: int = Field(default=0, ge=0, le=50)
    visible: bool = True

    @model_validator(mode="after")
    def validate_column_type(self):
        if self.column_type not in ALLOWED_COLUMN_TYPES:
            raise ValueError(f"column_type must be one of {ALLOWED_COLUMN_TYPES}")
        if self.input_type not in ALLOWED_INPUT_TYPES:
            raise ValueError(f"input_type must be one of {ALLOWED_INPUT_TYPES}")
        return self

class GradeColumnUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    # Category (أعمال السنة/الاختبارات). Editable so the أنماط التقييم
    # pattern editor can re-classify a column — before this field existed
    # the key was silently dropped and a column's category was frozen at
    # creation time.
    column_type: Optional[str] = None
    input_type: Optional[str] = None
    max_grade: Optional[float] = Field(default=None, ge=1, le=100)
    order: Optional[int] = Field(default=None, ge=0, le=50)
    visible: Optional[bool] = None

    @model_validator(mode="after")
    def validate_input_type(self):
        if self.column_type is not None and self.column_type not in ALLOWED_COLUMN_TYPES:
            raise ValueError(f"column_type must be one of {ALLOWED_COLUMN_TYPES}")
        if self.input_type is not None and self.input_type not in ALLOWED_INPUT_TYPES:
            raise ValueError(f"input_type must be one of {ALLOWED_INPUT_TYPES}")
        return self


@class_teaching_router.get("/class/{class_id}/grade-columns")
async def get_grade_columns(
    class_id: str,
    current_user: dict = Depends(get_current_user),
):
    await _verify_class_access(class_id, current_user)
    columns = await gd_find(db.session, "grade_columns", {"class_id": class_id}, order_by="order", limit=50)
    if not columns:
        defaults = [
            {"name": "المشاركة", "name_en": "Participation", "column_type": "coursework", "max_grade": 5, "order": 1},
            {"name": "الواجبات", "name_en": "Homework", "column_type": "coursework", "max_grade": 5, "order": 2},
            {"name": "المهام الأدائية", "name_en": "Performance Tasks", "column_type": "coursework", "max_grade": 10, "order": 3},
            {"name": "اختبار قصير", "name_en": "Short Quiz", "column_type": "exams", "max_grade": 10, "order": 4},
            {"name": "اختبار نهاية الفترة", "name_en": "End of Period Exam", "column_type": "exams", "max_grade": 20, "order": 5},
        ]
        for d in defaults:
            d["id"] = str(uuid.uuid4())
            d["class_id"] = class_id
            d["visible"] = True
            d["input_type"] = "grade"
            d["created_at"] = datetime.now(timezone.utc).isoformat()
        await gd_insert_many(db.session, "grade_columns", defaults)
        columns = defaults
    return columns


@class_teaching_router.post("/class/{class_id}/grade-columns")
async def add_grade_column(
    class_id: str,
    col: GradeColumnCreate,
    current_user: dict = Depends(get_current_user),
):
    await _verify_class_access(class_id, current_user, write=True)
    doc_id = str(uuid.uuid4())
    doc = {
        "id": doc_id,
        "class_id": class_id,
        "name": col.name,
        "column_type": col.column_type,
        "input_type": col.input_type,
        "max_grade": col.max_grade,
        "order": col.order,
        "visible": col.visible,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "grade_columns", doc)
    return doc


@class_teaching_router.put("/grade-column/{column_id}")
async def update_grade_column(
    column_id: str,
    update: GradeColumnUpdate,
    current_user: dict = Depends(get_current_user),
):
    existing = await gd_find_one(db.session, "grade_columns", {"id": column_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Column not found")
    await _verify_class_access(existing["class_id"], current_user)
    data = {k: v for k, v in update.model_dump().items() if v is not None}
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "grade_columns", {"id": column_id}, data)
    return {**existing, **data}


@class_teaching_router.delete("/grade-column/{column_id}")
async def delete_grade_column(
    column_id: str,
    current_user: dict = Depends(get_current_user),
):
    existing = await gd_find_one(db.session, "grade_columns", {"id": column_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Column not found")
    await _verify_class_access(existing["class_id"], current_user)
    await gd_delete_one(db.session, "grade_columns", {"id": column_id})
    return {"success": True}


# ============== CLASS-LEVEL SESSION-SETTINGS TEMPLATE ==============
# The same session_settings row (keyed {class_id, subject_id, tenant_id})
# that the live lesson reads/writes via /session/{sid}/settings, exposed
# from the فصولي → class page so its "إعدادات الحصة" dialog edits the SAME
# template the next lesson will hydrate from. Validation is shared with
# the lesson route via backend/utils/session_settings.py.
#
# Session-scoped fields (correct_answer_weight / streak_bonus_value on
# class_sessions) are intentionally absent here — they belong to a live
# session only. Tenant scope derives from the CLASS row (never the
# caller), same §6.7 collaborator rationale as the grade reads above; for
# owners the class tenant equals the caller tenant, so both surfaces hit
# the same row.

async def _resolve_class_tenant(class_id: str) -> str:
    cls = await gd_find_one(db.session, "classes", {"id": class_id})
    if not cls:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")
    return str(cls.get("school_id") or cls.get("tenant_id") or "")


@class_teaching_router.get("/class/{class_id}/session-settings")
async def get_class_session_settings(
    class_id: str,
    subject_id: str = Query(..., min_length=1, max_length=100),
    current_user: dict = Depends(get_current_user),
):
    await _verify_class_access(class_id, current_user)
    tenant_id = await _resolve_class_tenant(class_id)
    record = await gd_find_one(
        db.session, "session_settings",
        {"class_id": class_id, "subject_id": subject_id, "tenant_id": tenant_id},
    )
    record = record or {}
    return {
        "class_id": class_id,
        "subject_id": subject_id,
        "exists": bool(record),
        "participation_enabled": record.get("participation_enabled", True),
        "homework_enabled": record.get("homework_enabled", True),
        "homework_view_mode": record.get("homework_view_mode", "not_submitted"),
        "recitation_enabled": record.get("recitation_enabled", False),
        "recitation_max_attempts": record.get("recitation_max_attempts", 1),
        "streak_bonus_enabled": record.get("streak_bonus_enabled", True),
        "skill_enabled": record.get("skill_enabled", False),
        "participation_scores": record.get("participation_scores", {}),
        **ss_custom_fields_from_record(record),
    }


@class_teaching_router.post("/class/{class_id}/session-settings")
async def save_class_session_settings(
    class_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    await _verify_class_access(class_id, current_user, write=True)
    tenant_id = await _resolve_class_tenant(class_id)
    subject_id = str(payload.get("subject_id") or "").strip()[:100]
    if not subject_id:
        raise HTTPException(status_code=422, detail="يجب تحديد المادة أولاً")
    lookup = {"class_id": class_id, "subject_id": subject_id, "tenant_id": tenant_id}
    existing = await gd_find_one(db.session, "session_settings", lookup)
    tenant_participation_max = await ss_load_tenant_participation_max(
        db.session, tenant_id, gd_find_one
    )
    record_data = {
        "class_id": class_id,
        "subject_id": subject_id,
        "tenant_id": tenant_id,
        "participation_enabled": bool(payload.get("participation_enabled", True)),
        "homework_enabled": bool(payload.get("homework_enabled", True)),
        "homework_view_mode": ss_sanitize_homework_view_mode(
            payload.get("homework_view_mode", "not_submitted")),
        "recitation_enabled": bool(payload.get("recitation_enabled", False)),
        "recitation_max_attempts": ss_sanitize_recitation_attempts(
            payload.get("recitation_max_attempts", 1)),
        "skill_enabled": bool(payload.get("skill_enabled", False)),
        "participation_scores": ss_sanitize_participation_scores(
            payload.get("participation_scores") or {}, tenant_participation_max),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Absent-key = don't-touch for streak_bonus_enabled (same contract as
    # the lesson route) so a client that doesn't render the toggle never
    # silently re-enables it.
    if "streak_bonus_enabled" in payload:
        record_data["streak_bonus_enabled"] = bool(payload.get("streak_bonus_enabled"))
    elif not existing:
        record_data["streak_bonus_enabled"] = True
    record_data.update(ss_sanitize_custom_element_fields(payload))
    if existing:
        await gd_update_one(db.session, "session_settings", lookup, {"$set": record_data})
    else:
        record_data["created_at"] = datetime.now(timezone.utc).isoformat()
        await gd_insert(db.session, "session_settings", record_data)
    return {"success": True, "class_id": class_id, "subject_id": subject_id}


@class_teaching_router.get("/class/{class_id}/subjects")
async def get_class_subjects(
    class_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Subject context for the Student Record (سجل الطلاب) tab.

    CLASS-WIDE by design (unlike the curriculum tab, whose plans are
    private per teacher): the record spec requires switching between ALL
    subjects attached to the class, and grade read access is already
    class-level via ``_verify_class_access``. The list is the union of:
      * ``schedule_sessions`` for the class (any teacher) — the class
        timetable is the authoritative "subjects taught in THIS class",
      * subjects that actually have ``student_grades`` docs for the class —
        so stored grades can never become unreachable if a timetable is
        later regenerated without that subject,
      * the class row's own ``subject_id`` when present.

    ``teacher_assignments`` is deliberately NOT part of the primary union:
    assignment rows can over-assign (e.g. a whole school catalogue linked
    to every class by bulk assignment/seeding), which flooded this
    dropdown with subjects never taught in the class — like chemistry on
    a grade-6 class. It is used only as a FALLBACK when the primary union
    is empty (class not yet scheduled and nothing graded), so the record
    tab never goes blank for a brand-new class.

    Each subject carries ``has_grades`` so the client can surface where
    data exists. ``default_subject_id`` prefers the caller's own first
    subject (a teacher lands on THEIR subject), then the first subject
    with grades, then the first subject overall.

    Tenant scope for the graded-subjects probe derives from the CLASS row
    (never the caller) — same §6.7 collaborator rationale as the
    student-grades read below.
    """
    await _verify_class_access(class_id, current_user)
    cls = await gd_find_one(db.session, "classes", {"id": class_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    class_school = str(cls.get("school_id") or cls.get("tenant_id") or "")

    pairs: Dict[str, str] = {}
    for ss in await gd_find(db.session, "schedule_sessions", {"class_id": class_id}, limit=1000):
        sid = ss.get("subject_id")
        if sid:
            pairs.setdefault(sid, ss.get("subject_name") or "")
    sid = cls.get("subject_id")
    if sid:
        pairs.setdefault(sid, cls.get("subject_name") or "")

    from sqlalchemy import text as _sql_text
    graded_stmt = _sql_text(
        """
        SELECT DISTINCT data->>'subject_id' AS subject_id
        FROM generic_documents
        WHERE collection = 'student_grades'
          AND data->>'class_id' = :class_id
          AND COALESCE(data->>'school_id', data->>'tenant_id') = :school_id
          AND data->>'subject_id' IS NOT NULL
        """
    )
    graded_rows = await db.session.execute(
        graded_stmt, {"class_id": class_id, "school_id": class_school}
    )
    graded_ids = {row.subject_id for row in graded_rows.all() if row.subject_id}
    for gsid in graded_ids:
        pairs.setdefault(gsid, "")

    if not pairs:
        # Fallback only: nothing scheduled and nothing graded yet. Active
        # assignments keep the tab usable for a brand-new class (and for
        # IT classes whose subject link exists only as an assignment row).
        for ta in await gd_find(
            db.session,
            "teacher_assignments",
            {"class_id": class_id, "is_active": {"$ne": False}},
            limit=500,
        ):
            sid = ta.get("subject_id")
            if sid:
                pairs.setdefault(sid, ta.get("subject_name") or "")

    subjects: List[Dict[str, Any]] = []
    for sub_id, name in pairs.items():
        if not name:
            subj = await gd_find_one(db.session, "subjects", {"id": sub_id})
            name = (subj or {}).get("name") or (subj or {}).get("name_ar") or ""
        subjects.append({"id": sub_id, "name": name, "has_grades": sub_id in graded_ids})
    # Subjects with recorded grades first, then alphabetically — keeps long
    # school lists usable without hiding anything.
    subjects.sort(key=lambda x: (not x["has_grades"], x.get("name") or ""))

    mine = await _resolve_curriculum_subjects(class_id, current_user, cls)
    mine_ids = [m["id"] for m in mine if m.get("id") in pairs]
    default_subject_id = None
    if mine_ids:
        # Among the caller's own subjects, land on one that actually has
        # grades when possible — an empty default sheet next to a sibling
        # subject full of data reads as a bug to the teacher.
        default_subject_id = next(
            (m for m in mine_ids if m in graded_ids), mine_ids[0]
        )
    elif subjects:
        default_subject_id = subjects[0]["id"]

    return {
        "class_id": class_id,
        "subjects": subjects,
        "default_subject_id": default_subject_id,
    }


@class_teaching_router.get("/class/{class_id}/student-grades")
async def get_class_student_grades(
    class_id: str,
    subject_id: Optional[str] = Query(default=None, max_length=100),
    current_user: dict = Depends(get_current_user),
):
    """Aggregated per-student grades for the class "Student Record" tab
    (سجل الطلاب).

    Each committed live session writes one ``student_grades`` doc per
    (session, student, coursework column) with a value already clamped to
    the column's [0, max] (see ``commit_session_scores``). The record shows
    the AVERAGE of those per-session values per (student, column), rounded
    to 1 decimal, so values stay on the column's fixed /max scale. The
    denominator is the number of sessions where THAT student has a row for
    THAT column — absent/no-data students never got rows, so those lessons
    don't count against them.

    Tenant scope is derived from the CLASS row (never the caller): a §6.7
    collaborator's own workspace tenant differs from the host class's
    school_id, and filtering by caller tenant would silently return zero
    rows for exactly the co-teaching path. Access itself is enforced by
    ``_verify_class_access`` (school linkage tables / IT ownership /
    collaborator widening / §8 inv. 3 cross-workspace 404).

    Aggregation runs in SQL (AVG .. GROUP BY) so a busy class with
    thousands of rows can never be truncated by a fetch limit.
    """
    await _verify_class_access(class_id, current_user)
    cls = await gd_find_one(db.session, "classes", {"id": class_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    class_school = str(cls.get("school_id") or cls.get("tenant_id") or "")

    from sqlalchemy import text as _sql_text

    params: Dict[str, Any] = {"class_id": class_id, "school_id": class_school}
    subject_clause = ""
    if subject_id:
        subject_clause = "AND data->>'subject_id' = :subject_id"
        params["subject_id"] = subject_id
    stmt = _sql_text(
        """
        SELECT data->>'student_id' AS student_id,
               data->>'column_id'  AS column_id,
               AVG((data->>'score')::float) AS avg_score,
               COUNT(*) AS sessions
        FROM generic_documents
        WHERE collection = 'student_grades'
          AND data->>'class_id' = :class_id
          AND COALESCE(data->>'school_id', data->>'tenant_id') = :school_id
          AND data->>'student_id' IS NOT NULL
          AND data->>'column_id' IS NOT NULL
          AND (data->>'score') ~ '^-?[0-9]+(\\.[0-9]+)?$'
          {subject_clause}
        GROUP BY 1, 2
        """.replace("{subject_clause}", subject_clause)
    )
    result = await db.session.execute(stmt, params)
    grades = [
        {
            "student_id": row.student_id,
            "column_id": row.column_id,
            "score": round(float(row.avg_score), 1),
            "sessions": int(row.sessions),
        }
        for row in result.all()
    ]

    # check (تحقق) / text (نص) column values are — by design — never
    # materialized into student_grades (the AVG above casts score::float, so
    # a text value there would poison the whole aggregation). Their single
    # source of truth is the followup_records blob keyed (class_id,
    # subject_id). Surface them alongside the numeric aggregation (raw,
    # uncoerced) so the class-page sheet can render what the teacher entered
    # during the lesson; grade-type manual values stay excluded here (they
    # reach the record via the commit materialization instead).
    manual_values: List[dict] = []
    try:
        columns = await gd_find(db.session, "grade_columns", {"class_id": class_id}, limit=200)
        nonnumeric_cols = {
            str(c.get("id"))
            for c in columns
            if (c.get("input_type") or "grade") in ("check", "text")
        }
        if nonnumeric_cols:
            lookup: Dict[str, Any] = {"class_id": class_id}
            if subject_id:
                lookup["subject_id"] = subject_id
            # One doc per (class, subject) — the class-wide read is bounded by
            # the class's subject count, far below the fetch limit.
            records = await gd_find(db.session, "followup_records", lookup, limit=50)
            # Defense-in-depth tenant pin: newer docs stamp school_id — reject
            # any stamped doc from a foreign tenant (malformed/stale data);
            # legacy docs without the stamp stay readable (class access is
            # already enforced above).
            records = [
                r for r in records
                if not r.get("school_id") or str(r.get("school_id")) == class_school
            ]
            # Without a subject filter a class can have one doc per subject;
            # merge oldest-first so the most recently updated doc wins a
            # (student, column) collision deterministically.
            records.sort(key=lambda r: str((r.get("data") or {}).get("updated_at") or ""))
            merged: Dict[tuple, Any] = {}
            for rec in records:
                blob = rec.get("data") or {}
                manual = blob.get("data") if isinstance(blob, dict) else None
                if not isinstance(manual, dict):
                    continue
                for sid, cols in manual.items():
                    if not isinstance(cols, dict):
                        continue
                    for cid, val in cols.items():
                        if str(cid) in nonnumeric_cols and val not in (None, ""):
                            merged[(str(sid), str(cid))] = val
            manual_values = [
                {"student_id": sid, "column_id": cid, "value": val}
                for (sid, cid), val in merged.items()
            ]
    except Exception as e:
        logger.warning(f"followup manual-values read failed for class {class_id}: {e}")

    return {
        "class_id": class_id,
        "subject_id": subject_id,
        "grades": grades,
        "manual_values": manual_values,
    }


# ============== LEGACY ROUTES ==============
@router.get("/")
async def root():
    return {"message": "مرحباً بك في نَسَّق - نظام إدارة المدارس الذكي"}

@router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await gd_insert(db.session, "status_checks", doc)
    return status_obj

@router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await gd_find(db.session, "status_checks", {}, limit=1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

# Include the router in the main app



# ============== SESSION MOVE API (Drag & Drop) ==============
class MoveSessionRequest(BaseModel):
    """طلب نقل حصة"""
    new_day_of_week: str
    new_time_slot_id: str

class MoveSessionResponse(BaseModel):
    """استجابة نقل حصة"""
    success: bool
    session_id: str
    old_day: str
    old_time_slot_id: str
    new_day: str
    new_time_slot_id: str
    conflicts: List[dict] = []
    status: str  # 'success', 'conflict_warning', 'hard_conflict'
    message: str
    message_en: str

@router.put("/schedule-sessions/{session_id}/move", response_model=MoveSessionResponse)
async def move_schedule_session(
    session_id: str,
    move_data: MoveSessionRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """
    نقل حصة من موقع إلى آخر (Drag & Drop)
    
    يتحقق من:
    1. تعارض المعلم
    2. تعارض الفصل
    3. تعارض القاعة (إن وجدت)
    
    يُرجع:
    - success: تم النقل بنجاح
    - conflict_warning: تم النقل مع وجود تعارض يحتاج مراجعة
    - hard_conflict: تم رفض النقل وإرجاع الحصة
    """
    # Get the session
    session = await gd_find_one(db.session, "schedule_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    old_day = session.get("day_of_week")
    old_time_slot_id = session.get("time_slot_id")
    schedule_id = session.get("schedule_id")
    assignment_id = session.get("assignment_id")
    
    # Get assignment details
    assignment = await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    
    teacher_id = assignment.get("teacher_id")
    class_id = assignment.get("class_id")
    
    # Validate the new time slot exists
    new_slot = await gd_find_one(db.session, "time_slots", {"id": move_data.new_time_slot_id})
    if not new_slot:
        raise HTTPException(status_code=400, detail="الفترة الزمنية غير موجودة")
    
    # Check for conflicts at the new position
    conflicts = []
    is_hard_conflict = False
    
    # 1. Check teacher conflict
    teacher_conflict = await gd_find_one(db.session, "schedule_sessions", {
        "schedule_id": schedule_id,
        "day_of_week": move_data.new_day_of_week,
        "time_slot_id": move_data.new_time_slot_id,
        "id": {"$ne": session_id},
        "status": {"$ne": SessionStatusEnum.CANCELLED.value}
    })
    
    if teacher_conflict:
        conflict_assignment = await gd_find_one(db.session, "teacher_assignments", {"id": teacher_conflict.get("assignment_id")})
        if conflict_assignment:
            conflict_teacher_id = conflict_assignment.get("teacher_id")
            conflict_class_id = conflict_assignment.get("class_id")
            
            # Check if same teacher
            if conflict_teacher_id == teacher_id:
                teacher_doc = await gd_find_one(db.session, "teachers", {"id": teacher_id})
                teacher_name = teacher_doc.get("full_name", "المعلم") if teacher_doc else "المعلم"
                conflicts.append({
                    "type": "teacher_double_booking",
                    "message": f"المعلم {teacher_name} لديه حصة أخرى في نفس الوقت",
                    "message_en": f"Teacher {teacher_name} has another session at the same time",
                    "severity": "hard",
                    "conflicting_session_id": teacher_conflict.get("id")
                })
                is_hard_conflict = True
            
            # Check if same class
            if conflict_class_id == class_id:
                class_doc = await gd_find_one(db.session, "classes", {"id": class_id})
                class_name = class_doc.get("name", "الفصل") if class_doc else "الفصل"
                conflicts.append({
                    "type": "class_double_booking",
                    "message": f"الفصل {class_name} لديه حصة أخرى في نفس الوقت",
                    "message_en": f"Class {class_name} has another session at the same time",
                    "severity": "hard",
                    "conflicting_session_id": teacher_conflict.get("id")
                })
                is_hard_conflict = True
    
    # If hard conflict, reject the move
    if is_hard_conflict:
        return MoveSessionResponse(
            success=False,
            session_id=session_id,
            old_day=old_day,
            old_time_slot_id=old_time_slot_id,
            new_day=move_data.new_day_of_week,
            new_time_slot_id=move_data.new_time_slot_id,
            conflicts=conflicts,
            status="hard_conflict",
            message="لا يمكن نقل الحصة بسبب تعارض. تم إرجاع الحصة إلى مكانها السابق.",
            message_en="Cannot move session due to conflict. Session returned to original position."
        )
    
    # Perform the move
    await gd_update_one(db.session, "schedule_sessions", {"id": session_id}, {
            "day_of_week": move_data.new_day_of_week,
            "time_slot_id": move_data.new_time_slot_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Determine response status
    if conflicts:
        status = "conflict_warning"
        message = "تم نقل الحصة مع وجود تحذيرات. يرجى مراجعة التعارضات."
        message_en = "Session moved with warnings. Please review conflicts."
    else:
        status = "success"
        message = "تم نقل الحصة بنجاح"
        message_en = "Session moved successfully"
    
    return MoveSessionResponse(
        success=True,
        session_id=session_id,
        old_day=old_day,
        old_time_slot_id=old_time_slot_id,
        new_day=move_data.new_day_of_week,
        new_time_slot_id=move_data.new_time_slot_id,
        conflicts=conflicts,
        status=status,
        message=message,
        message_en=message_en
    )



