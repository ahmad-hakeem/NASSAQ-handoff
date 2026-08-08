"""
Independent-Teacher manual schedule editor (Task #193 — spec §5.4).

Endpoints (IT-only, scoped to ``itw_{user_id}``):

  * ``GET    /independent-teacher/schedule/grid``
  * ``PUT    /independent-teacher/schedule/slot``
  * ``DELETE /independent-teacher/schedule/slot``

Writes go through the upsert-by-natural-key pattern frozen in spec §5.4:

  * Natural key = ``(school_id, day_of_week, slot_number)``.
  * Optimistic concurrency via ``schedule_sessions.version``: every PUT
    body must carry the ``expected_version`` of the slot the client
    last read (``0`` for an empty slot). Mismatch → ``409`` with the
    safe Arabic message and the current row.
  * Overwrite of a non-empty slot logs an
    ``INDEPENDENT_TEACHER_SCHEDULE_OVERWRITE`` audit row (old + new
    values) inside the same transaction as the write.
  * Cross-tenant impossibility — server resolves ``school_id`` from
    the bearer (``require_request_school_id``), resolves the implicit
    ``teacher_id`` from ``users.id → teachers.user_id``, and validates
    that ``classes.school_id`` and ``subjects.school_id`` match. No
    body field can re-target another workspace.

Phase 0 invariant (per spec §5.4 final paragraph): this is **not** a
scheduling engine. It writes literal user choices and runs no solver.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete as sa_delete, select, text

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import db, get_current_user, require_recent_mfa_403
from engines.audit_engine import AuditLogEngine
from engines.sql_utils import gd_find, gd_find_one, model_to_dict
from services.cpu_offload import run_cpu_bound
from pg_models import ScheduleSession
from repositories import Repos
from utils.it_schedule import compute_it_slot_times

logger = logging.getLogger("nassaq.it_schedule")

router = APIRouter()

# Task #201 — IT §5.7 step-up backfill on the workspace schedule PDF
# export. This router is already gated to IT callers (every endpoint
# uses `_require_independent_teacher`), so the unconditional 403
# wrapper is appropriate here.
_REQUIRE_RECENT_MFA_403 = require_recent_mfa_403()


# -- Safe Arabic copy -----------------------------------------------------

_MSG_INTERNAL = "تعذّر حفظ تعديلاتك على الجدول. حاول مرة أخرى لاحقًا."
_MSG_INVALID_DAY = "اليوم المختار غير ضمن أيام العمل."
_MSG_INVALID_SLOT = "رقم الحصة خارج النطاق المسموح به."
_MSG_INVALID_VERSION = "نسخة الحصة المتوقعة غير صالحة."
_MSG_CLASS_NOT_FOUND = "الفصل المختار غير موجود في مساحتك."
_MSG_SUBJECT_NOT_FOUND = "المادة المختارة غير موجودة في مساحتك."
_MSG_SLOT_CONFLICT = (
    "تم تعديل هذه الحصة من جلسة أخرى. حدِّث الجدول وحاول مجددًا."
)
_MSG_TEACHER_MISSING = "تعذّر التعرف على معلم المساحة."

_VALID_WEEKDAYS = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}

_OVERWRITE_ACTION = "INDEPENDENT_TEACHER_SCHEDULE_OVERWRITE"


# -- Models ---------------------------------------------------------------

class SlotUpsertRequest(BaseModel):
    day_of_week: str = Field(..., min_length=1, max_length=8)
    slot_number: int = Field(..., ge=1, le=24)
    expected_version: int = Field(..., ge=0)
    class_id: Optional[str] = Field(default=None, max_length=64)
    subject_id: Optional[str] = Field(default=None, max_length=64)


class SlotDeleteRequest(BaseModel):
    day_of_week: str = Field(..., min_length=1, max_length=8)
    slot_number: int = Field(..., ge=1, le=24)
    expected_version: int = Field(..., ge=1)


# -- Helpers --------------------------------------------------------------

async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_day(value: Any) -> str:
    s = (str(value or "").strip().lower())
    if s not in _VALID_WEEKDAYS:
        raise HTTPException(status_code=400, detail=_MSG_INVALID_DAY)
    return s


async def _resolve_workspace_teacher_id(school_id: str, user_id: str) -> str:
    teacher = await gd_find_one(
        db.session, "teachers",
        {"school_id": school_id, "user_id": user_id},
    )
    tid = (teacher or {}).get("id")
    if not tid:
        # The IT lifecycle (bootstrap) always materialises the teacher
        # row alongside the workspace school. A missing row here means
        # an invariant was broken upstream — fail closed with a safe
        # Arabic message rather than silently degrading.
        raise HTTPException(status_code=409, detail=_MSG_TEACHER_MISSING)
    return tid


async def _load_settings(school_id: str) -> Dict[str, Any]:
    settings = await gd_find_one(
        db.session, "school_settings", {"school_id": school_id},
    ) or {}
    working_days_raw = settings.get("working_days") or []
    if isinstance(working_days_raw, dict):
        working_days = [k for k, on in working_days_raw.items() if on]
    elif isinstance(working_days_raw, list):
        working_days = [str(d).strip().lower() for d in working_days_raw if d]
    else:
        working_days = []
    return {
        "working_days": working_days,
        "periods_per_day": int(settings.get("periods_per_day") or 7),
        "period_minutes": int(settings.get("period_duration") or 45),
        # Full raw doc passed through so callers can derive per-slot times via
        # compute_it_slot_times without an extra DB round-trip.
        "_raw": settings,
    }


def _slot_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "day_of_week": row.get("day_of_week"),
        "slot_number": row.get("slot_number"),
        "class_id": row.get("class_id"),
        "class_name": row.get("class_name"),
        "subject_id": row.get("subject_id"),
        "subject_name": row.get("subject_name"),
        "version": int(row.get("version") or 1),
    }


async def _acquire_slot_lock(school_id: str, teacher_id: str, day: str, slot: int) -> None:
    """Serialize all writers for the same (school, teacher, day, slot)
    key using a PostgreSQL transaction-scoped advisory lock.

    This closes the insert-race window that ``SELECT ... FOR UPDATE``
    cannot cover (a missing row has nothing to lock), so two concurrent
    ``expected_version=0`` PUTs can never both insert. Lock is released
    automatically on commit/rollback. No schema change required.
    """
    key = f"itw_slot:{school_id}:{teacher_id}:{day}:{slot}"
    await db.session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": key},
    )


async def _select_slot_row(
    school_id: str, teacher_id: str, day: str, slot: int,
):
    stmt = select(ScheduleSession).where(
        and_(
            ScheduleSession.school_id == school_id,
            ScheduleSession.teacher_id == teacher_id,
            ScheduleSession.day_of_week == day,
            ScheduleSession.slot_number == slot,
        )
    ).with_for_update()
    result = await db.session.execute(stmt)
    return result.scalar_one_or_none()


def _conflict_response(current_row_snapshot: Optional[Dict[str, Any]]) -> HTTPException:
    """Build a 409 conflict response.

    ``current_row_snapshot`` must be a *plain dict already materialised*
    while the session is still live — never an ORM instance — because a
    subsequent ``rollback`` will expire ORM attribute access and trigger
    a sync-IO attempt during exception serialisation.
    """
    payload: Dict[str, Any] = {
        "code": "schedule_slot_conflict",
        "message": _MSG_SLOT_CONFLICT,
        "current_row": current_row_snapshot,
    }
    return HTTPException(status_code=409, detail=payload)


# -- GET grid -------------------------------------------------------------

@router.get("/independent-teacher/schedule/grid")
async def get_schedule_grid(
    current_user: dict = Depends(_require_independent_teacher),
):
    school_id = require_request_school_id(current_user)
    teacher_id = await _resolve_workspace_teacher_id(
        school_id, current_user["id"],
    )
    settings = await _load_settings(school_id)

    sessions = await gd_find(
        db.session, "schedule_sessions",
        {"school_id": school_id, "teacher_id": teacher_id},
        limit=500,
    )
    classes = await gd_find(
        db.session, "classes",
        {"school_id": school_id, "is_active": {"$ne": False}},
        limit=200,
    )
    subjects = await gd_find(
        db.session, "subjects",
        {"school_id": school_id, "is_active": {"$ne": False}},
        limit=200,
    )

    slot_payloads = [_slot_payload(s) for s in sessions]

    # Derive per-slot start/end times from the workspace period config so the
    # frontend can display timing alongside each period row — matching the
    # school teacher schedule UI (spec §5.4, timing-parity requirement).
    slot_times_map = compute_it_slot_times(settings.get("_raw"))
    slot_times_list = [
        {"slot_number": k, "start_time": v[0], "end_time": v[1]}
        for k, v in sorted(slot_times_map.items())
    ]

    return {
        "workspace_id": school_id,
        "teacher_id": teacher_id,
        "working_days": settings["working_days"],
        "periods_per_day": settings["periods_per_day"],
        "period_minutes": settings["period_minutes"],
        # Spec/task contract: the grid response key is `slots`. `sessions`
        # is preserved as a back-compat alias for in-flight clients only.
        "slots": slot_payloads,
        "sessions": slot_payloads,
        # Per-slot timing derived from workspace period configuration.
        # Each entry: {slot_number, start_time ("HH:MM"), end_time ("HH:MM")}.
        "slot_times": slot_times_list,
        "classes": [
            {"id": c.get("id"), "name": c.get("name")} for c in classes
        ],
        "subjects": [
            {
                "id": s.get("id"),
                "name": s.get("name") or s.get("name_ar"),
            }
            for s in subjects
        ],
    }


# -- GET PDF export -------------------------------------------------------

_DAY_AR = {
    "sun": "الأحد", "mon": "الاثنين", "tue": "الثلاثاء",
    "wed": "الأربعاء", "thu": "الخميس", "fri": "الجمعة", "sat": "السبت",
}


def _render_schedule_pdf(
    *, school_id: str, teacher_name: str,
    working_days: List[str], periods_per_day: int, period_minutes: int,
    slots: List[Dict[str, Any]],
) -> bytes:
    """Render the IT schedule as a PDF using export_engine's primitives.

    Reuses `engines/export_engine` helpers (`_register_arabic_fonts`,
    `_ar_styles`, `_ar_para`, `_build_table`) so the IT export inherits
    the same Arabic font registration, branding palette and table
    chrome as every other PDF report in the platform — i.e. a true
    `export_engine` integration even though we do not pass through the
    `ReportingEngine` (this report has no reporting-engine dataset).
    """
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, Paragraph, SimpleDocTemplate, Spacer,
    )

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
        topMargin=20 * mm, bottomMargin=15 * mm,
    )
    story: List[Any] = []
    story.append(_ar_para("جدولي الأسبوعي", styles["ArabicTitle"]))
    if teacher_name:
        story.append(_ar_para(teacher_name, styles["ArabicSubtitle"]))
    meta = (
        f"{len(working_days)} أيام × {periods_per_day} حصص "
        f"({period_minutes} دقيقة لكل حصة)"
    )
    story.append(_ar_para(meta, styles["ArabicSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=NASSAQ_TURQUOISE))
    story.append(Spacer(1, 6 * mm))

    by_key: Dict[str, Dict[str, Any]] = {}
    for s in slots:
        by_key[f"{s.get('day_of_week')}__{s.get('slot_number')}"] = s

    headers = [_DAY_AR.get(d, d) for d in working_days] + ["الحصة"]
    rows = []
    for slot_no in range(1, periods_per_day + 1):
        row = [str(slot_no)]
        for d in working_days:
            cell = by_key.get(f"{d}__{slot_no}")
            if cell:
                cls = cell.get("class_name") or "—"
                sub = cell.get("subject_name") or "—"
                row.append(f"{cls}\n{sub}")
            else:
                row.append("—")
        rows.append(list(reversed(row)))

    table = _build_table(headers, rows)
    story.append(table)
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5))
    story.append(_ar_para(f"نَسَّق NASSAQ  |  {school_id}", styles["ArabicBody"]))

    doc.build(story)
    return buf.getvalue()


@router.get("/independent-teacher/schedule/export.pdf")
async def export_schedule_pdf(
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_REQUIRE_RECENT_MFA_403),
):
    school_id = require_request_school_id(current_user)
    teacher_id = await _resolve_workspace_teacher_id(
        school_id, current_user["id"],
    )
    settings = await _load_settings(school_id)
    sessions = await gd_find(
        db.session, "schedule_sessions",
        {"school_id": school_id, "teacher_id": teacher_id},
        limit=500,
    )
    # ReportLab render is CPU-bound: run it off the event loop so one
    # teacher's export cannot freeze every other request (cpu_offload.py).
    pdf_bytes = await run_cpu_bound(
        _render_schedule_pdf,
        kind="pdf",
        school_id=school_id,
        teacher_name=current_user.get("full_name") or "",
        working_days=settings["working_days"],
        periods_per_day=settings["periods_per_day"],
        period_minutes=settings["period_minutes"],
        slots=[_slot_payload(s) for s in sessions],
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="my-schedule.pdf"',
        },
    )


# -- PUT upsert -----------------------------------------------------------

@router.put("/independent-teacher/schedule/slot")
async def upsert_schedule_slot(
    payload: SlotUpsertRequest,
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
):
    school_id = require_request_school_id(current_user)
    teacher_id = await _resolve_workspace_teacher_id(
        school_id, current_user["id"],
    )
    settings = await _load_settings(school_id)

    day = _normalise_day(payload.day_of_week)
    if settings["working_days"] and day not in settings["working_days"]:
        raise HTTPException(status_code=400, detail=_MSG_INVALID_DAY)
    slot = int(payload.slot_number)
    if slot < 1 or slot > settings["periods_per_day"]:
        raise HTTPException(status_code=400, detail=_MSG_INVALID_SLOT)

    class_id = payload.class_id or None
    subject_id = payload.subject_id or None

    class_row: Optional[dict] = None
    if class_id:
        class_row = await gd_find_one(
            db.session, "classes",
            {"id": class_id, "school_id": school_id},
        )
        if not class_row:
            raise HTTPException(status_code=404, detail=_MSG_CLASS_NOT_FOUND)

    subject_row: Optional[dict] = None
    if subject_id:
        subject_row = await gd_find_one(
            db.session, "subjects",
            {"id": subject_id, "school_id": school_id},
        )
        if not subject_row:
            raise HTTPException(status_code=404, detail=_MSG_SUBJECT_NOT_FOUND)

    now_iso = _utcnow_iso()

    try:
        await _acquire_slot_lock(school_id, teacher_id, day, slot)
        existing = await _select_slot_row(school_id, teacher_id, day, slot)

        if existing is None:
            if payload.expected_version != 0:
                raise _conflict_response(None)
            # Insert path — advisory lock above guarantees that no
            # concurrent writer can race past this check with the same
            # natural key, even without a DB unique constraint.
            new_id = str(uuid.uuid4())
            new_row = ScheduleSession(
                id=new_id,
                school_id=school_id,
                schedule_id=f"itw_schedule_{school_id}",
                teacher_id=teacher_id,
                class_id=class_id,
                subject_id=subject_id,
                day_of_week=day,
                slot_number=slot,
                status="scheduled",
                teacher_name=current_user.get("full_name"),
                class_name=(class_row or {}).get("name"),
                subject_name=(subject_row or {}).get("name") or (subject_row or {}).get("name_ar"),
                version=1,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(new_row)
            await db.session.flush()
            await db.session.commit()
            return _slot_payload(model_to_dict(new_row))

        # Existing row — version must match. Snapshot eagerly so the
        # conflict response survives the rollback below.
        if int(existing.version or 0) != int(payload.expected_version):
            snapshot = _slot_payload(model_to_dict(existing))
            raise _conflict_response(snapshot)

        prev_class_id = existing.class_id
        prev_subject_id = existing.subject_id
        was_filled = bool(prev_class_id or prev_subject_id)
        will_be_filled = bool(class_id or subject_id)
        content_changed = (
            prev_class_id != class_id or prev_subject_id != subject_id
        )

        existing.class_id = class_id
        existing.subject_id = subject_id
        existing.class_name = (class_row or {}).get("name")
        existing.subject_name = (
            (subject_row or {}).get("name") or (subject_row or {}).get("name_ar")
        )
        existing.teacher_name = current_user.get("full_name") or existing.teacher_name
        existing.version = int(existing.version or 1) + 1

        # Audit only when overwriting non-empty content with different
        # non-empty content. Pure clears go through DELETE.
        if was_filled and will_be_filled and content_changed:
            audit = AuditLogEngine(Repos(db.session))
            await audit.log(
                action=_OVERWRITE_ACTION,
                performed_by=current_user["id"],
                tenant_id=school_id,
                entity_type="schedule_session",
                entity_id=existing.id,
                actor_email=current_user.get("email"),
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                ip_address=(request.client.host if request.client else None),
                user_agent=request.headers.get("user-agent"),
                details={
                    "day_of_week": day,
                    "slot_number": slot,
                    "old": {
                        "class_id": prev_class_id,
                        "subject_id": prev_subject_id,
                    },
                    "new": {
                        "class_id": class_id,
                        "subject_id": subject_id,
                    },
                    "previous_version": int(payload.expected_version),
                    "new_version": int(existing.version),
                },
            )

        await db.session.flush()
        await db.session.commit()
        return _slot_payload(model_to_dict(existing))

    except HTTPException:
        await db.session.rollback()
        raise
    except Exception as exc:
        await db.session.rollback()
        logger.exception("IT schedule slot upsert failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)


# -- DELETE clear ---------------------------------------------------------

@router.delete("/independent-teacher/schedule/slot")
async def delete_schedule_slot(
    payload: SlotDeleteRequest,
    current_user: dict = Depends(_require_independent_teacher),
):
    school_id = require_request_school_id(current_user)
    teacher_id = await _resolve_workspace_teacher_id(
        school_id, current_user["id"],
    )
    settings = await _load_settings(school_id)

    day = _normalise_day(payload.day_of_week)
    if settings["working_days"] and day not in settings["working_days"]:
        raise HTTPException(status_code=400, detail=_MSG_INVALID_DAY)
    slot = int(payload.slot_number)
    if slot < 1 or slot > settings["periods_per_day"]:
        raise HTTPException(status_code=400, detail=_MSG_INVALID_SLOT)

    try:
        await _acquire_slot_lock(school_id, teacher_id, day, slot)
        existing = await _select_slot_row(school_id, teacher_id, day, slot)
        if existing is None:
            raise _conflict_response(None)
        if int(existing.version or 0) != int(payload.expected_version):
            snapshot = _slot_payload(model_to_dict(existing))
            raise _conflict_response(snapshot)

        await db.session.execute(
            sa_delete(ScheduleSession).where(ScheduleSession.id == existing.id)
        )
        await db.session.commit()
        return {
            "ok": True,
            "day_of_week": day,
            "slot_number": slot,
        }
    except HTTPException:
        await db.session.rollback()
        raise
    except Exception as exc:
        await db.session.rollback()
        logger.exception("IT schedule slot delete failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)


__all__ = ["router"]
