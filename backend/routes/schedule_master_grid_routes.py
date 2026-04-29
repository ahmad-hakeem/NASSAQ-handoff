"""
Schedule Master Grid Routes — مصفوفة الجداول الذكية الموحَّدة.

تُرجع كل البيانات اللازمة لعرض شاشة "إدارة الجداول الذكية":
- صفوف المعلمين × أعمدة (الأيام × الحصص).
- مؤشرات الأداء (KPIs): عدالة التوزيع، انتظار مُسند، معلم غائب، حصة شاغرة.
- تنبيه ديناميكي عند وجود حصص شاغرة.

تعتمد على المخازن الحالية (timetables, timetable_sessions, teachers, classes,
teacher_attendance) ولا تعدِّل أي endpoint قائم.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from dependencies import db, get_current_user
from engines.sql_utils import gd_count, gd_find, gd_find_one
from utils.tenant_scope import assert_school_access, resolve_school_id

logger = logging.getLogger("nassaq.schedule_master_grid")
router = APIRouter()


DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
PERIODS = list(range(1, 8))  # 1..7 لكل يوم


def _today_day_key() -> str:
    """Returns the day-of-week key in lowercase English (sunday..saturday)."""
    return datetime.now(timezone.utc).strftime("%A").lower()


def _jains_fairness(values: list[float]) -> float:
    """مؤشر العدالة لـ Jain — يعيد قيمة من 0 إلى 1 (1 = توزيع متساوٍ تماماً)."""
    n = len(values)
    if n == 0:
        return 1.0
    s = sum(values)
    if s <= 0:
        return 1.0
    sq = sum(v * v for v in values)
    if sq <= 0:
        return 1.0
    return (s * s) / (n * sq)


async def _resolve_active_timetable(school_id: str) -> Optional[dict]:
    """يبحث عن أحدث جدول منشور، وإن لم يوجد فأحدث مسودة (ترتيب حتمي)."""
    published = await gd_find(
        db.session,
        "timetables",
        {"school_id": school_id, "status": "published"},
        order_by="created_at",
        desc_order=True,
        limit=1,
    )
    if published:
        return published[0]
    drafts = await gd_find(
        db.session,
        "timetables",
        {"school_id": school_id, "status": "draft"},
        order_by="created_at",
        desc_order=True,
        limit=1,
    )
    return drafts[0] if drafts else None


def _date_matches_today(date_val, today_iso: str) -> bool:
    """يتحقق إن كانت قيمة التاريخ (نص/datetime/date) تخص يوم اليوم."""
    if date_val is None:
        return False
    if isinstance(date_val, str):
        return date_val.startswith(today_iso)
    # datetime / date objects
    iso_method = getattr(date_val, "isoformat", None)
    if callable(iso_method):
        try:
            return iso_method().startswith(today_iso)
        except Exception:
            return False
    return False


async def _absent_teacher_ids_today(school_id: str, valid_teacher_ids: set[str]) -> set[str]:
    """يجمع معرفات المعلمين الغائبين اليوم من teacher_attendance أو attendance.

    يطبِّع الحقول: قد يأتي معرف المعلم في `teacher_id` أو `user_id`، وقد يكون
    التاريخ نصاً أو كائن datetime/date. يقتصر على المعرفات المعروفة كمعلمين
    لتجنّب الخلط مع المستخدمين غير المعلمين.
    """
    today_iso = datetime.now(timezone.utc).date().isoformat()
    absent_ids: set[str] = set()

    def _collect(rows):
        for r in rows:
            if not _date_matches_today(r.get("date"), today_iso):
                continue
            tid = r.get("teacher_id") or r.get("user_id")
            if tid and tid in valid_teacher_ids:
                absent_ids.add(tid)

    rows1 = await gd_find(
        db.session,
        "teacher_attendance",
        {"school_id": school_id, "status": "absent"},
        limit=2000,
    )
    _collect(rows1)

    if not absent_ids:
        rows2 = await gd_find(
            db.session,
            "attendance",
            {"school_id": school_id, "type": "teacher", "status": "absent"},
            limit=2000,
        )
        _collect(rows2)

    return absent_ids


@router.get("/schedule/master-grid")
async def get_master_grid(
    school_id: Optional[str] = Query(None, description="معرف المدرسة (اختياري — يُشتق من المستخدم)"),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(get_current_user),
):
    """يُرجع البيانات الكاملة لشاشة المصفوفة الموحَّدة (Master Grid).

    البنية:
    - days: قائمة الأيام (sunday..thursday).
    - periods: قائمة الحصص (1..7).
    - teachers: صفوف المعلمين مع المعلومات (الاسم، التخصص، الرتبة، النصاب،
      عدد الحصص المُسندة، علم الغياب اليوم).
    - cells: قاموس مفهرس بـ teacher_id ثم اليوم ثم رقم الحصة.
    - kpis: مؤشرات الأداء الأربعة.
    - alert: نص تنبيه ديناميكي أو null.
    """
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    teachers = await gd_find(
        db.session,
        "teachers",
        {"school_id": sid, "is_active": True},
        order_by="full_name",
        limit=2000,
    )

    timetable = await _resolve_active_timetable(sid)
    sessions: list[dict] = []
    if timetable:
        sessions = await gd_find(
            db.session,
            "timetable_sessions",
            {"timetable_id": timetable.get("id")},
            limit=10000,
        )

    class_ids = list({s.get("class_id") for s in sessions if s.get("class_id")})
    classes = (
        await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=len(class_ids) or 1)
        if class_ids
        else []
    )
    class_name_map = {
        c.get("id"): (c.get("name") or c.get("name_ar") or "") for c in classes
    }

    subject_ids = list({s.get("subject_id") for s in sessions if s.get("subject_id")})
    subjects = (
        await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=len(subject_ids) or 1)
        if subject_ids
        else []
    )
    subject_name_map = {
        s.get("id"): (s.get("name_ar") or s.get("name") or "") for s in subjects
    }

    valid_teacher_ids = {t.get("id") for t in teachers if t.get("id")}
    absent_ids = await _absent_teacher_ids_today(sid, valid_teacher_ids)
    today_key = _today_day_key()

    cells: dict[str, dict[str, dict[str, object]]] = {}
    assigned_count: dict[str, int] = {}

    for sess in sessions:
        tid = sess.get("teacher_id")
        day = (sess.get("day_of_week") or sess.get("day") or "").lower()
        period = sess.get("period_number")
        if not tid or not day or period is None:
            continue
        try:
            period_int = int(period)
        except (TypeError, ValueError):
            continue
        period_key = str(period_int)
        teacher_cells = cells.setdefault(tid, {})
        day_cells = teacher_cells.setdefault(day, {})
        cls_id = sess.get("class_id")
        cls_name = class_name_map.get(cls_id, sess.get("class_name") or "")
        subj_name = subject_name_map.get(sess.get("subject_id"), sess.get("subject_name") or "")
        is_vacant_today = (day == today_key) and (tid in absent_ids)
        day_cells[period_key] = {
            "session_id": sess.get("id"),
            "class_id": cls_id,
            "class_name": cls_name,
            "subject_id": sess.get("subject_id"),
            "subject_name": subj_name,
            "is_vacant": is_vacant_today,
        }
        assigned_count[tid] = assigned_count.get(tid, 0) + 1

    teacher_rows: list[dict] = []
    fairness_values: list[float] = []
    for t in teachers:
        tid = t.get("id")
        quota = t.get("weekly_periods") or 0
        assigned = assigned_count.get(tid, 0)
        is_absent = tid in absent_ids
        teacher_rows.append({
            "id": tid,
            "full_name": t.get("full_name") or "",
            "subject": t.get("specialization") or t.get("subject") or "",
            "rank": t.get("rank") or "",
            "weekly_quota": quota,
            "assigned_periods": assigned,
            "is_absent_today": is_absent,
        })
        if quota and quota > 0:
            fairness_values.append(min(1.0, assigned / quota))

    fairness_pct = round(_jains_fairness(fairness_values) * 100)

    vacant_today = sum(
        1
        for s in sessions
        if (s.get("day_of_week") or s.get("day") or "").lower() == today_key
        and s.get("teacher_id") in absent_ids
    )

    assigned_waiting = 0
    if timetable:
        try:
            assigned_waiting = await gd_count(
                db.session,
                "timetable_unscheduled_demands",
                {"timetable_id": timetable.get("id")},
            )
        except Exception:  # collection may not exist yet
            assigned_waiting = 0

    kpis = {
        "fairness_pct": fairness_pct,
        "assigned_waiting": assigned_waiting,
        "absent_teachers_today": len(absent_ids),
        "vacant_sessions_today": vacant_today,
    }

    alert = None
    if vacant_today > 0:
        alert = (
            f"يوجد {vacant_today} حصة شاغرة بلا معلم — اضغط على الخلية الحمراء لعرض المرشحين"
        )

    return {
        "school_id": sid,
        "timetable_id": timetable.get("id") if timetable else None,
        "timetable_status": timetable.get("status") if timetable else None,
        "days": DAYS,
        "periods": PERIODS,
        "today": today_key,
        "teachers": teacher_rows,
        "cells": cells,
        "kpis": kpis,
        "alert": alert,
    }
