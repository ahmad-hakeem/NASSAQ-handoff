"""
Schedule Candidates Routes — مرشحو الخانات الفارغة في الجدول المدرسي.

تتيح هذه النقاط للمدير أو نائبه:
- جلب 3 معلمين مرشحين لخانة فارغة (subject اختياري).
- اعتماد مرشح بنقرة واحدة.
- التراجع (حذف) عن آخر تعيين.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Tuple
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


# ─── slot_id encoding ──────────────────────────────────────────────────────
# الخانات الفارغة لا تملك معرفاً في قاعدة البيانات، لذا نستخدم معرفاً مركباً:
#   "{timetable_id}__{class_id}__{day_of_week}__{period_number}"
# للحصص المعتمدة، slot_id = id الحصة الفعلي في timetable_sessions.
def _parse_composite_slot_id(slot_id: str) -> Tuple[str, str, str, int]:
    parts = slot_id.split("__")
    if len(parts) != 4:
        raise HTTPException(
            status_code=400,
            detail="معرف الخانة غير صالح — تنسيق متوقع: timetableId__classId__day__period",
        )
    try:
        period = int(parts[3])
    except ValueError:
        raise HTTPException(status_code=400, detail="رقم الحصة في معرف الخانة غير صالح")
    return parts[0], parts[1], parts[2], period


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


@router.get("/schedule/slots/{slot_id}/candidates")
async def list_slot_candidates(
    slot_id: str,
    subject_id: Optional[str] = Query(None, description="معرف المادة (اختياري)"),
    specialty: Optional[str] = Query(None, description="فلترة بالتخصص"),
    only_available: bool = Query(False, description="عرض المتاحين فقط"),
    limit: int = Query(3, ge=1, le=10),
    current_user: dict = Depends(require_roles(_PRINCIPAL_ROLES)),
):
    """يُرجع أفضل المرشحين لخانة فارغة في الجدول.

    `slot_id` معرف مركب: `timetableId__classId__day__period`.
    """
    timetable_id, class_id, day_of_week, period_number = _parse_composite_slot_id(slot_id)
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
            "slot_id": slot_id,
            "timetable_id": timetable_id,
            "class_id": class_id,
            "day_of_week": day_of_week,
            "period_number": period_number,
            "subject_id": subject_id,
        },
        **result,
    }


class AssignSlotRequest(BaseModel):
    teacher_id: str
    subject_id: Optional[str] = None


@router.post("/schedule/slots/{slot_id}/assign")
async def assign_slot(
    slot_id: str,
    request: AssignSlotRequest,
    current_user: dict = Depends(require_roles(_PRINCIPAL_ROLES)),
):
    """يعتمد مرشحاً لخانة فارغة وينشئ حصة في timetable_sessions.

    `slot_id` معرف مركب للخانة الفارغة (راجع ملاحظة الترميز أعلاه).
    """
    timetable_id, class_id, day_of_week, period_number = _parse_composite_slot_id(slot_id)
    tt = await _ensure_timetable_access(timetable_id, current_user)
    result = await assign_teacher_to_slot(
        db.session,
        timetable_id=timetable_id,
        school_id=tt["school_id"],
        class_id=class_id,
        subject_id=request.subject_id,
        teacher_id=request.teacher_id,
        day_of_week=day_of_week,
        period_number=period_number,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=409,
            detail=result.get("message_ar", "تعذّر اعتماد التعيين"),
        )
    return {
        "success": True,
        "slot_id": slot_id,
        "session_id": result["session_id"],
        "session": result["session"],
        "message_ar": "تم اعتماد المعلم وتثبيت الحصة",
    }


@router.post("/schedule/slots/{session_id}/unassign")
async def unassign_slot(
    session_id: str,
    current_user: dict = Depends(require_roles(_PRINCIPAL_ROLES)),
):
    """يتراجع عن تعيين سابق بحذف الحصة من الجدول.

    `session_id` هنا هو معرف الحصة المعتمدة (وليس المعرف المركب للخانة الفارغة).
    """
    sess = await gd_find_one(db.session, "timetable_sessions", {"id": session_id})
    if not sess:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة (ربما حُذفت بالفعل)")
    await _ensure_timetable_access(sess.get("timetable_id"), current_user)
    await gd_delete_one(db.session, "timetable_sessions", {"id": session_id})
    return {
        "success": True,
        "session_id": session_id,
        "message_ar": "تم التراجع عن التعيين",
    }
