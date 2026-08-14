"""
Independent-Teacher — Workspace-aware bulk student import (Task #207).

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.1.

Two endpoints, IT-only, workspace-pinned:

  * ``POST /independent-teacher/students/bulk/parse``
      Parses a CSV upload and returns per-row validation. NO writes.
      Idempotent dry-run; safe to call repeatedly.

  * ``POST /independent-teacher/students/bulk/commit``
      Accepts the previously-validated rows envelope and inserts all
      students atomically (all-or-nothing). Gated by
      ``require_recent_mfa_403`` so the FE axios interceptor can
      replay after passkey assertion. Increments the workspace daily
      import counter and refuses past ``max_imports_per_day`` /
      ``max_rows_per_import`` / ``max_students`` (canonical IT
      ``MAX_STUDENTS``).

CSV schema (Arabic-only headers — no classroom column per spec):

    الاسم الكامل      (required)
    رقم الهوية        (optional)
    الجنس            (optional, ذكر | أنثى)
    تاريخ الميلاد     (optional, ISO yyyy-mm-dd or yyyy/mm/dd)
    الصف             (optional, free-form grade label)

Cross-workspace ``school_id`` (or any explicit tenant column) in the
payload is rejected with 422 — IT writes always pin to
``itw_{user_id}``.
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator

from src.core.guards.tenant_guard import (
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
from engines.name_validation import validate_personal_name
from sqlalchemy import select

from engines.sql_utils import gd_count, gd_find_one, gd_insert, gd_update_one
from pg_models import WorkspaceQuota
from quotas.independent_teacher import MAX_STUDENTS


logger = logging.getLogger("nassaq.it_bulk_import")

router = APIRouter()


# -- Safe Arabic copy -----------------------------------------------------

_MSG_INTERNAL = "تعذّر استيراد الطلاب — حاول لاحقًا."
_MSG_FILE_REQUIRED = "الرجاء إرفاق ملف."
_MSG_FILE_TYPE = "صيغة الملف غير مدعومة — استخدم CSV أو ملف Excel من نظام نور (.xls/.xlsx)."
_MSG_FILE_EMPTY = "الملف فارغ — لا توجد صفوف للاستيراد."
_MSG_FILE_TOO_LARGE = "الملف كبير جدًا — الحد الأقصى ٢٠٠ صف."
_MSG_HEADER_MISSING = "العمود «الاسم الكامل» مطلوب في رأس الملف."
_MSG_NOOR_NOT_STUDENT = "الملف ليس تقرير طلاب من نظام نور — حمّل تقرير «بيانات الطلاب»."
_MSG_QUOTA_DAILY = (
    "تجاوزت الحد اليومي لعمليات الاستيراد. حاول غدًا أو راسل الدعم."
)
_MSG_QUOTA_STUDENTS = (
    "بلغت الحد الأقصى لعدد الطلاب في حسابك المستقل (٢٠٠). "
    "أرشف طالبًا قبل استيراد المزيد."
)
_MSG_NO_VALID_ROWS = "لا توجد صفوف صحيحة للاستيراد."
_MSG_CROSS_TENANT = "لا يمكن تعيين مدرسة خارج مساحة عملك."
_MSG_NEED_PARSE = "الرجاء التحقق من الملف أولًا قبل التأكيد."

_AUDIT_ACTION = "INDEPENDENT_TEACHER_BULK_IMPORT_STUDENTS"

# Header → canonical field name. Arabic-only per spec.
_HEADER_MAP = {
    "الاسم الكامل": "full_name",
    "رقم الهوية": "national_id",
    "الجنس": "gender",
    "تاريخ الميلاد": "date_of_birth",
    "الصف": "grade_level",
}

_FORBIDDEN_KEYS = {
    "school_id", "tenant_id", "workspace_school_id", "class_id",
    "homeroom_teacher_id",
}

_GENDER_MAP = {"ذكر": "male", "أنثى": "female", "انثى": "female"}

_MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MiB hard cap on the upload itself.


# -- Models ---------------------------------------------------------------


# Per-row verdicts — mirror the School-Admin Noor import so a repeated
# identifier no longer hard-blocks the whole file. A row is routed to
# exactly one action against the FRESH workspace student index:
#   insert            — no existing match; a brand-new student row
#   update            — matches an ACTIVE student (same identity) → patch
#   restore           — matches a SOFT-DELETED student → reactivate + patch
#   duplicate_in_file — identity already consumed by an earlier row here
#   skip              — field validation failed (bad name / gender / dob)
_VERDICT_INSERT = "insert"
_VERDICT_UPDATE = "update"
_VERDICT_RESTORE = "restore"
_VERDICT_DUP_IN_FILE = "duplicate_in_file"
_VERDICT_SKIP = "skip"
_IMPORTABLE_VERDICTS = {_VERDICT_INSERT, _VERDICT_UPDATE, _VERDICT_RESTORE}


class ParsedRow(BaseModel):
    row_number: int
    full_name: Optional[str] = None
    # Noor student number — the School-Admin dedupe key. Stored in the
    # canonical `students.student_number` column, never overloaded into
    # the `national_id` slot where it used to collide.
    student_number: Optional[str] = None
    national_id: Optional[str] = None
    gender: Optional[str] = None  # canonical "male"/"female" or None
    date_of_birth: Optional[str] = None  # ISO yyyy-mm-dd or None
    grade_level: Optional[str] = None
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    # Advisory at parse-time (display only). The commit path re-derives it
    # against a fresh index — the client value is never trusted.
    verdict: Optional[str] = None


class ParseResponse(BaseModel):
    total_rows: int
    valid_count: int
    invalid_count: int
    importable_count: int  # rows that will insert / update / restore
    verdict_counts: Dict[str, int]
    rows: List[ParsedRow]
    quota: Dict[str, Any]
    projected_students: int  # current active students after commit


class CommitRequest(BaseModel):
    rows: List[ParsedRow]

    @field_validator("rows")
    @classmethod
    def _non_empty(cls, v: List[ParsedRow]) -> List[ParsedRow]:
        if not v:
            raise ValueError(_MSG_NO_VALID_ROWS)
        return v


class CommitResponse(BaseModel):
    inserted: int
    updated: int
    restored: int
    duplicates: int
    skipped: int
    quota: Dict[str, Any]


# -- Helpers --------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


def _quota_to_dict(row: WorkspaceQuota) -> Dict[str, Any]:
    return {
        "workspace_school_id": row.workspace_school_id,
        "max_students": row.max_students,
        "max_classes": row.max_classes,
        "max_imports_per_day": row.max_imports_per_day,
        "max_rows_per_import": row.max_rows_per_import,
        "imports_today": row.imports_today,
        "imports_today_date": row.imports_today_date,
        "lesson_plans_today": row.lesson_plans_today,
        "lesson_plans_today_date": row.lesson_plans_today_date,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def _get_quota_orm(workspace_id: str) -> Optional[WorkspaceQuota]:
    stmt = select(WorkspaceQuota).where(
        WorkspaceQuota.workspace_school_id == workspace_id,
    )
    result = await db.session.execute(stmt)
    return result.scalars().first()


async def _load_quota(workspace_id: str) -> Dict[str, Any]:
    """Read or lazily seed the workspace_quota row for this IT workspace."""
    row = await _get_quota_orm(workspace_id)
    if row:
        return _quota_to_dict(row)
    now = _utcnow()
    seed = {
        "workspace_school_id": workspace_id,
        "max_students": MAX_STUDENTS,
        "max_classes": 5,
        "max_imports_per_day": 5,
        "max_rows_per_import": 200,
        "imports_today": 0,
        "imports_today_date": None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        db.session.add(WorkspaceQuota(**seed))
        await db.session.flush()
    except Exception as exc:
        logger.warning(
            "workspace_quota lazy seed failed for %s: %s", workspace_id, exc,
        )
    return seed


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _quota_view(quota: Dict[str, Any], current_students: int) -> Dict[str, Any]:
    today = _today_utc()
    last = quota.get("imports_today_date")
    # imports_today_date may arrive as date, datetime, or ISO string.
    if isinstance(last, datetime):
        last = last.date()
    elif isinstance(last, str):
        try:
            last = date.fromisoformat(last[:10])
        except ValueError:
            last = None
    imports_today = int(quota.get("imports_today") or 0) if last == today else 0
    return {
        "max_students": int(quota.get("max_students") or MAX_STUDENTS),
        "max_rows_per_import": int(quota.get("max_rows_per_import") or 200),
        "max_imports_per_day": int(quota.get("max_imports_per_day") or 5),
        "imports_today": imports_today,
        "current_students": current_students,
    }


def _normalise_header(name: str) -> Optional[str]:
    if not name:
        return None
    cleaned = name.strip().replace("\ufeff", "")
    return _HEADER_MAP.get(cleaned)


def _parse_dob(value: str) -> Optional[str]:
    s = (value or "").strip()
    if not s:
        return None
    s = s.replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _validate_row(idx: int, raw: Dict[str, str]) -> ParsedRow:
    errors: List[str] = []

    # Reject any Latin keys that look like a tenant escape attempt.
    for k in raw.keys():
        if (k or "").strip().lower() in _FORBIDDEN_KEYS:
            errors.append(_MSG_CROSS_TENANT)

    full_name = (raw.get("full_name") or "").strip() or None
    student_number = (raw.get("student_number") or "").strip() or None
    national_id = (raw.get("national_id") or "").strip() or None
    gender_raw = (raw.get("gender") or "").strip()
    dob_raw = (raw.get("date_of_birth") or "").strip()
    grade_level = (raw.get("grade_level") or "").strip() or None

    if not full_name:
        errors.append("الاسم الكامل مطلوب")
    else:
        ok, msg = validate_personal_name(full_name)
        if not ok:
            errors.append(msg or "الاسم غير صالح")

    if national_id and not national_id.isdigit():
        errors.append("رقم الهوية يجب أن يحتوي على أرقام فقط")

    gender = None
    if gender_raw:
        gender = _GENDER_MAP.get(gender_raw)
        if gender is None:
            errors.append("الجنس غير صالح — استخدم «ذكر» أو «أنثى»")

    dob = None
    if dob_raw:
        dob = _parse_dob(dob_raw)
        if dob is None:
            errors.append("تاريخ الميلاد غير صالح — استخدم yyyy-mm-dd")

    return ParsedRow(
        row_number=idx,
        full_name=full_name,
        student_number=student_number,
        national_id=national_id,
        gender=gender,
        date_of_birth=dob,
        grade_level=grade_level,
        is_valid=not errors,
        errors=errors,
    )


async def _load_student_index(workspace_id: str) -> Dict[str, Dict[str, Any]]:
    """Load ALL students in the workspace (active AND soft-deleted) keyed by
    both identity slots.

    Soft-deleted rows are included on purpose so a re-import of a previously
    archived student is routed to RESTORE (reactivate the row) rather than a
    blind INSERT — which would otherwise collide with the surviving
    `uq_students_number_school` / `uq_students_national_id_school` unique
    constraints. Mirrors the School-Admin `load_school_student_index`
    authority model.
    """
    from engines.sql_utils import gd_find
    rows = await gd_find(db.session, "students", {"school_id": workspace_id})
    by_num: Dict[str, Dict[str, Any]] = {}
    by_nid: Dict[str, Dict[str, Any]] = {}

    def _prefer(bucket: Dict[str, Dict[str, Any]], key: str, row: Dict[str, Any]) -> None:
        prev = bucket.get(key)
        # Prefer an active row over a soft-deleted one (the unique
        # constraints make this collision impossible in practice, but the
        # tie-break keeps the routing deterministic if it ever occurs).
        if prev is None or (
            prev.get("is_active") is False and row.get("is_active") is not False
        ):
            bucket[key] = row

    for row in rows or []:
        num = (row.get("student_number") or "").strip()
        nid = (row.get("national_id") or "").strip()
        if num:
            _prefer(by_num, num, row)
        if nid:
            _prefer(by_nid, nid, row)
    return {"by_num": by_num, "by_nid": by_nid}


def _plan_rows(
    rows: List[ParsedRow], index: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Assign a per-row verdict against the FRESH student index and return a
    parallel plan of ``{row, verdict, existing_id}``.

    Also mutates each ``row.verdict`` so the parse response and the FE can
    surface the badge. Identity precedence is student_number (Noor) then
    national_id (CSV) — the two are mutually exclusive per source shape.
    Deduping is per-file (first occurrence wins; later repeats →
    ``duplicate_in_file``) and per-DB (existing active → update, existing
    soft-deleted → restore).
    """
    by_num = index.get("by_num") or {}
    by_nid = index.get("by_nid") or {}
    seen_num: set = set()
    seen_nid: set = set()
    plan: List[Dict[str, Any]] = []
    for r in rows:
        verdict = _VERDICT_SKIP
        existing_id: Optional[str] = None
        if r.is_valid and (r.full_name or "").strip():
            num = (r.student_number or "").strip()
            nid = (r.national_id or "").strip()
            if num:
                if num in seen_num:
                    verdict = _VERDICT_DUP_IN_FILE
                else:
                    seen_num.add(num)
                    ex = by_num.get(num)
                    if ex:
                        existing_id = ex.get("id")
                        verdict = (
                            _VERDICT_RESTORE if ex.get("is_active") is False
                            else _VERDICT_UPDATE
                        )
                    else:
                        verdict = _VERDICT_INSERT
            elif nid:
                if nid in seen_nid:
                    verdict = _VERDICT_DUP_IN_FILE
                else:
                    seen_nid.add(nid)
                    ex = by_nid.get(nid)
                    if ex:
                        existing_id = ex.get("id")
                        verdict = (
                            _VERDICT_RESTORE if ex.get("is_active") is False
                            else _VERDICT_UPDATE
                        )
                    else:
                        verdict = _VERDICT_INSERT
            else:
                # No identity slot at all — can never dedupe; always insert.
                verdict = _VERDICT_INSERT
        r.verdict = verdict
        plan.append({"row": r, "verdict": verdict, "existing_id": existing_id})
    return plan


def _verdict_counts(plan: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        _VERDICT_INSERT: 0,
        _VERDICT_UPDATE: 0,
        _VERDICT_RESTORE: 0,
        _VERDICT_DUP_IN_FILE: 0,
        _VERDICT_SKIP: 0,
    }
    for item in plan:
        v = item["verdict"]
        if v in counts:
            counts[v] += 1
    return counts


def _read_csv(content: bytes) -> List[Dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail=_MSG_FILE_TYPE) from exc

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise HTTPException(status_code=422, detail=_MSG_FILE_EMPTY)

    # Reject explicit cross-tenant escape attempts in the CSV header
    # itself (e.g. school_id / tenant_id / class_id columns). Spec §6.1:
    # IT writes always pin to itw_{user_id}, so any tenant-scoping
    # column in the upload must 422 — never silently dropped.
    for h in header:
        if (h or "").strip().lower().replace("\ufeff", "") in _FORBIDDEN_KEYS:
            raise HTTPException(status_code=422, detail=_MSG_CROSS_TENANT)

    field_map: Dict[int, str] = {}
    for i, h in enumerate(header):
        canon = _normalise_header(h)
        if canon:
            field_map[i] = canon

    if "full_name" not in field_map.values():
        raise HTTPException(status_code=422, detail=_MSG_HEADER_MISSING)

    rows: List[Dict[str, str]] = []
    for raw_row in reader:
        if not any((cell or "").strip() for cell in raw_row):
            continue  # skip blank lines
        rec: Dict[str, str] = {}
        for i, cell in enumerate(raw_row):
            key = field_map.get(i)
            if key:
                rec[key] = cell
        rows.append(rec)
    return rows


def _read_noor_workbook(content: bytes, filename: str) -> List[Dict[str, str]]:
    """Parse a Noor .xls/.xlsx student-report workbook and map each row to
    the IT bulk-import shape (full_name / student_number / grade_level).

    Noor reports have no gender or date-of-birth columns; those fields are
    left blank. Noor `رقم الطالب` (school student number) is mapped into the
    canonical `student_number` slot — the same field School Admin dedupes on
    — so a repeated placeholder number is skipped per-row instead of
    hard-blocking the whole file, and `national_id` is left free.
    """
    from engines.noor_import.parser import (  # local import — cold path
        NoorParseError,
        STUDENT_REPORT,
        parse_workbook_bytes,
    )

    try:
        result = parse_workbook_bytes(content, filename)
    except NoorParseError as exc:
        diag = getattr(exc, "diagnostics", None)
        if diag:
            logger.warning("noor parse failed for IT upload: %s", diag)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — never leak raw parser errors
        logger.warning("noor parse crashed for IT upload: %s", exc)
        raise HTTPException(status_code=422, detail=_MSG_FILE_TYPE) from exc

    if (result.get("detected_type") or "") != STUDENT_REPORT:
        raise HTTPException(status_code=422, detail=_MSG_NOOR_NOT_STUDENT)

    bulk_rows: List[Dict[str, str]] = []
    for entry in result.get("rows") or []:
        data = entry.get("data") or {}
        full_name = (data.get("full_name") or "").strip()
        student_number = (data.get("student_number") or "").strip()
        grade_code = (data.get("grade_code") or "").strip()
        section_code = (data.get("section_code") or "").strip()
        if grade_code and section_code:
            grade_label = f"الصف {grade_code} / الفصل {section_code}"
        else:
            grade_label = grade_code or section_code or ""
        bulk_rows.append({
            "full_name": full_name,
            "student_number": student_number,
            "national_id": "",
            "gender": "",
            "date_of_birth": "",
            "grade_level": grade_label,
        })
    return bulk_rows


# -- Endpoints ------------------------------------------------------------


@router.post(
    "/independent-teacher/students/bulk/parse",
    response_model=ParseResponse,
)
async def parse_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(_require_independent_teacher),
) -> ParseResponse:
    """Validate a CSV or Noor .xls/.xlsx upload and return per-row
    diagnostics. NO writes."""
    name = ((file.filename if file else None) or "").lower()
    is_csv = name.endswith(".csv")
    is_excel = name.endswith(".xls") or name.endswith(".xlsx")
    if not file or not (is_csv or is_excel):
        raise HTTPException(status_code=422, detail=_MSG_FILE_TYPE)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail=_MSG_FILE_REQUIRED)
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=_MSG_FILE_TOO_LARGE)

    workspace_id = require_request_school_id(current_user)
    quota = await _load_quota(workspace_id)
    max_rows = int(quota.get("max_rows_per_import") or 200)

    rows = _read_noor_workbook(content, name) if is_excel else _read_csv(content)
    if not rows:
        raise HTTPException(status_code=422, detail=_MSG_FILE_EMPTY)
    if len(rows) > max_rows:
        raise HTTPException(status_code=413, detail=_MSG_FILE_TOO_LARGE)

    parsed = [_validate_row(i + 1, r) for i, r in enumerate(rows)]
    valid_count = sum(1 for p in parsed if p.is_valid)

    # Per-row verdicts against a fresh workspace index (advisory preview —
    # commit re-derives them). A repeated identifier no longer flips
    # `is_valid` to False; it is routed to `duplicate_in_file` and skipped.
    index = await _load_student_index(workspace_id)
    plan = _plan_rows(parsed, index)
    counts = _verdict_counts(plan)
    importable_count = (
        counts[_VERDICT_INSERT] + counts[_VERDICT_UPDATE] + counts[_VERDICT_RESTORE]
    )

    current_students = await gd_count(
        db.session, "students",
        {"school_id": workspace_id, "is_active": {"$ne": False}},
    )
    # Only inserts and restores grow the active-student count.
    net_new = counts[_VERDICT_INSERT] + counts[_VERDICT_RESTORE]

    return ParseResponse(
        total_rows=len(parsed),
        valid_count=valid_count,
        invalid_count=len(parsed) - valid_count,
        importable_count=importable_count,
        verdict_counts=counts,
        rows=parsed,
        quota=_quota_view(quota, current_students),
        projected_students=current_students + net_new,
    )


@router.post(
    "/independent-teacher/students/bulk/commit",
    response_model=CommitResponse,
)
async def commit_csv(
    payload: CommitRequest,
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(require_recent_mfa_403()),
) -> CommitResponse:
    """All-or-nothing insert of the validated rows into the workspace."""
    workspace_id = require_request_school_id(current_user)
    expected = independent_workspace_id(current_user)
    if expected and workspace_id != expected:
        # Defense-in-depth — IT writes always pin to itw_{user_id}.
        raise HTTPException(status_code=403, detail=_MSG_CROSS_TENANT)
    workspace_id = expected or workspace_id

    quota = await _load_quota(workspace_id)
    quota_view_pre = _quota_view(quota, 0)

    # Daily import-count cap.
    if quota_view_pre["imports_today"] >= quota_view_pre["max_imports_per_day"]:
        raise HTTPException(status_code=429, detail=_MSG_QUOTA_DAILY)

    # Full server-side re-validation of every field — a tampered preview
    # cannot smuggle bad gender / dob / identity values past parse. Rows
    # that fail field validation are SKIPPED per-row (School-Admin model),
    # never a 422 for the whole file.
    revalidated: List[ParsedRow] = []
    for r in payload.rows:
        v = _validate_row(r.row_number, {
            "full_name": r.full_name,
            "student_number": r.student_number,
            "national_id": r.national_id,
            # Map canonical genders back to the Arabic the validator accepts.
            "gender": (
                "ذكر" if r.gender == "male"
                else "أنثى" if r.gender == "female"
                else ""
            ),
            "date_of_birth": r.date_of_birth or "",
            "grade_level": r.grade_level or "",
        })
        revalidated.append(v)

    # Re-derive verdicts against a FRESH workspace index — the client's
    # advisory verdict is never trusted. Dedupe is on the canonical
    # student_number (Noor) / national_id (CSV) slots.
    index = await _load_student_index(workspace_id)
    plan = _plan_rows(revalidated, index)
    counts = _verdict_counts(plan)
    importable = (
        counts[_VERDICT_INSERT] + counts[_VERDICT_UPDATE] + counts[_VERDICT_RESTORE]
    )
    duplicates = counts[_VERDICT_DUP_IN_FILE]
    skipped = counts[_VERDICT_SKIP]
    if importable == 0:
        raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)

    field_valid = sum(1 for r in revalidated if r.is_valid and r.full_name)
    if field_valid > quota_view_pre["max_rows_per_import"]:
        raise HTTPException(status_code=413, detail=_MSG_FILE_TOO_LARGE)

    current_students = await gd_count(
        db.session, "students",
        {"school_id": workspace_id, "is_active": {"$ne": False}},
    )
    # Only inserts and restores grow the active-student count; updates
    # patch a row that already counts against the cap.
    net_new = counts[_VERDICT_INSERT] + counts[_VERDICT_RESTORE]
    max_students = quota_view_pre["max_students"]
    if current_students + net_new > max_students:
        raise HTTPException(status_code=409, detail=_MSG_QUOTA_STUDENTS)

    session = db.session
    inserted = 0
    updated = 0
    restored = 0
    try:
        async with session.begin_nested():
            now_iso = _utcnow_iso()
            for item in plan:
                verdict = item["verdict"]
                r = item["row"]
                existing_id = item["existing_id"]
                if verdict == _VERDICT_INSERT:
                    student_doc = {
                        "id": str(uuid.uuid4()),
                        "school_id": workspace_id,
                        "tenant_id": workspace_id,
                        "full_name": r.full_name,
                        "student_number": r.student_number,
                        "national_id": r.national_id,
                        "gender": r.gender,
                        "date_of_birth": r.date_of_birth,
                        "grade_level": r.grade_level,
                        "is_active": True,
                        "created_by": current_user.get("id"),
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    }
                    await gd_insert(session, "students", student_doc)
                    inserted += 1
                elif verdict in (_VERDICT_UPDATE, _VERDICT_RESTORE):
                    updates = {
                        "full_name": r.full_name,
                        "gender": r.gender,
                        "date_of_birth": r.date_of_birth,
                        "grade_level": r.grade_level,
                        "updated_at": now_iso,
                    }
                    if verdict == _VERDICT_RESTORE:
                        updates["is_active"] = True
                    await gd_update_one(
                        session, "students",
                        {"id": existing_id, "school_id": workspace_id},
                        updates,
                    )
                    if verdict == _VERDICT_RESTORE:
                        restored += 1
                    else:
                        updated += 1
                # duplicate_in_file / skip → no write.

            today = _today_utc()
            last = quota.get("imports_today_date")
            if isinstance(last, datetime):
                last = last.date()
            elif isinstance(last, str):
                try:
                    last = date.fromisoformat(last[:10])
                except ValueError:
                    last = None
            new_count = (
                int(quota.get("imports_today") or 0) + 1
                if last == today else 1
            )
            quota_orm = await _get_quota_orm(workspace_id)
            if quota_orm is not None:
                quota_orm.imports_today = new_count
                quota_orm.imports_today_date = today
                quota_orm.updated_at = _utcnow()
                await session.flush()

            try:
                await audit_engine.log(
                    action=_AUDIT_ACTION,
                    performed_by=current_user["id"],
                    tenant_id=workspace_id,
                    entity_type="students",
                    entity_id=workspace_id,
                    actor_email=current_user.get("email"),
                    actor_name=current_user.get("full_name"),
                    actor_role=current_user.get("role"),
                    ip_address=(request.client.host if request.client else None),
                    user_agent=request.headers.get("user-agent"),
                    details={
                        "inserted": inserted,
                        "updated": updated,
                        "restored": restored,
                        "duplicates": duplicates,
                        "skipped": skipped,
                        "imports_today": new_count,
                    },
                )
            except Exception as audit_exc:  # noqa: BLE001
                logger.warning("bulk-import audit failed: %s", audit_exc)

            # Recompute the workspace's stored counts from live rows (Task #826)
            # so the denormalized columns stay accurate instead of drifting.
            from engines.entity_counts import reconcile_school_counts
            await reconcile_school_counts(session, workspace_id)

        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.exception("IT bulk import failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    # Task #260 — quota near-limit warning at 80% on the bulk-import
    # path, mirroring the lesson-plan emit. Fires only on the row that
    # crosses the threshold (prev < 80% AND new >= 80%) so a heavy
    # importer cannot generate duplicate notifications on the same day.
    try:
        max_per_day = quota_view_pre["max_imports_per_day"]
        prev_count = quota_view_pre["imports_today"]
        if max_per_day:
            threshold = int(max_per_day * 0.8)
            if (
                threshold > 0
                and new_count >= threshold > prev_count
                and new_count < max_per_day
            ):
                from src.modules.notifications.controllers.notification_routes_mod import create_notification_internal
                from src.modules.independent_teacher.controllers.independent_teacher_notifications_routes import should_send_channel
                if await should_send_channel(current_user, "quota", "in_app"):
                    await create_notification_internal(
                        title="اقتراب الحد اليومي لاستيراد الطلاب",
                        message=f"استخدمت {new_count} من {max_per_day} عمليات استيراد اليوم.",
                        title_en="Daily student-import quota nearly reached",
                        message_en=f"Used {new_count} of {max_per_day} imports today.",
                        recipient_id=current_user["id"],
                        notification_type="quota_warning",
                        priority="medium",
                        school_id=workspace_id,
                        category="quota",
                        cta_url="/teacher/import-students",
                        extra_data={
                            "imports_today": new_count,
                            "max_imports_per_day": max_per_day,
                        },
                    )
    except Exception as exc:  # noqa: BLE001
        logger.debug("bulk-import quota warning notify failed: %s", exc)

    refreshed_orm = await _get_quota_orm(workspace_id)
    refreshed = _quota_to_dict(refreshed_orm) if refreshed_orm else quota
    new_current = await gd_count(
        db.session, "students",
        {"school_id": workspace_id, "is_active": {"$ne": False}},
    )
    return CommitResponse(
        inserted=inserted,
        updated=updated,
        restored=restored,
        duplicates=duplicates,
        skipped=skipped,
        quota=_quota_view(refreshed, new_current),
    )


__all__ = ["router"]
