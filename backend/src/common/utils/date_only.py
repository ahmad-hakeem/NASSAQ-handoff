"""Shared validation and Umm al-Qura conversion for teacher birth dates."""

import re
from datetime import date, datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from hijridate import Gregorian, Hijri


_STRICT_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STRICT_HIJRI_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_SAUDI_TIMEZONE = ZoneInfo("Asia/Riyadh")


def saudi_today() -> date:
    """Return the calendar day in Saudi Arabia, independent of server timezone."""
    return datetime.now(_SAUDI_TIMEZONE).date()


def normalize_optional_past_date(
    value: Any, *, today: Optional[date] = None
) -> Optional[str]:
    """Normalize an optional strict Gregorian YYYY-MM-DD value.

    Null and whitespace-only strings become ``None``. Non-string, malformed,
    impossible, and future values are rejected. The canonical return value is
    always the original strict ISO date string.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("date must use YYYY-MM-DD format")
    if not value.strip():
        return None
    if not _STRICT_DATE_ONLY.fullmatch(value):
        raise ValueError("date must use YYYY-MM-DD format")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must be a valid Gregorian date") from exc
    if parsed > (today if today is not None else saudi_today()):
        raise ValueError("date must not be in the future")
    return value


def _gregorian_to_hijri(value: str) -> str:
    parsed = date.fromisoformat(value)
    try:
        converted = Gregorian.fromdate(parsed).to_hijri()
    except OverflowError as exc:
        raise ValueError(
            "date is outside the supported Umm al-Qura range"
        ) from exc
    return f"{converted.day:02d}/{converted.month:02d}/{converted.year:04d}"


def _hijri_to_gregorian(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Hijri date must use DD/MM/YYYY format")
    if not value.strip():
        raise ValueError("Hijri date is blank")
    match = _STRICT_HIJRI_DATE.fullmatch(value)
    if not match:
        raise ValueError("Hijri date must use DD/MM/YYYY format")
    day, month, year = (int(part) for part in match.groups())
    try:
        converted = Hijri(year, month, day).to_gregorian()
    except OverflowError as exc:
        raise ValueError(
            "Hijri date is outside the supported Umm al-Qura range"
        ) from exc
    except ValueError as exc:
        raise ValueError("Hijri date must be a valid Umm al-Qura date") from exc
    return f"{converted.year:04d}-{converted.month:02d}-{converted.day:02d}"


def resolve_optional_birth_dates(
    gregorian_value: Any,
    hijri_value: Any,
    *,
    today: Optional[date] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Validate either calendar and return canonical Gregorian and derived Hijri.

    Empty values are absent. If both non-empty values are supplied, they must
    represent the same Umm al-Qura day.
    """
    gregorian = normalize_optional_past_date(gregorian_value, today=today)
    hijri_blank = hijri_value is None or (
        isinstance(hijri_value, str) and not hijri_value.strip()
    )

    if gregorian is None and hijri_blank:
        return None, None

    converted_gregorian = None
    if not hijri_blank:
        converted_gregorian = _hijri_to_gregorian(hijri_value)
        normalize_optional_past_date(converted_gregorian, today=today)

    if gregorian is None:
        gregorian = converted_gregorian
    elif converted_gregorian is not None and converted_gregorian != gregorian:
        raise ValueError(
            "Gregorian and Hijri birth dates do not represent the same date"
        )

    return gregorian, _gregorian_to_hijri(gregorian)


def derive_optional_hijri_date(gregorian_value: Any) -> Optional[str]:
    """Best-effort derived value for legacy reads without rewriting stored data."""
    try:
        gregorian = normalize_optional_past_date(gregorian_value)
        return _gregorian_to_hijri(gregorian) if gregorian else None
    except (TypeError, ValueError):
        return None