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
from fastapi.responses import StreamingResponse
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
_MSG_EXPORT_FAILED = "تعذّر تصدير التحليلات — حاول لاحقًا."

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
        {"id": cid, "school_id": workspace_id, "is_active": {"$ne": False}},
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


# ----------------------------------------------------------------------
# Export helpers (Task #283 — CSV + PDF download)
# ----------------------------------------------------------------------

def _hijri_stamp(now: Optional[datetime] = None) -> str:
    """Hijri ``YYYY-MM-DD`` stamp suitable for use inside a filename.

    Falls back to the Gregorian stamp when ``hijri_converter`` blows up
    (e.g. an out-of-range date), so we never wedge an export on a date
    edge case.
    """
    n = now or datetime.now(timezone.utc)
    try:
        from hijri_converter import Gregorian as HGregorian  # type: ignore
        h = HGregorian(n.year, n.month, n.day).to_hijri()
        return f"{h.year:04d}-{h.month:02d}-{h.day:02d}H"
    except Exception as exc:  # noqa: BLE001
        logger.debug("hijri stamp fallback: %s", exc)
        return n.strftime("%Y-%m-%d")


async def _aggregate_all(
    workspace_id: str, start: datetime, end: datetime, cid: Optional[str],
) -> Dict[str, Any]:
    return {
        "attendance":   await _attendance_series(workspace_id, start, end, cid),
        "behavior":     await _behavior_series(workspace_id, start, end, cid),
        "lesson_plans": await _lesson_plan_series(workspace_id, start, end),
        "top_students_absence":   await _top_students_absence(workspace_id, start, end, cid),
        "top_students_behavior":  await _top_students_behavior(workspace_id, start, end, cid),
        "top_classes_attendance": await _top_classes_attendance(workspace_id, start, end),
    }


def _fmt_pct(value: Any) -> str:
    """Render a 0..1 ratio as a localized percentage string (``95%``)."""
    try:
        return f"{round(float(value or 0) * 100)}%"
    except (TypeError, ValueError):
        return "0%"


def _fmt_date(value: Any) -> str:
    """Strip any time/zone tail from an ISO timestamp so the workbook
    shows a clean ``YYYY-MM-DD`` instead of ``2026-04-19T00:00:00Z``."""
    if not value:
        return ""
    s = str(value)
    return s[:10] if len(s) >= 10 else s


_UUID_LIKE_RE = __import__("re").compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _safe_person_name(value: Any, fallback: str = "طالب غير مسمى") -> str:
    """Return a display-safe person name.

    Upstream SQL falls back to ``COALESCE(full_name, id)`` so a missing
    name can leak a UUID. The export must show an Arabic placeholder
    instead — the spec is explicit that no raw IDs reach the workbook.
    """
    s = "" if value is None else str(value).strip()
    if not s or _UUID_LIKE_RE.match(s):
        return fallback
    return s


def _safe_class_name(value: Any) -> str:
    return _safe_person_name(value, fallback="فصل غير مسمى")


_FORMULA_INJECTION_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_csv_cell(value: Any) -> Any:
    """Neutralize spreadsheet formula injection in CSV/XLSX exports.

    If *value* is a string that starts with a spreadsheet metacharacter
    (``=``, ``+``, ``-``, ``@``, tab, or carriage-return) it is prefixed
    with a tab character so that Excel, LibreOffice, and Google Sheets
    treat the cell as literal text rather than a formula.

    Non-string values (ints, floats, None) are returned as-is because
    numeric cells cannot carry formula payloads.
    """
    if not isinstance(value, str):
        return value
    if value.startswith(_FORMULA_INJECTION_CHARS):
        return "\t" + value
    return value


def _render_analytics_xlsx(
    payload: Dict[str, Any], start: datetime, end: datetime, cid: Optional[str],
    workspace_id: str, class_label: Optional[str] = None,
) -> bytes:
    """Render the analytics dashboard as a multi-sheet Arabic workbook.

    One worksheet per data category, Arabic headers, localized dates
    and percentages, no raw IDs. Header row is bold/coloured, sheets
    are RTL, the first row is frozen and column widths are pre-sized.

    Defensive: every ``payload[...]`` slice is normalised to a list
    via ``payload.get(key) or []`` so an upstream None / missing key
    cannot crash the workbook with ``TypeError: 'NoneType' is not
    iterable``. Each per-sheet row build is also wrapped in a guard
    so one bad slice degrades to an empty sheet instead of killing
    the entire export (Phase-1 + graceful-degradation guardrails).
    """
    import io
    import pandas as pd  # type: ignore

    def _safe_rows(key: str, builder):
        try:
            return [builder(r) for r in (payload.get(key) or []) if isinstance(r, dict)]
        except Exception as exc:  # noqa: BLE001
            logger.warning("xlsx sheet '%s' degraded to empty: %s", key, exc)
            return []

    attendance_rows = _safe_rows("attendance", lambda r: {
        "اليوم": _fmt_date(r.get("day")),
        "حاضر": int(r.get("present") or 0),
        "غائب": int(r.get("absent") or 0),
        "متأخر": int(r.get("late") or 0),
        "بعذر": int(r.get("excused") or 0),
        "الإجمالي": int(r.get("total") or 0),
        "نسبة الحضور": _fmt_pct(
            ((int(r.get("present") or 0) + int(r.get("late") or 0))
             / int(r.get("total") or 0))
            if int(r.get("total") or 0) else 0
        ),
    })

    behavior_rows = _safe_rows("behavior", lambda r: {
        "بداية الأسبوع": _fmt_date(r.get("week")),
        "إيجابي": int(r.get("positive") or 0),
        "سلبي": int(r.get("negative") or 0),
        "الإجمالي": int(r.get("positive") or 0) + int(r.get("negative") or 0),
    })

    lesson_plan_rows = _safe_rows("lesson_plans", lambda r: {
        "اليوم": _fmt_date(r.get("day")),
        "تم التوليد": int(r.get("generated") or 0),
        "تم الحفظ": int(r.get("saved") or 0),
    })

    top_absence_rows = _safe_rows("top_students_absence", lambda r: {
        "الاسم": _safe_person_name(r.get("name")),
        "عدد مرات الغياب": int(r.get("absent_count") or 0),
        "إجمالي الأيام": int(r.get("total_count") or 0),
        "نسبة الغياب": _fmt_pct(r.get("absence_rate")),
    })

    top_behavior_rows = _safe_rows("top_students_behavior", lambda r: {
        "الاسم": _safe_person_name(r.get("name")),
        "عدد السلوكيات السلبية": int(r.get("negative_count") or 0),
    })

    top_classes_rows = _safe_rows("top_classes_attendance", lambda r: {
        "الفصل": _safe_class_name(r.get("name")),
        "الحضور": int(r.get("present_count") or 0),
        "الإجمالي": int(r.get("total_count") or 0),
        "نسبة الحضور": _fmt_pct(r.get("attendance_rate")),
    })

    summary_class = "كل الفصول"
    if cid:
        summary_class = _safe_class_name(class_label) if class_label else "فصل محدد"

    summary_rows = [
        {"البند": "تقرير", "القيمة": "تحليلات مساحة نَسَّق"},
        {"البند": "من تاريخ", "القيمة": _fmt_date(start.isoformat())},
        {"البند": "إلى تاريخ", "القيمة": _fmt_date(end.isoformat())},
        {"البند": "الفصل", "القيمة": summary_class},
        {"البند": "تاريخ التصدير", "القيمة": _hijri_stamp()},
    ]

    # Ordered (sheet_name -> rows, column_widths)
    sheets: List[tuple[str, List[Dict[str, Any]], List[int]]] = [
        ("ملخص التقرير",       summary_rows,       [22, 32]),
        ("ملخص الحضور",        attendance_rows,    [14, 10, 10, 10, 10, 12, 16]),
        ("تقارير السلوك",      behavior_rows,      [18, 12, 12, 14]),
        ("خطط الدروس",        lesson_plan_rows,    [14, 16, 14]),
        ("أكثر الطلاب غياباً", top_absence_rows,   [28, 18, 16, 14]),
        ("السلوكيات السلبية",  top_behavior_rows,  [28, 24]),
        ("أفضل الفصول حضوراً", top_classes_rows,   [24, 12, 12, 14]),
    ]

    buf = io.BytesIO()
    # Disable xlsxwriter's automatic string-to-formula / string-to-url
    # conversion so a roster name like ``=HYPERLINK(...)`` is written as
    # a literal text cell instead of an evaluated formula when the
    # workbook is opened in Excel / LibreOffice (CSV/XLSX injection
    # hardening — task #452).
    with pd.ExcelWriter(
        buf,
        engine="xlsxwriter",
        engine_kwargs={"options": {
            "strings_to_formulas": False,
            "strings_to_urls": False,
        }},
    ) as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#1F3A5F",
            "font_color": "#FFFFFF",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        empty_fmt = workbook.add_format({
            "italic": True,
            "font_color": "#6B7280",
            "align": "center",
        })
        for sheet_name, rows, widths in sheets:
            safe_name = sheet_name[:31]
            # Per-sheet guard: one bad slice must not kill the whole
            # workbook (graceful degradation). On failure we still
            # emit a placeholder sheet so the user gets a complete
            # download instead of an error modal.
            try:
                if rows:
                    df = pd.DataFrame(rows)
                else:
                    df = pd.DataFrame(columns=["لا توجد بيانات"])
                df.to_excel(writer, sheet_name=safe_name, index=False)
                ws = writer.sheets[safe_name]
                ws.freeze_panes(1, 0)
                try:
                    ws.right_to_left()
                except Exception:  # noqa: BLE001
                    pass
                for idx, col in enumerate(df.columns):
                    width = widths[idx] if idx < len(widths) else 18
                    ws.set_column(idx, idx, width)
                    ws.write(0, idx, col, header_fmt)
                if not rows:
                    ws.write(1, 0, "لا توجد بيانات لهذه الفترة", empty_fmt)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "xlsx sheet '%s' failed to render, emitting placeholder: %s",
                    sheet_name, exc,
                )
                fallback = pd.DataFrame(columns=["لا توجد بيانات"])
                fallback.to_excel(writer, sheet_name=safe_name, index=False)
                ws = writer.sheets[safe_name]
                try:
                    ws.right_to_left()
                except Exception:  # noqa: BLE001
                    pass
                ws.write(0, 0, "لا توجد بيانات", header_fmt)
                ws.write(1, 0, "تعذّر تجهيز هذه الورقة", empty_fmt)

    return buf.getvalue()


def _render_analytics_csv(
    payload: Dict[str, Any], start: datetime, end: datetime, cid: Optional[str],
) -> bytes:
    """Build a single CSV bundle with one section per aggregated table.

    A blank line + section header separates each block so the file
    stays readable in Excel/Numbers while remaining a single download.
    """
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["NASSAQ Workspace Analytics"])
    w.writerow(["from", start.isoformat()])
    w.writerow(["to", end.isoformat()])
    w.writerow(["class_id", cid or ""])
    w.writerow([])

    def _section(title: str, headers: List[str], rows: List[List[Any]]) -> None:
        w.writerow([title])
        w.writerow(headers)
        for r in rows:
            w.writerow(r)
        w.writerow([])

    _section(
        "attendance",
        ["day", "present", "absent", "late", "excused", "total"],
        [[r["day"], r["present"], r["absent"], r["late"], r["excused"], r["total"]]
         for r in payload["attendance"]],
    )
    _section(
        "behavior",
        ["week", "positive", "negative"],
        [[r["week"], r["positive"], r["negative"]] for r in payload["behavior"]],
    )
    _section(
        "lesson_plans",
        ["day", "generated", "saved"],
        [[r["day"], r["generated"], r["saved"]] for r in payload["lesson_plans"]],
    )
    _section(
        "top_students_absence",
        ["student_id", "name", "absent_count", "total_count", "absence_rate"],
        [[r["student_id"], _sanitize_csv_cell(r["name"]), r["absent_count"], r["total_count"], r["absence_rate"]]
         for r in payload["top_students_absence"]],
    )
    _section(
        "top_students_behavior",
        ["student_id", "name", "negative_count"],
        [[r["student_id"], _sanitize_csv_cell(r["name"]), r["negative_count"]]
         for r in payload["top_students_behavior"]],
    )
    _section(
        "top_classes_attendance",
        ["class_id", "name", "attendance_rate", "present_count", "total_count"],
        [[r["class_id"], _sanitize_csv_cell(r["name"]), r["attendance_rate"], r["present_count"], r["total_count"]]
         for r in payload["top_classes_attendance"]],
    )

    # UTF-8 BOM keeps Arabic readable when opened in Excel on Windows.
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _build_attendance_chart(rows: List[Dict[str, Any]]):
    """Stacked bar chart of present / absent / late / excused per day.

    Returns a ``reportlab`` ``Drawing`` ready to append to the story,
    or ``None`` when the series is empty (caller falls back to text).
    """
    if not rows:
        return None
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.lib import colors

    data = [
        [int(r.get("present", 0)) for r in rows],
        [int(r.get("absent", 0))  for r in rows],
        [int(r.get("late", 0))    for r in rows],
        [int(r.get("excused", 0)) for r in rows],
    ]
    palette = [
        colors.HexColor("#10b981"),
        colors.HexColor("#dc2626"),
        colors.HexColor("#f59e0b"),
        colors.HexColor("#6b7280"),
    ]
    labels = ["Present", "Absent", "Late", "Excused"]

    d = Drawing(480, 180)
    chart = VerticalBarChart()
    chart.x = 40
    chart.y = 30
    chart.height = 130
    chart.width = 420
    chart.data = data
    chart.categoryAxis.categoryNames = [str(r.get("day", "")) for r in rows]
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.angle = 45
    chart.categoryAxis.labels.dy = -6
    chart.valueAxis.valueMin = 0
    chart.bars.strokeColor = None
    for i, c in enumerate(palette):
        chart.bars[i].fillColor = c
    chart.categoryAxis.style = "stacked"

    legend = Legend()
    legend.x = 40
    legend.y = 175
    legend.alignment = "right"
    legend.colorNamePairs = list(zip(palette, labels))
    legend.fontSize = 7
    legend.deltax = 70
    legend.dxTextSpace = 4
    d.add(chart)
    d.add(legend)
    d.add(String(0, 0, "", fontSize=1))
    return d


def _build_behavior_chart(rows: List[Dict[str, Any]]):
    if not rows:
        return None
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.lib import colors

    data = [
        [int(r.get("positive", 0)) for r in rows],
        [int(r.get("negative", 0)) for r in rows],
    ]
    palette = [colors.HexColor("#10b981"), colors.HexColor("#dc2626")]
    labels = ["Positive", "Negative"]
    d = Drawing(480, 180)
    chart = VerticalBarChart()
    chart.x = 40
    chart.y = 30
    chart.height = 130
    chart.width = 420
    chart.data = data
    chart.categoryAxis.categoryNames = [str(r.get("week", "")) for r in rows]
    chart.categoryAxis.labels.fontSize = 6
    chart.valueAxis.valueMin = 0
    chart.bars.strokeColor = None
    for i, c in enumerate(palette):
        chart.bars[i].fillColor = c
    legend = Legend()
    legend.x = 40
    legend.y = 175
    legend.alignment = "right"
    legend.colorNamePairs = list(zip(palette, labels))
    legend.fontSize = 7
    legend.deltax = 70
    d.add(chart)
    d.add(legend)
    return d


def _build_lesson_plan_chart(rows: List[Dict[str, Any]]):
    if not rows:
        return None
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.lib import colors

    data = [
        [int(r.get("generated", 0)) for r in rows],
        [int(r.get("saved", 0))     for r in rows],
    ]
    palette = [colors.HexColor("#2563eb"), colors.HexColor("#10b981")]
    labels = ["Generated", "Saved"]
    d = Drawing(480, 180)
    chart = HorizontalLineChart()
    chart.x = 40
    chart.y = 30
    chart.height = 130
    chart.width = 420
    chart.data = data
    chart.categoryAxis.categoryNames = [str(r.get("day", "")) for r in rows]
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.angle = 45
    chart.categoryAxis.labels.dy = -6
    chart.valueAxis.valueMin = 0
    for i, c in enumerate(palette):
        chart.lines[i].strokeColor = c
        chart.lines[i].strokeWidth = 1.5
    legend = Legend()
    legend.x = 40
    legend.y = 175
    legend.alignment = "right"
    legend.colorNamePairs = list(zip(palette, labels))
    legend.fontSize = 7
    legend.deltax = 70
    d.add(chart)
    d.add(legend)
    return d


def _render_analytics_pdf(
    payload: Dict[str, Any], start: datetime, end: datetime, cid: Optional[str],
    workspace_id: str,
) -> bytes:
    """Render the analytics dashboard as a printable Arabic PDF.

    Each major series is rendered as both a chart (so the document is
    a true visual snapshot of the in-app dashboard) AND a data table
    underneath it (so the values are still legible when printed).
    Reuses ``engines.export_engine`` primitives so the report inherits
    the same Arabic font registration, palette and table chrome as
    every other PDF in the platform.
    """
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, SimpleDocTemplate, Spacer

    from engines.export_engine import (
        _ar_para, _ar_styles, _build_table, _register_arabic_fonts,
        NASSAQ_TURQUOISE,
    )

    _register_arabic_fonts()
    styles = _ar_styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=18 * mm, bottomMargin=15 * mm,
    )
    story: List[Any] = []
    story.append(_ar_para("تقرير التحليلات", styles["ArabicTitle"]))
    range_line = (
        f"من {start.strftime('%Y-%m-%d')} إلى {end.strftime('%Y-%m-%d')}"
    )
    story.append(_ar_para(range_line, styles["ArabicSubtitle"]))
    if cid:
        story.append(_ar_para(f"الفصل: {cid}", styles["ArabicSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=NASSAQ_TURQUOISE))
    story.append(Spacer(1, 4 * mm))

    def _section(title: str, headers: List[str], rows: List[List[Any]],
                 empty_label: str = "لا توجد بيانات") -> None:
        story.append(_ar_para(title, styles["ArabicSection"]))
        if not rows:
            story.append(_ar_para(empty_label, styles["ArabicBody"]))
        else:
            story.append(_build_table(headers, rows))
        story.append(Spacer(1, 4 * mm))

    story.append(_ar_para("الحضور اليومي", styles["ArabicSection"]))
    att_chart = _build_attendance_chart(payload["attendance"])
    if att_chart is not None:
        story.append(att_chart)
        story.append(Spacer(1, 2 * mm))
    _section(
        "تفاصيل الحضور",
        ["الإجمالي", "بعذر", "متأخر", "غائب", "حاضر", "اليوم"],
        [[r["total"], r["excused"], r["late"], r["absent"], r["present"], r["day"]]
         for r in payload["attendance"]],
    )

    story.append(_ar_para("السلوك الأسبوعي", styles["ArabicSection"]))
    beh_chart = _build_behavior_chart(payload["behavior"])
    if beh_chart is not None:
        story.append(beh_chart)
        story.append(Spacer(1, 2 * mm))
    _section(
        "تفاصيل السلوك",
        ["سلبي", "إيجابي", "الأسبوع"],
        [[r["negative"], r["positive"], r["week"]] for r in payload["behavior"]],
    )

    story.append(_ar_para("خطط الدروس اليومية", styles["ArabicSection"]))
    lp_chart = _build_lesson_plan_chart(payload["lesson_plans"])
    if lp_chart is not None:
        story.append(lp_chart)
        story.append(Spacer(1, 2 * mm))
    _section(
        "تفاصيل خطط الدروس",
        ["محفوظ", "تم إنشاؤه", "اليوم"],
        [[r["saved"], r["generated"], r["day"]] for r in payload["lesson_plans"]],
    )
    _section(
        "أعلى نسبة غياب — الطلاب",
        ["نسبة الغياب", "الإجمالي", "الغياب", "الاسم"],
        [[f"{round((r['absence_rate'] or 0) * 100)}%",
          r["total_count"], r["absent_count"], r["name"]]
         for r in payload["top_students_absence"]],
    )
    _section(
        "أكثر السلوكيات السلبية — الطلاب",
        ["العدد", "الاسم"],
        [[r["negative_count"], r["name"]] for r in payload["top_students_behavior"]],
    )
    _section(
        "أعلى نسبة حضور — الفصول",
        ["نسبة الحضور", "الإجمالي", "الحضور", "الفصل"],
        [[f"{round((r['attendance_rate'] or 0) * 100)}%",
          r["total_count"], r["present_count"], r["name"]]
         for r in payload["top_classes_attendance"]],
    )

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5))
    story.append(_ar_para(
        f"نَسَّق NASSAQ  |  {workspace_id}  |  {_hijri_stamp()}",
        styles["ArabicBody"],
    ))

    doc.build(story)
    return buf.getvalue()


@router.get("/export.csv")
async def export_workspace_analytics_csv(
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    class_id: Optional[str] = Query(default=None),
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)
    start, end = _resolve_range(from_, to)
    cid = await _resolve_class_filter(workspace_id, class_id)
    try:
        payload = await _aggregate_all(workspace_id, start, end, cid)
        body = _render_analytics_csv(payload, start, end, cid)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("workspace analytics CSV export failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_EXPORT_FAILED)

    fname = f"nassaq-analytics-{_hijri_stamp()}.csv"
    return StreamingResponse(
        iter([body]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/export.xlsx")
async def export_workspace_analytics_xlsx(
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    class_id: Optional[str] = Query(default=None),
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)
    start, end = _resolve_range(from_, to)
    cid = await _resolve_class_filter(workspace_id, class_id)
    class_label: Optional[str] = None
    if cid:
        cls_row = await gd_find_one(
            db.session, "classes", {"id": cid, "school_id": workspace_id},
        )
        if cls_row:
            class_label = cls_row.get("name") or None
    try:
        payload = await _aggregate_all(workspace_id, start, end, cid)
        body = _render_analytics_xlsx(
            payload, start, end, cid, workspace_id, class_label=class_label,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("workspace analytics XLSX export failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_EXPORT_FAILED)

    fname = f"nassaq-analytics-{_hijri_stamp()}.xlsx"
    return StreamingResponse(
        iter([body]),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/export.pdf")
async def export_workspace_analytics_pdf(
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    class_id: Optional[str] = Query(default=None),
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)
    start, end = _resolve_range(from_, to)
    cid = await _resolve_class_filter(workspace_id, class_id)
    try:
        payload = await _aggregate_all(workspace_id, start, end, cid)
        body = _render_analytics_pdf(payload, start, end, cid, workspace_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("workspace analytics PDF export failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_EXPORT_FAILED)

    fname = f"nassaq-analytics-{_hijri_stamp()}.pdf"
    return StreamingResponse(
        iter([body]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


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
