"""
NASSAQ Scheduling Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64, asyncio

logger = logging.getLogger("nassaq.scheduling")

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code,
)
from engines.school_notification_engine import (
    SchoolNotificationEngine,
    SendNotificationRequest, RecipientType, NotificationPriority, NotificationType,
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct
from src.common.utils.tenant_scope import assert_school_access, resolve_school_id
from src.common.utils.subject_display import subject_display_name
from src.modules.scheduling.controllers._publish_gate import assert_publishable
from sqlalchemy import text
from engines.timetable_session_lifecycle import find_live_timetable_sessions


from shared_models import (
    StatusCheck, StatusCheckCreate, TeacherRankEnum, SessionStatusEnum, ScheduleStatusEnum, TimeSlotCreate, TimeSlotResponse, TeacherAssignmentCreate, TeacherAssignmentResponse, SchoolScheduleCreate, SchoolScheduleResponse, ScheduleSessionCreate, ScheduleSessionResponse
)

router = APIRouter()

# ============== SMART SCHEDULING ENGINE APIs ==============

# --- Models for Smart Scheduling ---
class SmartTimetableGenerateRequest(BaseModel):
    """طلب توليد الجدول الذكي"""
    academic_year_id: Optional[str] = None
    term_id: Optional[str] = None


class SmartValidationResponse(BaseModel):
    """استجابة التحقق من جاهزية البيانات"""
    is_valid: bool
    can_proceed: bool
    issues: List[dict] = []
    summary: dict = {}


class SmartTimetableResponse(BaseModel):
    """استجابة الجدول"""
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    name: str
    status: str
    is_published: bool
    version_number: int = 1
    created_at: str
    statistics: dict = {}


class ManualTimetableCreateRequest(BaseModel):
    """طلب إنشاء جدول يدوي فارغ"""
    name: str = Field(..., min_length=1, max_length=200)
    academic_year: Optional[str] = None
    semester: Optional[int] = None

    @model_validator(mode="after")
    def name_not_whitespace(self) -> "ManualTimetableCreateRequest":
        if not self.name.strip():
            raise ValueError("اسم الجدول لا يمكن أن يكون فارغاً أو مسافات فقط")
        return self


class SmartTimetableSessionResponse(BaseModel):
    """استجابة حصة في الجدول"""
    model_config = ConfigDict(extra="ignore")
    id: str
    timetable_id: str
    class_id: str
    grade_id: Optional[str] = None
    subject_id: str
    teacher_id: str
    day_of_week: str
    period_number: int
    start_time: str
    end_time: str
    session_type: str = "class"
    source_type: str = "ai_generated"
    status: str = "scheduled"


# --- Pre-Validation API ---
@router.get("/smart-scheduling/validate/{school_id}")
async def smart_validate_data_readiness(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    التحقق من جاهزية البيانات قبل توليد الجدول
    Phase 1: Validate data readiness before timetable generation
    
    يتحقق من:
    - المدرسة والعام الدراسي
    - المراحل والصفوف والفصول
    - المواد الدراسية والإسنادات
    - المعلمين والتوافر
    - إعدادات اليوم الدراسي
    - القيود الإدارية
    """
    assert_school_access(current_user, str(school_id))
    result = await smart_scheduling_engine.validate_data_readiness(school_id)
    
    return {
        "school_id": school_id,
        "is_valid": result.is_valid,
        "can_proceed": result.can_proceed,
        "issues": [i.model_dump() for i in result.issues],
        "summary": result.summary,
        "message_ar": "البيانات جاهزة للجدولة" if result.is_valid else f"يوجد {len(result.issues)} مشكلة تحتاج للمعالجة",
        "message_en": "Data is ready for scheduling" if result.is_valid else f"There are {len(result.issues)} issues that need attention"
    }


# --- Generate Timetable API ---
@router.post("/smart-scheduling/generate/{school_id}")
async def smart_generate_timetable(
    school_id: str,
    request: SmartTimetableGenerateRequest = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    توليد الجدول الدراسي بالذكاء الاصطناعي
    Smart AI-Powered Timetable Generation
    
    المراحل:
    1. التحقق من جاهزية البيانات
    2. تحميل إعدادات المدرسة
    3. بناء مصفوفة الطلب الأكاديمي
    4. بناء مصفوفة الموارد المتاحة
    5. التحقق المسبق من التعارضات
    6. توليد مسودة الجدول
    7. اكتشاف التعارضات
    8. تحسين الجدول
    """
    assert_school_access(current_user, str(school_id))
    request = request or SmartTimetableGenerateRequest()

    # حمولة سياق حكيم — نُجمِّع البيانات الفعليّة من تبويبات إعدادات الجدول
    # الخمسة (التوقيت/الفصول/الإسناد/عدم التوفر/قيود الجدول) ونمرّرها صراحةً
    # للمحرك بدلاً من ترك المحرّك يقرأ القاعدة من جديد لكل مرحلة.
    context_payload = await _assemble_hakim_context_payload(school_id)

    report = await smart_scheduling_engine.build_infeasibility_report(school_id)
    if report.blocks_generation:
        raise HTTPException(
            status_code=422,
            detail={"code": "GENERATION_BLOCKED", "report": report.model_dump(mode="json")},
        )

    result = await smart_scheduling_engine.generate_timetable(
        school_id=school_id,
        academic_year_id=request.academic_year_id,
        term_id=request.term_id,
        created_by=current_user.get("id", "system"),
        calling_user=current_user,
        context_payload=context_payload,
    )
    
    return result.model_dump()


# --- Generate Timetable as a background job -------------------------------
#
# The synchronous endpoint above still exists (scripts and tests use it), but
# the principal UI goes through this pair. Generation takes 1-27 s of pure CPU
# depending on school size (scripts/evidence_event_loop_timetable.py), which is
# long enough that a plain request/response is a bad shape: proxies and
# browsers time it out, a refresh looks like a failure, and the principal is
# pinned to the page. Instead we queue a run, hand back its id, and let the UI
# poll.
#
# The job record IS the ``timetable_runs`` row — the engine already creates one
# and walks it through validating → generating → optimizing → completed with a
# completion_percentage. Reusing it means job state is in Postgres, so polling
# works even when the poll lands on a different autoscale instance than the one
# running the job.

# Non-terminal statuses: a run sitting in any of these is still in flight.
_ACTIVE_RUN_STATUSES = [
    TimetableRunStatus.PENDING.value,
    TimetableRunStatus.VALIDATING.value,
    TimetableRunStatus.LOADING.value,
    TimetableRunStatus.GENERATING.value,
    TimetableRunStatus.OPTIMIZING.value,
]


def _run_started_at(run: Dict[str, Any]) -> Optional[datetime]:
    raw = run.get("started_at")
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _run_liveness_at(run: Dict[str, Any]) -> Optional[datetime]:
    """When this run last proved it was alive.

    Staleness is judged on the **heartbeat**, not on ``started_at``. A large
    school legitimately takes tens of seconds and could take minutes on a
    loaded instance; reaping on elapsed time alone would kill a healthy worker
    and then let a second generation start beside it, with both writing the
    same draft. A live worker refreshes ``heartbeat_at`` every
    ``_HEARTBEAT_INTERVAL_S`` — silence means the process is genuinely gone.
    """
    return _run_started_at({"started_at": run.get("heartbeat_at")}) or _run_started_at(run)


async def _reap_if_stale(run: Dict[str, Any]) -> Dict[str, Any]:
    """Fail a run whose worker vanished (instance restart, deploy, crash).

    Without this a killed instance leaves the row "generating" forever, which
    both lies to the principal and permanently blocks the one-run-per-school
    guard below.
    """
    from config import config as _cfg

    if run.get("status") not in _ACTIVE_RUN_STATUSES:
        return run
    alive_at = _run_liveness_at(run)
    if not alive_at:
        return run
    age_s = (datetime.now(timezone.utc) - alive_at).total_seconds()
    if age_s <= _cfg.TIMETABLE_JOB_STALE_AFTER_S:
        return run

    logger.warning(
        "timetable job reaped as stale run_id=%s school=%s silent_for_s=%.0f status=%s",
        run.get("id"), run.get("school_id"), age_s, run.get("status"),
    )
    patch = {
        "status": TimetableRunStatus.FAILED.value,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "notes": "توقّف التوليد بشكل غير متوقع. يرجى إعادة المحاولة.",
        "error_code": "JOB_STALE",
    }
    # Compare-and-set on status: concurrent pollers race here, and a worker
    # that is merely slow to write must not be overwritten by a second reaper.
    await gd_update_one(
        db.session, "timetable_runs",
        {"id": run.get("id"), "status": {"$in": _ACTIVE_RUN_STATUSES}},
        patch,
    )
    return {**run, **patch}


# How often a running job proves it is alive. Cheap (one UPDATE) and only
# possible at all because the CPU phases no longer hold the event loop.
_HEARTBEAT_INTERVAL_S = 20


async def _heartbeat_loop(run_id: str) -> None:
    """Refresh ``heartbeat_at`` on its own session until cancelled."""
    from db import async_session_factory

    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
        try:
            async with async_session_factory() as hb_session:
                await gd_update_one(
                    hb_session, "timetable_runs",
                    {"id": run_id, "status": {"$in": _ACTIVE_RUN_STATUSES}},
                    {"heartbeat_at": datetime.now(timezone.utc).isoformat()},
                )
                await hb_session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — a missed beat must not kill the job
            logger.warning("timetable job heartbeat failed run_id=%s", run_id)


async def _terminalize_run(run_id: str, error_code: str, message_ar: str) -> None:
    """Mark a run failed on a brand-new session.

    Used when the job's own session is the thing that broke — otherwise the
    row would stay non-terminal until some later poll reaped it, and the
    school would stay blocked in the meantime.
    """
    from db import async_session_factory

    try:
        async with async_session_factory() as rescue:
            await _fail_run(rescue, run_id, error_code, message_ar)
    except Exception:  # noqa: BLE001
        logger.exception("could not terminalize timetable run run_id=%s", run_id)


async def _find_active_run(school_id: str) -> Optional[Dict[str, Any]]:
    """The school's in-flight run, or None. Reaps a dead one on the way past."""
    existing = await gd_find(
        db.session, "timetable_runs",
        {"school_id": school_id, "status": {"$in": _ACTIVE_RUN_STATUSES}},
        # Order by the real column, not the JSONB-overflow "started_at".
        order_by="created_at", desc_order=True, limit=1,
    )
    if not existing:
        return None
    run = await _reap_if_stale(existing[0])
    return run if run.get("status") in _ACTIVE_RUN_STATUSES else None


def _already_running_response(active: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": active.get("id"),
        "run_id": active.get("id"),
        "status": active.get("status"),
        "already_running": True,
        "message_ar": "يوجد توليد جارٍ لهذه المدرسة بالفعل.",
        "message_en": "A generation is already running for this school.",
    }


async def _run_generation_job(
    run_id: str,
    school_id: str,
    academic_year_id: Optional[str],
    term_id: Optional[str],
    created_by: str,
    calling_user: Dict[str, Any],
    context_payload: Dict[str, Any],
) -> None:
    """Execute a queued generation with its OWN database session.

    The request-scoped session bound by ``pg_session_middleware`` is closed by
    the time a background task runs, so reusing it would corrupt the pooled
    connection. The CPU phases inside the engine are already offloaded to the
    timetable pool; this coroutine only supervises them and owns the writes.
    """
    from db import async_session_factory
    from services.cpu_offload import CpuOffloadBusy, CpuOffloadTimeout

    started = datetime.now(timezone.utc)
    logger.info(
        "timetable job started run_id=%s school=%s requested_by=%s",
        run_id, school_id, created_by,
    )
    heartbeat = asyncio.create_task(_heartbeat_loop(run_id))
    # `db.session` is a ContextVar. Background tasks run inside the request's
    # context, so the request's session must be put back — otherwise anything
    # scheduled after us inherits a closed background session.
    previous_session = db.session
    try:
        async with async_session_factory() as bg_session:
            db.set_session(bg_session)
            try:
                result = await smart_scheduling_engine.generate_timetable(
                    school_id=school_id,
                    academic_year_id=academic_year_id,
                    term_id=term_id,
                    created_by=created_by,
                    calling_user=calling_user,
                    context_payload=context_payload,
                    run_id=run_id,
                )
                # Persist the parts of GenerationResult the UI needs but that
                # have no home on the run row (Hakim insight list, the
                # localized message). Polling is the only channel the caller
                # has left, so anything the synchronous response used to carry
                # has to survive here.
                await gd_update_one(bg_session, "timetable_runs", {"id": run_id}, {
                    "job_result": {
                        "success": result.success,
                        "timetable_id": result.timetable_id,
                        "status": result.status,
                        "completion_percentage": result.completion_percentage,
                        "total_sessions": result.total_sessions,
                        "scheduled_sessions": result.scheduled_sessions,
                        "conflicts_count": result.conflicts_count,
                        "unscheduled_count": result.unscheduled_count,
                        "optimization_score": result.optimization_score,
                        "message_ar": result.message_ar,
                        "message_en": result.message_en,
                        "unresolved_conflicts": result.unresolved_conflicts or [],
                        "capacity_issues": result.capacity_issues,
                    },
                })
                await bg_session.commit()
                logger.info(
                    "timetable job finished run_id=%s school=%s status=%s "
                    "elapsed_ms=%d sessions=%s conflicts=%s unscheduled=%s",
                    run_id, school_id, result.status,
                    int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
                    result.scheduled_sessions, result.conflicts_count,
                    result.unscheduled_count,
                )
            except (CpuOffloadBusy, CpuOffloadTimeout) as exc:
                await bg_session.rollback()
                await _fail_run(
                    bg_session, run_id, exc.code,
                    getattr(exc, "message_ar", "تعذّر إكمال توليد الجدول."),
                )
                logger.error(
                    "timetable job rejected run_id=%s school=%s reason=%s",
                    run_id, school_id, exc.code,
                )
            except Exception as exc:  # noqa: BLE001 — a job must never die silently
                await bg_session.rollback()
                await _fail_run(
                    bg_session, run_id, "GENERATION_ERROR",
                    "فشل توليد الجدول. يرجى المحاولة مرة أخرى.",
                )
                logger.exception(
                    "timetable job failed run_id=%s school=%s err=%s",
                    run_id, school_id, exc,
                )
    except Exception:  # noqa: BLE001 — the job's own session broke
        logger.exception("timetable job bookkeeping failed run_id=%s", run_id)
        # The session we would normally write the failure with is the thing
        # that failed, so terminalize on a fresh one. Otherwise the run stays
        # "generating" and blocks the school until the stale reaper fires.
        await _terminalize_run(
            run_id, "GENERATION_ERROR",
            "فشل توليد الجدول. يرجى المحاولة مرة أخرى.",
        )
    finally:
        heartbeat.cancel()
        try:
            await heartbeat
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        db.set_session(previous_session)


async def _fail_run(session, run_id: str, error_code: str, message_ar: str) -> None:
    """Best-effort terminal FAILED write on a fresh transaction."""
    try:
        await gd_update_one(session, "timetable_runs", {"id": run_id}, {
            "status": TimetableRunStatus.FAILED.value,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "completion_percentage": 100,
            "error_code": error_code,
            "notes": message_ar,
        })
        await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("could not mark timetable run failed run_id=%s", run_id)


@router.post("/smart-scheduling/generate/{school_id}/job", status_code=202)
async def smart_generate_timetable_job(
    school_id: str,
    background_tasks: BackgroundTasks,
    request: SmartTimetableGenerateRequest = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """بدء توليد الجدول كمهمة خلفية وإرجاع معرّف المهمة فوراً.

    Queue timetable generation and return immediately with a job id. Poll
    ``GET /smart-scheduling/job/{job_id}`` for status and progress.
    """
    assert_school_access(current_user, str(school_id))
    request = request or SmartTimetableGenerateRequest()

    # One generation per school at a time. Two concurrent runs would race to
    # write the same draft and burn two of the very few CPU workers on a result
    # that one of them is going to overwrite anyway.
    #
    # Cheap first look, so the common "user double-clicked" case answers
    # without touching the lock. The authoritative check is under the lock
    # below — this one can be raced past and that is fine.
    active = await _find_active_run(school_id)
    if active:
        return _already_running_response(active)

    # Fail fast on constraints that make the school unsolvable — cheaper to
    # answer now than to queue a job that can only fail.
    context_payload = await _assemble_hakim_context_payload(school_id)
    report = await smart_scheduling_engine.build_infeasibility_report(school_id)
    if report.blocks_generation:
        raise HTTPException(
            status_code=422,
            detail={"code": "GENERATION_BLOCKED", "report": report.model_dump(mode="json")},
        )

    # Authoritative claim. The check above and the insert below are separated
    # by two awaited round-trips, which is more than enough for two principals
    # (or one impatient double-click) to both pass it and start competing
    # searches over the same draft. A transaction-scoped advisory lock keyed on
    # the school makes claim-or-defer atomic without a schema change; it is
    # released by the commit a few lines down.
    await db.session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": f"timetable_gen:{school_id}"},
    )
    active = await _find_active_run(school_id)
    if active:
        await db.session.commit()  # release the lock; we are not claiming
        return _already_running_response(active)

    now_iso = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetable_runs", {
        "id": run_id,
        "school_id": school_id,
        "academic_year_id": request.academic_year_id,
        "term_id": request.term_id,
        "run_type": "full_generation",
        "target_class_ids": [],
        "status": TimetableRunStatus.PENDING.value,
        "started_at": now_iso,
        # Seed the heartbeat so a job that dies before its first beat is still
        # reaped on the normal timer instead of looking permanently fresh.
        "heartbeat_at": now_iso,
        "created_by": current_user.get("id", "system"),
        "completion_percentage": 0,
        "conflicts_count": 0,
        "unscheduled_count": 0,
        "notes": "",
    })
    # Commit before scheduling: under BaseHTTPMiddleware the background task's
    # own session can start before pg_session_middleware commits this one, and
    # the engine would then not find the row it is meant to fill in.
    await db.session.commit()

    logger.info(
        "timetable job queued run_id=%s school=%s requested_by=%s role=%s",
        run_id, school_id, current_user.get("id"), current_user.get("role"),
    )

    background_tasks.add_task(
        _run_generation_job,
        run_id, school_id, request.academic_year_id, request.term_id,
        current_user.get("id", "system"),
        # Sanitized copy — the engine only needs identity/tenant for its
        # tenant assertion, never the token fields.
        {
            "id": current_user.get("id"),
            "role": current_user.get("role"),
            "tenant_id": current_user.get("tenant_id"),
            "school_id": current_user.get("school_id"),
        },
        context_payload,
    )

    return {
        "job_id": run_id,
        "run_id": run_id,
        "status": TimetableRunStatus.PENDING.value,
        "poll_url": f"/api/smart-scheduling/job/{run_id}",
        "message_ar": "بدأ توليد الجدول. يمكنك متابعة التقدّم أو مواصلة عملك.",
        "message_en": "Timetable generation started. You can follow progress or keep working.",
    }


@router.get("/smart-scheduling/job/{job_id}")
async def smart_get_generation_job(
    job_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """حالة مهمة توليد الجدول وتقدّمها. Status and progress of a generation job."""
    run = await gd_find_one(db.session, "timetable_runs", {"id": job_id})
    if not run:
        raise HTTPException(status_code=404, detail="لم يتم العثور على مهمة التوليد")
    assert_school_access(current_user, str(run.get("school_id") or ""))

    run = await _reap_if_stale(run)
    status_value = run.get("status")
    is_done = status_value in (
        TimetableRunStatus.COMPLETED.value,
        TimetableRunStatus.PARTIAL.value,
        TimetableRunStatus.FAILED.value,
    )
    return {
        "job_id": job_id,
        "run_id": job_id,
        "school_id": run.get("school_id"),
        "status": status_value,
        "is_done": is_done,
        "success": status_value in (
            TimetableRunStatus.COMPLETED.value, TimetableRunStatus.PARTIAL.value
        ),
        "progress": run.get("completion_percentage") or 0,
        "timetable_id": run.get("timetable_id"),
        "conflicts_count": run.get("conflicts_count") or 0,
        "unscheduled_count": run.get("unscheduled_count") or 0,
        "optimization_score": run.get("optimization_score"),
        "generation_summary": run.get("generation_summary"),
        # Full GenerationResult payload once the job is done — the same shape
        # the synchronous endpoint returns, so the UI has one code path.
        "result": run.get("job_result"),
        "error_code": run.get("error_code"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "message_ar": run.get("notes") or "",
    }


async def _assemble_hakim_context_payload(school_id: str) -> Dict[str, Any]:
    """Assemble the strict context payload for Hakeem.

    The payload is a single, validated dict that mirrors the five
    Schedule Settings tabs the user fills in:

      - ``school_settings``     — التوقيت + إعدادات اليوم الدراسي
      - ``time_slots``          — حصص اليوم وأنواعها
      - ``classes``             — الفصول الفعّالة
      - ``teacher_assignments`` — الإسنادات الفعّالة
      - ``teacher_unavailability``
      - ``class_unavailability``
      - ``school_constraints``  + ``administrative_constraints``

    We surface a basic structural validation (timing must exist) and
    log per-category counts; the engine then consumes the payload as
    its primary source instead of re-querying the DB per phase.
    """
    school_settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    time_slots = await gd_find(db.session, "time_slots", {"school_id": school_id}, limit=500)
    classes = await gd_find(db.session, "classes", {"school_id": school_id, "is_active": True}, limit=2000)
    assignments = await gd_find(db.session, "teacher_assignments", {"school_id": school_id, "is_active": True}, limit=5000)

    # Schedule Settings UI writes both teacher- and class-level rows into a
    # single `unavailability` collection with an `entity_type` discriminator
    # (teacher / class). We split here so each engine phase consumes only
    # the rows it cares about.
    unavailability_rows = await gd_find(db.session, "unavailability", {"school_id": school_id}, limit=10000)
    teacher_unavail = [u for u in unavailability_rows if u.get("entity_type") == "teacher"]
    class_unavail = [u for u in unavailability_rows if u.get("entity_type") == "class"]

    school_constraints = await gd_find(db.session, "school_constraints", {"school_id": school_id, "is_active": True}, limit=500)
    admin_constraints = await gd_find(db.session, "administrative_constraints", {"school_id": school_id, "is_active": True}, limit=500)

    # ── Constraints UI tab #1: Hard Constraints (القيود الإلزامية) ───────
    # ACTIVATION MODEL: hard constraints are SYSTEM-LEVEL absolute blockers.
    # The `timetable_hard_constraints` collection is the immutable global
    # reference; principals may only toggle the handful of rules the system
    # marks `can_disable: true`, stored as per-school rows in
    # `school_hard_constraint_overrides`. We merge those overrides in here so
    # the engine honours the principal's toggles on the next generation run.
    # The registry honours the merged `is_active` via `active_validation_keys`.
    global_hard = await gd_find(
        db.session, "timetable_hard_constraints", {"is_system": True},
        order_by="order", desc_order=False, limit=50,
    )
    hard_overrides_rows = await gd_find(
        db.session, "school_hard_constraint_overrides", {"school_id": school_id}, limit=200,
    )
    hard_overrides_by_code = {ov["code"]: ov for ov in hard_overrides_rows if ov.get("code")}
    hard_constraints: list = []
    for c in global_hard:
        merged = dict(c)
        ov = hard_overrides_by_code.get(c.get("code"))
        # A per-school override can only disable a rule the system explicitly
        # allows to be disabled — mandatory blockers are never silenced even
        # if a stale override row exists.
        if ov and "is_active" in ov and bool(c.get("can_disable", False)):
            merged["is_active"] = ov["is_active"]
        hard_constraints.append(merged)

    # ── Constraints UI tab #2: Soft Constraints (القيود التفضيلية) ───────
    # Global immutable list + per-school overrides (is_active / weight /
    # target_subject_ids) merged in, plus any custom soft constraints
    # the principal added. Engine uses `weight` as the soft-scoring
    # multiplier and treats `is_active=False` as a no-op.
    global_soft = await gd_find(
        db.session, "timetable_soft_constraints", {},
        order_by="order", desc_order=False, limit=50,
    )
    soft_overrides_rows = await gd_find(
        db.session, "school_soft_constraint_overrides", {"school_id": school_id}, limit=200,
    )
    soft_overrides_by_code = {ov["code"]: ov for ov in soft_overrides_rows if ov.get("code")}
    merged_soft: list = []
    for c in global_soft:
        merged = dict(c)
        ov = soft_overrides_by_code.get(c.get("code"))
        if ov:
            for k in ("is_active", "weight", "target_subject_ids"):
                if k in ov:
                    merged[k] = ov[k]
        merged_soft.append(merged)
    custom_soft = await gd_find(
        db.session, "custom_soft_constraints", {"school_id": school_id, "is_active": True},
        limit=100,
    )

    # ── Constraints UI tab #3: Teacher Quotas (النصاب والتكليفات) ────────
    # Per-teacher effective teaching cap = total_periods (from rank)
    #   − other_duty_periods (sum of teacher_other_duties.equivalent_periods)
    #   − standby_override (manual override on teacher_workload_overrides)
    # Engine treats `max_teaching_periods` as a strict ceiling: once a
    # teacher's `resource_usage` reaches it, the teacher is removed from
    # the candidate pool for every remaining demand.
    from src.modules.schools.controllers.school_settings_mod import RANK_TOTAL_PERIODS
    teachers_for_quota = await gd_find(
        db.session, "teachers", {"school_id": school_id, "is_active": {"$ne": False}}, limit=500,
    )
    duties_rows = await gd_find(
        db.session, "teacher_other_duties", {"school_id": school_id}, limit=500,
    )
    duties_by_teacher: Dict[str, int] = {}
    for d in duties_rows:
        tid = d.get("teacher_id")
        if not tid:
            continue
        try:
            eq = int(d.get("equivalent_periods", 0) or 0)
        except (TypeError, ValueError):
            eq = 0
        duties_by_teacher[tid] = duties_by_teacher.get(tid, 0) + eq
    overrides_rows = await gd_find(
        db.session, "teacher_workload_overrides", {"school_id": school_id}, limit=500,
    )
    overrides_by_teacher: Dict[str, int] = {}
    for o in overrides_rows:
        tid = o.get("teacher_id")
        std = o.get("standby_override")
        if tid and isinstance(std, int):
            overrides_by_teacher[tid] = std
    teacher_quotas: Dict[str, Dict[str, int]] = {}
    for t in teachers_for_quota:
        tid = t.get("id") or t.get("teacher_id")
        if not tid:
            continue
        rank = t.get("rank", "") or ""
        total = RANK_TOTAL_PERIODS.get(rank, 24)
        other_duty = duties_by_teacher.get(tid, 0)
        standby = overrides_by_teacher.get(tid, 0)
        # Teaching cap can never go negative, and must be at least 0 so
        # an over-allocated teacher is simply never picked rather than
        # crashing the placement loop.
        max_teaching = max(0, int(total) - int(other_duty) - int(standby))
        teacher_quotas[tid] = {
            "total_periods": int(total),
            "other_duty_periods": int(other_duty),
            "standby_override_periods": int(standby),
            "max_teaching_periods": max_teaching,
        }

    # Strict contract — sections mirror the five Schedule Settings tabs
    # the user fills in (timing / classes / assignments / unavailability /
    # constraints). The engine reads from these named sections only.
    payload: Dict[str, Any] = {
        "school_id": school_id,
        "timing": {
            "school_settings": school_settings or None,
            "time_slots": time_slots or [],
        },
        "classes": classes or [],
        "assignments": assignments or [],
        "unavailability": {
            "teacher": teacher_unavail or [],
            "class": class_unavail or [],
        },
        "constraints": {
            "school": school_constraints or [],
            "administrative": admin_constraints or [],
        },
        # Three Schedule Settings → Constraints categories — the engine
        # consumes these directly so the principal's UI toggles take
        # effect on the very next generation run.
        "hard_constraints": hard_constraints or [],
        "soft_constraints": {
            "system": merged_soft,
            "custom": custom_soft or [],
        },
        "teacher_quotas": teacher_quotas,
    }

    has_timing = bool(payload["timing"]["time_slots"]) or bool(
        (payload["timing"]["school_settings"] or {}).get("periods_per_day")
    )
    if not has_timing:
        # The infeasibility report (INF-05) will block generation, but
        # we surface the structural contract explicitly here so any
        # caller knows the payload is incomplete.
        logger.warning("hakim_context_payload school_id=%s missing timing — generation will be blocked by INF-05", school_id)

    logger.info(
        "hakim_context_payload school_id=%s timing.time_slots=%d classes=%d assignments=%d "
        "unavailability.teacher=%d unavailability.class=%d constraints.school=%d "
        "constraints.administrative=%d hard_constraints=%d soft_constraints.system=%d "
        "soft_constraints.custom=%d teacher_quotas=%d validated=%s",
        school_id,
        len(payload["timing"]["time_slots"]),
        len(payload["classes"]),
        len(payload["assignments"]),
        len(payload["unavailability"]["teacher"]),
        len(payload["unavailability"]["class"]),
        len(payload["constraints"]["school"]),
        len(payload["constraints"]["administrative"]),
        len(payload["hard_constraints"]),
        len(payload["soft_constraints"]["system"]),
        len(payload["soft_constraints"]["custom"]),
        len(payload["teacher_quotas"]),
        has_timing,
    )
    return payload


# --- Generate Timetable Smart API (Alternative endpoint for frontend) ---
@router.post("/timetable/generate-smart")
async def generate_timetable_smart(
    request: Request,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    توليد الجدول الدراسي بالذكاء الاصطناعي - نقطة نهاية بديلة
    Smart AI-Powered Timetable Generation - Alternative endpoint
    """
    try:
        body = await request.json()
        use_baseline = bool(body.get("use_baseline", False))

        override = body.get("school_id") or request.headers.get("X-School-Context")
        if override is not None and not isinstance(override, str):
            raise HTTPException(status_code=400, detail="school_id يجب أن يكون نصاً")
        if isinstance(override, str):
            override = override.strip() or None

        school_id = resolve_school_id(current_user, override)
        if not school_id:
            raise HTTPException(status_code=400, detail="school_id مطلوب")
        
        # Get school settings
        settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
        if not settings:
            raise HTTPException(status_code=404, detail="لم يتم العثور على إعدادات المدرسة")
        
        nested_settings = settings.get("settings", {})
        academic_year = nested_settings.get("academic_year") or settings.get("academicYear") or settings.get("academic_year")

        context_payload = await _assemble_hakim_context_payload(school_id)

        report = await smart_scheduling_engine.build_infeasibility_report(school_id)
        if report.blocks_generation:
            raise HTTPException(
                status_code=422,
                detail={"code": "GENERATION_BLOCKED", "report": report.model_dump(mode="json")},
            )

        # Generate timetable
        result = await smart_scheduling_engine.generate_timetable(
            school_id=school_id,
            academic_year_id=academic_year,
            term_id=None,
            created_by=current_user.get("id", "system"),
            calling_user=current_user,
            context_payload=context_payload,
        )
        
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="فشل في توليد الجدول")


# --- Get School Timetables API ---
@router.get("/smart-scheduling/timetables/{school_id}")
async def smart_get_school_timetables(
    school_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على جميع الجداول للمدرسة
    Get all timetables for a school
    """
    assert_school_access(current_user, str(school_id))
    timetables = await smart_scheduling_engine.get_school_timetables(school_id)
    return {
        "school_id": school_id,
        "total": len(timetables),
        "timetables": timetables
    }


# --- Manual Timetable Creation API ---
@router.post("/smart-scheduling/timetables/manual", status_code=201)
async def create_timetable_manually(
    request: ManualTimetableCreateRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN])),
    x_school_context: Optional[str] = Header(None),
):
    """
    إنشاء جدول يدوي فارغ
    Create a blank manual draft timetable that the admin can populate session-by-session.
    """
    school_id = resolve_school_id(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, school_id)

    now = datetime.now(timezone.utc).isoformat()
    timetable_id = str(uuid.uuid4())
    user_id = current_user.get("id", "system")

    await gd_insert(db.session, "timetables", {
        "id": timetable_id,
        "school_id": school_id,
        "name": request.name.strip(),
        "academic_year": request.academic_year or "2026-2027",
        "semester": request.semester or 1,
        "status": TimetableStatus.DRAFT.value,
        "is_published": False,
        "total_sessions": 0,
        "version": 1,
        "generation_mode": "manual",
        "created_by": user_id,
        "updated_by": user_id,
        "created_at": now,
        "updated_at": now,
    })

    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=500, detail="تعذّر إنشاء الجدول")

    return {
        "id": timetable.get("id"),
        "school_id": timetable.get("school_id"),
        "name": timetable.get("name"),
        "status": timetable.get("status"),
        "is_published": timetable.get("is_published", False),
        "generation_mode": timetable.get("generation_mode", "manual"),
        "created_at": timetable.get("created_at"),
        "created_by": timetable.get("created_by"),
        "message_ar": "تم إنشاء الجدول اليدوي بنجاح",
        "message_en": "Manual timetable created successfully",
    }


# --- Timetable Versions List API (New - Must be before dynamic route) ---
@router.get("/smart-scheduling/timetable/versions")
async def get_timetable_versions(
    current_user: dict = Depends(get_current_user),
    x_school_context: Optional[str] = Header(None),
    status: Optional[str] = Query(None, description="Filter by status. Default returns draft+published, excludes archived."),
):
    """
    الحصول على جميع نسخ الجدول للمدرسة
    Get all timetable versions for the school (draft + published by default, excludes archived).
    """
    school_id = resolve_school_id(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")

    query: dict = {"school_id": school_id}
    if status:
        query["status"] = status
    else:
        query["status"] = {"$in": [TimetableStatus.DRAFT.value, TimetableStatus.PUBLISHED.value]}

    timetables = await gd_find(db.session, "timetables", query, order_by="created_at", desc_order=True, limit=100)

    versions = []
    for tt in timetables:
        versions.append({
            "id": tt.get("id"),
            "versionName": tt.get("version_name") or tt.get("name") or f"نسخة {tt.get('id', '')[:6]}",
            "status": tt.get("status", "draft"),
            "generation_mode": tt.get("generation_mode", "full"),
            "quality_score": tt.get("quality_score", 0),
            "conflicts_count": tt.get("conflicts_count", 0),
            "warnings_count": tt.get("warnings_count", 0),
            "created_at": tt.get("created_at"),
            "published_at": tt.get("published_at"),
            "published_by": tt.get("published_by"),
            "created_by": tt.get("created_by", "النظام"),
            "updated_by": tt.get("updated_by"),
        })

    return {
        "school_id": school_id,
        "total": len(versions),
        "versions": versions,
    }


# --- Active Timetable Sessions API (New - Must be before dynamic route) ---
@router.get("/smart-scheduling/timetable/active/sessions")
async def get_active_timetable_sessions(
    class_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    x_school_context: Optional[str] = Header(None)
):
    """
    الحصول على حصص الجدول النشط (المنشور أو المسودة)
    Get sessions for the active timetable
    """
    school_id = resolve_school_id(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    
    # Find active (published) timetable first, then draft
    timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"})
    
    if not timetable:
        timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "draft"})
    
    if not timetable:
        return {"sessions": [], "total": 0, "message": "لا يوجد جدول نشط"}
    
    # Build query
    query = {"timetable_id": timetable.get("id")}
    if class_id:
        query["class_id"] = class_id
    if teacher_id:
        query["teacher_id"] = teacher_id
    
    # Fetch sessions
    sessions = await find_live_timetable_sessions(db.session, query, limit=1000)
    
    # Enrich sessions
    enriched_sessions = []
    for session in sessions:
        # Get teacher name
        teacher = await gd_find_one(db.session, "teachers", {"id": session.get("teacher_id")})
        # Get class name
        cls = await gd_find_one(db.session, "classes", {"id": session.get("class_id")})
        # Get grade
        grade = await gd_find_one(db.session, "grades", {"id": cls.get("grade_id") if cls else None})
        
        session["teacher_name"] = teacher.get("full_name") if teacher else ""
        session["class_name"] = f"{grade.get('name_ar', '')} - {cls.get('section', '') if cls else ''}" if grade else (cls.get("name", "") if cls else "")
        enriched_sessions.append(session)
    
    return {
        "timetable_id": timetable.get("id"),
        "total": len(enriched_sessions),
        "sessions": enriched_sessions
    }


# --- Get Timetable Details API ---
@router.get("/smart-scheduling/timetable/{timetable_id}")
async def smart_get_timetable(
    timetable_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على تفاصيل جدول محدد
    Get specific timetable details
    """
    timetable = await smart_scheduling_engine.get_timetable(timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    
    return timetable


# --- Get Timetable Sessions API ---
@router.get("/smart-scheduling/timetable/{timetable_id}/sessions")
async def smart_get_timetable_sessions(
    timetable_id: str,
    class_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    day_of_week: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على حصص الجدول
    Get timetable sessions with optional filters
    """
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    sessions = await smart_scheduling_engine.get_timetable_sessions(
        timetable_id=timetable_id,
        class_id=class_id,
        teacher_id=teacher_id,
        day_of_week=day_of_week
    )

    # Batch fetch related entities (massive perf win vs N+1 queries)
    teacher_ids = list({s.get("teacher_id") for s in sessions if s.get("teacher_id")})
    class_ids = list({s.get("class_id") for s in sessions if s.get("class_id")})
    subject_ids = list({s.get("subject_id") for s in sessions if s.get("subject_id")})

    teachers = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=len(teacher_ids) or 1) if teacher_ids else []
    classes = await gd_find(db.session, "classes", {"id": {"$in": class_ids}, "is_active": {"$ne": False}}, limit=len(class_ids) or 1) if class_ids else []
    subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=len(subject_ids) or 1) if subject_ids else []
    found_subj_ids = {s.get("id") for s in subjects}
    missing_subj_ids = [sid for sid in subject_ids if sid not in found_subj_ids]
    if missing_subj_ids:
        ref_subjects = await gd_find(db.session, "reference_subjects", {"id": {"$in": missing_subj_ids}}, limit=len(missing_subj_ids))
        subjects = list(subjects) + list(ref_subjects)

    teacher_map = {t.get("id"): (t.get("full_name") or t.get("full_name_ar") or "") for t in teachers}
    class_map = {c.get("id"): (c.get("name") or c.get("name_ar") or "") for c in classes}
    subject_map = {s.get("id"): (s.get("name_ar") or s.get("name") or "") for s in subjects}

    for session in sessions:
        session["teacher_name"] = teacher_map.get(session.get("teacher_id"), "")
        session["class_name"] = class_map.get(session.get("class_id"), "")
        session["subject_name"] = subject_map.get(session.get("subject_id"), "")

    return {
        "timetable_id": timetable_id,
        "total": len(sessions),
        "sessions": sessions
    }


# --- Get Timetable Conflicts API ---
@router.get("/smart-scheduling/timetable/{timetable_id}/conflicts")
async def smart_get_timetable_conflicts(
    timetable_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على تعارضات الجدول
    Get timetable conflicts
    """
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    conflicts = await smart_scheduling_engine.get_timetable_conflicts(timetable_id)
    
    return {
        "timetable_id": timetable_id,
        "total": len(conflicts),
        "critical_count": len([c for c in conflicts if c.get("severity") == "critical"]),
        "high_count": len([c for c in conflicts if c.get("severity") == "high"]),
        "conflicts": conflicts
    }


# --- Get Run Logs API ---
@router.get("/smart-scheduling/run/{run_id}/logs")
async def smart_get_run_logs(
    run_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على سجلات تشغيل المحرك
    Get scheduling engine run logs
    """
    logs = await smart_scheduling_engine.get_run_logs(run_id)
    
    return {
        "run_id": run_id,
        "total": len(logs),
        "logs": logs
    }


async def _acquire_draft_lifecycle_lock(school_id: str) -> None:
    """Serialize draft creation and publish-state transitions per school."""
    await db.session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"sched_draft_ensure:{school_id}"},
    )


# --- Publish Timetable API ---
@router.post("/smart-scheduling/timetable/{timetable_id}/publish")
async def smart_publish_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    نشر الجدول
    Publish the timetable (makes it visible to teachers and students)
    """
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    school_id = str(timetable.get("school_id"))
    assert_school_access(current_user, school_id)
    await _acquire_draft_lifecycle_lock(school_id)
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable or str(timetable.get("school_id")) != school_id:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    await assert_publishable(
        smart_scheduling_engine,
        school_id=school_id,
        timetable_id=timetable_id,
    )
    success = await smart_scheduling_engine.publish_timetable(
        timetable_id=timetable_id,
        published_by=current_user.get("id", "system")
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="لا يمكن نشر الجدول - يوجد تعارضات حرجة غير محلولة"
        )
    
    # Task #145 — push a lightweight ``schedule_published`` event over the
    # tenant WebSocket bus so any open teacher screen silently refetches
    # within seconds. We swallow failures so a transient WS hiccup never
    # masks a successful publish; the polling fallback still covers it.
    try:
        from src.modules.notifications.controllers.websocket_routes import get_connection_manager
        _published_row = await gd_find_one(db.session, "timetables", {"id": timetable_id}) or {}
        await get_connection_manager().broadcast_to_tenant(
            {
                "type": "schedule_published",
                "timetable_id": timetable_id,
                "school_id": str(timetable.get("school_id")),
                "published_at": _published_row.get("published_at"),
            },
            str(timetable.get("school_id")),
        )
    except Exception as _ws_err:  # noqa: BLE001
        logger.warning("schedule_published WS broadcast failed: %s", _ws_err)

    return {
        "success": True,
        "timetable_id": timetable_id,
        "message_ar": "تم نشر الجدول بنجاح",
        "message_en": "Timetable published successfully"
    }


# --- Task #141 — Lifecycle promote DRAFT → PUBLISHED ─────────────────
# Thin wrapper over ``smart_scheduling_engine.publish_timetable`` that:
#   1. Resolves the latest DRAFT for ``school_id`` if no ``timetable_id``
#      is supplied (the new master-schedule UI always calls with just
#      the school context).
#   2. Runs ``assert_publishable`` so HIGH/CRITICAL constraint
#      violations short-circuit with a structured 409 envelope.
#   3. Delegates the actual UPDATE to ``publish_timetable`` (which
#      archives any prior published row via UPDATE only — no DELETE in
#      production data per replit.md policy).
#   4. Fans out an Arabic announcement to all teachers via the school
#      notification engine.
class PublishScheduleRequest(BaseModel):
    school_id: str = Field(..., min_length=1)
    timetable_id: Optional[str] = None


@router.post("/schedule/publish")
async def publish_schedule(
    payload: PublishScheduleRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN])),
):
    school_id = payload.school_id.strip()
    assert_school_access(current_user, school_id)
    await _acquire_draft_lifecycle_lock(school_id)

    timetable_id = (payload.timetable_id or "").strip() or None
    if not timetable_id:
        # Resolve the most-recently updated DRAFT for this school. The
        # generation endpoint guarantees there is at most one DRAFT row
        # per (school, academic_year, semester) tuple.
        drafts = await gd_find(
            db.session, "timetables",
            {"school_id": school_id, "status": TimetableStatus.DRAFT.value},
            order_by="updated_at", desc_order=True, limit=1,
        )
        if not drafts:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "NO_DRAFT_TO_PUBLISH",
                    "message_ar": "لا توجد مسودة جدول قابلة للنشر.",
                    "message_en": "No draft timetable available to publish.",
                },
            )
        timetable_id = drafts[0].get("id")

    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable or timetable.get("school_id") != school_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "TIMETABLE_NOT_FOUND",
                "message_ar": "الجدول المطلوب غير موجود.",
                "message_en": "Requested timetable not found.",
            },
        )
    if timetable.get("status") != TimetableStatus.DRAFT.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NOT_A_DRAFT",
                "message_ar": "لا يمكن نشر هذا الجدول لأنه ليس مسودة.",
                "message_en": "Only draft timetables can be published.",
            },
        )

    await assert_publishable(
        smart_scheduling_engine,
        school_id=school_id,
        timetable_id=timetable_id,
    )

    # Capture the id of the currently published timetable (if any)
    # *before* we promote, so we can return it to the caller as
    # ``archived_timetable_id``. ``publish_timetable`` archives prior
    # published rows in-place via UPDATE only (no DELETE), per the
    # replit.md production-data policy.
    prior_published = await gd_find(
        db.session, "timetables",
        {"school_id": school_id, "status": TimetableStatus.PUBLISHED.value},
        order_by="updated_at", desc_order=True, limit=1,
    )
    archived_timetable_id = prior_published[0].get("id") if prior_published else None

    success = await smart_scheduling_engine.publish_timetable(
        timetable_id=timetable_id,
        published_by=current_user.get("id", "system"),
    )
    if not success:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PUBLISH_BLOCKED",
                "message_ar": "تعذّر نشر الجدول بسبب تعارضات حرجة غير محلولة.",
                "message_en": "Publish failed due to unresolved critical conflicts.",
            },
        )

    # Fetch the freshly published row so we can echo its
    # ``published_at`` back to the client.
    published_row = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    published_at = (published_row or {}).get("published_at")

    # Fan-out: notify all teachers of the new published timetable. We
    # swallow notification failures so a delivery hiccup never rolls
    # back the publish itself — the audit trail on the timetable row
    # is the source of truth. We track the recipient count so the
    # caller can show "تم إبلاغ N معلماً" toast text.
    notified_count = 0
    try:
        _notif = SchoolNotificationEngine(db)
        _result = await _notif.send_notification(
            request=SendNotificationRequest(
                title_ar="تم نشر جدول جديد",
                title_en="New schedule published",
                message_ar=(
                    "تم نشر جدول الحصص الجديد. "
                    "افتح شاشة جدولي لمراجعة الحصص المسندة إليك."
                ),
                message_en=(
                    "A new class schedule has been published. "
                    "Open your schedule screen to review your assigned periods."
                ),
                recipient_type=RecipientType.all_teachers,
                notification_type=NotificationType.announcement,
                priority=NotificationPriority.high,
                # The frontend reads ``recipient_filter`` from
                # ``extra_data`` to surface the deep-link in the
                # notification card.
                recipient_filter={
                    "kind": "schedule_published",
                    "timetable_id": timetable_id,
                    "link": "/teacher/schedule",
                },
            ),
            tenant_id=school_id,
            sent_by=current_user.get("id", "system"),
        )
        if isinstance(_result, dict):
            notified_count = int(
                _result.get("delivered_count")
                or _result.get("recipient_count")
                or 0
            )
    except Exception as _e:  # noqa: BLE001
        logger.warning("publish notification fan-out failed: %s", _e)

    # Task #145 — fire ``schedule_published`` over the tenant WS bus so
    # any teacher screens currently open refetch within seconds. The DB
    # notification above persists the announcement; this just nudges
    # live clients. Failures are swallowed — the 5-min polling fallback
    # still covers offline/dropped sockets.
    try:
        from src.modules.notifications.controllers.websocket_routes import get_connection_manager
        await get_connection_manager().broadcast_to_tenant(
            {
                "type": "schedule_published",
                "timetable_id": timetable_id,
                "school_id": school_id,
                "published_at": published_at,
            },
            school_id,
        )
    except Exception as _ws_err:  # noqa: BLE001
        logger.warning("schedule_published WS broadcast failed: %s", _ws_err)

    return {
        "ok": True,
        "success": True,
        "timetable_id": timetable_id,
        "school_id": school_id,
        "published_at": published_at,
        "archived_timetable_id": archived_timetable_id,
        "notified_count": notified_count,
        "message_ar": "تم نشر الجدول بنجاح.",
        "message_en": "Timetable published successfully.",
    }


# --- Ensure Editable Draft API ---
class EnsureDraftRequest(BaseModel):
    school_id: Optional[str] = None


@router.post("/schedule/draft/ensure")
async def ensure_editable_draft_route(
    payload: EnsureDraftRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN])),
    x_school_context: Optional[str] = Header(None),
):
    """يضمن وجود مسودة قابلة للتعديل للجدول المدرسي ويعيد معرّفها.

    قاعدة المنتج: المسودة نسخةُ عملٍ قابلة للتعديل من آخر جدول منشور ما لم
    توجد مسودة أحدث. تستدعيها الواجهة مرّة واحدة عندما تعود شبكة المسودة
    فارغة بعد النشر، فتُنشئ الخدمة مسودة بنسخ الجدول المنشور (إن لم توجد
    مسودة). تُعيد ``timetable_id=null`` عندما لا يوجد منشور ولا مسودة.
    """
    school_id = resolve_school_id(current_user, payload.school_id or x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, school_id)

    # The same transaction lock also guards both publish paths and unpublish,
    # so a draft cannot be cloned from state that is changing concurrently.
    await _acquire_draft_lifecycle_lock(school_id)

    timetable_id = await smart_scheduling_engine.ensure_editable_draft(
        school_id=school_id,
        user_id=current_user.get("id", "system"),
    )
    return {
        "ok": True,
        "timetable_id": timetable_id,
        "school_id": school_id,
    }


# --- Unpublish Timetable API ---
class UnpublishTimetableRequest(BaseModel):
    keep_existing_draft: bool = False


@router.post("/smart-scheduling/timetable/{timetable_id}/unpublish")
async def unpublish_timetable(
    timetable_id: str,
    payload: Optional[UnpublishTimetableRequest] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN])),
):
    """
    إلغاء نشر الجدول — يعيده إلى حالة المسودة
    Unpublish a timetable, returning it to draft so it can be edited.
    """
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")

    school_id = str(timetable.get("school_id", ""))
    assert_school_access(current_user, school_id)
    await _acquire_draft_lifecycle_lock(school_id)

    # The first read establishes tenant access only. Re-read after waiting for
    # the school lock so every lifecycle decision below uses current state.
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable or str(timetable.get("school_id", "")) != school_id:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")

    if timetable.get("status") != TimetableStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NOT_PUBLISHED",
                "message_ar": "لا يمكن إلغاء نشر جدول غير منشور.",
                "message_en": "Only published timetables can be unpublished.",
            },
        )

    # مع تفعيل التهيئة التلقائية للمسودة، قد توجد مسودة قابلة للتعديل فعلاً.
    # السماح بإلغاء النشر حينئذٍ ينشئ مسودة ثانية ويكسر ثابت «مسودة واحدة
    # على الأكثر» الذي يعتمد عليه النشر. نرفض ونوجّه المدير لتعديل المسودة.
    existing_drafts = await gd_find(
        db.session, "timetables",
        {"school_id": school_id, "status": TimetableStatus.DRAFT.value},
        limit=1,
    )
    keep_existing_draft = bool(payload and payload.keep_existing_draft)
    if existing_drafts and not keep_existing_draft:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DRAFT_ALREADY_EXISTS",
                "message_ar": "توجد مسودة قابلة للتعديل بالفعل. عدِّل المسودة الحالية بدلاً من إلغاء نشر الجدول.",
                "message_en": "An editable draft already exists. Edit the existing draft instead of unpublishing.",
            },
        )

    now = datetime.now(timezone.utc).isoformat()
    user_id = current_user.get("id", "system")
    retained_draft_id = existing_drafts[0].get("id") if existing_drafts else None
    next_status = (
        TimetableStatus.ARCHIVED.value
        if retained_draft_id
        else TimetableStatus.DRAFT.value
    )
    lifecycle_updates = {
        "status": next_status,
        "is_published": False,
        "updated_by": user_id,
        "updated_at": now,
    }
    await gd_update_one(
        db.session, "timetables", {"id": timetable_id}, lifecycle_updates
    )

    updated = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    return {
        "ok": True,
        "timetable_id": timetable_id,
        "status": (updated or {}).get("status", next_status),
        "editable_draft_id": retained_draft_id or timetable_id,
        "kept_existing_draft": bool(retained_draft_id),
        "message_ar": (
            "تم إلغاء نشر الجدول مع الاحتفاظ بالمسودة الحالية."
            if retained_draft_id
            else "تم إلغاء نشر الجدول وعاد إلى المسودة."
        ),
        "message_en": (
            "Timetable unpublished; the existing editable draft was kept."
            if retained_draft_id
            else "Timetable unpublished and returned to draft."
        ),
    }


# --- Archive Timetable API ---
@router.post("/smart-scheduling/timetable/{timetable_id}/archive")
async def smart_archive_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    أرشفة الجدول
    Archive the timetable
    """
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    success = await smart_scheduling_engine.archive_timetable(
        timetable_id=timetable_id,
        archived_by=current_user.get("id", "system")
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    return {
        "success": True,
        "timetable_id": timetable_id,
        "message_ar": "تم أرشفة الجدول",
        "message_en": "Timetable archived"
    }


# --- Pre-Scheduling Check API ---
@router.get("/smart-scheduling/pre-check/{school_id}")
async def smart_pre_scheduling_check(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    التحقق المسبق من إمكانية الجدولة
    Pre-scheduling feasibility check
    
    يحسب:
    - إجمالي الطلب الأكاديمي
    - إجمالي سعة المعلمين
    - المواد بدون معلمين
    - نسبة الاستخدام المتوقعة
    """
    assert_school_access(current_user, str(school_id))
    # Load settings
    settings = await smart_scheduling_engine.load_school_settings(school_id)
    
    # Build demand and resources
    demands = await smart_scheduling_engine.build_academic_demand(school_id)
    resources = await smart_scheduling_engine.build_resource_availability(school_id, settings)
    
    # Run pre-check
    result = await smart_scheduling_engine.pre_scheduling_check(school_id, demands, resources, settings)
    infeasibility_report = await smart_scheduling_engine.build_infeasibility_report(school_id)

    return {
        "school_id": school_id,
        "can_schedule": result["can_schedule"],
        "warnings": result["warnings"],
        "errors": result["errors"],
        "statistics": result["statistics"],
        "infeasibility_report": infeasibility_report.model_dump(mode="json"),
        "message_ar": "يمكن بدء الجدولة" if result["can_schedule"] else "يوجد مشاكل تمنع الجدولة",
        "message_en": "Ready to schedule" if result["can_schedule"] else "Issues preventing scheduling"
    }


# --- Get Academic Demand Matrix API ---
@router.get("/smart-scheduling/demand-matrix/{school_id}")
async def smart_get_academic_demand(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    الحصول على مصفوفة الطلب الأكاديمي
    Get Academic Demand Matrix (classes with their subjects and periods)
    """
    assert_school_access(current_user, str(school_id))
    demands = await smart_scheduling_engine.build_academic_demand(school_id)
    
    # Enrich with names
    enriched = []
    for demand in demands:
        # Get subjects with names
        subjects_with_names = []
        for subj in demand.subjects:
            subject_doc = await gd_find_one(db.session, "subjects", {"id": subj.get("subject_id")})
            if not subject_doc:
                subject_doc = await gd_find_one(db.session, "reference_subjects", {"id": subj.get("subject_id")})
            
            subjects_with_names.append({
                **subj,
                "subject_name": subject_display_name(subject_doc)
            })
        
        enriched.append({
            "class_id": demand.class_id,
            "class_name": demand.class_name,
            "grade_id": demand.grade_id,
            "subjects": subjects_with_names,
            "total_periods_required": demand.total_periods_required
        })
    
    return {
        "school_id": school_id,
        "total_classes": len(enriched),
        "total_demand_periods": sum(d["total_periods_required"] for d in enriched),
        "demands": enriched
    }


# --- Get Resource Availability Matrix API ---
@router.get("/smart-scheduling/resource-matrix/{school_id}")
async def smart_get_resource_availability(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    الحصول على مصفوفة توافر الموارد
    Get Resource Availability Matrix (teachers with their availability)
    """
    assert_school_access(current_user, str(school_id))
    settings = await smart_scheduling_engine.load_school_settings(school_id)
    resources = await smart_scheduling_engine.build_resource_availability(school_id, settings)
    
    # Convert to serializable format
    resources_data = []
    for r in resources:
        resources_data.append({
            "teacher_id": r.teacher_id,
            "teacher_name": r.teacher_name,
            "subject_ids": r.subject_ids,
            "weekly_load": r.weekly_load,
            "current_load": r.current_load,
            "availability": r.availability
        })
    
    return {
        "school_id": school_id,
        "total_teachers": len(resources_data),
        "total_capacity": sum(r["weekly_load"] for r in resources_data),
        "resources": resources_data
    }


# --- Delete Timetable API ---
@router.delete("/smart-scheduling/timetable/{timetable_id}")
async def smart_delete_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    حذف الجدول
    Delete timetable and all its sessions
    """
    # Get timetable first
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    
    # Don't delete published timetables
    if timetable.get("status") == TimetableStatus.PUBLISHED.value:
        raise HTTPException(status_code=400, detail="لا يمكن حذف جدول منشور - قم بأرشفته أولاً")
    
    # Delete sessions
    await gd_delete_many(db.session, "timetable_sessions", {"timetable_id": timetable_id})
    
    # Delete conflicts
    await gd_delete_many(db.session, "timetable_conflicts", {"timetable_id": timetable_id})
    
    # Delete unscheduled demands
    await gd_delete_many(db.session, "timetable_unscheduled_demands", {"timetable_id": timetable_id})
    
    # Delete timetable
    await gd_delete_one(db.session, "timetables", {"id": timetable_id})
    
    return {
        "success": True,
        "message_ar": "تم حذف الجدول بنجاح",
        "message_en": "Timetable deleted successfully"
    }





