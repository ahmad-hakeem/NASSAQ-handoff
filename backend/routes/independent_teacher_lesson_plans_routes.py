"""IT Phase 2 §6.4 — Light AI lesson-planning assistant (Task #209).

Three IT-only endpoints, workspace-pinned, NO MFA step-up
(low-sensitivity content generation):

  * ``POST   /independent-teacher/lesson-plans/generate``
      Calls the OpenAI integration with the IT's prompt fields, parses
      the model's JSON response, and returns the parsed plan + a fresh
      ``lesson_plans`` row with ``is_saved=False``. The daily counter
      on ``workspace_quota`` is bumped on every successful generation.

  * ``GET    /independent-teacher/lesson-plans``
      Lists the IT's own saved plans in their workspace, newest first.

  * ``POST   /independent-teacher/lesson-plans/{plan_id}/save-to-class``
      Marks a previously-generated row ``is_saved=True`` and pins it to
      one of the IT's own classes (cross-workspace plan_id OR class_id
      → 404 per spec §8 inv. 3).

Cross-workspace ids on the read/save paths return **404** so the API
does not confirm the existence of foreign-tenant rows. The route never
trusts ``workspace_school_id`` / ``tenant_id`` / ``created_by`` from
the request body — all three are pinned server-side.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import db, get_current_user
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from middleware.rate_limiter import rate_store
from quotas.independent_teacher import MAX_LESSON_PLANS_PER_DAY
from routes.ai_routes_mod import AI_NOT_CONFIGURED_RESPONSE, get_openai_client


logger = logging.getLogger("nassaq.it_lesson_plans")

router = APIRouter(
    prefix="/independent-teacher/lesson-plans",
    tags=["IT Lesson Plans"],
)


# -- Safe Arabic copy ----------------------------------------------------

_MSG_NOT_FOUND = "خطة الدرس غير موجودة"
_MSG_TOPIC_REQUIRED = "موضوع الدرس مطلوب"
_MSG_INTERNAL = "تعذّر توليد خطة الدرس — حاول لاحقًا"
_MSG_QUOTA_DAILY = "بلغت الحد اليومي لتوليد خطط الدروس. حاول مرة أخرى غدًا."
_MSG_RATE_LIMITED = "طلبات متكررة بسرعة كبيرة لتوليد خطط الدروس. يرجى الانتظار قليلًا قبل المحاولة مجددًا."

# Short-window burst limits (Task #221) — per workspace, in addition to
# the daily quota. Mirrors the parent-invitation accept route's use of
# the in-memory ``rate_store``.
_BURST_SHORT_MAX = 1
_BURST_SHORT_WINDOW = 10  # seconds
_BURST_LONG_MAX = 3
_BURST_LONG_WINDOW = 60  # seconds
_MSG_CLASS_NOT_FOUND = "الفصل غير موجود في مساحتك"
_MSG_AI_PARSE = "تعذّر تحليل ردّ الذكاء الاصطناعي — حاول مرة أخرى"

_MODEL = os.environ.get("AI_LESSON_PLAN_MODEL", "gpt-5-mini")

# Foreign-id keys that must be stripped from the LLM payload before we
# return / persist it. Spec §6.4: the assistant content lives in JSONB
# and must NEVER smuggle student/class/parent ids back into the FE — IT
# users have no need for them and a tampered prompt could try to leak
# unrelated workspace ids.
_FORBIDDEN_KEYS = {
    "student_id", "students", "student_ids",
    "class_id", "classroom_id",
    "parent_id", "parents", "parent_ids",
    "tenant_id", "school_id", "workspace_school_id",
    "user_id", "teacher_id", "created_by",
}


# -- Models --------------------------------------------------------------


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    subject: Optional[str] = Field(default=None, max_length=200)
    grade_level: Optional[str] = Field(default=None, max_length=200)
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=600)
    objectives: Optional[str] = Field(default=None, max_length=2000)
    language: str = Field(default="ar", max_length=8)

    @field_validator("topic", "subject", "grade_level", "objectives", "language")
    @classmethod
    def _strip(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("language")
    @classmethod
    def _lang(cls, v):
        v = (v or "ar").strip().lower()
        return v if v in {"ar", "en"} else "ar"


class SaveToClassRequest(BaseModel):
    class_id: str = Field(min_length=1, max_length=64)


class UpdateLessonPlanRequest(BaseModel):
    """Partial-update payload. Every field is optional; only the keys
    explicitly provided by the caller are written. ``plan`` (the JSONB
    body) is scrubbed of foreign id keys before persistence — same rule
    as the LLM payload on the generate path.
    """
    topic: Optional[str] = Field(default=None, max_length=500)
    subject: Optional[str] = Field(default=None, max_length=200)
    grade_level: Optional[str] = Field(default=None, max_length=200)
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=600)
    language: Optional[str] = Field(default=None, max_length=8)
    plan: Optional[Dict[str, Any]] = None

    @field_validator("topic", "subject", "grade_level", "language")
    @classmethod
    def _strip(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("language")
    @classmethod
    def _lang(cls, v):
        if v is None:
            return None
        v = v.strip().lower()
        return v if v in {"ar", "en"} else "ar"


# -- Gates ---------------------------------------------------------------


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


def _workspace_id(current_user: dict) -> str:
    return independent_workspace_id(current_user) or require_request_school_id(current_user)


# -- Quota helpers (mirrors §6.1 imports_today pattern) -----------------


async def _load_quota(workspace_id: str) -> Dict[str, Any]:
    row = await gd_find_one(
        db.session, "workspace_quota", {"workspace_school_id": workspace_id},
    )
    if row:
        return row
    now_iso = datetime.now(timezone.utc).isoformat()
    seed = {
        "workspace_school_id": workspace_id,
        "max_students": 200,
        "max_classes": 5,
        "max_imports_per_day": 5,
        "max_rows_per_import": 200,
        "imports_today": 0,
        "imports_today_date": None,
        "lesson_plans_today": 0,
        "lesson_plans_today_date": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    try:
        await gd_insert(db.session, "workspace_quota", seed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("workspace_quota lazy seed failed for %s: %s", workspace_id, exc)
    return seed


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _coerce_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _lesson_plans_today(quota: Dict[str, Any]) -> int:
    last = _coerce_date(quota.get("lesson_plans_today_date"))
    if last != _today_utc():
        return 0
    return int(quota.get("lesson_plans_today") or 0)


# -- LLM payload sanitisation -------------------------------------------


def _strip_foreign_ids(value: Any) -> Any:
    """Recursively scrub forbidden id-like keys from the LLM payload."""
    if isinstance(value, dict):
        return {
            k: _strip_foreign_ids(v)
            for k, v in value.items()
            if str(k).strip().lower() not in _FORBIDDEN_KEYS
        }
    if isinstance(value, list):
        return [_strip_foreign_ids(item) for item in value]
    return value


def _coerce_plan_payload(raw_text: str) -> Dict[str, Any]:
    """Parse the LLM response into a JSON dict. Falls back to wrapping
    free-text into {"summary": <text>} so we never raise on a model
    that ignored the JSON instruction — we still want the IT to see the
    output and the row to be persisted.
    """
    if not raw_text:
        return {"summary": ""}
    text = raw_text.strip()
    # Strip ```json fences if the model wrapped them.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            parsed = {"content": parsed}
    except (json.JSONDecodeError, ValueError):
        parsed = {"summary": raw_text.strip()}
    return _strip_foreign_ids(parsed)


def _build_prompt(req: GenerateRequest) -> str:
    parts = [
        "أنت مساعد تعليمي يساعد المعلم المستقل في إعداد خطة درس قصيرة وعملية.",
        "اكتب الردّ بصيغة JSON صالح فقط وبدون أي نصّ إضافي حول الـ JSON.",
        "هيكل الردّ المطلوب:",
        '{',
        '  "title": "عنوان الدرس",',
        '  "objectives": ["هدف 1", "هدف 2"],',
        '  "warmup": "نشاط افتتاحي قصير",',
        '  "activities": [{"name": "...", "duration_minutes": 0, "description": "..."}],',
        '  "assessment": "كيفية تقييم الفهم",',
        '  "homework": "واجب اختياري",',
        '  "materials": ["..."]',
        '}',
        "",
        f"الموضوع: {req.topic}",
    ]
    if req.subject:
        parts.append(f"المادة: {req.subject}")
    if req.grade_level:
        parts.append(f"الصف: {req.grade_level}")
    if req.duration_minutes:
        parts.append(f"المدة المتاحة: {req.duration_minutes} دقيقة")
    if req.objectives:
        parts.append(f"أهداف اقترحها المعلم: {req.objectives}")
    parts.append(
        "اللغة: " + ("العربية" if req.language == "ar" else "الإنجليزية") + "."
    )
    return "\n".join(parts)


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    if not row:
        return {}
    out = {
        "id": row.get("id"),
        "subject": row.get("subject"),
        "grade_level": row.get("grade_level"),
        "topic": row.get("topic"),
        "duration_minutes": row.get("duration_minutes"),
        "language": row.get("language") or "ar",
        "plan": row.get("plan") or {},
        "class_id": row.get("class_id"),
        "is_saved": bool(row.get("is_saved")),
    }
    for k in ("created_at", "updated_at"):
        v = row.get(k)
        if v is not None:
            out[k] = v if isinstance(v, str) else v.isoformat()
    return out


# -- Endpoints -----------------------------------------------------------


@router.post("/generate")
async def generate_lesson_plan(
    payload: GenerateRequest,
    current_user: dict = Depends(_require_independent_teacher),
):
    if not payload.topic:
        raise HTTPException(status_code=422, detail=_MSG_TOPIC_REQUIRED)

    workspace_id = _workspace_id(current_user)

    # Short-window burst guard (Task #221). Keyed per workspace so a
    # stolen IT token cannot drain the daily quota in seconds and spike
    # OpenAI cost/latency for the rest of the platform. Two windows are
    # checked: 1 req / 10s and 3 req / 60s. The longer window is checked
    # first so its retry-after dominates when both fire.
    for max_req, window in (
        (_BURST_LONG_MAX, _BURST_LONG_WINDOW),
        (_BURST_SHORT_MAX, _BURST_SHORT_WINDOW),
    ):
        limited, _, retry_after = await rate_store.is_rate_limited(
            f"it_lesson_plan_generate:{workspace_id}:{window}",
            max_req,
            window,
        )
        if limited:
            raise HTTPException(
                status_code=429,
                detail=_MSG_RATE_LIMITED,
                headers={"Retry-After": str(retry_after)},
            )

    quota = await _load_quota(workspace_id)
    used_today = _lesson_plans_today(quota)
    if used_today >= MAX_LESSON_PLANS_PER_DAY:
        raise HTTPException(status_code=429, detail=_MSG_QUOTA_DAILY)

    client = get_openai_client()
    if client is None:
        return JSONResponse(status_code=503, content=AI_NOT_CONFIGURED_RESPONSE)

    user_prompt = _build_prompt(payload)
    raw_text = ""
    try:
        completion = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise lesson-planning assistant. "
                        "Always respond with a single JSON object. No prose."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=900,
            reasoning_effort="minimal",
        )
        raw_text = (
            (completion.choices[0].message.content if completion and completion.choices else "")
            or ""
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("lesson plan generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=_MSG_INTERNAL)

    plan = _coerce_plan_payload(raw_text)

    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()),
        "workspace_school_id": workspace_id,
        "created_by": current_user["id"],
        "subject": payload.subject,
        "grade_level": payload.grade_level,
        "topic": payload.topic,
        "duration_minutes": payload.duration_minutes,
        "language": payload.language or "ar",
        "prompt": user_prompt,
        "plan": plan,
        "class_id": None,
        "is_saved": False,
        "created_at": now,
        "updated_at": now,
    }
    await gd_insert(db.session, "lesson_plans", doc)

    today = _today_utc()
    new_count = _lesson_plans_today(quota) + 1
    await gd_update_one(
        db.session,
        "workspace_quota",
        {"workspace_school_id": workspace_id},
        {
            "lesson_plans_today": new_count,
            "lesson_plans_today_date": today.isoformat(),
            "updated_at": now.isoformat(),
        },
    )

    # Task #249 — surface the completion in the IT inbox so the user
    # sees a persistent record (and can deep-link to the saved plan).
    # In-app channel is non-suppressible; suppression is only for email.
    try:
        from routes.notification_routes_mod import create_notification_internal
        from routes.independent_teacher_notifications_routes import should_send_channel
        if await should_send_channel(current_user, "lesson_plan", "in_app"):
            topic_label = (payload.topic or "").strip() or "—"
            await create_notification_internal(
                title="اكتملت خطة الدرس",
                message=f"تم إنشاء خطة الدرس: {topic_label}.",
                title_en="Lesson plan ready",
                message_en=f"Lesson plan generated: {topic_label}.",
                recipient_id=current_user["id"],
                notification_type="lesson_plan_complete",
                priority="low",
                related_entity="lesson_plan",
                related_entity_id=doc["id"],
                school_id=workspace_id,
                category="lesson_plan",
                cta_url="/teacher/lesson-planner",
                extra_data={"lesson_plan_id": doc["id"]},
            )
        # Quota near-limit warning at 80% so the user sees a heads-up
        # instead of a hard 429 next time.
        if MAX_LESSON_PLANS_PER_DAY and new_count >= int(MAX_LESSON_PLANS_PER_DAY * 0.8) \
                and new_count < MAX_LESSON_PLANS_PER_DAY \
                and await should_send_channel(current_user, "quota", "in_app"):
            await create_notification_internal(
                title="اقتراب الحد اليومي لخطط الدروس",
                message=f"استخدمت {new_count} من {MAX_LESSON_PLANS_PER_DAY} خططًا اليوم.",
                title_en="Daily lesson-plan quota nearly reached",
                message_en=f"Used {new_count} of {MAX_LESSON_PLANS_PER_DAY} lesson plans today.",
                recipient_id=current_user["id"],
                notification_type="quota_warning",
                priority="medium",
                school_id=workspace_id,
                category="quota",
                cta_url="/teacher/lesson-planner",
                extra_data={"used_today": new_count, "max_per_day": MAX_LESSON_PLANS_PER_DAY},
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("lesson plan inbox notify failed: %s", exc)

    return {
        "lesson_plan": _serialize(doc),
        "quota": {
            "max_per_day": MAX_LESSON_PLANS_PER_DAY,
            "used_today": new_count,
        },
    }


@router.get("")
async def list_lesson_plans(
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)
    rows = await gd_find(
        db.session,
        "lesson_plans",
        {
            "workspace_school_id": workspace_id,
            "created_by": current_user["id"],
            "is_saved": True,
        },
        order_by="created_at",
        desc_order=True,
    )
    quota = await _load_quota(workspace_id)
    return {
        "lesson_plans": [_serialize(r) for r in (rows or [])],
        "quota": {
            "max_per_day": MAX_LESSON_PLANS_PER_DAY,
            "used_today": _lesson_plans_today(quota),
        },
    }


@router.post("/{plan_id}/save-to-class")
async def save_to_class(
    plan_id: str,
    payload: SaveToClassRequest,
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)

    # Cross-workspace plan_id → 404 (spec §8 inv. 3). We pin
    # workspace_school_id AND created_by so another IT in another
    # workspace cannot probe row existence.
    row = await gd_find_one(db.session, "lesson_plans", {
        "id": plan_id,
        "workspace_school_id": workspace_id,
        "created_by": current_user["id"],
    })
    if not row:
        raise HTTPException(status_code=404, detail=_MSG_NOT_FOUND)

    # Class must live in the same workspace; otherwise → 404 (never 403)
    # so a foreign class id is indistinguishable from an unknown one.
    klass = await gd_find_one(db.session, "classes", {
        "id": payload.class_id,
        "school_id": workspace_id,
    })
    if not klass:
        raise HTTPException(status_code=404, detail=_MSG_CLASS_NOT_FOUND)

    now = datetime.now(timezone.utc)
    await gd_update_one(
        db.session,
        "lesson_plans",
        {
            "id": plan_id,
            "workspace_school_id": workspace_id,
            "created_by": current_user["id"],
        },
        {
            "is_saved": True,
            "class_id": payload.class_id,
            "updated_at": now,
        },
    )
    refreshed = await gd_find_one(db.session, "lesson_plans", {"id": plan_id}) or row
    return {"lesson_plan": _serialize(refreshed)}


@router.put("/{plan_id}")
async def update_lesson_plan(
    plan_id: str,
    payload: UpdateLessonPlanRequest,
    current_user: dict = Depends(_require_independent_teacher),
):
    """Edit/rename a saved or draft lesson plan (Task #220).

    Pins ``workspace_school_id == itw_{user_id}`` + ``created_by ==
    current_user.id``; cross-workspace ``plan_id`` → 404 per spec §8
    inv. 3. ``plan`` is recursively scrubbed of foreign id keys, same
    rule as the LLM-generate path.
    """
    workspace_id = _workspace_id(current_user)
    row = await gd_find_one(db.session, "lesson_plans", {
        "id": plan_id,
        "workspace_school_id": workspace_id,
        "created_by": current_user["id"],
    })
    if not row:
        raise HTTPException(status_code=404, detail=_MSG_NOT_FOUND)

    data = payload.model_dump(exclude_unset=True)
    updates: Dict[str, Any] = {}
    for key in ("topic", "subject", "grade_level", "duration_minutes", "language"):
        if key in data:
            updates[key] = data[key]
    if "plan" in data:
        plan_val = data["plan"]
        if plan_val is None:
            updates["plan"] = {}
        elif isinstance(plan_val, dict):
            updates["plan"] = _strip_foreign_ids(plan_val)
        else:
            raise HTTPException(status_code=422, detail=_MSG_NOT_FOUND)

    if "topic" in updates and not (updates["topic"] or "").strip():
        raise HTTPException(status_code=422, detail=_MSG_TOPIC_REQUIRED)

    if not updates:
        return {"lesson_plan": _serialize(row)}

    updates["updated_at"] = datetime.now(timezone.utc)
    await gd_update_one(
        db.session,
        "lesson_plans",
        {
            "id": plan_id,
            "workspace_school_id": workspace_id,
            "created_by": current_user["id"],
        },
        updates,
    )
    refreshed = await gd_find_one(db.session, "lesson_plans", {"id": plan_id}) or row
    return {"lesson_plan": _serialize(refreshed)}


@router.delete("/{plan_id}")
async def delete_lesson_plan(
    plan_id: str,
    current_user: dict = Depends(_require_independent_teacher),
):
    """Delete a lesson plan owned by the calling IT (Task #220).

    Cross-workspace ``plan_id`` → 404 per spec §8 inv. 3.
    """
    workspace_id = _workspace_id(current_user)
    row = await gd_find_one(db.session, "lesson_plans", {
        "id": plan_id,
        "workspace_school_id": workspace_id,
        "created_by": current_user["id"],
    })
    if not row:
        raise HTTPException(status_code=404, detail=_MSG_NOT_FOUND)

    from engines.sql_utils import gd_delete_one
    await gd_delete_one(
        db.session,
        "lesson_plans",
        {
            "id": plan_id,
            "workspace_school_id": workspace_id,
            "created_by": current_user["id"],
        },
    )
    return {"ok": True, "id": plan_id}


__all__ = ["router"]
