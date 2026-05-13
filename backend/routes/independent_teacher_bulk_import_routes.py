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
from engines.name_validation import validate_personal_name
from engines.sql_utils import gd_count, gd_find_one, gd_insert, gd_update_one
from quotas.independent_teacher import MAX_STUDENTS


logger = logging.getLogger("nassaq.it_bulk_import")

router = APIRouter()


# -- Safe Arabic copy -----------------------------------------------------

_MSG_INTERNAL = "تعذّر استيراد الطلاب — حاول لاحقًا."
_MSG_FILE_REQUIRED = "الرجاء إرفاق ملف CSV."
_MSG_FILE_TYPE = "صيغة الملف غير مدعومة — استخدم CSV."
_MSG_FILE_EMPTY = "الملف فارغ — لا توجد صفوف للاستيراد."
_MSG_FILE_TOO_LARGE = "الملف كبير جدًا — الحد الأقصى ٢٠٠ صف."
_MSG_HEADER_MISSING = "العمود «الاسم الكامل» مطلوب في رأس الملف."
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
_MSG_DUPLICATE_NATIONAL_ID_IN_CSV = "رقم الهوية مكرر داخل الملف"
_MSG_DUPLICATE_NATIONAL_ID_IN_DB = "طالب بهذا رقم الهوية موجود مسبقًا في مساحتك"

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


class ParsedRow(BaseModel):
    row_number: int
    full_name: Optional[str] = None
    national_id: Optional[str] = None
    gender: Optional[str] = None  # canonical "male"/"female" or None
    date_of_birth: Optional[str] = None  # ISO yyyy-mm-dd or None
    grade_level: Optional[str] = None
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)


class ParseResponse(BaseModel):
    total_rows: int
    valid_count: int
    invalid_count: int
    rows: List[ParsedRow]
    quota: Dict[str, Any]
    projected_students: int  # current_students + valid_count, post-commit projection


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
    skipped: int
    quota: Dict[str, Any]


# -- Helpers --------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


async def _load_quota(workspace_id: str) -> Dict[str, Any]:
    """Read or lazily seed the workspace_quota row for this IT workspace."""
    row = await gd_find_one(
        db.session, "workspace_quota", {"workspace_school_id": workspace_id},
    )
    if row:
        return row
    now = _utcnow_iso()
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
        await gd_insert(db.session, "workspace_quota", seed)
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
        national_id=national_id,
        gender=gender,
        date_of_birth=dob,
        grade_level=grade_level,
        is_valid=not errors,
        errors=errors,
    )


async def _flag_duplicate_national_ids(
    parsed: List[ParsedRow], workspace_id: str,
) -> None:
    """Mark rows whose national_id is duplicated within the upload OR
    already present on an active student in the same workspace.

    Mutates ``parsed`` in place — appending a localized error and
    flipping ``is_valid`` to False so commit cannot smuggle them in.
    """
    seen: Dict[str, int] = {}
    candidates: List[str] = []
    for r in parsed:
        if not r.national_id:
            continue
        nid = r.national_id
        if nid in seen:
            # Mark BOTH the prior occurrence and this one.
            prior = parsed[seen[nid] - 1] if 0 < seen[nid] <= len(parsed) else None
            if prior is not None and _MSG_DUPLICATE_NATIONAL_ID_IN_CSV not in prior.errors:
                prior.errors.append(_MSG_DUPLICATE_NATIONAL_ID_IN_CSV)
                prior.is_valid = False
            r.errors.append(_MSG_DUPLICATE_NATIONAL_ID_IN_CSV)
            r.is_valid = False
        else:
            seen[nid] = r.row_number
            candidates.append(nid)

    if not candidates:
        return

    # Detect collisions against existing active students in the workspace.
    try:
        from engines.sql_utils import gd_find
        existing = await gd_find(
            db.session, "students",
            {
                "school_id": workspace_id,
                "is_active": {"$ne": False},
                "national_id": {"$in": candidates},
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("national_id collision lookup failed: %s", exc)
        return

    db_hits = {(row.get("national_id") or "") for row in (existing or [])}
    if not db_hits:
        return
    for r in parsed:
        if r.national_id and r.national_id in db_hits:
            if _MSG_DUPLICATE_NATIONAL_ID_IN_DB not in r.errors:
                r.errors.append(_MSG_DUPLICATE_NATIONAL_ID_IN_DB)
            r.is_valid = False


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


# -- Endpoints ------------------------------------------------------------


@router.post(
    "/independent-teacher/students/bulk/parse",
    response_model=ParseResponse,
)
async def parse_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(_require_independent_teacher),
) -> ParseResponse:
    """Validate a CSV upload and return per-row diagnostics. NO writes."""
    if not file or not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail=_MSG_FILE_TYPE)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail=_MSG_FILE_REQUIRED)
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=_MSG_FILE_TOO_LARGE)

    workspace_id = require_request_school_id(current_user)
    quota = await _load_quota(workspace_id)
    max_rows = int(quota.get("max_rows_per_import") or 200)

    rows = _read_csv(content)
    if not rows:
        raise HTTPException(status_code=422, detail=_MSG_FILE_EMPTY)
    if len(rows) > max_rows:
        raise HTTPException(status_code=413, detail=_MSG_FILE_TOO_LARGE)

    parsed = [_validate_row(i + 1, r) for i, r in enumerate(rows)]
    await _flag_duplicate_national_ids(parsed, workspace_id)
    valid_count = sum(1 for p in parsed if p.is_valid)

    current_students = await gd_count(
        db.session, "students",
        {"school_id": workspace_id, "is_active": {"$ne": False}},
    )

    return ParseResponse(
        total_rows=len(parsed),
        valid_count=valid_count,
        invalid_count=len(parsed) - valid_count,
        rows=parsed,
        quota=_quota_view(quota, current_students),
        projected_students=current_students + valid_count,
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

    candidate_rows = [r for r in payload.rows if r.is_valid and r.full_name]
    skipped = len(payload.rows) - len(candidate_rows)
    if not candidate_rows:
        raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)

    if len(candidate_rows) > quota_view_pre["max_rows_per_import"]:
        raise HTTPException(status_code=413, detail=_MSG_FILE_TOO_LARGE)

    # Full server-side re-validation of every field — a tampered preview
    # cannot smuggle bad gender / dob / national_id values past parse.
    revalidated: List[ParsedRow] = []
    for r in candidate_rows:
        v = _validate_row(r.row_number, {
            "full_name": r.full_name,
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
        if not v.is_valid:
            raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)
        revalidated.append(v)

    # Duplicate-national-id checks (within payload + against active DB rows)
    # mirror the parse contract; a tampered preview that flipped is_valid
    # cannot bypass them.
    await _flag_duplicate_national_ids(revalidated, workspace_id)
    if any(not r.is_valid for r in revalidated):
        raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)
    valid_rows = revalidated

    current_students = await gd_count(
        db.session, "students",
        {"school_id": workspace_id, "is_active": {"$ne": False}},
    )
    max_students = quota_view_pre["max_students"]
    if current_students + len(valid_rows) > max_students:
        raise HTTPException(status_code=409, detail=_MSG_QUOTA_STUDENTS)

    session = db.session
    inserted = 0
    try:
        async with session.begin_nested():
            now_iso = _utcnow_iso()
            for r in valid_rows:
                student_doc = {
                    "id": str(uuid.uuid4()),
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "full_name": r.full_name,
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
            await gd_update_one(
                session, "workspace_quota",
                {"workspace_school_id": workspace_id},
                {
                    "imports_today": new_count,
                    "imports_today_date": today.isoformat(),
                    "updated_at": now_iso,
                },
            )

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
                        "skipped": skipped,
                        "imports_today": new_count,
                    },
                )
            except Exception as audit_exc:  # noqa: BLE001
                logger.warning("bulk-import audit failed: %s", audit_exc)

        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.exception("IT bulk import failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    refreshed = await gd_find_one(
        db.session, "workspace_quota", {"workspace_school_id": workspace_id},
    ) or quota
    new_current = await gd_count(
        db.session, "students",
        {"school_id": workspace_id, "is_active": {"$ne": False}},
    )
    return CommitResponse(
        inserted=inserted,
        skipped=skipped,
        quota=_quota_view(refreshed, new_current),
    )


__all__ = ["router"]
