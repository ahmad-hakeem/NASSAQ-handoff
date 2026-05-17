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
    patch_draft_payload,
    purge_expired,
    update_draft_rows,
)
from engines.noor_import.class_match import normalize_grade, normalize_section
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
    seen_nid: set = set()
    seen_name_phone: set = set()
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
            # In-batch duplicate detection — second+ occurrences of the
            # same national_id (or same name+phone) inside ONE upload
            # are flagged distinctly so the preview shows them and the
            # commit path skips them instead of silently overwriting.
            np_key = f"{name}|{phone}" if name and phone else ""
            if nid and nid in seen_nid:
                dedupe = "duplicate_in_file"
            elif np_key and np_key in seen_name_phone:
                dedupe = "duplicate_in_file"
            elif nid in by_nid:
                dedupe = "update"
                existing_id = by_nid[nid]["id"]
            elif name and phone and np_key in by_name_phone:
                dedupe = "ambiguous"
                existing_id = by_name_phone[np_key]["id"]
            if nid:
                seen_nid.add(nid)
            if np_key:
                seen_name_phone.add(np_key)
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

        dedupe = "skip" if issues else "insert"
        existing_id: Optional[str] = None
        if not issues:
            # In-batch duplicate detection — second+ occurrences of the
            # same student_number inside ONE upload are flagged so the
            # preview shows them and the commit path skips them instead
            # of silently overwriting the previously-inserted row.
            if num and num in in_batch_seen:
                dedupe = "duplicate_in_file"
            elif num in students:
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
        # Only reserve the number when the row is actually
        # processable — otherwise an invalid row could poison a later
        # valid row carrying the same number into a false duplicate.
        if num and not issues:
            in_batch_seen.add(num)
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
    counts = {
        "total": len(rows),
        "insert": 0,
        "update": 0,
        "skip": 0,
        "ambiguous": 0,
        "duplicate_in_file": 0,
        "unclassified": 0,
    }
    for r in rows:
        counts[r["dedupe"]] = counts.get(r["dedupe"], 0) + 1
        if r.get("class_unresolved"):
            counts["unclassified"] += 1
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
            diag = getattr(e, "diagnostics", None)
            if diag:
                logger.warning(
                    "Noor parse failure: filename=%r size=%s head_hex=%s "
                    "content_type=%r looks_like_html=%s readers=%s",
                    diag.get("filename"),
                    diag.get("size"),
                    diag.get("head_hex"),
                    file.content_type,
                    diag.get("looks_like_html"),
                    diag.get("readers_tried"),
                )
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Noor parse failure: filename=%r size=%s content_type=%r "
                "head_hex=%s err_type=%s err=%s",
                file.filename,
                len(content),
                file.content_type,
                content[:16].hex() if content else "",
                type(e).__name__,
                str(e)[:200],
            )
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

        created_class_ids = (draft.get("payload") or {}).get("created_class_ids") or []
        await delete_draft(db.session, draft_id=body.import_draft_id)

        # Normalise: both id-list keys are always present regardless of
        # which report type was processed, so the client contract is stable.
        outcome.setdefault("imported_student_ids", [])
        outcome.setdefault("imported_teacher_ids", [])

        # Create a short-lived undo manifest (1 h TTL) so the principal
        # can undo these specific records via /undo-committed.  The
        # manifest is principal-bound + school-bound (same guarantees as
        # import drafts) and the token is a random URL-safe secret that
        # the client must round-trip back — it cannot enumerate or forge
        # it.  Only stored when there is actually something to undo.
        undo_token: Optional[str] = None
        undo_sids: List[str] = outcome["imported_student_ids"]
        undo_tids: List[str] = outcome["imported_teacher_ids"]
        if undo_sids or undo_tids:
            import json as _json
            import secrets as _secrets
            from datetime import datetime as _dt2, timedelta as _td2, timezone as _tz2
            undo_token = _secrets.token_urlsafe(24)
            _now2 = _dt2.now(_tz2.utc)
            _exp2 = _now2 + _td2(hours=1)
            _undo_payload = _json.dumps(
                {"student_ids": undo_sids, "teacher_ids": undo_tids},
                ensure_ascii=False,
            )
            await db.session.execute(
                text(
                    """
                    INSERT INTO noor_import_drafts
                        (id, principal_id, school_id, detected_type,
                         header_row, payload, counts, created_at, expires_at)
                    VALUES
                        (:id, :pid, :sid, 'undo_manifest',
                         0, CAST(:payload AS JSONB), '{}'::JSONB,
                         :now, :exp)
                    """
                ),
                {
                    "id": undo_token,
                    "pid": principal_id,
                    "sid": school_id,
                    "payload": _undo_payload,
                    "now": _now2,
                    "exp": _exp2,
                },
            )

        await _write_import_history(
            db.session,
            school_id=school_id,
            actor_id=principal_id,
            actor_name=str(current_user.get("full_name") or current_user.get("name") or ""),
            detected_type=detected_type,
            outcome=outcome,
            created_class_ids=created_class_ids,
        )
        await db.session.commit()
        outcome["undo_token"] = undo_token
        return outcome

    @router.post("/draft/{draft_id}/create-missing-classes")
    async def create_missing_classes_endpoint(
        draft_id: str,
        request: Request,
        current_user: dict = Depends(get_current_user),
    ):
        """Create the classes referenced by `class_unresolved` rows in a
        live student draft, then re-annotate the draft against the new
        class index. No second upload needed.

        Fail-closed contract (matches /commit's authority model):
          • Only valid for `detected_type == STUDENT_REPORT`.
          • Pairs whose grade or section can't be canonicalised
            (`normalize_*` returns empty / out-of-range) are REJECTED
            and never silently invented.
          • Pairs that already resolve against an existing class are
            skipped — re-annotation will pick them up.
          • Pairs that would collide on the unique
            (school_id, grade_level, section) shape are skipped too.
        """
        school_id = _require_school_role(current_user)
        principal_id = str(current_user.get("id") or current_user.get("_id") or "")
        draft = await load_draft(
            db.session,
            draft_id=draft_id,
            principal_id=principal_id,
            school_id=school_id,
        )
        if not draft:
            raise HTTPException(status_code=403, detail=_SAFE_DRAFT_DENIED)
        if draft["detected_type"] != STUDENT_REPORT:
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)

        # Optional per-pair overrides — `{overrides: [{grade_code,
        # section_code, capacity?, homeroom_teacher_id?, classroom_id?}]}`.
        # The body is OPTIONAL (a bare POST keeps the old hardcoded-defaults
        # behaviour). Anything malformed is rejected with a safe
        # Arabic 400 — zero writes, zero draft mutation.
        override_by_raw: Dict[str, Dict[str, Any]] = {}
        try:
            raw_body = await request.json()
        except Exception:
            raw_body = None
        if raw_body is not None:
            if not isinstance(raw_body, dict):
                raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
            ov_list = raw_body.get("overrides")
            if ov_list is not None:
                if not isinstance(ov_list, list):
                    raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
                # Collect ids to validate in bulk, tenant-scoped.
                requested_teacher_ids: set = set()
                requested_classroom_ids: set = set()
                for item in ov_list:
                    if not isinstance(item, dict):
                        raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
                    tid = item.get("homeroom_teacher_id")
                    if tid:
                        requested_teacher_ids.add(str(tid))
                    cid = item.get("classroom_id")
                    if cid:
                        requested_classroom_ids.add(str(cid))
                valid_teachers: Dict[str, str] = {}
                if requested_teacher_ids:
                    res = await db.session.execute(
                        text(
                            """
                            SELECT id, full_name
                            FROM teachers
                            WHERE school_id = :sid
                              AND COALESCE(is_active, TRUE) = TRUE
                              AND id = ANY(:ids)
                            """
                        ),
                        {"sid": school_id, "ids": list(requested_teacher_ids)},
                    )
                    for row in res.mappings().all():
                        valid_teachers[str(row["id"])] = (row.get("full_name") or "").strip()
                # Validate classroom_ids in one tenant-scoped query.
                # Reject classrooms that don't belong to this school or are
                # marked unavailable — mirrors the active-only check on teachers.
                valid_classrooms: set = set()
                if requested_classroom_ids:
                    res2 = await db.session.execute(
                        text(
                            """
                            SELECT id
                            FROM physical_classrooms
                            WHERE tenant_id = :sid
                              AND COALESCE(is_available, TRUE) = TRUE
                              AND id = ANY(:ids)
                            """
                        ),
                        {"sid": school_id, "ids": list(requested_classroom_ids)},
                    )
                    for row in res2.mappings().all():
                        valid_classrooms.add(str(row["id"]))
                for item in ov_list:
                    g = (item.get("grade_code") or "").strip()
                    s = (item.get("section_code") or "").strip()
                    if not g and not s:
                        continue
                    cap_raw = item.get("capacity")
                    cap_val: Optional[int] = None
                    if cap_raw is not None and cap_raw != "":
                        try:
                            cap_val = int(cap_raw)
                        except (TypeError, ValueError):
                            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
                        if cap_val < 1 or cap_val > 500:
                            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
                    tid = item.get("homeroom_teacher_id")
                    tid_resolved: Optional[str] = None
                    tname_resolved: Optional[str] = None
                    if tid:
                        tid_str = str(tid)
                        if tid_str not in valid_teachers:
                            # Tenant-isolation: any teacher id that isn't
                            # an active teacher of THIS school is rejected
                            # (no silent drop — the principal explicitly
                            # picked them).
                            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
                        tid_resolved = tid_str
                        tname_resolved = valid_teachers[tid_str] or None
                    cid = item.get("classroom_id")
                    cid_resolved: Optional[str] = None
                    if cid:
                        cid_str = str(cid)
                        if cid_str not in valid_classrooms:
                            # Tenant-isolation: classroom must belong to this school.
                            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
                        cid_resolved = cid_str
                    override_by_raw[f"{g}||{s}"] = {
                        "capacity": cap_val,
                        "homeroom_teacher_id": tid_resolved,
                        "homeroom_teacher_name": tname_resolved,
                        "classroom_id": cid_resolved,
                    }

        payload = draft.get("payload") or {}
        rows: List[Dict[str, Any]] = payload.get("rows") or []

        # Collect missing (grade, section) pairs from unresolved rows.
        # Key by NORMALISED form so `"١"` / `"1"` / `"أ"` collapse to one
        # pair. Keep the first raw values seen for the human label.
        proposed: Dict[str, Dict[str, Any]] = {}
        rejected_pairs: List[Dict[str, Any]] = []
        for r in rows:
            if not r.get("class_unresolved"):
                continue
            data = r.get("data") or {}
            raw_grade = (data.get("grade_code") or "").strip()
            raw_section = (data.get("section_code") or "").strip()
            ng = normalize_grade(raw_grade)
            ns = normalize_section(raw_section)
            # Fail closed on either side: empty result, or grade not in 1..12,
            # or section that didn't fold to a digit string.
            if not ng or not ns or not ng.isdigit() or not (1 <= int(ng) <= 12) or not ns.isdigit():
                key = f"{raw_grade}|{raw_section}"
                if key not in {p["_raw_key"] for p in rejected_pairs}:
                    rejected_pairs.append({
                        "_raw_key": key,
                        "grade_code": raw_grade,
                        "section_code": raw_section,
                    })
                continue
            key = f"{ng}|{ns}"
            ov = override_by_raw.get(f"{raw_grade}||{raw_section}") or {}
            proposed.setdefault(key, {
                "grade_norm": ng,
                "section_norm": ns,
                "grade_label": raw_grade or ng,
                "section_label": raw_section or ns,
                "capacity": ov.get("capacity"),
                "homeroom_teacher_id": ov.get("homeroom_teacher_id"),
                "homeroom_teacher_name": ov.get("homeroom_teacher_name"),
                "classroom_id": ov.get("classroom_id"),
            })
        for p in rejected_pairs:
            p.pop("_raw_key", None)

        # Re-load class index so we can skip pairs that already resolve.
        classes = await load_school_class_index(db.session, school_id)
        existing_norm: set = set()
        for c in classes:
            cg = normalize_grade(c.get("grade_level") or c.get("grade_id"))
            cs = normalize_section(c.get("section"))
            if cg and cs:
                existing_norm.add(f"{cg}|{cs}")

        created_pairs: List[Dict[str, Any]] = []
        skipped_existing: List[Dict[str, Any]] = []
        import uuid as _uuid
        from datetime import datetime as _dt, timezone as _tz
        now = _dt.now(_tz.utc)
        for key, p in proposed.items():
            if key in existing_norm:
                skipped_existing.append({
                    "grade_code": p["grade_label"],
                    "section_code": p["section_label"],
                })
                continue
            new_id = str(_uuid.uuid4())
            cap_value = p.get("capacity") if p.get("capacity") is not None else 30
            hr_id = p.get("homeroom_teacher_id")
            hr_name = p.get("homeroom_teacher_name")
            cr_id = p.get("classroom_id")
            try:
                async with db.session.begin_nested():
                    await db.session.execute(
                        text(
                            """
                            INSERT INTO classes
                                (id, name, school_id, grade_level, section,
                                 capacity, current_students,
                                 homeroom_teacher_id, homeroom_teacher_name,
                                 classroom_id,
                                 is_active, created_at, updated_at)
                            VALUES
                                (:id, :name, :sid, :grade, :section,
                                 :cap, 0,
                                 :hr_id, :hr_name,
                                 :cr_id,
                                 TRUE, :now, :now)
                            """
                        ),
                        {
                            "id": new_id,
                            "name": f"{p['grade_label']} - {p['section_label']}",
                            "sid": school_id,
                            "grade": p["grade_norm"],
                            "section": p["section_norm"],
                            "cap": cap_value,
                            "hr_id": hr_id,
                            "hr_name": hr_name,
                            "cr_id": cr_id,
                            "now": now,
                        },
                    )
                existing_norm.add(key)
                created_pairs.append({
                    "class_id": new_id,
                    "grade_code": p["grade_label"],
                    "section_code": p["section_label"],
                    "capacity": cap_value,
                    "homeroom_teacher_id": hr_id,
                    "homeroom_teacher_name": hr_name,
                    "classroom_id": cr_id,
                })
            except Exception as e:  # noqa: BLE001
                logger.warning("noor create-missing-classes insert failed: %s", e)
                rejected_pairs.append({
                    "grade_code": p["grade_label"],
                    "section_code": p["section_label"],
                })

        # Re-annotate the draft's rows server-side. The helper expects
        # parse-shape inputs (`{row_index, data}`); annotated extras are
        # stripped so the verdicts are recomputed from scratch.
        reseed_rows = [
            {"row_index": r.get("row_index"), "data": dict(r.get("data") or {})}
            for r in rows
        ]
        new_annotated = await _annotate_student_rows(
            db.session, school_id=school_id, parsed_rows=reseed_rows
        )
        new_counts = _summarise_counts(new_annotated)

        updated_ok = await update_draft_rows(
            db.session,
            draft_id=draft_id,
            principal_id=principal_id,
            school_id=school_id,
            rows=new_annotated,
            counts=new_counts,
        )
        if not updated_ok:
            raise HTTPException(status_code=403, detail=_SAFE_DRAFT_DENIED)

        # Persist created class IDs in the draft payload so commit can
        # include them in the history row even if the browser navigates away
        # and back.
        all_created_class_ids = [p["class_id"] for p in created_pairs]
        if all_created_class_ids:
            await patch_draft_payload(
                db.session,
                draft_id=draft_id,
                principal_id=principal_id,
                school_id=school_id,
                patch={"created_class_ids": all_created_class_ids},
            )

        await db.session.commit()

        return {
            "import_draft_id": draft_id,
            "detected_type": draft["detected_type"],
            "header_row": draft["header_row"],
            "sheet_name": payload.get("sheet_name"),
            "mapped_columns": payload.get("mapped_columns") or {},
            "rows": new_annotated,
            "counts": new_counts,
            "created_classes": created_pairs,
            "skipped_existing_classes": skipped_existing,
            "rejected_pairs": rejected_pairs,
        }

    @router.post("/draft/{draft_id}/undo-created-classes")
    async def undo_created_classes_endpoint(
        draft_id: str,
        request: Request,
        current_user: dict = Depends(get_current_user),
    ):
        """Undo classes auto-created by `/create-missing-classes` for a
        live draft.

        Fail-closed contract:
          • Principal + tenant binding via `load_draft` — cross-tenant
            or cross-principal lookups 403, identical to every other
            draft surface.
          • Only valid for `detected_type == STUDENT_REPORT`.
          • Each candidate class is verified to belong to the caller's
            tenant AND to have zero students attached before deletion.
            Anything that has students (e.g. because /commit already
            ran or the principal hand-attached students) is REFUSED
            with a per-class reason — never silently force-deleted.
          • After deletion the draft is re-annotated so unresolved
            rows reflect the new class index.
        """
        school_id = _require_school_role(current_user)
        principal_id = str(current_user.get("id") or current_user.get("_id") or "")
        draft = await load_draft(
            db.session,
            draft_id=draft_id,
            principal_id=principal_id,
            school_id=school_id,
        )
        if not draft:
            raise HTTPException(status_code=403, detail=_SAFE_DRAFT_DENIED)
        if draft["detected_type"] != STUDENT_REPORT:
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)

        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
        candidate_ids = raw.get("class_ids") or []
        if not isinstance(candidate_ids, list) or not all(
            isinstance(x, str) and x for x in candidate_ids
        ):
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
        # De-dupe while preserving order.
        seen: set = set()
        candidate_ids = [c for c in candidate_ids if not (c in seen or seen.add(c))]

        undone: List[Dict[str, Any]] = []
        refused: List[Dict[str, Any]] = []

        for cid in candidate_ids:
            row = (
                await db.session.execute(
                    text(
                        """
                        SELECT id, grade_level, section
                        FROM classes
                        WHERE id = :id AND school_id = :sid
                        """
                    ),
                    {"id": cid, "sid": school_id},
                )
            ).mappings().first()
            if not row:
                # Tenant mismatch or already gone — treat as not-found
                # rather than leaking which case it is.
                refused.append({"class_id": cid, "reason": "not_found"})
                continue
            student_count = (
                await db.session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM students
                        WHERE class_id = :id AND school_id = :sid
                        """
                    ),
                    {"id": cid, "sid": school_id},
                )
            ).scalar() or 0
            if student_count > 0:
                refused.append({
                    "class_id": cid,
                    "grade_code": row["grade_level"],
                    "section_code": row["section"],
                    "reason": "has_students",
                    "student_count": int(student_count),
                })
                continue
            try:
                async with db.session.begin_nested():
                    await db.session.execute(
                        text(
                            "DELETE FROM classes WHERE id = :id AND school_id = :sid"
                        ),
                        {"id": cid, "sid": school_id},
                    )
                undone.append({
                    "class_id": cid,
                    "grade_code": row["grade_level"],
                    "section_code": row["section"],
                })
            except Exception as e:  # noqa: BLE001
                logger.warning("noor undo-created-classes delete failed: %s", e)
                refused.append({"class_id": cid, "reason": "delete_failed"})

        payload = draft.get("payload") or {}
        rows: List[Dict[str, Any]] = payload.get("rows") or []
        reseed_rows = [
            {"row_index": r.get("row_index"), "data": dict(r.get("data") or {})}
            for r in rows
        ]
        new_annotated = await _annotate_student_rows(
            db.session, school_id=school_id, parsed_rows=reseed_rows
        )
        new_counts = _summarise_counts(new_annotated)
        updated_ok = await update_draft_rows(
            db.session,
            draft_id=draft_id,
            principal_id=principal_id,
            school_id=school_id,
            rows=new_annotated,
            counts=new_counts,
        )
        if not updated_ok:
            raise HTTPException(status_code=403, detail=_SAFE_DRAFT_DENIED)
        await db.session.commit()

        return {
            "import_draft_id": draft_id,
            "detected_type": draft["detected_type"],
            "header_row": draft["header_row"],
            "sheet_name": payload.get("sheet_name"),
            "mapped_columns": payload.get("mapped_columns") or {},
            "rows": new_annotated,
            "counts": new_counts,
            "undone_classes": undone,
            "refused_classes": refused,
        }

    @router.post("/undo-committed")
    async def undo_committed_endpoint(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ):
        """Delete students/teachers that were just imported, provided they
        have no downstream data (attendance, grades, links, assignments, etc.).

        Security contract:
          • Caller must be school_principal / school_admin / platform_admin.
          • `school_id` is always pinned from `current_user.tenant_id`.
          • `undo_token` is REQUIRED — issued by /commit for the specific
            import batch. It binds the undo operation to the exact IDs
            produced by that commit, this caller, and this school (TTL 1 h).
            Without a valid token the endpoint returns 403 with zero writes.
          • Only IDs listed in the undo manifest (from the token) may be
            deleted. Any ID not in the manifest is silently skipped.
          • Every remaining candidate id is re-verified against the caller's
            school_id; cross-tenant ids appear as 'not_found' (§8 invariant).
          • Student safety guard: refuses any student with attendance,
            assessment_submissions, behaviour_records, or parent links
            (parent_id IS NOT NULL or parent_invitations rows).
          • Teacher safety guard: refuses any teacher with teacher_assignments,
            teacher_class_assignments, or teacher_sessions rows.
          • Refusals are returned per-row; successfully deleted rows confirmed.
        """
        school_id = _require_school_role(current_user)
        principal_id = str(current_user.get("id") or current_user.get("_id") or "")

        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)

        undo_token = raw.get("undo_token") or ""
        if not isinstance(undo_token, str) or not undo_token:
            raise HTTPException(status_code=400, detail=_SAFE_COMMIT_FAIL)

        # Load the undo manifest — principal + school + TTL bound.
        manifest = await load_draft(
            db.session,
            draft_id=undo_token,
            principal_id=principal_id,
            school_id=school_id,
        )
        if not manifest or manifest.get("detected_type") != "undo_manifest":
            raise HTTPException(status_code=403, detail=_SAFE_DRAFT_DENIED)

        import json as _json2
        manifest_payload = manifest.get("payload") or {}
        if isinstance(manifest_payload, str):
            try:
                manifest_payload = _json2.loads(manifest_payload)
            except Exception:
                manifest_payload = {}
        allowed_student_ids: set = set(manifest_payload.get("student_ids") or [])
        allowed_teacher_ids: set = set(manifest_payload.get("teacher_ids") or [])

        # Use manifest as the authoritative set — process all allowed IDs.
        # The client may pass a subset via student_ids / teacher_ids;
        # anything not in the manifest is ignored regardless.
        client_sids = raw.get("student_ids")
        client_tids = raw.get("teacher_ids")
        if isinstance(client_sids, list):
            candidate_student_ids = [x for x in client_sids if isinstance(x, str) and x in allowed_student_ids]
        else:
            candidate_student_ids = list(allowed_student_ids)
        if isinstance(client_tids, list):
            candidate_teacher_ids = [x for x in client_tids if isinstance(x, str) and x in allowed_teacher_ids]
        else:
            candidate_teacher_ids = list(allowed_teacher_ids)

        # De-dupe while preserving order.
        def _dedup(ids: list) -> List[str]:
            seen: set = set()
            return [x for x in ids if not (x in seen or seen.add(x))]

        candidate_student_ids = _dedup(candidate_student_ids)
        candidate_teacher_ids = _dedup(candidate_teacher_ids)

        undone_students: List[Dict[str, Any]] = []
        refused_students: List[Dict[str, Any]] = []
        undone_teachers: List[Dict[str, Any]] = []
        refused_teachers: List[Dict[str, Any]] = []

        # --- Students ---
        for sid in candidate_student_ids:
            row = (
                await db.session.execute(
                    text(
                        """
                        SELECT id, full_name, student_number, parent_id
                        FROM students
                        WHERE id = :id AND school_id = :school
                        """
                    ),
                    {"id": sid, "school": school_id},
                )
            ).mappings().first()
            if not row:
                # 404-style: do not confirm cross-tenant existence.
                refused_students.append({"student_id": sid, "reason": "not_found"})
                continue

            # Safety check — any downstream data or link blocks deletion.
            downstream = (
                await db.session.execute(
                    text(
                        """
                        SELECT
                            (SELECT COUNT(*) FROM attendance
                             WHERE student_id = :id) AS att,
                            (SELECT COUNT(*) FROM assessment_submissions
                             WHERE student_id = :id) AS sub,
                            (SELECT COUNT(*) FROM behaviour_records
                             WHERE student_id = :id) AS beh,
                            (SELECT COUNT(*) FROM parent_invitations
                             WHERE student_id = :id) AS inv
                        """
                    ),
                    {"id": sid},
                )
            ).mappings().first()

            if (downstream["att"] or 0) > 0:
                refused_students.append({
                    "student_id": sid,
                    "full_name": row["full_name"],
                    "reason": "has_attendance",
                    "count": int(downstream["att"]),
                })
                continue
            if (downstream["sub"] or 0) > 0:
                refused_students.append({
                    "student_id": sid,
                    "full_name": row["full_name"],
                    "reason": "has_grades",
                    "count": int(downstream["sub"]),
                })
                continue
            if (downstream["beh"] or 0) > 0:
                refused_students.append({
                    "student_id": sid,
                    "full_name": row["full_name"],
                    "reason": "has_behaviour",
                    "count": int(downstream["beh"]),
                })
                continue
            if row.get("parent_id"):
                refused_students.append({
                    "student_id": sid,
                    "full_name": row["full_name"],
                    "reason": "has_parent_link",
                })
                continue
            if (downstream["inv"] or 0) > 0:
                refused_students.append({
                    "student_id": sid,
                    "full_name": row["full_name"],
                    "reason": "has_parent_invitation",
                    "count": int(downstream["inv"]),
                })
                continue

            try:
                async with db.session.begin_nested():
                    await db.session.execute(
                        text("DELETE FROM students WHERE id = :id AND school_id = :school"),
                        {"id": sid, "school": school_id},
                    )
                undone_students.append({
                    "student_id": sid,
                    "full_name": row["full_name"],
                    "student_number": row["student_number"],
                })
            except Exception as e:  # noqa: BLE001
                logger.warning("noor undo-committed student delete failed: %s", e)
                refused_students.append({"student_id": sid, "reason": "delete_failed"})

        # --- Teachers ---
        for tid in candidate_teacher_ids:
            row = (
                await db.session.execute(
                    text(
                        """
                        SELECT id, full_name, user_id
                        FROM teachers
                        WHERE id = :id AND school_id = :school
                        """
                    ),
                    {"id": tid, "school": school_id},
                )
            ).mappings().first()
            if not row:
                refused_teachers.append({"teacher_id": tid, "reason": "not_found"})
                continue

            # Safety check — refuse if the teacher has any active
            # assignments, class assignments, or recorded sessions.
            downstream = (
                await db.session.execute(
                    text(
                        """
                        SELECT
                            (SELECT COUNT(*) FROM teacher_assignments
                             WHERE teacher_id = :id) AS asgn,
                            (SELECT COUNT(*) FROM teacher_class_assignments
                             WHERE teacher_id = :id) AS casgn,
                            (SELECT COUNT(*) FROM teacher_sessions
                             WHERE teacher_id = :id) AS sess
                        """
                    ),
                    {"id": tid},
                )
            ).mappings().first()

            if (downstream["asgn"] or 0) > 0:
                refused_teachers.append({
                    "teacher_id": tid,
                    "full_name": row["full_name"],
                    "reason": "has_assignments",
                    "count": int(downstream["asgn"]),
                })
                continue
            if (downstream["casgn"] or 0) > 0:
                refused_teachers.append({
                    "teacher_id": tid,
                    "full_name": row["full_name"],
                    "reason": "has_class_assignments",
                    "count": int(downstream["casgn"]),
                })
                continue
            if (downstream["sess"] or 0) > 0:
                refused_teachers.append({
                    "teacher_id": tid,
                    "full_name": row["full_name"],
                    "reason": "has_sessions",
                    "count": int(downstream["sess"]),
                })
                continue

            user_id = row.get("user_id")
            try:
                async with db.session.begin_nested():
                    await db.session.execute(
                        text("DELETE FROM teachers WHERE id = :id AND school_id = :school"),
                        {"id": tid, "school": school_id},
                    )
                    if user_id:
                        await db.session.execute(
                            text("DELETE FROM users WHERE id = :uid"),
                            {"uid": user_id},
                        )
                undone_teachers.append({
                    "teacher_id": tid,
                    "full_name": row["full_name"],
                })
            except Exception as e:  # noqa: BLE001
                logger.warning("noor undo-committed teacher delete failed: %s", e)
                refused_teachers.append({"teacher_id": tid, "reason": "delete_failed"})

        # Consume the undo manifest so each token is single-use.
        await delete_draft(db.session, draft_id=undo_token)
        await db.session.commit()
        return {
            "undone_students": undone_students,
            "refused_students": refused_students,
            "undone_teachers": undone_teachers,
            "refused_teachers": refused_teachers,
        }

    @router.get("/history")
    async def get_import_history_endpoint(
        current_user: dict = Depends(get_current_user),
        limit: int = 50,
    ):
        """Return the last N committed Noor imports for this school.

        Returns rows newest-first, capped at 200 to keep the payload
        manageable. Credentials CSV is included so the principal can
        re-download teacher login credentials.
        """
        school_id = _require_school_role(current_user)
        cap = min(max(1, limit), 200)
        result = await db.session.execute(
            text(
                """
                SELECT id, school_id, actor_id, actor_name, detected_type,
                       imported_count, updated_count, skipped_count,
                       failed_count, duplicates_count, unclassified_count,
                       created_ids, updated_ids, created_class_ids,
                       credentials_csv, committed_at
                FROM noor_import_history
                WHERE school_id = :sid
                ORDER BY committed_at DESC
                LIMIT :cap
                """
            ),
            {"sid": school_id, "cap": cap},
        )
        rows = result.mappings().all()
        return {"history": [dict(r) for r in rows]}

    return router


# ---------------------------------------------------------------------------
# History writer
# ---------------------------------------------------------------------------


async def _write_import_history(
    session,
    *,
    school_id: str,
    actor_id: str,
    actor_name: str,
    detected_type: str,
    outcome: Dict[str, Any],
    created_class_ids: List[str],
) -> None:
    """Insert one row into noor_import_history.

    Errors are swallowed and logged — the caller has already committed
    the actual import data so we must never roll back that work just
    because the audit write failed.
    """
    import json as _json
    try:
        await session.execute(
            text(
                """
                INSERT INTO noor_import_history
                    (id, school_id, actor_id, actor_name, detected_type,
                     imported_count, updated_count, skipped_count,
                     failed_count, duplicates_count, unclassified_count,
                     created_ids, updated_ids, created_class_ids,
                     credentials_csv, committed_at)
                VALUES
                    (:id, :sid, :actor_id, :actor_name, :dt,
                     :imp, :upd, :skp, :fld, :dup, :unc,
                     CAST(:created_ids AS JSONB),
                     CAST(:updated_ids AS JSONB),
                     CAST(:class_ids AS JSONB),
                     CAST(:creds AS JSONB),
                     NOW())
                """
            ),
            {
                "id": str(__import__("uuid").uuid4()),
                "sid": school_id,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "dt": detected_type,
                "imp": outcome.get("imported") or 0,
                "upd": outcome.get("updated") or 0,
                "skp": outcome.get("skipped") or 0,
                "fld": outcome.get("failed") or 0,
                "dup": outcome.get("duplicates") or 0,
                "unc": outcome.get("unclassified") or 0,
                "created_ids": _json.dumps(outcome.get("created_ids") or []),
                "updated_ids": _json.dumps(outcome.get("updated_ids") or []),
                "class_ids": _json.dumps(created_class_ids or []),
                "creds": _json.dumps(outcome.get("credentials_csv") or []),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("noor import history write failed (non-fatal): %s", exc)


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
    duplicates = 0
    errors: List[Dict[str, Any]] = []
    credentials_csv: List[Dict[str, str]] = []
    imported_teacher_ids: List[str] = []
    created_ids: List[str] = []
    updated_ids: List[str] = []

    # Track ids we've ALREADY accepted into this batch (whether the
    # first sighting was an insert or a live UPDATE). A second row
    # carrying the same national_id / (name+phone) is an in-file
    # duplicate and must be rejected — otherwise rows 2..N would
    # repeatedly UPDATE the same DB record, contradicting the
    # parse-time `duplicate_in_file` verdict.
    batch_inserted_nid: set = set()
    batch_inserted_name_phone: set = set()

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
                np_key = f"{name}|{phone}" if name and phone else ""

                # In-batch duplicate detection MUST run before the
                # update lookup — otherwise the second row would find
                # the just-inserted record in `by_nid` and silently
                # overwrite it.
                if (nid and nid in batch_inserted_nid) or (
                    np_key and np_key in batch_inserted_name_phone
                ):
                    duplicates += 1
                    errors.append(
                        {
                            "row": row_idx,
                            "message": "رقم الهوية مكرر داخل نفس الملف",
                        }
                    )
                    continue

                live_existing_id: Optional[str] = None
                live_dedupe = "insert"
                if nid and nid in by_nid:
                    live_dedupe = "update"
                    live_existing_id = by_nid[nid]["id"]
                elif name and phone and np_key in by_name_phone:
                    live_dedupe = "ambiguous"
                    live_existing_id = by_name_phone[np_key]["id"]

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
                    # Mark this key as accepted in-batch BEFORE doing
                    # the update — so a later row with the same id is
                    # blocked instead of repeatedly overwriting the
                    # same DB record.
                    if nid:
                        batch_inserted_nid.add(nid)
                    if np_key:
                        batch_inserted_name_phone.add(np_key)
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
                    updated_ids.append(live_existing_id)
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
                imported_teacher_ids.append(str(result.get("teacher_id") or ""))
                if result.get("teacher_id"):
                    created_ids.append(str(result["teacher_id"]))
                # Track in-batch insertion so later rows with the same
                # national_id (or name+phone) are rejected as
                # in-file duplicates, NOT silently overwritten.
                if nid:
                    batch_inserted_nid.add(nid)
                if np_key:
                    batch_inserted_name_phone.add(np_key)
                # Update live indexes too, so a re-run of the same row
                # within a single batch (defensive) still hits UPDATE
                # rather than producing a unique-constraint violation.
                if nid:
                    by_nid[nid] = {
                        "id": result.get("teacher_id"),
                        "national_id": nid,
                        "full_name": name,
                        "phone": phone,
                        "email": resolved["email"],
                    }
                if name and phone:
                    by_name_phone[np_key] = by_nid.get(nid) or {
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
        "duplicates": duplicates,
        "errors": errors,
        "credentials_csv": credentials_csv,
        "imported_teacher_ids": [tid for tid in imported_teacher_ids if tid],
        "created_ids": created_ids,
        "updated_ids": updated_ids,
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
    duplicates = 0
    unclassified = 0
    errors: List[Dict[str, Any]] = []
    imported_student_ids: List[str] = []
    created_ids: List[str] = []
    updated_ids: List[str] = []

    # Track student_numbers we ACCEPTED in this batch (insert OR live
    # UPDATE). A second row with the same number is an in-file
    # duplicate — must not be allowed to repeatedly overwrite the same
    # DB record (the bug that collapsed 6 rows into 1).
    batch_inserted_nums: set = set()

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
                # In-batch duplicate detection MUST run before the
                # update lookup. Otherwise the second row finds the
                # just-inserted record in `students` and silently
                # overwrites it (the bug that collapsed 6 rows into 1).
                if num and num in batch_inserted_nums:
                    # Duplicate rows are skipped — they did NOT land in
                    # the DB, so they must not inflate the
                    # `unclassified` counter (which describes rows
                    # actually persisted without a class).
                    duplicates += 1
                    errors.append(
                        {
                            "row": row_idx,
                            "message": "رقم الطالب مكرر داخل نفس الملف",
                        }
                    )
                    continue

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
                    # Mark the number BEFORE the UPDATE so a later row
                    # with the same student_number is rejected as
                    # duplicate, not allowed to re-update.
                    if num:
                        batch_inserted_nums.add(num)
                    # Change-detection guard — a no-op re-import (same
                    # name + grade + class) must not bump `updated_at`
                    # nor inflate the "updated" counter. Mobile is not
                    # in the cached index, so any incoming mobile
                    # value forces a write.
                    incoming_name = (full_name or "").strip()
                    incoming_grade = (grade_code or "").strip() if grade_code else ""
                    existing_name = (existing.get("full_name") or "").strip()
                    existing_grade = (existing.get("grade") or "").strip()
                    existing_class = existing.get("class_id")
                    name_changed = bool(incoming_name) and incoming_name != existing_name
                    grade_changed = bool(incoming_grade) and incoming_grade != existing_grade
                    class_changed = class_id is not None and class_id != existing_class
                    mobile_changed = bool(mobile)
                    if not (name_changed or grade_changed or class_changed or mobile_changed):
                        # No effective change — count as updated for
                        # user-visible "row was processed" semantics
                        # but skip the DB write.
                        updated += 1
                        if existing_class is None and (grade_code or section_code):
                            unclassified += 1
                        continue
                    await update_student_mutable_fields(
                        session,
                        student_id=existing["id"],
                        school_id=school_id,
                        full_name=full_name or None,
                        grade_code=grade_code,
                        class_id=class_id,
                        mobile=mobile,
                    )
                    updated_ids.append(str(existing["id"]))
                    updated += 1
                    # Use post-update class for unclassified accounting:
                    # if the row brought a new class_id, that's the
                    # current state; otherwise the existing one stands.
                    effective_class = class_id if class_changed else existing_class
                    if effective_class is None and (grade_code or section_code):
                        unclassified += 1
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
                imported_student_ids.append(new_id)
                created_ids.append(str(new_id))
                if class_id is None and (grade_code or section_code):
                    unclassified += 1
                if num:
                    batch_inserted_nums.add(num)
                # Update live index so a re-run of the same row within
                # one batch (defensive) hits UPDATE rather than crashing
                # on the unique (school_id, student_number) index.
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
        "duplicates": duplicates,
        "unclassified": unclassified,
        "errors": errors,
        "imported_student_ids": imported_student_ids,
        "created_ids": created_ids,
        "updated_ids": updated_ids,
    }
