"""IT-only workspace settings (Task #189 §5.2)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from src.core.guards.tenant_guard import (
    INDEPENDENT_TEACHER_DENIED_AR,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import db, get_current_user
from engines.sql_utils import gd_find_one, gd_update_one, gd_upsert
from src.common.utils.avatar_image import normalize_image_field_or_400

logger = logging.getLogger("nassaq.it_workspace_settings")

from src.common.utils.avatar_serving import signed_image_url, is_internal_image_url

router = APIRouter()

_MSG_DISALLOWED_FIELD = "لا تملك صلاحية تعديل هذا الحقل."
_MSG_NAME_REQUIRED = "اسم المساحة باللغة العربية مطلوب."
_MSG_PERIODS_INVALID = "عدد الحصص اليومي يجب أن يكون بين ١ و١٢."
_MSG_PERIOD_MINUTES_INVALID = "مدة الحصة يجب أن تكون بين ١٠ و١٢٠ دقيقة."
_MSG_WORKING_DAYS_INVALID = "اختر يومًا واحدًا على الأقل ضمن أيام العمل."
_MSG_DAY_START_INVALID = "وقت بداية اليوم الدراسي يجب أن يكون بصيغة صحيحة (HH:MM)."
_MSG_INTERNAL = "تعذّر حفظ إعدادات مساحتك. حاول مرة أخرى لاحقًا."

_DEFAULT_DAY_START = "07:00"

_ALLOWED_FIELDS = frozenset({
    "name_ar",
    "name_en",
    "logo_url",
    "working_days",
    "periods_per_day",
    "period_minutes",
    "period_duration",
    "school_day_start",
    "timezone",
    "academic_year_label",
    "academic_term_label",
})

_VALID_WEEKDAYS = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_day_start(value: Any) -> str:
    """Validate/normalise an ``HH:MM`` day-start string → zero-padded form.

    Raises ``HTTPException(400)`` when the value is not a parseable 24h time.
    """
    if not isinstance(value, str) or ":" not in value:
        raise HTTPException(status_code=400, detail=_MSG_DAY_START_INVALID)
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail=_MSG_DAY_START_INVALID)
    try:
        hh = int(parts[0])
        mm = int(parts[1])
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=_MSG_DAY_START_INVALID)
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise HTTPException(status_code=400, detail=_MSG_DAY_START_INVALID)
    return f"{hh:02d}:{mm:02d}"


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(
            status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR,
        )
    return current_user


def _validate_payload_keys(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail=_MSG_DISALLOWED_FIELD)
    for key in payload.keys():
        if key not in _ALLOWED_FIELDS:
            raise HTTPException(status_code=403, detail=_MSG_DISALLOWED_FIELD)


def _validate_field_values(payload: Dict[str, Any]) -> None:
    if "period_duration" in payload and "period_minutes" not in payload:
        payload["period_minutes"] = payload.pop("period_duration")
    elif "period_duration" in payload:
        payload.pop("period_duration")

    if "name_ar" in payload:
        v = payload["name_ar"]
        if not isinstance(v, str) or not v.strip():
            raise HTTPException(status_code=400, detail=_MSG_NAME_REQUIRED)
    if "name_en" in payload and payload["name_en"] is not None:
        if not isinstance(payload["name_en"], str):
            raise HTTPException(status_code=400, detail=_MSG_DISALLOWED_FIELD)
    if "logo_url" in payload and payload["logo_url"] is not None:
        if not isinstance(payload["logo_url"], str):
            raise HTTPException(status_code=400, detail=_MSG_DISALLOWED_FIELD)
    if "working_days" in payload:
        v = payload["working_days"]
        if not isinstance(v, list) or not v:
            raise HTTPException(status_code=400, detail=_MSG_WORKING_DAYS_INVALID)
        cleaned = [str(d).strip().lower() for d in v if d]
        if not cleaned or any(d not in _VALID_WEEKDAYS for d in cleaned):
            raise HTTPException(status_code=400, detail=_MSG_WORKING_DAYS_INVALID)
        payload["working_days"] = cleaned
    if "periods_per_day" in payload:
        try:
            n = int(payload["periods_per_day"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=_MSG_PERIODS_INVALID)
        if n < 1 or n > 12:
            raise HTTPException(status_code=400, detail=_MSG_PERIODS_INVALID)
        payload["periods_per_day"] = n
    if "period_minutes" in payload:
        try:
            m = int(payload["period_minutes"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=_MSG_PERIOD_MINUTES_INVALID)
        if m < 10 or m > 120:
            raise HTTPException(status_code=400, detail=_MSG_PERIOD_MINUTES_INVALID)
        payload["period_minutes"] = m
    if "school_day_start" in payload:
        payload["school_day_start"] = _normalise_day_start(payload["school_day_start"])
    if "timezone" in payload and payload["timezone"] is not None:
        if not isinstance(payload["timezone"], str) or len(payload["timezone"]) > 64:
            raise HTTPException(status_code=400, detail=_MSG_DISALLOWED_FIELD)
    for k in ("academic_year_label", "academic_term_label"):
        if k in payload and payload[k] is not None:
            v = payload[k]
            if not isinstance(v, str) or not v.strip() or len(v) > 64:
                raise HTTPException(status_code=400, detail=_MSG_DISALLOWED_FIELD)


def _normalise_working_days(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(d).strip().lower() for d in value if d]
    if isinstance(value, dict):
        return [k for k, on in value.items() if on]
    return []


@router.get("/independent-teacher/workspace/settings")
async def get_workspace_settings(
    current_user: dict = Depends(_require_independent_teacher),
):
    school_id = require_request_school_id(current_user)

    school = await gd_find_one(db.session, "schools", {"id": school_id}) or {}
    settings = await gd_find_one(
        db.session, "school_settings", {"school_id": school_id}
    ) or {}
    custom = settings.get("custom_settings") or {}

    year = await gd_find_one(
        db.session, "academic_years",
        {"school_id": school_id, "is_current": True},
    )
    term = await gd_find_one(
        db.session, "academic_terms",
        {"school_id": school_id, "is_current": True},
    )

    return {
        "workspace_id": school_id,
        "name_ar": school.get("name") or "",
        "name_en": school.get("name_en") or "",
        "logo_url": signed_image_url("logo", school_id, school.get("logo_url")) or "",
        "working_days": _normalise_working_days(settings.get("working_days")),
        "periods_per_day": settings.get("periods_per_day") or 7,
        "period_minutes": settings.get("period_duration") or 45,
        "school_day_start": (custom.get("school_day_start") if isinstance(custom, dict) else None)
                            or _DEFAULT_DAY_START,
        "timezone": (custom.get("timezone") if isinstance(custom, dict) else None)
                    or "Asia/Riyadh",
        "academic_year_label": (year or {}).get("name") or "",
        "academic_term_label": (term or {}).get("name") or "",
        "academic_year_id": (year or {}).get("id"),
        "academic_term_id": (term or {}).get("id"),
    }


@router.put("/independent-teacher/workspace/settings")
async def update_workspace_settings(
    payload: Dict[str, Any],
    current_user: dict = Depends(_require_independent_teacher),
):
    _validate_payload_keys(payload)
    if not payload:
        return await get_workspace_settings(current_user=current_user)

    _validate_field_values(payload)

    school_id = require_request_school_id(current_user)
    now_iso = _utcnow_iso()

    school_update: Dict[str, Any] = {}
    if "name_ar" in payload:
        school_update["name"] = payload["name_ar"].strip()
    if "name_en" in payload:
        school_update["name_en"] = (payload["name_en"] or None)
    if "logo_url" in payload and not is_internal_image_url(payload["logo_url"]):
        school_update["logo_url"] = await normalize_image_field_or_400(
            payload["logo_url"] or None
        )
    if school_update:
        school_update["updated_at"] = now_iso
        await gd_update_one(
            db.session, "schools", {"id": school_id}, school_update
        )

    settings_update: Dict[str, Any] = {}
    if "working_days" in payload:
        settings_update["working_days"] = payload["working_days"]
    if "periods_per_day" in payload:
        settings_update["periods_per_day"] = payload["periods_per_day"]
    if "period_minutes" in payload:
        settings_update["period_duration"] = payload["period_minutes"]
    if "timezone" in payload or "school_day_start" in payload:
        existing = await gd_find_one(
            db.session, "school_settings", {"school_id": school_id}
        ) or {}
        cs = dict(existing.get("custom_settings") or {})
        if "timezone" in payload:
            cs["timezone"] = payload["timezone"]
        if "school_day_start" in payload:
            cs["school_day_start"] = payload["school_day_start"]
        settings_update["custom_settings"] = cs
    if settings_update:
        settings_update["updated_at"] = now_iso
        await gd_upsert(
            db.session, "school_settings",
            {"school_id": school_id}, settings_update,
        )

    if "academic_year_label" in payload and payload["academic_year_label"]:
        await gd_update_one(
            db.session, "academic_years",
            {"school_id": school_id, "is_current": True},
            {"name": payload["academic_year_label"].strip(),
             "updated_at": now_iso},
        )
    if "academic_term_label" in payload and payload["academic_term_label"]:
        await gd_update_one(
            db.session, "academic_terms",
            {"school_id": school_id, "is_current": True},
            {"name": payload["academic_term_label"].strip(),
             "updated_at": now_iso},
        )

    try:
        await db.session.commit()
    except Exception as exc:
        await db.session.rollback()
        logger.exception("IT workspace settings update failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    return await get_workspace_settings(current_user=current_user)


__all__ = ["router"]
