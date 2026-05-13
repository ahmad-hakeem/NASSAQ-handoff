"""
Independent-Teacher — Bulk-import extensions (Task #278).

Mirrors the §6.1 student-import envelope for two additional onboarding
shortcuts and a one-shot weekly-schedule duplicator.

Endpoints (all IT-only, workspace-pinned, daily-quota gated):

  * ``POST /independent-teacher/classes/bulk/parse``
  * ``POST /independent-teacher/classes/bulk/commit``
  * ``POST /independent-teacher/subjects/bulk/parse``
  * ``POST /independent-teacher/subjects/bulk/commit``
  * ``POST /independent-teacher/schedule/duplicate-week``

Cross-tenant escape attempts (e.g. ``school_id`` / ``tenant_id`` /
``class_id`` columns in the CSV header, or ids in any commit-payload
column) are rejected with the safe Arabic message — IT writes always
pin to ``itw_{user_id}``.

The ``imports_today`` counter on ``workspace_quota`` is shared across
the student / classes / subjects / duplicate-week paths so the daily
cap (default 5) applies uniformly to every workspace-mutating bulk
action regardless of the entity type.
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
from engines.sql_utils import (
    gd_count,
    gd_find,
    gd_find_one,
    gd_insert,
    gd_update_one,
)
from quotas.independent_teacher import MAX_CLASSES, MAX_STUDENTS

# Reuse the canonical helpers from the student-import module so quota
# bookkeeping and cross-tenant copy stay byte-identical across all four
# bulk paths.
from routes.independent_teacher_bulk_import_routes import (
    _FORBIDDEN_KEYS,
    _MSG_CROSS_TENANT,
    _MSG_FILE_EMPTY,
    _MSG_FILE_REQUIRED,
    _MSG_FILE_TOO_LARGE,
    _MSG_FILE_TYPE,
    _MSG_HEADER_MISSING,
    _MSG_NO_VALID_ROWS,
    _MSG_QUOTA_DAILY,
    _MAX_FILE_BYTES,
    _load_quota,
    _quota_view,
    _today_utc,
    _utcnow_iso,
)


logger = logging.getLogger("nassaq.it_bulk_ext")

router = APIRouter()


# -- Safe Arabic copy -----------------------------------------------------

_MSG_INTERNAL = "تعذّر إكمال العملية — حاول مرة أخرى لاحقًا."
_MSG_QUOTA_CLASSES = (
    "بلغت الحد الأقصى لعدد الفصول في حسابك المستقل (٥). "
    "احذف فصلًا قبل استيراد المزيد."
)
_MSG_QUOTA_SUBJECTS_PER_IMPORT = (
    "تجاوزت الحد الأعلى لعدد المواد في عملية استيراد واحدة (٥٠)."
)
_MSG_BAD_DATE = "تاريخ غير صالح. استخدم الصيغة YYYY-MM-DD"
_MSG_BAD_WEEK_GAP = "يجب أن يكون الأسبوع المستهدف بعد أسبوع المصدر بسبعة أيام."
_MSG_NOTHING_TO_DUPLICATE = "لا توجد حصص في الأسبوع المصدر لنسخها."

_AUDIT_CLASSES = "INDEPENDENT_TEACHER_BULK_IMPORT_CLASSES"
_AUDIT_SUBJECTS = "INDEPENDENT_TEACHER_BULK_IMPORT_SUBJECTS"
_AUDIT_DUPLICATE_WEEK = "INDEPENDENT_TEACHER_SCHEDULE_DUPLICATE_WEEK"

# Header → canonical field name. Arabic-only per spec.
_CLASS_HEADER_MAP = {
    "اسم الفصل": "name",
    "المرحلة": "grade_level",
    "المادة الافتراضية": "default_subject",
}

_SUBJECT_HEADER_MAP = {
    "اسم المادة": "name",
    "الكود": "code",
}

# Shared with student-import. Plus class_id / subject_id which are
# meaningful here too (subjects/classes belong to a workspace, never
# carry an explicit foreign id from the caller).
_FORBIDDEN_KEYS_EXT = set(_FORBIDDEN_KEYS) | {"subject_id", "id"}

_SUBJECTS_PER_IMPORT_CAP = 50


# -- Models ---------------------------------------------------------------


_ROW_ALLOWED_KEYS_CLASS = {
    "row_number", "name", "grade_level", "default_subject",
    "is_valid", "errors",
}
_ROW_ALLOWED_KEYS_SUBJECT = {
    "row_number", "name", "code", "is_valid", "errors",
}


def _reject_cross_tenant_extras(data: Any, allowed: set) -> Any:
    """Raise ``HTTPException(422, _MSG_CROSS_TENANT)`` — the safe Arabic
    cross-tenant message — when a commit-payload row carries any extra
    key that overlaps with the forbidden id-column set, OR any other
    unknown key. Belt-and-suspenders complement to the parse-time CSV
    header check."""
    if not isinstance(data, dict):
        return data
    extras = [k for k in data.keys() if k not in allowed]
    if not extras:
        return data
    lowered = {k.lower() for k in extras}
    # Smuggling attempt → safe Arabic message + 422.
    if lowered & _FORBIDDEN_KEYS_EXT:
        raise HTTPException(status_code=422, detail=_MSG_CROSS_TENANT)
    # Any other unexpected key — reuse the same safe message so the FE
    # surfaces a single, branded error string for any malformed row.
    raise HTTPException(status_code=422, detail=_MSG_CROSS_TENANT)


class ParsedClassRow(BaseModel):
    row_number: int
    name: Optional[str] = None
    grade_level: Optional[str] = None
    default_subject: Optional[str] = None
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_extras(cls, data: Any) -> Any:
        return _reject_cross_tenant_extras(data, _ROW_ALLOWED_KEYS_CLASS)


class ParsedSubjectRow(BaseModel):
    row_number: int
    name: Optional[str] = None
    code: Optional[str] = None
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _reject_extras(cls, data: Any) -> Any:
        return _reject_cross_tenant_extras(data, _ROW_ALLOWED_KEYS_SUBJECT)


class ParseClassResponse(BaseModel):
    total_rows: int
    valid_count: int
    invalid_count: int
    rows: List[ParsedClassRow]
    quota: Dict[str, Any]
    projected_classes: int


class ParseSubjectResponse(BaseModel):
    total_rows: int
    valid_count: int
    invalid_count: int
    rows: List[ParsedSubjectRow]
    quota: Dict[str, Any]


class CommitClassesRequest(BaseModel):
    rows: List[ParsedClassRow]

    @field_validator("rows")
    @classmethod
    def _non_empty(cls, v):
        if not v:
            raise ValueError(_MSG_NO_VALID_ROWS)
        return v


class CommitSubjectsRequest(BaseModel):
    rows: List[ParsedSubjectRow]

    @field_validator("rows")
    @classmethod
    def _non_empty(cls, v):
        if not v:
            raise ValueError(_MSG_NO_VALID_ROWS)
        return v


class CommitResponse(BaseModel):
    inserted: int
    skipped: int
    quota: Dict[str, Any]


class DuplicateWeekRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_week_start: str = Field(..., min_length=10, max_length=10)
    to_week_start: str = Field(..., min_length=10, max_length=10)
    # When True, no rows are written, no quota counter is bumped, and
    # the response carries per-slot conflict diagnostics. The FE calls
    # this before showing the final confirmation modal so the teacher
    # sees exactly which slots will be created vs. skipped.
    dry_run: bool = False


class SlotPreview(BaseModel):
    day_of_week: str
    slot_number: int
    subject_name: Optional[str] = None
    class_name: Optional[str] = None
    will_create: bool


class DuplicateWeekResponse(BaseModel):
    created: int
    skipped: int
    from_week_start: str
    to_week_start: str
    quota: Dict[str, Any]
    # Populated on dry_run; on a real commit it carries the same per-slot
    # breakdown so the FE can render a "what was done" report instead of
    # just a count.
    slots: List[SlotPreview] = Field(default_factory=list)
    dry_run: bool = False


# -- Helpers --------------------------------------------------------------


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


def _normalise_header(name: str, mapping: Dict[str, str]) -> Optional[str]:
    if not name:
        return None
    cleaned = name.strip().replace("\ufeff", "")
    return mapping.get(cleaned)


def _read_csv(content: bytes, header_map: Dict[str, str]) -> List[Dict[str, str]]:
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

    for h in header:
        if (h or "").strip().lower().replace("\ufeff", "") in _FORBIDDEN_KEYS_EXT:
            raise HTTPException(status_code=422, detail=_MSG_CROSS_TENANT)

    field_map: Dict[int, str] = {}
    for i, h in enumerate(header):
        canon = _normalise_header(h, header_map)
        if canon:
            field_map[i] = canon

    if "name" not in field_map.values():
        raise HTTPException(status_code=422, detail=_MSG_HEADER_MISSING)

    rows: List[Dict[str, str]] = []
    for raw_row in reader:
        if not any((cell or "").strip() for cell in raw_row):
            continue
        rec: Dict[str, str] = {}
        for i, cell in enumerate(raw_row):
            key = field_map.get(i)
            if key:
                rec[key] = cell
        rows.append(rec)
    return rows


def _validate_class_row(idx: int, raw: Dict[str, str]) -> ParsedClassRow:
    errors: List[str] = []
    for k in raw.keys():
        if (k or "").strip().lower() in _FORBIDDEN_KEYS_EXT:
            errors.append(_MSG_CROSS_TENANT)
    name = (raw.get("name") or "").strip() or None
    grade = (raw.get("grade_level") or "").strip() or None
    subj = (raw.get("default_subject") or "").strip() or None
    if not name:
        errors.append("اسم الفصل مطلوب")
    elif len(name) > 80:
        errors.append("اسم الفصل طويل جدًا")
    if grade and len(grade) > 80:
        errors.append("اسم المرحلة طويل جدًا")
    if subj and len(subj) > 80:
        errors.append("اسم المادة طويل جدًا")
    return ParsedClassRow(
        row_number=idx,
        name=name,
        grade_level=grade,
        default_subject=subj,
        is_valid=not errors,
        errors=errors,
    )


def _validate_subject_row(idx: int, raw: Dict[str, str]) -> ParsedSubjectRow:
    errors: List[str] = []
    for k in raw.keys():
        if (k or "").strip().lower() in _FORBIDDEN_KEYS_EXT:
            errors.append(_MSG_CROSS_TENANT)
    name = (raw.get("name") or "").strip() or None
    code = (raw.get("code") or "").strip() or None
    if not name:
        errors.append("اسم المادة مطلوب")
    elif len(name) > 80:
        errors.append("اسم المادة طويل جدًا")
    if code and len(code) > 32:
        errors.append("الكود طويل جدًا")
    return ParsedSubjectRow(
        row_number=idx,
        name=name,
        code=code,
        is_valid=not errors,
        errors=errors,
    )


def _flag_duplicate_subjects_in_csv(rows: List[ParsedSubjectRow]) -> None:
    seen: Dict[str, int] = {}
    for r in rows:
        if not r.name:
            continue
        key = r.name.strip().lower()
        if key in seen:
            r.errors.append("اسم المادة مكرر داخل الملف")
            r.is_valid = False
            prior = rows[seen[key] - 1] if 0 < seen[key] <= len(rows) else None
            if prior is not None and "اسم المادة مكرر داخل الملف" not in prior.errors:
                prior.errors.append("اسم المادة مكرر داخل الملف")
                prior.is_valid = False
        else:
            seen[key] = r.row_number


def _flag_duplicate_classes_in_csv(rows: List[ParsedClassRow]) -> None:
    seen: Dict[str, int] = {}
    for r in rows:
        if not r.name:
            continue
        key = r.name.strip().lower()
        if key in seen:
            r.errors.append("اسم الفصل مكرر داخل الملف")
            r.is_valid = False
            prior = rows[seen[key] - 1] if 0 < seen[key] <= len(rows) else None
            if prior is not None and "اسم الفصل مكرر داخل الملف" not in prior.errors:
                prior.errors.append("اسم الفصل مكرر داخل الملف")
                prior.is_valid = False
        else:
            seen[key] = r.row_number


async def _bump_imports_counter(
    session, workspace_id: str, quota: Dict[str, Any], current_count: int,
) -> int:
    today = _today_utc()
    last = quota.get("imports_today_date")
    if isinstance(last, datetime):
        last = last.date()
    elif isinstance(last, str):
        try:
            last = date.fromisoformat(last[:10])
        except ValueError:
            last = None
    new_count = current_count + 1 if last == today else 1
    await gd_update_one(
        session, "workspace_quota",
        {"workspace_school_id": workspace_id},
        {
            "imports_today": new_count,
            "imports_today_date": today.isoformat(),
            "updated_at": _utcnow_iso(),
        },
    )
    return new_count


async def _maybe_emit_quota_warning(
    current_user: dict, workspace_id: str,
    prev_count: int, new_count: int, max_per_day: int,
    cta_url: str,
) -> None:
    """Mirror Task #260 — fire exactly one warning when crossing 80% on
    the same UTC day. Best-effort; never raises."""
    try:
        if not max_per_day:
            return
        threshold = int(max_per_day * 0.8)
        if not (
            threshold > 0
            and new_count >= threshold > prev_count
            and new_count < max_per_day
        ):
            return
        from routes.notification_routes_mod import create_notification_internal
        from routes.independent_teacher_notifications_routes import should_send_channel
        if await should_send_channel(current_user, "quota", "in_app"):
            await create_notification_internal(
                title="اقتراب الحد اليومي للاستيراد",
                message=f"استخدمت {new_count} من {max_per_day} عمليات استيراد اليوم.",
                title_en="Daily import quota nearly reached",
                message_en=f"Used {new_count} of {max_per_day} imports today.",
                recipient_id=current_user["id"],
                notification_type="quota_warning",
                priority="medium",
                school_id=workspace_id,
                category="quota",
                cta_url=cta_url,
                extra_data={
                    "imports_today": new_count,
                    "max_imports_per_day": max_per_day,
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("bulk-ext quota warning notify failed: %s", exc)


async def _audit_safe(
    *, action: str, current_user: dict, workspace_id: str,
    request: Request, details: Dict[str, Any],
) -> None:
    try:
        await audit_engine.log(
            action=action,
            performed_by=current_user["id"],
            tenant_id=workspace_id,
            entity_type="workspace",
            entity_id=workspace_id,
            actor_email=current_user.get("email"),
            actor_name=current_user.get("full_name"),
            actor_role=current_user.get("role"),
            ip_address=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
            details=details,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("bulk-ext audit (%s) failed: %s", action, exc)


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=_MSG_BAD_DATE) from exc


def _resolve_workspace(current_user: dict) -> str:
    expected = independent_workspace_id(current_user)
    workspace_id = require_request_school_id(current_user)
    if expected and workspace_id != expected:
        raise HTTPException(status_code=403, detail=_MSG_CROSS_TENANT)
    return expected or workspace_id


# ============================================================
# Classes — parse / commit
# ============================================================

@router.post(
    "/independent-teacher/classes/bulk/parse",
    response_model=ParseClassResponse,
)
async def parse_classes_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(_require_independent_teacher),
) -> ParseClassResponse:
    if not file or not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail=_MSG_FILE_TYPE)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail=_MSG_FILE_REQUIRED)
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=_MSG_FILE_TOO_LARGE)

    workspace_id = _resolve_workspace(current_user)
    quota = await _load_quota(workspace_id)
    max_rows = int(quota.get("max_rows_per_import") or 200)

    rows = _read_csv(content, _CLASS_HEADER_MAP)
    if not rows:
        raise HTTPException(status_code=422, detail=_MSG_FILE_EMPTY)
    if len(rows) > max_rows:
        raise HTTPException(status_code=413, detail=_MSG_FILE_TOO_LARGE)

    parsed = [_validate_class_row(i + 1, r) for i, r in enumerate(rows)]
    _flag_duplicate_classes_in_csv(parsed)
    valid_count = sum(1 for p in parsed if p.is_valid)

    current_classes = await gd_count(
        db.session, "classes",
        {"school_id": workspace_id, "is_active": {"$ne": False}},
    )
    qview = _quota_view(quota, 0)
    qview["current_classes"] = current_classes
    qview["max_classes"] = MAX_CLASSES

    return ParseClassResponse(
        total_rows=len(parsed),
        valid_count=valid_count,
        invalid_count=len(parsed) - valid_count,
        rows=parsed,
        quota=qview,
        projected_classes=current_classes + valid_count,
    )


@router.post(
    "/independent-teacher/classes/bulk/commit",
    response_model=CommitResponse,
)
async def commit_classes_csv(
    payload: CommitClassesRequest,
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(require_recent_mfa_403()),
) -> CommitResponse:
    workspace_id = _resolve_workspace(current_user)
    quota = await _load_quota(workspace_id)
    quota_view_pre = _quota_view(quota, 0)

    if quota_view_pre["imports_today"] >= quota_view_pre["max_imports_per_day"]:
        raise HTTPException(status_code=429, detail=_MSG_QUOTA_DAILY)

    candidate = [r for r in payload.rows if r.is_valid and r.name]
    skipped = len(payload.rows) - len(candidate)
    if not candidate:
        raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)

    revalidated: List[ParsedClassRow] = []
    for r in candidate:
        v = _validate_class_row(r.row_number, {
            "name": r.name,
            "grade_level": r.grade_level or "",
            "default_subject": r.default_subject or "",
        })
        if not v.is_valid:
            raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)
        revalidated.append(v)
    _flag_duplicate_classes_in_csv(revalidated)
    if any(not r.is_valid for r in revalidated):
        raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)

    current_classes = await gd_count(
        db.session, "classes",
        {"school_id": workspace_id, "is_active": {"$ne": False}},
    )
    if current_classes + len(revalidated) > MAX_CLASSES:
        raise HTTPException(status_code=409, detail=_MSG_QUOTA_CLASSES)

    session = db.session
    inserted = 0
    new_count = quota_view_pre["imports_today"]
    try:
        async with session.begin_nested():
            now_iso = _utcnow_iso()
            for r in revalidated:
                doc = {
                    "id": str(uuid.uuid4()),
                    "school_id": workspace_id,
                    "name": r.name,
                    "grade_level": r.grade_level,
                    "capacity": 30,
                    "current_students": 0,
                    "is_active": True,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
                await gd_insert(session, "classes", doc)
                inserted += 1
            new_count = await _bump_imports_counter(
                session, workspace_id, quota, quota_view_pre["imports_today"],
            )
            await _audit_safe(
                action=_AUDIT_CLASSES, current_user=current_user,
                workspace_id=workspace_id, request=request,
                details={"inserted": inserted, "skipped": skipped,
                         "imports_today": new_count},
            )
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.exception("IT bulk classes import failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    await _maybe_emit_quota_warning(
        current_user, workspace_id,
        quota_view_pre["imports_today"], new_count,
        quota_view_pre["max_imports_per_day"],
        cta_url="/teacher/bulk-import",
    )

    refreshed = await gd_find_one(
        db.session, "workspace_quota",
        {"workspace_school_id": workspace_id},
    ) or quota
    new_total = await gd_count(
        db.session, "classes",
        {"school_id": workspace_id, "is_active": {"$ne": False}},
    )
    qv = _quota_view(refreshed, 0)
    qv["current_classes"] = new_total
    qv["max_classes"] = MAX_CLASSES
    return CommitResponse(inserted=inserted, skipped=skipped, quota=qv)


# ============================================================
# Subjects — parse / commit
# ============================================================

@router.post(
    "/independent-teacher/subjects/bulk/parse",
    response_model=ParseSubjectResponse,
)
async def parse_subjects_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(_require_independent_teacher),
) -> ParseSubjectResponse:
    if not file or not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail=_MSG_FILE_TYPE)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail=_MSG_FILE_REQUIRED)
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=_MSG_FILE_TOO_LARGE)

    workspace_id = _resolve_workspace(current_user)
    quota = await _load_quota(workspace_id)

    rows = _read_csv(content, _SUBJECT_HEADER_MAP)
    if not rows:
        raise HTTPException(status_code=422, detail=_MSG_FILE_EMPTY)
    if len(rows) > _SUBJECTS_PER_IMPORT_CAP:
        raise HTTPException(status_code=413, detail=_MSG_QUOTA_SUBJECTS_PER_IMPORT)

    parsed = [_validate_subject_row(i + 1, r) for i, r in enumerate(rows)]
    _flag_duplicate_subjects_in_csv(parsed)
    valid_count = sum(1 for p in parsed if p.is_valid)

    qview = _quota_view(quota, 0)
    qview["max_subjects_per_import"] = _SUBJECTS_PER_IMPORT_CAP

    return ParseSubjectResponse(
        total_rows=len(parsed),
        valid_count=valid_count,
        invalid_count=len(parsed) - valid_count,
        rows=parsed,
        quota=qview,
    )


@router.post(
    "/independent-teacher/subjects/bulk/commit",
    response_model=CommitResponse,
)
async def commit_subjects_csv(
    payload: CommitSubjectsRequest,
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(require_recent_mfa_403()),
) -> CommitResponse:
    workspace_id = _resolve_workspace(current_user)
    quota = await _load_quota(workspace_id)
    quota_view_pre = _quota_view(quota, 0)

    if quota_view_pre["imports_today"] >= quota_view_pre["max_imports_per_day"]:
        raise HTTPException(status_code=429, detail=_MSG_QUOTA_DAILY)

    candidate = [r for r in payload.rows if r.is_valid and r.name]
    skipped = len(payload.rows) - len(candidate)
    if not candidate:
        raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)
    if len(candidate) > _SUBJECTS_PER_IMPORT_CAP:
        raise HTTPException(status_code=413, detail=_MSG_QUOTA_SUBJECTS_PER_IMPORT)

    revalidated: List[ParsedSubjectRow] = []
    for r in candidate:
        v = _validate_subject_row(r.row_number, {
            "name": r.name, "code": r.code or "",
        })
        if not v.is_valid:
            raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)
        revalidated.append(v)
    _flag_duplicate_subjects_in_csv(revalidated)
    if any(not r.is_valid for r in revalidated):
        raise HTTPException(status_code=422, detail=_MSG_NO_VALID_ROWS)

    session = db.session
    inserted = 0
    new_count = quota_view_pre["imports_today"]
    try:
        async with session.begin_nested():
            now_iso = _utcnow_iso()
            for r in revalidated:
                sid = str(uuid.uuid4())
                doc = {
                    "id": sid,
                    "school_id": workspace_id,
                    "name": r.name,
                    "name_ar": r.name,
                    "code": r.code or f"SUB-{sid[:8].upper()}",
                    "category": "core",
                    "is_active": True,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
                await gd_insert(session, "subjects", doc)
                inserted += 1
            new_count = await _bump_imports_counter(
                session, workspace_id, quota, quota_view_pre["imports_today"],
            )
            await _audit_safe(
                action=_AUDIT_SUBJECTS, current_user=current_user,
                workspace_id=workspace_id, request=request,
                details={"inserted": inserted, "skipped": skipped,
                         "imports_today": new_count},
            )
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.exception("IT bulk subjects import failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    await _maybe_emit_quota_warning(
        current_user, workspace_id,
        quota_view_pre["imports_today"], new_count,
        quota_view_pre["max_imports_per_day"],
        cta_url="/teacher/bulk-import",
    )

    refreshed = await gd_find_one(
        db.session, "workspace_quota",
        {"workspace_school_id": workspace_id},
    ) or quota
    qv = _quota_view(refreshed, 0)
    qv["max_subjects_per_import"] = _SUBJECTS_PER_IMPORT_CAP
    return CommitResponse(inserted=inserted, skipped=skipped, quota=qv)


# ============================================================
# Schedule — duplicate week
# ============================================================

async def _resolve_workspace_teacher_id(workspace_id: str, user_id: str) -> Optional[str]:
    teacher = await gd_find_one(
        db.session, "teachers",
        {"school_id": workspace_id, "user_id": user_id},
    )
    return (teacher or {}).get("id")


def _week_target_schedule_id(workspace_id: str, week_start_iso: str) -> str:
    return f"itw_schedule_{workspace_id}_w_{week_start_iso}"


@router.post(
    "/independent-teacher/schedule/duplicate-week",
    response_model=DuplicateWeekResponse,
)
async def duplicate_week(
    payload: DuplicateWeekRequest,
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(require_recent_mfa_403()),
) -> DuplicateWeekResponse:
    workspace_id = _resolve_workspace(current_user)

    src_date = _parse_iso_date(payload.from_week_start)
    dst_date = _parse_iso_date(payload.to_week_start)
    if dst_date - src_date != timedelta(days=7):
        raise HTTPException(status_code=422, detail=_MSG_BAD_WEEK_GAP)

    quota = await _load_quota(workspace_id)
    quota_view_pre = _quota_view(quota, 0)
    if not payload.dry_run and quota_view_pre["imports_today"] >= quota_view_pre["max_imports_per_day"]:
        raise HTTPException(status_code=429, detail=_MSG_QUOTA_DAILY)

    # Workspace-wide duplication: copy EVERY schedule_sessions row in
    # the workspace for the requested source week. Filtering by
    # teacher_id would silently drop co-teaching / collaborator rows
    # that legitimately live in this IT workspace, so the only scope
    # is school_id == workspace_id. (Owner authorisation is already
    # enforced by the IT-only router gate + Tier-A MFA above.)
    target_schedule_id = _week_target_schedule_id(workspace_id, payload.to_week_start)
    src_schedule_id = _week_target_schedule_id(workspace_id, payload.from_week_start)
    base_schedule_id = f"itw_schedule_{workspace_id}"

    # Targeted, paginated reads. Each "bucket" is fetched in 500-row
    # pages so a workspace with thousands of historical schedule_sessions
    # rows is still fully evaluated for both source-row selection and
    # target-conflict detection (review fix). Bucketing also lets the
    # database use the natural composite indexes on
    # (school_id, schedule_id) and (school_id, start_time) instead of a
    # full table scan with in-memory partitioning.
    PAGE = 500

    async def _fetch_all(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        offset = 0
        while True:
            page = await gd_find(
                db.session, "schedule_sessions", filters,
                limit=PAGE, offset=offset,
            )
            if not page:
                break
            out.extend(page)
            if len(page) < PAGE:
                break
            offset += PAGE
        return out

    # Source bucket #1: rows explicitly tagged for the requested week.
    src_by_tag = await _fetch_all({
        "school_id": workspace_id, "schedule_id": src_schedule_id,
    })
    # Source bucket #2: rows whose start_time stamps the requested week.
    src_by_start = await _fetch_all({
        "school_id": workspace_id, "start_time": payload.from_week_start,
    })
    # Source bucket #3: the recurring/template rows on the workspace's
    # base schedule_id. Filter in memory to drop any that happen to
    # carry a different week-stamped start_time (defensive — should be
    # NULL for templates).
    src_template_raw = await _fetch_all({
        "school_id": workspace_id, "schedule_id": base_schedule_id,
    })
    src_template = [
        r for r in src_template_raw
        if (
            r.get("start_time") in (None, "")
            or not isinstance(r.get("start_time"), str)
            or str(r.get("start_time"))[:10] == payload.from_week_start
        )
    ]
    # De-duplicate across the three buckets by row id.
    seen_ids: set = set()
    source_rows: List[Dict[str, Any]] = []
    for bucket in (src_by_tag, src_by_start, src_template):
        for r in bucket:
            rid = r.get("id")
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            source_rows.append(r)

    if not source_rows:
        raise HTTPException(status_code=422, detail=_MSG_NOTHING_TO_DUPLICATE)

    # Target conflict-detection bucket — fully paginated as well.
    existing_target = await _fetch_all({
        "school_id": workspace_id, "schedule_id": target_schedule_id,
    })
    occupied: set = {
        (row.get("day_of_week"), int(row.get("slot_number") or 0))
        for row in existing_target
    }

    # Source dedupe — keep the last row per (day, slot) so we don't
    # try to create two duplicates of the same logical slot.
    by_slot: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for r in source_rows:
        d = r.get("day_of_week")
        s = int(r.get("slot_number") or 0)
        if not d or s <= 0:
            continue
        by_slot[(d, s)] = r

    slots_preview: List[SlotPreview] = [
        SlotPreview(
            day_of_week=d,
            slot_number=s,
            subject_name=src.get("subject_name"),
            class_name=src.get("class_name"),
            will_create=(d, s) not in occupied,
        )
        for (d, s), src in by_slot.items()
    ]

    if payload.dry_run:
        created_n = sum(1 for x in slots_preview if x.will_create)
        skipped_n = len(slots_preview) - created_n
        return DuplicateWeekResponse(
            created=created_n,
            skipped=skipped_n,
            from_week_start=payload.from_week_start,
            to_week_start=payload.to_week_start,
            quota=_quota_view(quota, 0),
            slots=slots_preview,
            dry_run=True,
        )

    session = db.session
    created = 0
    skipped = 0
    new_count = quota_view_pre["imports_today"]
    try:
        async with session.begin_nested():
            now_iso = _utcnow_iso()
            for (d, s), src in by_slot.items():
                if (d, s) in occupied:
                    skipped += 1
                    continue
                doc = {
                    "id": str(uuid.uuid4()),
                    "school_id": workspace_id,
                    "schedule_id": target_schedule_id,
                    "teacher_id": src.get("teacher_id"),
                    "class_id": src.get("class_id"),
                    "subject_id": src.get("subject_id"),
                    "day_of_week": d,
                    "slot_number": s,
                    "status": "scheduled",
                    "teacher_name": src.get("teacher_name"),
                    "class_name": src.get("class_name"),
                    "subject_name": src.get("subject_name"),
                    "start_time": payload.to_week_start,
                    "version": 1,
                    "created_at": now_iso,
                }
                await gd_insert(session, "schedule_sessions", doc)
                created += 1

            new_count = await _bump_imports_counter(
                session, workspace_id, quota, quota_view_pre["imports_today"],
            )
            await _audit_safe(
                action=_AUDIT_DUPLICATE_WEEK, current_user=current_user,
                workspace_id=workspace_id, request=request,
                details={
                    "from_week_start": payload.from_week_start,
                    "to_week_start": payload.to_week_start,
                    "created": created,
                    "skipped": skipped,
                    "imports_today": new_count,
                },
            )
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.exception("IT schedule duplicate-week failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    await _maybe_emit_quota_warning(
        current_user, workspace_id,
        quota_view_pre["imports_today"], new_count,
        quota_view_pre["max_imports_per_day"],
        cta_url="/teacher/bulk-import",
    )

    refreshed = await gd_find_one(
        db.session, "workspace_quota",
        {"workspace_school_id": workspace_id},
    ) or quota
    return DuplicateWeekResponse(
        created=created,
        skipped=skipped,
        from_week_start=payload.from_week_start,
        to_week_start=payload.to_week_start,
        quota=_quota_view(refreshed, 0),
        slots=slots_preview,
        dry_run=False,
    )


__all__ = ["router"]
