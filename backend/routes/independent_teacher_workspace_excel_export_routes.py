"""
Independent-Teacher — Excel (.xlsx) workspace export.

This is the **teacher-readable** product export. It is intentionally
separate from the lifecycle/compliance JSON-ZIP export served by
``backend/routes/independent_teacher_workspace_lifecycle_routes.py``:

  * The lifecycle export stamps ``schools.last_export_at`` and gates
    soft-delete pre-conditions; it returns a signed download token
    over a JSON-ZIP archive of whitelisted tables. It MUST keep its
    current semantics (right-to-portability + soft-delete prereq).

  * This route returns an ``.xlsx`` workbook with human-readable
    Arabic worksheets (Overview, Classes, Students, Subjects,
    Schedule, Attendance, Assessments, Behaviour, Parent invitations)
    intended for day-to-day teacher use. It does NOT touch
    ``schools.last_export_at`` and does NOT mint a single-use token
    — the workbook is streamed inline as the HTTP response body.

Security boundary (matches the lifecycle export):
  * IT-only (``_require_independent_teacher``).
  * Recent-MFA gated via ``require_recent_mfa_403`` — same step-up
    envelope the IT FE axios interceptor already replays.
  * RBAC ``workspace.export`` permission required.
  * Every query is pinned to the caller's ``itw_{user_id}`` workspace
    via ``independent_workspace_id(current_user)`` /
    ``require_request_school_id``. No request param ever supplies a
    school id.
  * Sensitive columns (password hashes, MFA secrets, reset tokens,
    webauthn material, token hashes) are stripped at the table-read
    boundary — same allow-list approach as the lifecycle export, only
    even stricter because the Excel format is end-user facing.

Workbook structure: one sheet per data domain, Arabic sheet names,
frozen header row, sensible column widths. Empty collections emit a
single "لا توجد بيانات" row so xlsxwriter never writes a blank sheet
(which Excel renders confusingly).
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import (
    audit_engine,
    db,
    get_current_user,
    require_recent_mfa_403,
)
from engines.sql_utils import gd_find, gd_find_one
from middleware.rbac import Permission, RBACMiddleware


logger = logging.getLogger("nassaq.it_workspace_excel_export")

router = APIRouter()


# -- Audit -----------------------------------------------------------------

AUDIT_EXPORT_EXCEL = "INDEPENDENT_TEACHER_EXPORT_EXCEL"


# -- Safe Arabic copy ------------------------------------------------------

_MSG_INTERNAL = "تعذّر إنشاء ملف Excel — حاول لاحقًا."
_MSG_WORKSPACE_NOT_FOUND = "لم يتم العثور على مساحة العمل."
_EMPTY_ROW_LABEL = "لا توجد بيانات"

_XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Columns we never expose in the workbook (parallels the lifecycle
# export's _REDACTED_COLUMNS but kept locally so a future widening of
# one surface can't silently widen the other).
_REDACTED_COLUMNS = frozenset({
    "password_hash",
    "reset_token_hash", "reset_token_expires_at",
    "webauthn_public_key", "webauthn_credential_id", "webauthn_sign_count",
    "totp_secret", "totp_secret_encrypted",
    "token_hash",
})


# -- Dependencies ----------------------------------------------------------

async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


_recent_mfa_403_dep = require_recent_mfa_403()


async def _require_workspace_export_perm(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not RBACMiddleware.has_permission(
        current_user, Permission.WORKSPACE_EXPORT.value,
    ):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


# -- Formatting helpers ---------------------------------------------------

_AR_DAY_OF_WEEK = {
    "sunday": "الأحد", "monday": "الإثنين", "tuesday": "الثلاثاء",
    "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة",
    "saturday": "السبت",
    "0": "الأحد", "1": "الإثنين", "2": "الثلاثاء", "3": "الأربعاء",
    "4": "الخميس", "5": "الجمعة", "6": "السبت",
}

_AR_GENDER = {"male": "ذكر", "female": "أنثى", "m": "ذكر", "f": "أنثى"}

_AR_ATTENDANCE_STATUS = {
    "present": "حاضر", "absent": "غائب", "late": "متأخر",
    "excused": "غائب بعذر", "early_leave": "انصراف مبكر",
}

_AR_ASSESSMENT_STATUS = {
    "draft": "مسودة", "published": "منشور", "graded": "مُصحَّح",
    "closed": "مغلق", "scheduled": "مجدول",
}

_AR_BEHAVIOUR_TYPE = {
    "positive": "إيجابي", "negative": "سلبي",
    "warning": "تنبيه", "incident": "حادثة",
}

_AR_INVITATION_STATUS = {
    "pending": "قيد الانتظار", "accepted": "مقبولة",
    "cancelled": "ملغاة", "expired": "منتهية", "revoked": "ملغاة",
}

_AR_YES_NO = {True: "نعم", False: "لا"}


def _fmt_dt(v: Any) -> str:
    """Human-readable timestamp. Returns '' for falsy inputs so empty
    cells stay empty instead of literal 'None'."""
    if v is None or v == "":
        return ""
    if isinstance(v, datetime):
        dt = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return v
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    return str(v)


def _fmt_date(v: Any) -> str:
    """Date-only variant of ``_fmt_dt``."""
    if v is None or v == "":
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return v[:10]
    return str(v)


def _fmt_list(v: Any) -> str:
    """Flatten JSONB arrays to a comma-separated string for cell use.
    Never returns a raw list/dict — Excel would otherwise serialize it
    as ``[object Object]``-style noise."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        parts: List[str] = []
        for item in v:
            if item is None:
                continue
            if isinstance(item, dict):
                # Pick a sensible display field if present, else flatten.
                disp = item.get("name") or item.get("title") or item.get("label")
                parts.append(str(disp) if disp else ", ".join(
                    f"{k}: {vv}" for k, vv in item.items() if vv is not None
                ))
            else:
                parts.append(str(item))
        return "، ".join(parts)
    if isinstance(v, dict):
        return "، ".join(
            f"{k}: {vv}" for k, vv in v.items() if vv is not None
        )
    return str(v)


def _ar_bool(v: Any) -> str:
    if v is True:
        return "نعم"
    if v is False:
        return "لا"
    return ""


# Leading characters that spreadsheet apps (Excel / LibreOffice / Sheets)
# interpret as the start of a formula. A roster value like
# ``=HYPERLINK(...)`` or ``+cmd|...`` would otherwise execute when the
# workbook is opened. We neutralize by prefixing a literal apostrophe so
# the cell renders as text — parity with the analytics export's
# ``_sanitize_csv_cell`` and the shared ``export_engine``.
_FORMULA_INJECTION_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_cell(value: Any) -> Any:
    """Prefix a literal apostrophe to any string cell that begins with a
    formula trigger char. Non-string values are returned unchanged."""
    if isinstance(value, str) and value and value[0] in _FORMULA_INJECTION_CHARS:
        return "'" + value
    return value


def _redact(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in row.items() if k not in _REDACTED_COLUMNS}


async def _safe_find(table: str, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Best-effort scoped read. A missing table / column logs a warning
    and yields an empty list so a single optional collection never
    fails the whole workbook."""
    try:
        rows = await gd_find(db.session, table, scope)
        return [_redact(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("excel export: table=%s scope=%s skipped: %s", table, scope, exc)
        return []


def _lookup(rows: Iterable[Dict[str, Any]], key: str = "id") -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = r.get(key)
        if k:
            out[k] = r
    return out


def _class_label(class_row: Optional[Dict[str, Any]]) -> str:
    if not class_row:
        return ""
    name = class_row.get("name") or class_row.get("name_en") or ""
    section = class_row.get("section")
    grade = class_row.get("grade_level") or class_row.get("grade_id")
    bits = [str(name)] if name else []
    if grade:
        bits.append(str(grade))
    if section:
        bits.append(str(section))
    return " - ".join([b for b in bits if b])


def _student_label(student_row: Optional[Dict[str, Any]]) -> str:
    if not student_row:
        return ""
    return str(student_row.get("full_name") or student_row.get("full_name_en") or "")


def _subject_label(subject_row: Optional[Dict[str, Any]]) -> str:
    if not subject_row:
        return ""
    return str(
        subject_row.get("name_ar")
        or subject_row.get("name")
        or subject_row.get("name_en")
        or ""
    )


# -- Sheet builders -------------------------------------------------------
#
# Each builder returns a list of OrderedDict-style rows where keys are
# Arabic column headers. Empty collections return a single sentinel row
# so xlsxwriter never produces a header-only sheet.


def _empty_sheet(columns: List[str]) -> List[Dict[str, Any]]:
    row = {col: "" for col in columns}
    row[columns[0]] = _EMPTY_ROW_LABEL
    return [row]


def _build_overview_sheet(
    school: Dict[str, Any],
    counts: Dict[str, int],
) -> List[Dict[str, Any]]:
    rows = [
        {"الحقل": "اسم المساحة", "القيمة": school.get("name_ar") or school.get("name") or ""},
        {"الحقل": "الاسم بالإنجليزية", "القيمة": school.get("name_en") or ""},
        {"الحقل": "معرّف المساحة", "القيمة": school.get("id") or ""},
        {"الحقل": "تاريخ الإنشاء", "القيمة": _fmt_dt(school.get("created_at"))},
        {"الحقل": "آخر تصدير قياسي (للأرشفة)", "القيمة": _fmt_dt(school.get("last_export_at"))},
        {"الحقل": "عدد الفصول", "القيمة": counts.get("classes", 0)},
        {"الحقل": "عدد الطلاب", "القيمة": counts.get("students", 0)},
        {"الحقل": "عدد المواد", "القيمة": counts.get("subjects", 0)},
        {"الحقل": "حصص الجدول", "القيمة": counts.get("schedule", 0)},
        {"الحقل": "سجلات الحضور", "القيمة": counts.get("attendance", 0)},
        {"الحقل": "التقييمات", "القيمة": counts.get("assessments", 0)},
        {"الحقل": "سجلات السلوك", "القيمة": counts.get("behaviour", 0)},
        {"الحقل": "دعوات أولياء الأمور", "القيمة": counts.get("invitations", 0)},
        {"الحقل": "تاريخ توليد الملف", "القيمة": _fmt_dt(datetime.now(timezone.utc))},
    ]
    return rows


def _build_classes_sheet(classes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cols = ["الاسم", "الاسم بالإنجليزية", "المرحلة", "الشعبة", "السعة",
            "الطلاب الحاليون", "معلم الفصل", "نشط", "تاريخ الإنشاء"]
    if not classes:
        return _empty_sheet(cols)
    return [
        {
            "الاسم": c.get("name") or "",
            "الاسم بالإنجليزية": c.get("name_en") or "",
            "المرحلة": c.get("grade_level") or c.get("grade_id") or "",
            "الشعبة": c.get("section") or "",
            "السعة": c.get("capacity") or 0,
            "الطلاب الحاليون": c.get("current_students") or 0,
            "معلم الفصل": c.get("homeroom_teacher_name") or "",
            "نشط": _ar_bool(c.get("is_active")),
            "تاريخ الإنشاء": _fmt_dt(c.get("created_at")),
        }
        for c in classes
    ]


def _build_students_sheet(
    students: List[Dict[str, Any]],
    classes_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cols = ["الاسم الكامل", "الاسم بالإنجليزية", "رقم الطالب", "رقم الهوية",
            "الجنس", "تاريخ الميلاد", "المرحلة", "الفصل", "اسم ولي الأمر",
            "هاتف ولي الأمر", "البريد الإلكتروني لولي الأمر", "موهبة", "نشط"]
    if not students:
        return _empty_sheet(cols)
    return [
        {
            "الاسم الكامل": s.get("full_name") or "",
            "الاسم بالإنجليزية": s.get("full_name_en") or "",
            "رقم الطالب": s.get("student_number") or "",
            "رقم الهوية": s.get("national_id") or "",
            "الجنس": _AR_GENDER.get(str(s.get("gender") or "").lower(), s.get("gender") or ""),
            "تاريخ الميلاد": _fmt_date(s.get("date_of_birth")),
            "المرحلة": s.get("grade") or "",
            "الفصل": _class_label(classes_by_id.get(s.get("class_id") or "")),
            "اسم ولي الأمر": s.get("parent_name") or s.get("pending_parent_name") or "",
            "هاتف ولي الأمر": s.get("parent_phone") or s.get("pending_parent_phone") or "",
            "البريد الإلكتروني لولي الأمر": s.get("parent_email") or s.get("pending_parent_email") or "",
            "موهبة": _ar_bool(s.get("is_gifted")),
            "نشط": _ar_bool(s.get("is_active")),
        }
        for s in students
    ]


def _build_subjects_sheet(subjects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cols = ["الاسم", "الاسم بالعربية", "الاسم بالإنجليزية", "الرمز",
            "الفئة", "الحصص الأسبوعية الافتراضية", "نشط"]
    if not subjects:
        return _empty_sheet(cols)
    return [
        {
            "الاسم": s.get("name") or "",
            "الاسم بالعربية": s.get("name_ar") or "",
            "الاسم بالإنجليزية": s.get("name_en") or "",
            "الرمز": s.get("code") or "",
            "الفئة": s.get("category") or "",
            "الحصص الأسبوعية الافتراضية": s.get("default_periods_per_week") or 0,
            "نشط": _ar_bool(s.get("is_active")),
        }
        for s in subjects
    ]


def _build_schedule_sheet(
    sessions: List[Dict[str, Any]],
    classes_by_id: Dict[str, Dict[str, Any]],
    subjects_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cols = ["اليوم", "رقم الحصة", "وقت البداية", "وقت النهاية",
            "الفصل", "المادة", "الحالة"]
    if not sessions:
        return _empty_sheet(cols)
    return [
        {
            "اليوم": _AR_DAY_OF_WEEK.get(
                str(s.get("day_of_week") or s.get("day") or "").lower(),
                s.get("day_of_week") or s.get("day") or "",
            ),
            "رقم الحصة": s.get("slot_number") or "",
            "وقت البداية": s.get("start_time") or "",
            "وقت النهاية": s.get("end_time") or "",
            "الفصل": s.get("class_name")
                or _class_label(classes_by_id.get(s.get("class_id") or "")),
            "المادة": s.get("subject_name")
                or _subject_label(subjects_by_id.get(s.get("subject_id") or "")),
            "الحالة": s.get("status") or "",
        }
        for s in sessions
    ]


def _build_attendance_sheet(
    attendance: List[Dict[str, Any]],
    students_by_id: Dict[str, Dict[str, Any]],
    classes_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cols = ["التاريخ", "الطالب", "الفصل", "الحالة", "بعذر",
            "سبب العذر", "ملاحظات"]
    if not attendance:
        return _empty_sheet(cols)
    return [
        {
            "التاريخ": _fmt_date(a.get("date")),
            "الطالب": _student_label(students_by_id.get(a.get("student_id") or "")),
            "الفصل": _class_label(classes_by_id.get(a.get("class_id") or "")),
            "الحالة": _AR_ATTENDANCE_STATUS.get(
                str(a.get("status") or "").lower(), a.get("status") or "",
            ),
            "بعذر": _ar_bool(a.get("is_excused")),
            "سبب العذر": a.get("excuse_reason") or "",
            "ملاحظات": a.get("notes") or "",
        }
        for a in attendance
    ]


def _build_assessments_sheet(
    assessments: List[Dict[str, Any]],
    classes_by_id: Dict[str, Dict[str, Any]],
    subjects_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cols = ["الاسم", "النوع", "الفصل", "المادة", "الدرجة العظمى",
            "الوزن", "تاريخ التسليم", "الحالة", "الوصف"]
    if not assessments:
        return _empty_sheet(cols)
    return [
        {
            "الاسم": a.get("name") or "",
            "النوع": a.get("type") or "",
            "الفصل": _class_label(classes_by_id.get(a.get("class_id") or "")),
            "المادة": _subject_label(subjects_by_id.get(a.get("subject_id") or "")),
            "الدرجة العظمى": a.get("max_score") or 0,
            "الوزن": a.get("weight") if a.get("weight") is not None else "",
            "تاريخ التسليم": _fmt_dt(a.get("due_date")),
            "الحالة": _AR_ASSESSMENT_STATUS.get(
                str(a.get("status") or "").lower(), a.get("status") or "",
            ),
            "الوصف": a.get("description") or "",
        }
        for a in assessments
    ]


def _build_behaviour_sheet(
    behaviour: List[Dict[str, Any]],
    students_by_id: Dict[str, Dict[str, Any]],
    classes_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cols = ["التاريخ", "الطالب", "الفصل", "النوع", "الفئة", "الشدة",
            "النقاط", "الوصف", "الإجراء المتخذ", "إبلاغ ولي الأمر"]
    if not behaviour:
        return _empty_sheet(cols)
    return [
        {
            "التاريخ": _fmt_date(b.get("date") or b.get("created_at")),
            "الطالب": _student_label(students_by_id.get(b.get("student_id") or "")),
            "الفصل": _class_label(classes_by_id.get(b.get("class_id") or "")),
            "النوع": _AR_BEHAVIOUR_TYPE.get(
                str(b.get("type") or "").lower(), b.get("type") or "",
            ),
            "الفئة": b.get("category") or "",
            "الشدة": b.get("severity") or "",
            "النقاط": b.get("points") or 0,
            "الوصف": b.get("description") or "",
            "الإجراء المتخذ": b.get("action_taken") or "",
            "إبلاغ ولي الأمر": _ar_bool(b.get("parent_notified")),
        }
        for b in behaviour
    ]


def _build_invitations_sheet(
    invitations: List[Dict[str, Any]],
    students_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cols = ["الطالب", "البريد الإلكتروني لولي الأمر", "هاتف ولي الأمر",
            "الحالة", "تاريخ الإرسال", "تاريخ القبول", "تاريخ الانتهاء"]
    if not invitations:
        return _empty_sheet(cols)
    return [
        {
            "الطالب": _student_label(students_by_id.get(i.get("student_id") or "")),
            "البريد الإلكتروني لولي الأمر": i.get("parent_email") or "",
            "هاتف ولي الأمر": i.get("parent_phone") or "",
            "الحالة": _AR_INVITATION_STATUS.get(
                str(i.get("status") or "").lower(), i.get("status") or "",
            ),
            "تاريخ الإرسال": _fmt_dt(i.get("sent_at")),
            "تاريخ القبول": _fmt_dt(i.get("accepted_at")),
            "تاريخ الانتهاء": _fmt_dt(i.get("expires_at")),
        }
        for i in invitations
    ]


# -- Workbook builder -----------------------------------------------------

_SHEET_COL_WIDTHS = {
    # Sane defaults per sheet — keeps the file readable without a
    # second autosize pass. Columns not listed get a 18-wide default.
    "معلومات الحساب": [28, 42],
    "الفصول": [22, 22, 16, 12, 10, 16, 24, 8, 20],
    "الطلاب": [26, 26, 14, 16, 10, 14, 14, 22, 24, 18, 30, 10, 8],
    "المواد": [24, 24, 24, 14, 14, 26, 8],
    "الجدول": [12, 12, 12, 12, 22, 22, 14],
    "الحضور": [14, 26, 22, 14, 8, 28, 32],
    "التقييمات": [26, 14, 22, 22, 14, 10, 18, 14, 36],
    "السلوك": [14, 26, 22, 14, 14, 12, 10, 36, 32, 16],
    "أولياء الأمور": [26, 30, 18, 14, 18, 18, 18],
}


def _build_workbook(sheets: Dict[str, List[Dict[str, Any]]]) -> bytes:
    """Render the ordered ``sheets`` mapping to an ``.xlsx`` byte string.

    Uses ``xlsxwriter`` (already a project dependency) for header
    formatting, frozen header row, and per-sheet column widths.
    """
    buf = io.BytesIO()
    # Disable xlsxwriter's automatic string-to-formula / string-to-url
    # conversion so a roster name like ``=HYPERLINK(...)`` is written as
    # a literal text cell instead of an evaluated formula when the
    # workbook is opened in Excel / LibreOffice (CSV/XLSX injection
    # hardening — parity with the analytics export).
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
            "bg_color": "#1F3A5F",  # brand-navy
            "font_color": "#FFFFFF",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        for sheet_name, rows in sheets.items():
            # Excel sheet names cap at 31 chars and forbid a small set
            # of characters. Our Arabic names are all under the limit
            # and don't use any forbidden character, but truncate
            # defensively in case a future column drift sneaks one in.
            safe_name = sheet_name[:31]
            df = pd.DataFrame(rows)
            # Neutralize spreadsheet formula injection on every body cell
            # before it is written (attacker-controllable roster names /
            # notes). ``strings_to_formulas=False`` above is belt; this is
            # braces — it guarantees the literal apostrophe prefix even if
            # a future writer reads these cells with formula coercion on.
            if not df.empty:
                df = df.map(_sanitize_cell)
            df.to_excel(writer, sheet_name=safe_name, index=False)
            ws = writer.sheets[safe_name]
            # Frozen header row + RTL sheet direction (Arabic-first).
            ws.freeze_panes(1, 0)
            try:
                ws.right_to_left()
            except Exception:  # noqa: BLE001
                # xlsxwriter < 3.0 may not expose right_to_left; ignore
                # — the file is still valid, just LTR.
                pass
            widths = _SHEET_COL_WIDTHS.get(sheet_name, [])
            for idx, col in enumerate(df.columns):
                width = widths[idx] if idx < len(widths) else 18
                ws.set_column(idx, idx, width)
                # Headers are static Arabic labels, but sanitize defensively
                # so a future drift that surfaces a dynamic header can't
                # reintroduce the injection.
                ws.write(0, idx, _sanitize_cell(col), header_fmt)
    return buf.getvalue()


# -- Endpoint: POST /independent-teacher/workspace/export-excel ----------

@router.post("/independent-teacher/workspace/export-excel")
async def export_workspace_excel(
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
    _perm: dict = Depends(_require_workspace_export_perm),
):
    """Return an ``.xlsx`` workbook of the caller's workspace data.

    Tenant scope is resolved server-side from the JWT (never from a
    request body / query / path); every read below uses the same
    ``workspace_id`` filter.
    """
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)

    try:
        # Batch-load every collection up front. Each row count is bounded
        # by the IT per-user quotas (≤ 200 students, ≤ 10 classes, etc.),
        # so the entire workspace fits comfortably in memory and avoids
        # any N+1 inside the sheet builders.
        classes = await _safe_find("classes", {"school_id": workspace_id})
        students = await _safe_find("students", {"school_id": workspace_id})
        subjects = await _safe_find("subjects", {"school_id": workspace_id})
        sessions = await _safe_find("schedule_sessions", {"school_id": workspace_id})
        attendance = await _safe_find("attendance", {"school_id": workspace_id})
        assessments = await _safe_find("assessments", {"school_id": workspace_id})
        behaviour = await _safe_find("behaviour_records", {"school_id": workspace_id})
        invitations = await _safe_find(
            "parent_invitations", {"workspace_school_id": workspace_id},
        )

        classes_by_id = _lookup(classes)
        students_by_id = _lookup(students)
        subjects_by_id = _lookup(subjects)

        counts = {
            "classes": len(classes),
            "students": len(students),
            "subjects": len(subjects),
            "schedule": len(sessions),
            "attendance": len(attendance),
            "assessments": len(assessments),
            "behaviour": len(behaviour),
            "invitations": len(invitations),
        }

        sheets: Dict[str, List[Dict[str, Any]]] = {
            "معلومات الحساب": _build_overview_sheet(school, counts),
            "الفصول": _build_classes_sheet(classes),
            "الطلاب": _build_students_sheet(students, classes_by_id),
            "المواد": _build_subjects_sheet(subjects),
            "الجدول": _build_schedule_sheet(sessions, classes_by_id, subjects_by_id),
            "الحضور": _build_attendance_sheet(attendance, students_by_id, classes_by_id),
            "التقييمات": _build_assessments_sheet(assessments, classes_by_id, subjects_by_id),
            "السلوك": _build_behaviour_sheet(behaviour, students_by_id, classes_by_id),
            "أولياء الأمور": _build_invitations_sheet(invitations, students_by_id),
        }

        payload = _build_workbook(sheets)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "export_workspace_excel failed user=%s workspace=%s: %s",
            current_user.get("id"), workspace_id, exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    # Audit trail (best-effort — never fail the response on logging).
    try:
        await audit_engine.log(
            action=AUDIT_EXPORT_EXCEL,
            performed_by=current_user["id"],
            tenant_id=workspace_id,
            entity_type="school",
            entity_id=workspace_id,
            details={
                "school_id": workspace_id,
                "tenant_id": workspace_id,
                "user_id": current_user["id"],
                "bytes": len(payload),
                "counts": counts,
            },
            actor_name=current_user.get("full_name"),
            actor_role=current_user.get("role"),
            actor_email=current_user.get("email"),
            ip_address=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("audit log for excel export failed (ignored): %s", exc)

    filename = f"Nassaq_Export_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.xlsx"
    return Response(
        content=payload,
        media_type=_XLSX_MIME,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(payload)),
            "Cache-Control": "no-store",
        },
    )
