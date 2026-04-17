"""
Schedule Candidates Routes — مرشحو الخانات الفارغة في الجدول المدرسي.

تتيح هذه النقاط للمدير أو نائبه:
- جلب 3 معلمين مرشحين لخانة فارغة (subject اختياري).
- اعتماد مرشح بنقرة واحدة.
- التراجع (حذف) عن آخر تعيين.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional
import logging

from dependencies import db, require_roles, UserRole
from engines.sql_utils import gd_find_one, gd_delete_one
from services.schedule_candidates_service import (
    get_candidates,
    assign_teacher_to_slot,
)

logger = logging.getLogger("nassaq.schedule_candidates")
router = APIRouter()


_PRINCIPAL_ROLES = [
    UserRole.PLATFORM_ADMIN,
    UserRole.SCHOOL_PRINCIPAL,
    UserRole.SCHOOL_SUB_ADMIN,
]


async def _ensure_timetable_access(timetable_id: str, current_user: dict) -> dict:
    tt = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not tt:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    role = current_user.get("role", "")
    if role != UserRole.PLATFORM_ADMIN.value:
        user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
        if user_tenant and tt.get("school_id") != user_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى هذا الجدول")
    if tt.get("status") == "published":
        raise HTTPException(status_code=400, detail="لا يمكن تعديل جدول منشور")
    return tt


@router.get("/schedule/slots/candidates")
async def list_slot_candidates(
    timetable_id: str = Query(..., description="معرف الجدول"),
    class_id: str = Query(..., description="معرف الفصل"),
    day_of_week: str = Query(..., description="اليوم: sunday/monday/..."),
    period_number: int = Query(..., ge=1, description="رقم الحصة"),
    subject_id: Optional[str] = Query(None, description="معرف المادة (اختياري)"),
    specialty: Optional[str] = Query(None, description="فلترة بالتخصص"),
    only_available: bool = Query(False, description="عرض المتاحين فقط"),
    limit: int = Query(3, ge=1, le=10),
    current_user: dict = Depends(require_roles(_PRINCIPAL_ROLES)),
):
    """يُرجع أفضل المرشحين لخانة فارغة في الجدول."""
    tt = await _ensure_timetable_access(timetable_id, current_user)

    # تأكد أن الخانة فارغة فعلاً للفصل المحدد
    existing = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": timetable_id,
        "class_id": class_id,
        "day_of_week": day_of_week,
        "period_number": period_number,
    })
    if existing:
        raise HTTPException(
            status_code=409,
            detail="هذه الخانة مشغولة بالفعل — حدّث الجدول وأعد المحاولة",
        )

    result = await get_candidates(
        db.session,
        timetable_id=timetable_id,
        school_id=tt["school_id"],
        class_id=class_id,
        day_of_week=day_of_week,
        period_number=period_number,
        subject_id=subject_id,
        specialty_filter=specialty,
        only_available=only_available,
        limit=limit,
    )
    return {
        "slot": {
            "timetable_id": timetable_id,
            "class_id": class_id,
            "day_of_week": day_of_week,
            "period_number": period_number,
            "subject_id": subject_id,
        },
        **result,
    }


class AssignSlotRequest(BaseModel):
    timetable_id: str
    class_id: str
    day_of_week: str
    period_number: int = Field(..., ge=1)
    teacher_id: str
    subject_id: Optional[str] = None


@router.post("/schedule/slots/assign")
async def assign_slot(
    request: AssignSlotRequest,
    current_user: dict = Depends(require_roles(_PRINCIPAL_ROLES)),
):
    """يعتمد مرشحاً لخانة فارغة وينشئ حصة في timetable_sessions."""
    tt = await _ensure_timetable_access(request.timetable_id, current_user)
    result = await assign_teacher_to_slot(
        db.session,
        timetable_id=request.timetable_id,
        school_id=tt["school_id"],
        class_id=request.class_id,
        subject_id=request.subject_id,
        teacher_id=request.teacher_id,
        day_of_week=request.day_of_week,
        period_number=request.period_number,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=409,
            detail=result.get("message_ar", "تعذّر اعتماد التعيين"),
        )
    return {
        "success": True,
        "session_id": result["session_id"],
        "session": result["session"],
        "message_ar": "تم اعتماد المعلم وتثبيت الحصة",
    }


class UnassignSlotRequest(BaseModel):
    session_id: str


@router.post("/schedule/slots/unassign")
async def unassign_slot(
    request: UnassignSlotRequest,
    current_user: dict = Depends(require_roles(_PRINCIPAL_ROLES)),
):
    """يتراجع عن تعيين سابق بحذف الحصة من الجدول."""
    sess = await gd_find_one(db.session, "timetable_sessions", {"id": request.session_id})
    if not sess:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة (ربما حُذفت بالفعل)")
    await _ensure_timetable_access(sess.get("timetable_id"), current_user)
    await gd_delete_one(db.session, "timetable_sessions", {"id": request.session_id})
    return {
        "success": True,
        "message_ar": "تم التراجع عن التعيين",
    }
