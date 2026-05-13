"""IT Phase 2 §6.x — Workspace analytics dashboard (Task #273).

A single read-only IT-only endpoint that returns the four time-series
roll-ups consumed by ``/teacher/analytics`` in one round-trip:

    GET /independent-teacher/analytics?from=ISO&to=ISO&class_id=...

Response shape (all collections are lists, never null):

    {
      "range": {"from": "...", "to": "..."},
      "class_id": "..." | null,
      "attendance":   [{"day": "YYYY-MM-DD",
                        "present": int, "absent": int, "late": int,
                        "excused": int, "total": int}],
      "behavior":     [{"week": "YYYY-MM-DD",
                        "positive": int, "negative": int}],
      "lesson_plans": [{"day": "YYYY-MM-DD",
                        "generated": int, "saved": int}],
      "top_students_absence":  [{"student_id", "name",
                                 "absent_count", "total_count",
                                 "absence_rate"}],
      "top_students_behavior": [{"student_id", "name",
                                 "negative_count"}],
      "top_classes_attendance":[{"class_id", "name",
                                 "attendance_rate",
                                 "present_count", "total_count"}]
    }

Workspace pinning rules (spec §8 inv. 1 + inv. 3):
  * ``tenant_id == itw_{user_id}`` is forced on every aggregation query.
  * ``class_id`` is filtered through the IT's own ``classes`` rows; an
    unknown / cross-workspace id returns **404** so the API does not
    confirm the existence of foreign-tenant rows.

Authorization:
  * IT role gate (``is_independent_teacher``) AND
  * ``Permission.ANALYTICS_READ_OWN_WORKSPACE`` is required — both are
    enforced at the route layer so a future role tweak in
    ``ROLE_PERMISSIONS`` cannot silently widen access.

No MFA step-up — read-only aggregations of data the IT already owns.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import db, get_current_user
from engines.sql_utils import gd_find_one
from middleware.rbac import Permission, ROLE_PERMISSIONS


logger = logging.getLogger("nassaq.it_analytics")

router = APIRouter(
    prefix="/independent-teacher/analytics",
    tags=["IT Analytics"],
)

_MSG_BAD_RANGE = "نطاق التاريخ غير صالح."
_MSG_CLASS_NOT_FOUND = "الفصل غير موجود في مساحتك."
_MSG_PERMISSION = "ليست لديك صلاحية الوصول إلى التحليلات."
_MSG_INTERNAL = "تعذّر جلب التحليلات — حاول لاحقًا."

_DEFAULT_RANGE_DAYS = 30
_MAX_RANGE_DAYS = 365
_TOP_N = 10
# A student must have at least this many recorded attendance rows in
# the window before their absence rate can rank in the top-N. This
# stops a single one-day absence (1/1 = 100%) from outranking a
# student with a meaningful sample size.
_TOP_ABSENCE_MIN_TOTAL = 3


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    # Permission gate (independent of the role default mapping). We
    # check both the JWT-carried slice and the role default so a future
    # role-permission tweak cannot silently widen access without an
    # explicit RBAC decision.
    perm = Permission.ANALYTICS_READ_OWN_WORKSPACE.value
    perms = current_user.get("permissions") or []
    role_perms = ROLE_PERMISSIONS.get(current_user.get("role") or "", [])
    if perm not in perms and perm not in role_perms:
        raise HTTPException(status_code=403, detail=_MSG_PERMISSION)
    return current_user


def _workspace_id(current_user: dict) -> str:
    return independent_workspace_id(current_user) or require_request_school_id(current_user)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Accept bare YYYY-MM-DD too.
        try:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=_MSG_BAD_RANGE) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_range(
    from_q: Optional[str], to_q: Optional[str],
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    end = _parse_iso(to_q) or now
    start = _parse_iso(from_q) or (end - timedelta(days=_DEFAULT_RANGE_DAYS))
    if end < start:
        raise HTTPException(status_code=422, detail=_MSG_BAD_RANGE)
    span = end - start
    if span > timedelta(days=_MAX_RANGE_DAYS):
        raise HTTPException(status_code=422, detail=_MSG_BAD_RANGE)
    return start, end


async def _resolve_class_filter(
    workspace_id: str, class_id: Optional[str],
) -> Optional[str]:
    """Return the validated class id, or None when unfiltered.

    Cross-workspace ``class_id`` → 404 per spec §8 inv. 3.
    """
    if not class_id:
        return None
    cid = str(class_id).strip()
    if not cid:
        return None
    row = await gd_find_one(
        db.session, "classes",
        {"id": cid, "school_id": workspace_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail=_MSG_CLASS_NOT_FOUND)
    return cid


async def _attendance_series(
    workspace_id: str, start: datetime, end: datetime, class_id: Optional[str],
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT to_char(date_trunc('day', a.date), 'YYYY-MM-DD') AS day, "
        "       SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present, "
        "       SUM(CASE WHEN a.status = 'absent'  THEN 1 ELSE 0 END) AS absent, "
        "       SUM(CASE WHEN a.status = 'late'    THEN 1 ELSE 0 END) AS late, "
        "       SUM(CASE WHEN a.status = 'excused' OR a.is_excused = TRUE THEN 1 ELSE 0 END) AS excused, "
        "       COUNT(*) AS total "
        "  FROM attendance a "
        " WHERE a.school_id = :ws "
        "   AND a.date >= :start AND a.date < :end "
    )
    params: Dict[str, Any] = {"ws": workspace_id, "start": start, "end": end}
    if class_id:
        sql += "   AND a.class_id = :cid "
        params["cid"] = class_id
    sql += " GROUP BY 1 ORDER BY 1 ASC"
    rows = (await db.session.execute(text(sql), params)).mappings().all()
    return [
        {
            "day": r["day"],
            "present": int(r["present"] or 0),
            "absent": int(r["absent"] or 0),
            "late": int(r["late"] or 0),
            "excused": int(r["excused"] or 0),
            "total": int(r["total"] or 0),
        }
        for r in rows
    ]


async def _behavior_series(
    workspace_id: str, start: datetime, end: datetime, class_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Weekly grouped bars: positive vs negative counts.

    The spec calls for a positive/negative split (not an arbitrary
    ``category`` axis), so we bucket on ``behaviour_records.type`` and
    leave any other ``type`` value out of the chart (it is still
    visible elsewhere in the workspace).
    """
    sql = (
        "SELECT to_char(date_trunc('week', b.created_at), 'YYYY-MM-DD') AS week, "
        "       SUM(CASE WHEN b.type = 'positive' THEN 1 ELSE 0 END) AS positive, "
        "       SUM(CASE WHEN b.type = 'negative' THEN 1 ELSE 0 END) AS negative "
        "  FROM behaviour_records b "
        " WHERE b.school_id = :ws "
        "   AND b.created_at >= :start AND b.created_at < :end "
        "   AND b.type IN ('positive', 'negative') "
    )
    params: Dict[str, Any] = {"ws": workspace_id, "start": start, "end": end}
    if class_id:
        sql += "   AND b.class_id = :cid "
        params["cid"] = class_id
    sql += " GROUP BY 1 ORDER BY 1 ASC"
    rows = (await db.session.execute(text(sql), params)).mappings().all()
    return [
        {
            "week": r["week"],
            "positive": int(r["positive"] or 0),
            "negative": int(r["negative"] or 0),
        }
        for r in rows
    ]


async def _lesson_plan_series(
    workspace_id: str, start: datetime, end: datetime,
) -> List[Dict[str, Any]]:
    """Daily lesson-plan activity.

    Spec asks for two metrics per day:
      * ``generated`` — every row created in the window
        (``lesson_plans.created_at``).
      * ``saved`` — only the rows the IT chose to keep
        (``lesson_plans.is_saved = TRUE`` at read time).
    """
    sql = (
        "SELECT to_char(date_trunc('day', lp.created_at), 'YYYY-MM-DD') AS day, "
        "       COUNT(*) AS generated, "
        "       SUM(CASE WHEN lp.is_saved = TRUE THEN 1 ELSE 0 END) AS saved "
        "  FROM lesson_plans lp "
        " WHERE lp.workspace_school_id = :ws "
        "   AND lp.created_at >= :start AND lp.created_at < :end "
        " GROUP BY 1 ORDER BY 1 ASC"
    )
    rows = (await db.session.execute(
        text(sql), {"ws": workspace_id, "start": start, "end": end},
    )).mappings().all()
    return [
        {
            "day": r["day"],
            "generated": int(r["generated"] or 0),
            "saved": int(r["saved"] or 0),
        }
        for r in rows
    ]


async def _top_students_absence(
    workspace_id: str, start: datetime, end: datetime, class_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Top students by **absence rate** (absent / total) over the window.

    A minimum sample of ``_TOP_ABSENCE_MIN_TOTAL`` recorded rows is
    required so a single 1/1 absence cannot dominate the leaderboard.
    """
    sql = (
        "SELECT s.id AS student_id, "
        "       COALESCE(s.full_name, s.id) AS name, "
        "       SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) AS absent_count, "
        "       COUNT(*) AS total_count "
        "  FROM attendance a "
        "  JOIN students s ON s.id = a.student_id "
        " WHERE a.school_id = :ws "
        "   AND s.school_id = :ws "
        "   AND a.date >= :start AND a.date < :end "
    )
    params: Dict[str, Any] = {"ws": workspace_id, "start": start, "end": end}
    if class_id:
        sql += "   AND a.class_id = :cid "
        params["cid"] = class_id
    sql += (
        " GROUP BY s.id, s.full_name "
        "HAVING COUNT(*) >= :minrows "
        "   AND SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) > 0 "
        " ORDER BY (SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END)::float "
        "          / NULLIF(COUNT(*), 0)) DESC, name ASC "
        " LIMIT :lim"
    )
    params["lim"] = _TOP_N
    params["minrows"] = _TOP_ABSENCE_MIN_TOTAL
    rows = (await db.session.execute(text(sql), params)).mappings().all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        total = int(r["total_count"] or 0)
        absent = int(r["absent_count"] or 0)
        rate = (absent / total) if total else 0.0
        out.append({
            "student_id": r["student_id"],
            "name": r["name"],
            "absent_count": absent,
            "total_count": total,
            "absence_rate": round(rate, 4),
        })
    return out


async def _top_students_behavior(
    workspace_id: str, start: datetime, end: datetime, class_id: Optional[str],
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT s.id AS student_id, "
        "       COALESCE(s.full_name, s.id) AS name, "
        "       COUNT(*) AS negative_count "
        "  FROM behaviour_records b "
        "  JOIN students s ON s.id = b.student_id "
        " WHERE b.school_id = :ws "
        "   AND s.school_id = :ws "
        "   AND b.type = 'negative' "
        "   AND b.created_at >= :start AND b.created_at < :end "
    )
    params: Dict[str, Any] = {"ws": workspace_id, "start": start, "end": end}
    if class_id:
        sql += "   AND b.class_id = :cid "
        params["cid"] = class_id
    sql += (
        " GROUP BY s.id, s.full_name "
        " ORDER BY negative_count DESC, name ASC LIMIT :lim"
    )
    params["lim"] = _TOP_N
    rows = (await db.session.execute(text(sql), params)).mappings().all()
    return [
        {
            "student_id": r["student_id"],
            "name": r["name"],
            "negative_count": int(r["negative_count"] or 0),
        }
        for r in rows
    ]


async def _top_classes_attendance(
    workspace_id: str, start: datetime, end: datetime,
) -> List[Dict[str, Any]]:
    """Top classes by present-rate (present / total) over the window."""
    sql = (
        "SELECT c.id AS class_id, "
        "       COALESCE(c.name, c.id) AS name, "
        "       SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present_count, "
        "       COUNT(*) AS total_count "
        "  FROM attendance a "
        "  JOIN classes c ON c.id = a.class_id "
        " WHERE a.school_id = :ws "
        "   AND c.school_id = :ws "
        "   AND a.date >= :start AND a.date < :end "
        " GROUP BY c.id, c.name "
        "HAVING COUNT(*) > 0 "
        " ORDER BY (SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END)::float "
        "          / NULLIF(COUNT(*), 0)) DESC, name ASC "
        " LIMIT :lim"
    )
    rows = (await db.session.execute(
        text(sql),
        {"ws": workspace_id, "start": start, "end": end, "lim": _TOP_N},
    )).mappings().all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        total = int(r["total_count"] or 0)
        present = int(r["present_count"] or 0)
        rate = (present / total) if total else 0.0
        out.append({
            "class_id": r["class_id"],
            "name": r["name"],
            "attendance_rate": round(rate, 4),
            "present_count": present,
            "total_count": total,
        })
    return out


@router.get("")
async def get_workspace_analytics(
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    class_id: Optional[str] = Query(default=None),
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)
    start, end = _resolve_range(from_, to)
    cid = await _resolve_class_filter(workspace_id, class_id)

    try:
        attendance = await _attendance_series(workspace_id, start, end, cid)
        behavior = await _behavior_series(workspace_id, start, end, cid)
        lesson_plans = await _lesson_plan_series(workspace_id, start, end)
        top_abs = await _top_students_absence(workspace_id, start, end, cid)
        top_beh = await _top_students_behavior(workspace_id, start, end, cid)
        top_cls = await _top_classes_attendance(workspace_id, start, end)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("workspace analytics aggregation failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "class_id": cid,
        "attendance": attendance,
        "behavior": behavior,
        "lesson_plans": lesson_plans,
        "top_students_absence": top_abs,
        "top_students_behavior": top_beh,
        "top_classes_attendance": top_cls,
    }
