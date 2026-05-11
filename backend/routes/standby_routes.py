"""
Standby Routes — endpoints for the Smart Standby Roster + substitution flow.

  GET  /api/standby/candidates?day=&period=&original_session_id=&absence_date=
  POST /api/substitutions      → create + notify
  DELETE /api/substitutions/{id} → revoke + remove notification (undo)

  GET  /api/standby/roster                   → matrix payload for the manual
                                               override UI (Task #102)
  PUT  /api/standby/roster/cell              → add/remove/reset a single
                                               manual override

كل الـ endpoints تتطلب توثيقاً وعزل مستأجر صارم عبر `assert_school_access`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List

from dependencies import db, get_current_user, require_roles, UserRole
from engines.notification_engine import NotificationEngine
from engines.sql_utils import gd_delete_many, gd_find, gd_find_one, gd_insert
from utils.tenant_scope import assert_school_access, resolve_school_id

# Standby roster is principal/admin-only (Task #157).
_STANDBY_ROSTER_ROLES = [
    UserRole.SCHOOL_PRINCIPAL,
    UserRole.SCHOOL_ADMIN,
    UserRole.PLATFORM_ADMIN,
]
require_standby_roster_role = require_roles(_STANDBY_ROSTER_ROLES)

from services.standby_roster_service import (
    DAYS,
    PERIODS,
    _normalize_day_key,
    _resolve_blocked_days,
    apply_overrides_to_roster,
    compute_standby_roster,
    fetch_standby_overrides,
    project_day_centric_roster,
)
from services.substitution_service import (
    assign_bulk_substitutes,
    assign_substitute,
    list_vacant_slots_for_absent_teacher,
    revoke_substitute,
    revoke_substitute_batch,
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


@router.get("/standby/candidates/bulk")
async def get_bulk_candidates(
    absent_teacher_id: str = Query(..., description="معرف المعلم الغائب"),
    absence_date: Optional[str] = Query(None, description="تاريخ الغياب YYYY-MM-DD (افتراضياً اليوم)"),
    limit_per_slot: int = Query(3, ge=1, le=10),
    school_id: Optional[str] = Query(None),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(get_current_user),
):
    """يُرجع كل الحصص الشاغرة لمعلم غائب اليوم مع المرشحين الأنسب لكل خانة.

    تُستخدم لتغذية لوحة "تغطية كل حصص المعلم الغائب" — تختصر عدّة طلبات
    `/standby/candidates` في طلب واحد، وتستثني الحصص التي سبق إسناد بديل لها.
    """
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    abs_date = absence_date or _today_iso()
    return await list_vacant_slots_for_absent_teacher(
        db.session,
        school_id=str(sid),
        absent_teacher_id=absent_teacher_id,
        absence_date=abs_date,
        limit_per_slot=int(limit_per_slot),
    )


class BulkSubstitutionItem(BaseModel):
    original_session_id: str = Field(..., min_length=1)
    substitute_teacher_id: str = Field(..., min_length=1)


class BulkSubstitutionRequest(BaseModel):
    items: List[BulkSubstitutionItem] = Field(..., min_length=1, max_length=20)
    absence_date: Optional[str] = None


@router.post("/substitutions/bulk", status_code=201)
async def create_bulk_substitutions(
    body: BulkSubstitutionRequest,
    school_id: Optional[str] = Query(None),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(get_current_user),
):
    """يُسند عدّة حصص شاغرة دفعة واحدة ويُرسل إشعاراً مجمَّعاً لكل بديل.

    لا يُجهض الدفعة على فشل صف واحد — يُرجع 201 مع نتيجة تفصيلية لكل عنصر.
    إذا فشلت كل العناصر، يُعاد 409.
    """
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    abs_date = body.absence_date or _today_iso()
    notif_engine = NotificationEngine(db)
    items = [{"original_session_id": it.original_session_id,
              "substitute_teacher_id": it.substitute_teacher_id}
             for it in body.items]

    result = await assign_bulk_substitutes(
        db.session,
        school_id=str(sid),
        items=items,
        absence_date=abs_date,
        notification_engine=notif_engine,
        actor_user_id=current_user.get("id") if current_user else None,
    )
    if result.get("succeeded", 0) == 0:
        # All rows failed — surface a 409 with the per-row breakdown.
        raise HTTPException(status_code=409, detail=result)
    return result


@router.delete("/substitutions/batch/{batch_id}")
async def delete_substitution_batch(
    batch_id: str,
    school_id: Optional[str] = Query(None),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(get_current_user),
):
    """يحذف كامل دفعة الإسنادات ويزيل إشعاراتها المجمَّعة (Undo)."""
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    notif_engine = NotificationEngine(db)
    result = await revoke_substitute_batch(
        db.session,
        school_id=str(sid),
        batch_id=batch_id,
        notification_engine=notif_engine,
    )
    if not result.get("success"):
        err = result.get("error")
        status = 404 if err == "not_found" else 400
        raise HTTPException(status_code=status, detail=result.get("message_ar") or err or "فشل التراجع")
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


# ── Standby Roster (manual override) endpoints — Task #102 ────────────────

async def _resolve_active_timetable(school_id: str) -> Optional[dict]:
    """يبحث عن أحدث جدول منشور، وإن لم يوجد فأحدث مسودة."""
    pub = await gd_find(
        db.session, "timetables",
        {"school_id": school_id, "status": "published"},
        order_by="created_at", desc_order=True, limit=1,
    )
    if pub:
        return pub[0]
    drafts = await gd_find(
        db.session, "timetables",
        {"school_id": school_id, "status": "draft"},
        order_by="created_at", desc_order=True, limit=1,
    )
    return drafts[0] if drafts else None


def _detect_periods(sessions: list[dict]) -> list[int]:
    """يستنتج قائمة الحصص من الجدول الفعلي. الافتراضي 1..7 إن لم تكن هناك جلسات."""
    seen: set[int] = set()
    for s in sessions:
        try:
            p = int(s.get("period_number"))
            if 1 <= p <= 12:
                seen.add(p)
        except (TypeError, ValueError):
            continue
    if not seen:
        return list(range(1, 8))
    upper = max(max(seen), 7)
    return list(range(1, upper + 1))


@router.get("/standby/roster")
async def get_standby_roster(
    school_id: Optional[str] = Query(None),
    shape: Optional[str] = Query(
        None,
        description="نمط العرض الإضافي: 'day_centric' لإرفاق إسقاط الجدول السعودي.",
    ),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(require_standby_roster_role),
):
    """يُرجع جدول الانتظار الكامل بصيغة matrix (teachers × days × periods).

    لكل خانة:
      - status: "standby" | "busy" | "blocked" | "free"
      - auto: bool — هل اختارها المحرك التلقائي؟
      - override: "add" | "remove" | None — هل عُدّلت يدوياً؟
      - class_name / subject_name: عند status="busy"
    """
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    # Guardrail: standby generation requires that the master schedule has
    # produced at least one session. See
    # docs/superpowers/specs/2026-05-03-standby-engine-refactor-design.md.
    has_session = await gd_find_one(
        db.session, "timetable_sessions", {"school_id": str(sid)},
    )
    if not has_session:
        raise HTTPException(
            status_code=409,
            detail="يجب توليد الجدول الرئيسي أولاً قبل توليد جدول الانتظار",
        )

    teachers = await gd_find(
        db.session, "teachers",
        {"school_id": str(sid), "is_active": True},
        order_by="full_name", limit=2000,
    )

    timetable = await _resolve_active_timetable(str(sid))
    timetable_id = timetable.get("id") if timetable else None
    sessions: list[dict] = []
    if timetable_id:
        sessions = await gd_find(
            db.session, "timetable_sessions",
            {"timetable_id": timetable_id},
            limit=10000,
        )
    periods = _detect_periods(sessions)

    # Auto roster (without overrides) so we can label cells as auto vs override.
    auto_roster = await compute_standby_roster(
        db.session,
        school_id=str(sid),
        timetable_id=timetable_id,
        teachers=teachers,
        sessions=sessions,
        apply_overrides=False,
    )
    overrides = await fetch_standby_overrides(
        db.session, school_id=str(sid), timetable_id=timetable_id,
    )

    # Index: teacher_id -> set[(day, period)] busy slots from sessions.
    # Index: teacher_id -> dict[(day, period)] -> {class_name, subject_name}
    busy: dict[str, set] = {t.get("id"): set() for t in teachers if t.get("id")}
    busy_meta: dict[str, dict] = {t.get("id"): {} for t in teachers if t.get("id")}
    teacher_load: dict[str, int] = {tid: 0 for tid in busy}
    for s in sessions:
        tid = s.get("teacher_id")
        if not tid or tid not in busy:
            continue
        try:
            p = int(s.get("period_number"))
        except (TypeError, ValueError):
            continue
        d = (s.get("day_of_week") or s.get("day") or "").lower()
        if d not in DAYS or p not in periods:
            continue
        busy[tid].add((d, p))
        busy_meta[tid][(d, p)] = {
            "class_name": s.get("class_name") or "",
            "subject_name": s.get("subject_name") or "",
        }
        teacher_load[tid] += 1

    # Blocked-day map per teacher (uses the same helper used by the auto path).
    from services.standby_roster_service import _resolve_blocked_days  # internal use OK
    blocked_by_teacher: dict[str, set] = {
        t.get("id"): _resolve_blocked_days(t) for t in teachers if t.get("id")
    }

    # Override index: (teacher_id, day, period) -> action
    override_index: dict[tuple, str] = {}
    for ov in overrides:
        tid = ov.get("teacher_id")
        d = (ov.get("day") or "").lower()
        try:
            p = int(ov.get("period"))
        except (TypeError, ValueError):
            continue
        action = (ov.get("action") or "").lower()
        if tid and d in DAYS and p in periods and action in ("add", "remove"):
            override_index[(tid, d, p)] = action

    # Final roster after overrides — used to mark "standby" cells.
    final_roster = apply_overrides_to_roster(auto_roster, overrides, busy=busy)

    teacher_rows: list[dict] = []
    cells: dict[str, dict[str, dict[str, dict]]] = {}
    standby_count: dict[str, int] = {}
    for t in teachers:
        tid = t.get("id")
        if not tid:
            continue
        t_busy = busy.get(tid, set())
        t_busy_meta = busy_meta.get(tid, {})
        t_blocked = blocked_by_teacher.get(tid, set())
        t_auto = auto_roster.get(tid, set())
        t_final = final_roster.get(tid, set())

        teacher_cells: dict[str, dict[str, dict]] = {}
        for d in DAYS:
            day_cells: dict[str, dict] = {}
            for p in periods:
                cell: dict = {"status": "free", "auto": False, "override": None}
                if (d, p) in t_busy:
                    cell["status"] = "busy"
                    meta = t_busy_meta.get((d, p), {})
                    cell["class_name"] = meta.get("class_name", "")
                    cell["subject_name"] = meta.get("subject_name", "")
                elif d in t_blocked:
                    cell["status"] = "blocked"
                else:
                    if (d, p) in t_auto:
                        cell["auto"] = True
                    ov_action = override_index.get((tid, d, p))
                    if ov_action:
                        cell["override"] = ov_action
                    if (d, p) in t_final:
                        cell["status"] = "standby"
                day_cells[str(p)] = cell
            teacher_cells[d] = day_cells
        cells[tid] = teacher_cells
        standby_count[tid] = len(t_final)

        teacher_rows.append({
            "id": tid,
            "full_name": t.get("full_name") or t.get("name") or "—",
            "subject": t.get("specialization") or t.get("subject") or "",
            "weekly_quota": t.get("weekly_periods") or 0,
            "assigned_periods": teacher_load.get(tid, 0),
            "standby_capacity": standby_count[tid],
        })

    payload = {
        "timetable_id": timetable_id,
        "days": DAYS,
        "periods": periods,
        "teachers": teacher_rows,
        "cells": cells,
        "totals": {
            "teachers": len(teacher_rows),
            "auto_slots": sum(len(s) for s in auto_roster.values()),
            "final_slots": sum(len(s) for s in final_roster.values()),
            "overrides": len(overrides),
        },
    }

    # Optional Saudi-style day-centric projection (Task #157). Built from the
    # same atomic records (final_roster + overrides) that drive the legacy
    # teacher-centric matrix above — no new collection, no migration. Manual
    # overrides keep their priority because final_roster is already the
    # output of `apply_overrides_to_roster`.
    if (shape or "").lower() == "day_centric":
        # Pull per-slot unavailability so the projection can flag stale
        # manual overrides that collide with approved leave/lockouts.
        unavailable: dict[str, set] = {tid: set() for tid in busy}
        unavail_rows = await gd_find(
            db.session, "unavailability",
            {"school_id": str(sid), "entity_type": "teacher"},
            limit=10000,
        )
        for row in unavail_rows or []:
            tid = row.get("entity_id") or row.get("teacher_id")
            if not tid or tid not in unavailable:
                continue
            d = (row.get("day") or "").lower()
            try:
                p = int(row.get("period"))
            except (TypeError, ValueError):
                continue
            if d in DAYS and p in periods:
                unavailable[tid].add((d, p))

        payload["day_centric"] = project_day_centric_roster(
            final_roster=final_roster,
            teachers=teachers,
            overrides=overrides,
            busy=busy,
            periods=periods,
            days=DAYS,
            unavailable=unavailable,
            blocked_by_teacher=blocked_by_teacher,
        )

    return payload


class StandbyOverrideRequest(BaseModel):
    teacher_id: str = Field(..., min_length=1)
    day: str = Field(..., min_length=3)
    period: int = Field(..., ge=1, le=12)
    action: str = Field(..., description="add | remove | reset")
    # 1-based slot anchor for day-centric edits; omit for legacy scoping.
    slot_index: Optional[int] = Field(None, ge=1, le=50)


@router.put("/standby/roster/cell")
async def put_standby_override(
    body: StandbyOverrideRequest,
    school_id: Optional[str] = Query(None),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(require_standby_roster_role),
):
    """يضبط/يُلغي تعديلاً يدوياً لخانة انتظار واحدة.

    `action`:
      - "add"    — أُجبر إدراج المعلم في خانة الانتظار هذه.
      - "remove" — استثنِ المعلم من خانة الانتظار هذه.
      - "reset"  — احذف أي تعديل يدوي سابق على هذه الخانة (يعود التوزيع
                   التلقائي إلى التحكم).
    """
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    day = (body.day or "").lower().strip()
    if day not in DAYS:
        raise HTTPException(status_code=400, detail="يوم غير صالح")
    period = int(body.period)
    action = (body.action or "").lower().strip()
    if action not in ("add", "remove", "reset"):
        raise HTTPException(status_code=400, detail="إجراء غير صالح")

    teacher = await gd_find_one(db.session, "teachers", {"id": body.teacher_id})
    if not teacher or teacher.get("school_id") != str(sid):
        raise HTTPException(status_code=404, detail="المعلم غير موجود في هذه المدرسة")

    timetable = await _resolve_active_timetable(str(sid))
    timetable_id = timetable.get("id") if timetable else None

    # Reject manual adds that would be silently dropped (busy/leave/blocked).
    if action == "add":
        if timetable_id:
            clash = await gd_find(
                db.session, "timetable_sessions",
                {
                    "timetable_id": timetable_id,
                    "teacher_id": body.teacher_id,
                    "day_of_week": day,
                    "period_number": period,
                },
                limit=1,
            )
            if clash:
                raise HTTPException(
                    status_code=409,
                    detail="لا يمكن إضافة خانة انتظار فوق حصة مجدولة للمعلم نفسه",
                )

        # Match compute/projection semantics: unavailability rows can
        # use either `entity_id` or `teacher_id`, and `day` may be raw
        # English or Arabic — normalize both sides.
        unavail_rows = await gd_find(
            db.session, "unavailability",
            {"school_id": str(sid)},
            limit=10000,
        )
        for row in unavail_rows or []:
            row_tid = row.get("entity_id") or row.get("teacher_id")
            if row_tid != body.teacher_id:
                continue
            row_day = _normalize_day_key(row.get("day")) or (row.get("day") or "").lower()
            try:
                row_p = int(row.get("period"))
            except (TypeError, ValueError):
                continue
            if row_day == day and row_p == period:
                raise HTTPException(
                    status_code=409,
                    detail="لا يمكن إضافة خانة انتظار في وقت يقع ضمن منع زمني للمعلم",
                )

        if day in _resolve_blocked_days(teacher):
            raise HTTPException(
                status_code=409,
                detail="لا يمكن إضافة خانة انتظار في يوم إجازة المعلم",
            )

    slot_index = body.slot_index
    deleted_total = 0

    if slot_index is not None:
        # Slot-addressable edit: clear any override pinned to this cell
        # (any teacher) plus any legacy override for this teacher in
        # this column to keep the collection idempotent.
        deleted_total += await gd_delete_many(
            db.session, "standby_overrides",
            {
                "school_id": str(sid),
                "day": day,
                "period": period,
                "slot_index": slot_index,
            },
        )
        deleted_total += await gd_delete_many(
            db.session, "standby_overrides",
            {
                "school_id": str(sid),
                "teacher_id": body.teacher_id,
                "day": day,
                "period": period,
            },
        )
    else:
        # Legacy teacher-centric edit: scope by (teacher, day, period).
        deleted_total += await gd_delete_many(
            db.session, "standby_overrides",
            {
                "school_id": str(sid),
                "teacher_id": body.teacher_id,
                "day": day,
                "period": period,
            },
        )

    inserted_id: Optional[str] = None
    if action in ("add", "remove"):
        now_iso = datetime.now(timezone.utc).isoformat()
        doc = {
            "school_id": str(sid),
            "timetable_id": timetable_id,
            "teacher_id": body.teacher_id,
            "day": day,
            "period": period,
            "action": action,
            "created_at": now_iso,
            "created_by_user_id": current_user.get("id") if current_user else None,
        }
        if slot_index is not None:
            doc["slot_index"] = slot_index
        inserted_id = await gd_insert(db.session, "standby_overrides", doc)

    return {
        "success": True,
        "action": action,
        "removed_previous": deleted_total,
        "override_id": inserted_id,
        "teacher_id": body.teacher_id,
        "day": day,
        "period": period,
        "slot_index": slot_index,
    }
