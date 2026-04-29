"""
Standby Routes — endpoints for the Smart Standby Roster + substitution flow.

  GET  /api/standby/candidates?day=&period=&original_session_id=&absence_date=
  POST /api/substitutions      → create + notify
  DELETE /api/substitutions/{id} → revoke + remove notification (undo)

كل الـ endpoints تتطلب توثيقاً وعزل مستأجر صارم عبر `assert_school_access`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from dependencies import db, get_current_user
from engines.notification_engine import NotificationEngine
from engines.sql_utils import gd_find_one
from utils.tenant_scope import assert_school_access, resolve_school_id

from services.substitution_service import (
    assign_substitute,
    revoke_substitute,
    score_candidates_for_slot,
)


logger = logging.getLogger("nassaq.standby")
router = APIRouter()


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@router.get("/standby/candidates")
async def get_standby_candidates(
    day: str = Query(..., description="مفتاح اليوم بالإنجليزية: sunday..thursday"),
    period: int = Query(..., ge=1, le=12, description="رقم الحصة (1..7 افتراضياً)"),
    original_session_id: Optional[str] = Query(None, description="معرف الحصة الأصلية (للسياق)"),
    absence_date: Optional[str] = Query(None, description="تاريخ الغياب YYYY-MM-DD (افتراضياً اليوم)"),
    limit: int = Query(3, ge=1, le=10),
    school_id: Optional[str] = Query(None),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(get_current_user),
):
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    abs_date = absence_date or _today_iso()
    result = await score_candidates_for_slot(
        db.session,
        school_id=str(sid),
        day_of_week=day,
        period_number=int(period),
        absence_date=abs_date,
        limit=int(limit),
    )

    # Echo back original session context if provided (cheap, no extra query
    # if absent — frontend already has the cell data).
    if original_session_id:
        orig = await gd_find_one(db.session, "timetable_sessions", {"id": original_session_id})
        if orig and orig.get("school_id") in (sid, None):
            result["original_session"] = {
                "id": orig.get("id"),
                "class_id": orig.get("class_id"),
                "class_name": orig.get("class_name"),
                "subject_id": orig.get("subject_id"),
                "subject_name": orig.get("subject_name"),
                "teacher_id": orig.get("teacher_id"),
                "teacher_name": orig.get("teacher_name"),
            }

    return result


class CreateSubstitutionRequest(BaseModel):
    original_session_id: str = Field(..., min_length=1)
    substitute_teacher_id: str = Field(..., min_length=1)
    absence_date: Optional[str] = None  # YYYY-MM-DD; defaults to today


@router.post("/substitutions", status_code=201)
async def create_substitution(
    body: CreateSubstitutionRequest,
    school_id: Optional[str] = Query(None),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(get_current_user),
):
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    abs_date = body.absence_date or _today_iso()
    notif_engine = NotificationEngine(db)
    result = await assign_substitute(
        db.session,
        school_id=str(sid),
        original_session_id=body.original_session_id,
        substitute_teacher_id=body.substitute_teacher_id,
        absence_date=abs_date,
        notification_engine=notif_engine,
        actor_user_id=current_user.get("id") if current_user else None,
    )
    if not result.get("success"):
        # Map common errors to 4xx
        err = result.get("error")
        status = 400
        if err in ("session_not_found", "not_found"):
            status = 404
        elif err in ("cross_tenant",):
            status = 403
        elif err in ("teacher_busy", "already_substituting", "already_assigned"):
            status = 409
        raise HTTPException(status_code=status, detail=result.get("message_ar") or err or "فشل الإسناد")
    return result


@router.delete("/substitutions/{substitution_id}")
async def delete_substitution(
    substitution_id: str,
    school_id: Optional[str] = Query(None),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(get_current_user),
):
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    notif_engine = NotificationEngine(db)
    result = await revoke_substitute(
        db.session,
        school_id=str(sid),
        substitution_id=substitution_id,
        notification_engine=notif_engine,
    )
    if not result.get("success"):
        err = result.get("error")
        status = 400
        if err == "not_found":
            status = 404
        elif err == "cross_tenant":
            status = 403
        raise HTTPException(status_code=status, detail=result.get("message_ar") or err or "فشل التراجع")
    return result
