"""Teacher-facing merge of a student's health data for the live session view.

Two authoritative JSONB sources live on the ``students`` row:
  - ``health_info``       — medical record written by school admins / ITs /
    platform admins (flag + free-text pairs, blood type, medications, notes).
  - ``profile_settings``  — the parent-portal "ملف الطالب" editor (health
    condition chips, behavioral/learning aspect chips, free text, family
    fields).

Privacy contract (user decision 2026-07-20): teachers see HEALTH and
BEHAVIORAL/learning data only. Family situation fields and the profile emoji
NEVER leave this module. The roster summary additionally carries no free text
— only chip keys and boolean flags; free text is served exclusively by the
per-student detail endpoint.

All inputs are defensively coerced: JSONB payloads are client-influenced and
historical rows may hold malformed shapes (strings instead of lists, numbers
instead of strings). Malformed values degrade to empty, never raise.
"""
from typing import Any, Dict, List, Optional


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _chips(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def _text(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _gated_text(source: Dict[str, Any], flag_key: str, text_key: str) -> Optional[str]:
    """Flag + text pair from ``health_info``: the text is shown only while the
    flag is truthy, so stale text behind a switched-off toggle never leaks."""
    if not source.get(flag_key):
        return None
    return _text(source.get(text_key))


def build_student_health_detail(student: Dict[str, Any]) -> Dict[str, Any]:
    """Full read-only detail for the in-session health dialog."""
    profile = _as_dict(student.get("profile_settings"))
    medical = _as_dict(student.get("health_info"))

    health = {
        "conditions": _chips(profile.get("health_conditions")),
        "other_details": _text(profile.get("other_health_details")),
        "blood_type": _text(medical.get("blood_type")),
        "chronic_conditions": _gated_text(medical, "has_chronic_conditions", "chronic_conditions"),
        "allergies": _gated_text(medical, "has_allergies", "allergies"),
        "disabilities": _gated_text(medical, "has_disabilities", "disabilities"),
        "current_medications": _text(medical.get("current_medications")),
        "special_care_notes": _gated_text(medical, "requires_special_care", "special_care_notes"),
        "emergency_medical_notes": _text(medical.get("emergency_medical_notes")),
    }
    behavior = {
        "aspects": _chips(profile.get("behavioral_aspects")),
        "other_details": _text(profile.get("other_behavior_details")),
    }

    # Blood type alone is informational, not an alert — it must not light the
    # roster indicator for an otherwise healthy student.
    has_health_alert = bool(health["conditions"]) or any(
        health[k] for k in (
            "other_details", "chronic_conditions", "allergies", "disabilities",
            "current_medications", "special_care_notes", "emergency_medical_notes",
        )
    )
    has_behavior_alert = bool(behavior["aspects"]) or bool(behavior["other_details"])

    return {
        "health": health,
        "behavior": behavior,
        "has_health_alert": has_health_alert,
        "has_behavior_alert": has_behavior_alert,
        "has_any": has_health_alert or has_behavior_alert,
    }


def summarize_student_health(student: Dict[str, Any]) -> Dict[str, Any]:
    """Compact roster-safe summary: chip keys + booleans, no free text."""
    detail = build_student_health_detail(student)
    return {
        "health_conditions": detail["health"]["conditions"],
        "behavioral_aspects": detail["behavior"]["aspects"],
        "has_health_alert": detail["has_health_alert"],
        "has_behavior_alert": detail["has_behavior_alert"],
    }
