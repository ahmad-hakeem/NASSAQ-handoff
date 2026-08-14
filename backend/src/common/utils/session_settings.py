"""Shared sanitizers for the session_settings template.

The session_settings GenericDocument collection stores the durable
"lesson pattern" template keyed by {class_id, subject_id, tenant_id}.
It is written from TWO surfaces that must never drift apart:

  * POST /session/{session_id}/settings   (live lesson — role_dashboards_mod)
  * POST /class/{class_id}/session-settings (فصولي → سجل الطلاب —
    scheduling_smart_session_routes, class_teaching_router)

Both routes funnel every user-controlled field through the helpers in
this module so validation stays identical. Session-scoped fields
(correct_answer_weight / streak_bonus_value, stored on class_sessions)
are deliberately NOT handled here — they exist only on the live-lesson
route.

All sanitizers are tolerant (drop/clamp invalid entries) to match the
long-standing behavior of the lesson route's extra_columns handling.
The single hard 422 is the participation-score-over-tenant-max check,
which predates this module and returns a safe Arabic message.
"""
from datetime import datetime
import logging

from fastapi import HTTPException

logger = logging.getLogger("nassaq.session_settings")

# The five custom element-definition fields shared by the lesson dialog
# and the class-page dialog (تعريفات العناصر group).
CUSTOM_ELEMENT_FIELDS = (
    "custom_positive_behaviours",
    "custom_negative_behaviours",
    "custom_skills",
    "custom_evaluation_items",
    "behaviour_score_overrides",
)

_MAX_ITEMS = 50
_MAX_NAME_LEN = 100
_VALID_PARTICIPATION_TYPES = {"active", "initiative", "inactive", "refused"}


def sanitize_homework_view_mode(value):
    return value if value in ("not_submitted", "submitted") else "not_submitted"


def sanitize_recitation_attempts(value):
    try:
        attempts = int(value or 1)
    except (TypeError, ValueError):
        attempts = 1
    return max(1, min(3, attempts))


def sanitize_extra_columns(raw_cols):
    """Legacy extra_columns blob — kept byte-for-byte compatible with the
    historical inline sanitation in the lesson route."""
    extra_columns = []
    if isinstance(raw_cols, list):
        for c in raw_cols:
            if not isinstance(c, dict):
                continue
            extra_columns.append({
                "id": str(c.get("id") or f"col_{int(datetime.utcnow().timestamp() * 1000)}"),
                "name": str(c.get("name") or "")[:_MAX_NAME_LEN],
                "type": c.get("type") if c.get("type") in ("grade", "check", "text") else "grade",
                "maxGrade": int(c.get("maxGrade") or 0),
                "group": c.get("group") if c.get("group") in ("coursework", "exams") else "coursework",
                "hidden": bool(c.get("hidden", False)),
            })
    return extra_columns


async def load_tenant_participation_max(db_session, tenant_id, gd_find_one):
    """Tenant-configured participation max (falls back to 100)."""
    setting = None
    if tenant_id:
        try:
            setting = await gd_find_one(
                db_session, "tenant_settings",
                {"tenant_id": tenant_id, "setting_key": "participation_max"}
            )
        except Exception as exc:
            logger.warning(
                "session_settings: failed to load participation_max for tenant=%s: %s",
                tenant_id, exc
            )
    if setting and isinstance(setting.get("value"), (int, float)):
        return int(setting["value"])
    if not setting and tenant_id:
        logger.warning(
            "session_settings: no participation_max configured for tenant=%s — falling back to 100",
            tenant_id
        )
    return 100


def sanitize_participation_scores(raw_scores, tenant_participation_max):
    participation_scores = {}
    if isinstance(raw_scores, dict):
        for k, v in raw_scores.items():
            if k not in _VALID_PARTICIPATION_TYPES:
                continue
            try:
                iv = int(v)
            except (TypeError, ValueError):
                continue
            if iv < 1:
                continue
            if iv > tenant_participation_max:
                raise HTTPException(
                    status_code=422,
                    detail=f"قيمة المشاركة ({iv}) تتجاوز الحد الأقصى المسموح به للمدرسة ({tenant_participation_max})"
                )
            participation_scores[k] = iv
    return participation_scores


def _sanitize_behaviour_list(raw, *, positive, id_prefix):
    """Custom behaviours: list of {id, name, points} dicts (legacy plain
    strings are migrated). Points keep the sign convention of their list:
    positive list → +1..+100, negative list → -100..-1."""
    if not isinstance(raw, list):
        return []
    out = []
    for i, item in enumerate(raw[:_MAX_ITEMS]):
        if isinstance(item, str):
            name = item.strip()[:_MAX_NAME_LEN]
            if not name:
                continue
            out.append({
                "id": f"{id_prefix}_{i}_{name}"[:120],
                "name": name,
                "points": 2 if positive else -2,
            })
            continue
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:_MAX_NAME_LEN]
        if not name:
            continue
        try:
            mag = abs(int(item.get("points") or 0))
        except (TypeError, ValueError):
            mag = 0
        mag = max(1, min(100, mag or (2 if positive else 2)))
        out.append({
            "id": str(item.get("id") or f"{id_prefix}_{i}_{name}")[:120],
            "name": name,
            "points": mag if positive else -mag,
        })
    return out


def _sanitize_custom_skills(raw):
    """Custom skills: entries may be plain strings (name only) or
    {name, points} dicts — the frontend uses both shapes. Preserve the
    shape so round-trips are lossless."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:_MAX_ITEMS]:
        if isinstance(item, str):
            name = item.strip()[:_MAX_NAME_LEN]
            if name:
                out.append(name)
            continue
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:_MAX_NAME_LEN]
        if not name:
            continue
        entry = {"name": name}
        try:
            pts = int(item.get("points"))
            if 1 <= pts <= 100:
                entry["points"] = pts
        except (TypeError, ValueError):
            pass
        out.append(entry)
    return out


def _sanitize_evaluation_items(raw):
    """Custom evaluation items: {id, name, color, icon, points} objects as
    produced by the SidebarSettingsDialog evaluation tab."""
    if not isinstance(raw, list):
        return []
    out = []
    for i, item in enumerate(raw[:_MAX_ITEMS]):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:_MAX_NAME_LEN]
        if not name:
            continue
        try:
            pts = int(item.get("points") or 0)
        except (TypeError, ValueError):
            pts = 0
        pts = max(-100, min(100, pts))
        out.append({
            "id": str(item.get("id") or f"eval_{i}_{name}")[:120],
            "name": name,
            "color": str(item.get("color") or "gray")[:30],
            "icon": str(item.get("icon") or "Star")[:50],
            "points": pts,
        })
    return out


def _sanitize_behaviour_overrides(raw):
    """Built-in behaviour score overrides: {behaviour_id: magnitude 1–100}."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in list(raw.items())[:_MAX_ITEMS]:
        key = str(k)[:120]
        try:
            mag = int(v)
        except (TypeError, ValueError):
            continue
        if 1 <= mag <= 100:
            out[key] = mag
    return out


def sanitize_custom_element_fields(payload):
    """Return ONLY the custom element fields present in the payload,
    sanitized. Absent keys are omitted entirely so a partial POST (e.g.
    the pre-teach weight control) can never clobber stored definitions
    — mirrors the "absent key = don't touch" contract used for
    streak_bonus_enabled."""
    if not isinstance(payload, dict):
        return {}
    out = {}
    if "custom_positive_behaviours" in payload:
        out["custom_positive_behaviours"] = _sanitize_behaviour_list(
            payload.get("custom_positive_behaviours"), positive=True, id_prefix="custom_p")
    if "custom_negative_behaviours" in payload:
        out["custom_negative_behaviours"] = _sanitize_behaviour_list(
            payload.get("custom_negative_behaviours"), positive=False, id_prefix="custom_n")
    if "custom_skills" in payload:
        out["custom_skills"] = _sanitize_custom_skills(payload.get("custom_skills"))
    if "custom_evaluation_items" in payload:
        out["custom_evaluation_items"] = _sanitize_evaluation_items(
            payload.get("custom_evaluation_items"))
    if "behaviour_score_overrides" in payload:
        out["behaviour_score_overrides"] = _sanitize_behaviour_overrides(
            payload.get("behaviour_score_overrides"))
    return out


def custom_fields_from_record(record):
    """Read the custom element fields off a stored record (or None) with
    safe defaults, for GET responses."""
    record = record or {}
    return {
        "custom_positive_behaviours": record.get("custom_positive_behaviours") or [],
        "custom_negative_behaviours": record.get("custom_negative_behaviours") or [],
        "custom_skills": record.get("custom_skills") or [],
        "custom_evaluation_items": record.get("custom_evaluation_items") or [],
        "behaviour_score_overrides": record.get("behaviour_score_overrides") or {},
    }
