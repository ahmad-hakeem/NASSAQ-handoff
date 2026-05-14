"""
Noor (Saudi MoE) bulk import — server-authoritative two-step flow.

Endpoints (mounted at /noor-import):
    POST /parse   — multipart upload; returns import_draft_id + preview.
                    NO writes.
    POST /commit  — body: {import_draft_id, confirmations}; loads the
                    draft from server-side storage and upserts.

Trust model:
    • School roles cannot pass `school_id` — the route always pins
      `school_id = current_user.tenant_id`.
    • /commit accepts ONLY {import_draft_id, confirmations}. Any
      client-supplied `rows[]` is ignored. The draft is principal-bound
      AND tenant-bound AND TTL'd (1h) — any miss → 403, zero writes.
    • Teacher writes route through the canonical
      TeacherManagementEngine.create_teacher (creates users + teachers
      with proper login + must_change_password).
    • Student writes are login-suppressed: NO `users` row, NO login.
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text

from engines.noor_import import (
    NoorParseError,
    TEACHER_REPORT,
    STUDENT_REPORT,
    parse_workbook_bytes,
)
from engines.noor_import.draft_store import (
    create_draft,
    delete_draft,
    load_draft,
    purge_expired,
)
from engines.noor_import.teacher_mapper import (
    build_create_teacher_request,
    resolve_login_email,
)
from engines.noor_import.student_mapper import (
    insert_student_record_only,
    load_school_class_index,
    load_school_student_index,
    resolve_class,
    update_student_mutable_fields,
)
from engines.sql_utils import gd_find_one
from engines.teacher_management_engine import TeacherManagementEngine

logger = logging.getLogger("nassaq.noor_import")


_MAX_BYTES = 10 * 1024 * 1024
_ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
_ALLOWED_ROLES_VALUES = {"platform_admin", "school_principal", "school_admin"}
_SAFE_PARSE_FAIL = "تعذّر تحليل الملف — تأكد من رفع تقرير نور غير معدّل"
_SAFE_DRAFT_DENIED = "صلاحية المعاينة غير صالحة أو منتهية — أعد رفع الملف"
_SAFE_COMMIT_FAIL = "تعذّر إتمام عملية الاستيراد"
_SAFE_PERMISSION_DENIED = "غير مصرح لك بإجراء هذا الاستيراد"
_SAFE_NO_TENANT = "لا يمكن الاستيراد دون تحديد المدرسة"


class _RowAbort(Exception):
    """Internal sentinel — used inside per-row SAVEPOINTs to roll back
    one row without poisoning the outer transaction."""


class CommitRequest(BaseModel):
    """Strict commit envelope.

    Pydantic `extra='forbid'` makes any client-supplied field other
    than these two (e.g. an injected `rows[]`) raise a 422 BEFORE the
    handler runs — zero writes, zero draft consumption.
    """
    model_config = {"extra": "forbid"}

    import_draft_id: str = Field(..., min_length=8, max_length=128)
    confirmations: Optional[Dict[str, Any]] = None


def _require_school_role(current_user: dict) -> str:
    role = (current_user.get("role") or "").lower()
    if role not in _ALLOWED_ROLES_VALUES:
        raise HTTPException(status_code=403, detail=_SAFE_PERMISSION_DENIED)
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail=_SAFE_NO_TENANT)
    return tenant_id


def _ext_ok(filename: str) -> bool:
    name = (filename or "").lower()
    return any(name.endswith(ext) for ext in _ALLOWED_EXTENSIONS)


# ---------------------------------------------------------------------------
# Preview / dedupe annotation
# ---------------------------------------------------------------------------

async def _load_teacher_index(session, school_id: str):
    """Build (by_nid, by_name_phone) indexes for a school's teachers."""
    result = await session.execute(
        text(
            """
            SELECT id, national_id, email, full_name, phone
            FROM teachers
            WHERE school_id = :sid AND COALESCE(is_active, TRUE) = TRUE
            """
        ),
        {"sid": school_id},
    )
    by_nid: Dict[str, Dict[str, Any]] = {}
    by_name_phone: Dict[str, Dict[str, Any]] = {}
    for row in result.mappings().all():
        nid = (row.get("national_id") or "").strip()
        if nid:
            by_nid[nid] = dict(row)
        name = (row.get("full_name") or "").strip()
        phone = (row.get("phone") or "").strip()
        if name and phone:
            by_name_phone[f"{name}|{phone}"] = dict(row)
    return by_nid, by_name_phone


async def _annotate_teacher_rows(
    session, *, school_id: str, parsed_rows: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Attach per-row dedupe outcome.

    Outcomes:
      • insert    — passes validation, no existing match.
      • update    — exact national_id match against an active row.
      • ambiguous — same (full_name, phone) as an existing row but
                    no national_id match. /commit only inserts these
                    when confirmations.ambiguous_treat_as_new lists
                    the row_index, otherwise they're skipped.
      • skip      — failed validation (missing/invalid national_id
                    or full_name).
    """
    by_nid, by_name_phone = await _load_teacher_index(session, school_id)

    annotated: List[Dict[str, Any]] = []
    for r in parsed_rows:
        data = r["data"]
        issues: List[str] = []
        nid = (data.get("national_id") or "").strip()
        name = (data.get("full_name") or "").strip()
        phone = (data.get("phone") or "").strip()
        if not name:
            issues.append("missing_full_name")
        if not nid:
            issues.append("missing_national_id")
        elif len(nid) != 10 or not nid.isdigit():
            issues.append("invalid_national_id")

        dedupe = "skip" if issues else "insert"
        existing_id: Optional[str] = None
        if not issues:
            if nid in by_nid:
                dedupe = "update"
                existing_id = by_nid[nid]["id"]
            elif name and phone and f"{name}|{phone}" in by_name_phone:
                dedupe = "ambiguous"
                existing_id = by_name_phone[f"{name}|{phone}"]["id"]
        annotated.append(
            {
                "row_index": r["row_index"],
                "data": data,
                "issues": issues,
                "dedupe": dedupe,
                "existing_id": existing_id,
            }
        )
    return annotated


async def _annotate_student_rows(
    session, *, school_id: str, parsed_rows: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Annotate student rows.

    Dedupe verdicts:
      • update    — exact match on (school_id, student_number) against
                    an existing active row.
      • ambiguous — soft match on (normalized full_name + grade_code
                    + section_code) but a different/blank Noor number.
                    /commit only inserts when the row_index is in
                    confirmations.ambiguous_treat_as_new.
      • insert    — passes validation, no match.
      • skip      — fails validation.

    Missing student_number falls back to a DETERMINISTIC NSS-{hex8}
    internal id derived from sha256(school_id|full_name|grade|section)
    so re-imports of the same Noor row are idempotent (the second run
    finds the prior NSS row and routes it to UPDATE instead of insert).
    """
    import hashlib
    students = await load_school_student_index(session, school_id)
    classes = await load_school_class_index(session, school_id)

    # Soft-match index: (norm_name, grade, section) -> {id, student_number}
    soft_idx: Dict[str, Dict[str, Any]] = {}
    for s in students.values():
        nm = (s.get("full_name") or "").strip()
        gd = (s.get("grade") or "").strip()
        cid = s.get("class_id")
        if nm:
            key = f"{nm}|{gd}|{cid or ''}"
            soft_idx.setdefault(key, s)

    annotated: List[Dict[str, Any]] = []
    in_batch_seen: set = set()
    for r in parsed_rows:
        data = dict(r["data"])  # shallow copy — we may write back
        issues: List[str] = []
        num = (data.get("student_number") or "").strip()
        full_name = (data.get("full_name") or "").strip()
        grade_code = (data.get("grade_code") or "").strip()
        section_code = (data.get("section_code") or "").strip()
        if not full_name:
            issues.append("missing_full_name")

        # Deterministic NSS fallback derived from row contents — same
        # row content + same school always hashes to the same id, so
        # re-import is idempotent and the second pass routes to UPDATE.
        generated = False
        if not num and full_name:
            h = hashlib.sha256(
                f"{school_id}|{full_name}|{grade_code}|{section_code}".encode("utf-8")
            ).hexdigest()[:10].upper()
            num = f"NSS-{h}"
            data["student_number"] = num
            generated = True
        if num:
            in_batch_seen.add(num)

        dedupe = "skip" if issues else "insert"
        existing_id: Optional[str] = None
        if not issues:
            if num in students:
                dedupe = "update"
                existing_id = students[num]["id"]
            elif full_name:
                resolved_cid = resolve_class(
                    grade_code=grade_code,
                    section_code=section_code,
                    class_index=classes,
                )
                soft_key = f"{full_name}|{grade_code}|{resolved_cid or ''}"
                if soft_key in soft_idx:
                    dedupe = "ambiguous"
                    existing_id = soft_idx[soft_key]["id"]
        class_id = resolve_class(
            grade_code=grade_code,
            section_code=section_code,
            class_index=classes,
        )
        class_unresolved = class_id is None and (grade_code or section_code)
        annotated.append(
            {
                "row_index": r["row_index"],
                "data": data,
                "issues": issues,
                "dedupe": dedupe,
                "existing_id": existing_id,
                "class_id": class_id,
                "class_unresolved": bool(class_unresolved),
                "student_number_generated": generated,
            }
        )
    return annotated


def _summarise_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"total": len(rows), "insert": 0, "update": 0, "skip": 0, "ambiguous": 0}
    for r in rows:
        counts[r["dedupe"]] = counts.get(r["dedupe"], 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def create_noor_import_routes(db, get_current_user):
    router = APIRouter(prefix="/noor-import", tags=["Noor Import"])

    @router.post("/parse")
    async def parse_endpoint(
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user),
    ):
        school_id = _require_school_role(current_user)
        if not _ext_ok(file.filename or ""):
            raise HTTPException(
                status_code=400,
                detail="نوع الملف غير مدعوم — استخدم Excel (.xlsx أو .xls)",
            )
        try:
            content = await file.read()
        except Exception:
            raise HTTPException(status_code=400, detail=_SAFE_PARSE_FAIL)
        if len(content) > _MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail="حجم الملف يتجاوز الحد المسموح (10 ميغابايت)",
            )

        try:
            parsed = parse_workbook_bytes(content, file.filename or "")
        except NoorParseError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:  # noqa: BLE001
            logger.warning("Noor parse failure: %s", e)
            raise HTTPException(status_code=400, detail=_SAFE_PARSE_FAIL)

        if parsed["detected_type"] == TEACHER_REPORT:
            rows = await _annotate_teacher_rows(
                db.session, school_id=school_id, parsed_rows=parsed["rows"]
            )
        else:
            rows = await _annotate_student_rows(
                db.session, school_id=school_id, parsed_rows=parsed["rows"]
            )
        counts = _summarise_counts(rows)
        await purge_expired(db.session)

        principal_id = str(current_user.get("id") or current_user.get("_id") or "")
        draft_id = await create_draft(
            db.session,
            principal_id=principal_id,
            school_id=school_id,
            detected_type=parsed["detected_type"],
            header_row=parsed["header_row"],
            sheet_name=parsed.get("sheet_name"),
            mapped_columns=parsed["mapped_columns"],
            rows=rows,
            counts=counts,
        )
        await db.session.commit()

        return {
            "import_draft_id": draft_id,
            "detected_type": parsed["detected_type"],
            "sheet_name": parsed.get("sheet_name"),
            "header_row": parsed["header_row"],
            "mapped_columns": parsed["mapped_columns"],
            "rows": rows,
            "counts": counts,
        }

    @router.post("/commit")
    async def commit_endpoint(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ):
        # Manual envelope validation so a tampered body (e.g. an
        # injected `rows[]`) returns a SAFE ARABIC 400 instead of
        # FastAPI's default 422 schema dump. Zero writes either way.
        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
        try:
            body = CommitRequest(**raw)
        except ValidationError:
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
        school_id = _require_school_role(current_user)
        principal_id = str(current_user.get("id") or current_user.get("_id") or "")
        draft = await load_draft(
            db.session,
            draft_id=body.import_draft_id,
            principal_id=principal_id,
            school_id=school_id,
        )
        if not draft:
            raise HTTPException(status_code=403, detail=_SAFE_DRAFT_DENIED)

        payload = draft.get("payload") or {}
        rows: List[Dict[str, Any]] = payload.get("rows") or []
        detected_type: str = draft["detected_type"]

        confirmations = body.confirmations or {}
        ambiguous_treat_as_new = set(
            (confirmations.get("ambiguous_treat_as_new") or [])
        )

        if detected_type == TEACHER_REPORT:
            outcome = await _commit_teachers(
                db.session,
                school_id=school_id,
                rows=rows,
                created_by=principal_id,
                ambiguous_treat_as_new=ambiguous_treat_as_new,
            )
        elif detected_type == STUDENT_REPORT:
            outcome = await _commit_students(
                db.session,
                school_id=school_id,
                rows=rows,
                created_by=principal_id,
                ambiguous_treat_as_new=ambiguous_treat_as_new,
            )
        else:
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)

        await delete_draft(db.session, draft_id=body.import_draft_id)
        await db.session.commit()
        return outcome

    return router


# ---------------------------------------------------------------------------
# Commit helpers
# ---------------------------------------------------------------------------

async def _commit_teachers(
    session,
    *,
    school_id: str,
    rows: List[Dict[str, Any]],
    created_by: str,
    ambiguous_treat_as_new: set,
) -> Dict[str, Any]:
    engine = TeacherManagementEngine(type("DB", (), {"session": session})())
    school = await gd_find_one(session, "schools", {"id": school_id})
    school_code = (school or {}).get("code") or "sch"
    seen_emails: set = set()
    # Re-load DB index at commit time — state may have changed since
    # /parse, so we re-evaluate every row's dedupe verdict against
    # fresh teachers, not the stale one snapshotted into the draft.
    by_nid, by_name_phone = await _load_teacher_index(session, school_id)

    imported = 0
    updated = 0
    skipped = 0
    failed = 0
    errors: List[Dict[str, Any]] = []
    credentials_csv: List[Dict[str, str]] = []

    for r in rows:
        row_idx = r.get("row_index")
        data = r.get("data") or {}
        issues: List[str] = r.get("issues") or []
        if issues:
            skipped += 1
            errors.append({"row": row_idx, "message": "; ".join(issues)})
            continue
        try:
            # Per-row SAVEPOINT so a single bad row doesn't poison the
            # outer transaction (which would otherwise abort the final
            # delete_draft + commit).
            async with session.begin_nested():
                # Commit-time revalidation against fresh DB state.
                nid = (data.get("national_id") or "").strip()
                name = (data.get("full_name") or "").strip()
                phone = (data.get("phone") or "").strip()
                live_existing_id: Optional[str] = None
                live_dedupe = "insert"
                if nid and nid in by_nid:
                    live_dedupe = "update"
                    live_existing_id = by_nid[nid]["id"]
                elif name and phone and f"{name}|{phone}" in by_name_phone:
                    live_dedupe = "ambiguous"
                    live_existing_id = by_name_phone[f"{name}|{phone}"]["id"]

                if live_dedupe == "ambiguous" and row_idx not in ambiguous_treat_as_new:
                    skipped += 1
                    errors.append(
                        {
                            "row": row_idx,
                            "message": "تطابق غير مؤكد — أكّد المعالجة كصف جديد",
                        }
                    )
                    continue

                if live_dedupe == "update" and live_existing_id:
                    # NOTE: we only touch columns that exist on the
                    # `teachers` model (see `pg_models.Teacher`). Noor
                    # exports can carry address/dob, but those columns
                    # are not present in this schema — silently drop
                    # them rather than break the update path. Adding
                    # them is a future Alembic migration.
                    await session.execute(
                        text(
                            """
                            UPDATE teachers
                            SET full_name      = COALESCE(:full_name, full_name),
                                phone          = COALESCE(:phone, phone),
                                gender         = COALESCE(:gender, gender),
                                email          = COALESCE(:email, email),
                                specialization = COALESCE(:spec, specialization),
                                qualification  = COALESCE(:qual, qualification),
                                updated_at     = NOW()
                            WHERE id = :id AND school_id = :sid
                            """
                        ),
                        {
                            "full_name": data.get("full_name"),
                            "phone": data.get("phone"),
                            "gender": data.get("gender"),
                            "email": data.get("email"),
                            "spec": data.get("specialization"),
                            "qual": data.get("qualification"),
                            "id": live_existing_id,
                            "sid": school_id,
                        },
                    )
                    updated += 1
                    continue

                resolved = await resolve_login_email(
                    session,
                    noor_email=data.get("email"),
                    school_code=school_code,
                    seen_emails_in_batch=seen_emails,
                    stable_key=nid or name or None,
                )
                req = build_create_teacher_request(
                    data, login_email=resolved["email"]
                )
                result = await engine.create_teacher(req, school_id, created_by)
                if not result.get("success"):
                    failed += 1
                    errors.append(
                        {
                            "row": row_idx,
                            "message": result.get("message")
                            or result.get("error")
                            or "تعذّر إنشاء المعلم",
                        }
                    )
                    raise _RowAbort()
                imported += 1
                # Update in-memory index so a later row with the same
                # national_id (or name+phone) lands on UPDATE.
                if nid:
                    by_nid[nid] = {
                        "id": result.get("teacher_id"),
                        "national_id": nid,
                        "full_name": name,
                        "phone": phone,
                        "email": resolved["email"],
                    }
                if name and phone:
                    by_name_phone[f"{name}|{phone}"] = by_nid.get(nid) or {
                        "id": result.get("teacher_id"),
                        "full_name": name,
                        "phone": phone,
                    }
                account = result.get("user_account") or {}
                temp_password = account.get("temp_password")
                if temp_password:
                    credentials_csv.append(
                        {
                            "teacher_id": str(result.get("teacher_id") or ""),
                            "full_name": data.get("full_name") or "",
                            "login_email": resolved["email"],
                            "temp_password": temp_password,
                            "email_source": resolved["source"],
                        }
                    )
        except _RowAbort:
            pass
        except Exception as e:  # noqa: BLE001
            failed += 1
            logger.warning("Noor teacher commit row failed: %s", e)
            errors.append({"row": row_idx, "message": "تعذّر معالجة هذا الصف"})

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
        "credentials_csv": credentials_csv,
    }


async def _commit_students(
    session,
    *,
    school_id: str,
    rows: List[Dict[str, Any]],
    created_by: str,
    ambiguous_treat_as_new: set,
) -> Dict[str, Any]:
    # Re-load indexes — state may have moved since /parse. We rebuild
    # BOTH the exact-number index and the soft-match (name+grade+class)
    # index so every row's dedupe verdict is recomputed against fresh
    # DB state — the parse-time `r['dedupe']` is treated as advisory.
    students = await load_school_student_index(session, school_id)
    classes = await load_school_class_index(session, school_id)
    soft_idx: Dict[str, Dict[str, Any]] = {}
    for s in students.values():
        nm = (s.get("full_name") or "").strip()
        gd = (s.get("grade") or "").strip()
        cid = s.get("class_id")
        if nm:
            soft_idx.setdefault(f"{nm}|{gd}|{cid or ''}", s)

    imported = 0
    updated = 0
    skipped = 0
    failed = 0
    errors: List[Dict[str, Any]] = []

    for r in rows:
        row_idx = r.get("row_index")
        data = r.get("data") or {}
        issues: List[str] = r.get("issues") or []
        if issues:
            skipped += 1
            errors.append({"row": row_idx, "message": "; ".join(issues)})
            continue
        try:
            async with session.begin_nested():
                num = (data.get("student_number") or "").strip()
                full_name = (data.get("full_name") or "").strip()
                grade_code = data.get("grade_code")
                section_code = data.get("section_code")
                mobile = data.get("mobile")
                class_id = resolve_class(
                    grade_code=grade_code,
                    section_code=section_code,
                    class_index=classes,
                )
                # Recompute dedupe verdict at commit-time against the
                # FRESH indexes (mirrors teacher commit's authority
                # model). Parse-time `r['dedupe']` is ignored — only
                # live DB state can route a row.
                live_existing = students.get(num)
                live_soft = None
                if not live_existing and full_name:
                    live_soft = soft_idx.get(
                        f"{full_name}|{(grade_code or '').strip()}|{class_id or ''}"
                    )
                if (
                    live_soft
                    and not live_existing
                    and row_idx not in ambiguous_treat_as_new
                ):
                    skipped += 1
                    errors.append(
                        {
                            "row": row_idx,
                            "message": "تطابق غير مؤكد — أكّد المعالجة كصف جديد",
                        }
                    )
                    continue
                existing = live_existing
                if existing:
                    await update_student_mutable_fields(
                        session,
                        student_id=existing["id"],
                        school_id=school_id,
                        full_name=full_name or None,
                        grade_code=grade_code,
                        class_id=class_id,
                        mobile=mobile,
                    )
                    updated += 1
                    continue

                new_id = await insert_student_record_only(
                    session,
                    school_id=school_id,
                    student_number=num,
                    full_name=full_name,
                    grade_code=grade_code,
                    section_code=section_code,
                    class_id=class_id,
                    mobile=mobile,
                    created_by=created_by,
                )
                imported += 1
                # Track in-batch so later rows with the same student_number
                # become an UPDATE rather than colliding on the unique
                # (school_id, student_number) index.
                students[num] = {
                    "id": new_id,
                    "student_number": num,
                    "full_name": full_name,
                    "grade": grade_code,
                    "class_id": class_id,
                }
        except Exception as e:  # noqa: BLE001
            failed += 1
            logger.warning("Noor student commit row failed: %s", e)
            errors.append({"row": row_idx, "message": "تعذّر معالجة هذا الصف"})

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }
